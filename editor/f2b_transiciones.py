"""
Fase 2b — Transiciones entre cortes.

El pipeline une los tramos que sobreviven al corte (silencios, muletillas,
tomas repetidas) con un `concat` seco: corte duro, sin nada de imagen entre
plano y plano. Esta fase dibuja, EN LOS LÍMITES de esos cortes, una de diez
transiciones "virales" hechas solo con filtros nativos de ffmpeg.

La regla de oro de este módulo: **nunca cambia la duración**. Un `xfade` de
verdad solapa dos clips y acorta la línea de tiempo — y en este editor la línea
de tiempo es lo único que mantiene sincronizados los 13 módulos (palabras,
subtítulos, SFX, overlays, encuadre). Así que las transiciones se aplican como
efectos localizados por ventana (`enable='between(t, T-d, T+d)'`) sobre el
stream ya concatenado: cada fotograma sigue en su milisegundo. Nada aguas abajo
se entera.

Por eso tampoco se toca el audio: la voz de José no se puede cruzar en un
salto de plano. El "whoosh" del corte ya lo pone f5_audio; esto es solo lo
visual.

Las diez presets están pensadas para vertical/TikTok, no para cine:

    flash-blanco   destello blanco de 2-3 frames (el "hit" clásico)
    flash-negro    igual pero a negro (más dramático)
    flash-marca    destello en el cian de DeviceShop
    desenfoque     whip-blur: golpe de desenfoque gaussiano en el corte
    glitch         desplazamiento RGB + ruido, estética digital
    zoom-punch     empujón de zoom rápido que "aterriza" en el nuevo plano
    shake          sacudida de cámara corta
    barrido        una barra de luz cruza el cuadro tapando el corte
    zoom-desenfoque combo: zoom-punch + desenfoque (el más usado en cortes de venta)
    destello-glitch combo: flash-marca + glitch (para revelaciones)

Todas aceptan una `intensidad` (0.5 suave … 1.5 agresiva, 1.0 por defecto) que
escala la fuerza del efecto y, en algunas, el ancho de la ventana.

Uso como CLI (para ver cómo quedan):

    python f2b_transiciones.py entrada.mp4 --transicion glitch --intensidad 1.2
    python f2b_transiciones.py --demo        # las diez sobre un clip sintético
"""
import argparse
import subprocess
import sys
from pathlib import Path

try:
    import config
except ImportError:  # pragma: no cover - solo si se importa desde fuera de editor/
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import config


# Ventana base (media anchura, en segundos) de una transición a intensidad 1.0.
# El efecto vive en [T - VENTANA, T + VENTANA]. 0.10s => ~6 frames a 30fps,
# que es lo que dura un corte con pegada sin volverse un fundido lento.
VENTANA_BASE_S = 0.10

# Cian de marca, para flash-marca y destello-glitch. Igual que config.CIAN pero
# aquí lo necesitamos en hex para drawbox.
CIAN_HEX = "0x4FD1D9"

# Catálogo público: nombre -> etiqueta legible para el editor y el panel.
# El orden es el que verá José en el desplegable.
TRANSICIONES = {
    "ninguna":         "Sin transición (corte seco)",
    "flash-blanco":    "Flash blanco",
    "flash-negro":     "Flash negro",
    "flash-marca":     "Flash cian (marca)",
    "desenfoque":      "Whip / desenfoque",
    "glitch":          "Glitch RGB",
    "zoom-punch":      "Zoom punch",
    "shake":           "Sacudida",
    "barrido":         "Barrido de luz",
    "zoom-desenfoque": "Zoom + desenfoque",
    "destello-glitch": "Flash + glitch",
}

# Las que se dibujan como una cadena de filtros ventaneados (una instancia por
# corte). Se pueden encadenar sin límite y son baratas.
_CADENA = {"flash-blanco", "flash-negro", "flash-marca", "desenfoque",
           "glitch", "barrido", "destello-glitch"}
# Las que necesitan zoompan (reinterpretan el stream frame a frame). Cubren
# TODOS los cortes en una sola expresión.
_ZOOMPAN = {"zoom-punch", "shake", "zoom-desenfoque"}


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _ventana(t, half):
    return f"between(t,{t - half:.3f},{t + half:.3f})"


# ---------------------------------------------------------------------------
# Presets de cadena (drawbox / gblur / rgbashift / noise por ventana)
# ---------------------------------------------------------------------------
def _flash(color, boundaries, half, alpha):
    """drawbox a pantalla completa, encendido solo en la ventana del corte.

    Un flash duro de 2-3 frames se lee mejor que un fundido: es el "hit" que
    usan los cortes de TikTok. `alpha` controla cuánto tapa (0.85 casi blanco).
    """
    partes = []
    for t in boundaries:
        partes.append(
            f"drawbox=x=0:y=0:w=iw:h=ih:color={color}@{alpha:.2f}:t=fill:"
            f"enable='{_ventana(t, half)}'"
        )
    return ",".join(partes)


def _desenfoque(boundaries, half, sigma):
    partes = [f"gblur=sigma={sigma:.1f}:enable='{_ventana(t, half)}'" for t in boundaries]
    return ",".join(partes)


def _glitch(boundaries, half, shift, ruido):
    partes = []
    for t in boundaries:
        v = _ventana(t, half)
        partes.append(f"rgbashift=rh=-{shift}:bh={shift}:gv={shift // 2}:enable='{v}'")
        partes.append(f"noise=alls={ruido}:allf=t:enable='{v}'")
    return ",".join(partes)


def _barrido(boundaries, w, h, half):
    """Barra vertical blanca semitransparente que cruza el cuadro en la ventana.

    x recorre de -ancho a W en la ventana; fuera de ella drawbox está apagado,
    así que la barra no existe. `t` es el tiempo global; se normaliza por corte.
    """
    ancho = max(60, int(w * 0.22))
    partes = []
    for t in boundaries:
        ini = t - half
        dur = 2 * half
        # progreso 0..1 dentro de la ventana -> x de -ancho a W
        x = f"(-{ancho})+({w}+{ancho})*clip((t-{ini:.3f})/{dur:.3f},0,1)"
        partes.append(
            f"drawbox=x='{x}':y=0:w={ancho}:h=ih:color=white@0.55:t=fill:"
            f"enable='{_ventana(t, half)}'"
        )
    return ",".join(partes)


# ---------------------------------------------------------------------------
# Presets con zoompan (zoom-punch, shake) — una sola expresión para todo
# ---------------------------------------------------------------------------
def _pulso_por_cortes(boundaries, half):
    """Suma de triángulos 0..1 centrados en cada corte, como expresión de ffmpeg.

    Vale 1 justo en el corte y cae a 0 en los bordes de la ventana. Fuera de
    todas las ventanas vale 0 (el efecto se apaga). Se evalúa por frame con la
    variable `t` que zoompan expone como `on/fps`.
    """
    if not boundaries:
        return "0"
    # Comas SIN escapar: la expresión va dentro de comillas simples en el
    # filter_complex, igual que enable='between(t,...)' — verificado que ffmpeg
    # las lee bien ahí.
    terminos = []
    for t in boundaries:
        # max(0, 1 - |t - T|/half)
        terminos.append(f"max(0,1-abs(T-{t:.3f})/{half:.3f})")
    # el máximo de todos los triángulos (no la suma: cortes juntos no se apilan)
    expr = terminos[0]
    for term in terminos[1:]:
        expr = f"max({expr},{term})"
    return expr


def _zoom_punch(boundaries, w, h, half, fuerza, fps, con_blur=False, sigma=0.0):
    """zoompan que da un empujón de zoom en cada corte. Reemplaza la cadena.

    `T` = tiempo en segundos (definido como on/fps dentro de la expresión).
    z = 1 + fuerza*pulso. Fuera de los cortes z=1 => frames idénticos al origen.
    """
    pulso = _pulso_por_cortes(boundaries, half)
    z = f"1+{fuerza:.3f}*({pulso})"
    # zoompan necesita s= y d=1 (un frame de salida por frame de entrada).
    zp = (
        f"zoompan=d=1:s={w}x{h}:fps={fps}:"
        f"z='{z.replace('T', f'(on/{fps})')}':"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    )
    if con_blur:
        # el desenfoque acompaña al empujón: gblur ventaneado en cada corte
        zp = zp + "," + _desenfoque(boundaries, half, sigma)
    return zp


def _shake(boundaries, w, h, half, amp, fps):
    """Sacudida: zoompan con un pequeño margen (z=1.06 fijo) y x/y oscilando en
    los cortes. El margen evita que la sacudida muestre borde negro."""
    pulso = _pulso_por_cortes(boundaries, half)
    p = pulso.replace('T', f'(on/{fps})')
    base_z = 1.06
    # oscilación rápida modulada por el pulso
    dx = f"({amp})*sin((on/{fps})*90)*({p})"
    dy = f"({amp})*cos((on/{fps})*74)*({p})"
    return (
        f"zoompan=d=1:s={w}x{h}:fps={fps}:z='{base_z}':"
        f"x='iw/2-(iw/zoom/2)+{dx}':y='ih/2-(ih/zoom/2)+{dy}'"
    )


# ---------------------------------------------------------------------------
# API principal
# ---------------------------------------------------------------------------
def construir_filtro(transicion: str, boundaries: list, w: int, h: int,
                     intensidad: float = 1.0, fps: int = None) -> str:
    """Devuelve la cadena de filtros de video para la transición pedida, o "".

    `boundaries` son los instantes de corte (segundos) en la línea de tiempo YA
    concatenada. `intensidad` escala la fuerza (0.5..1.5). Si no hay cortes o la
    transición es "ninguna", devuelve "" (el llamador no añade nada).
    """
    if not boundaries or transicion in (None, "", "ninguna"):
        return ""
    if transicion not in TRANSICIONES:
        raise ValueError(f"Transición desconocida: {transicion!r}. "
                         f"Opciones: {', '.join(TRANSICIONES)}")
    fps = fps or config.FPS
    k = _clamp(float(intensidad), 0.3, 2.0)
    half = VENTANA_BASE_S * (0.8 + 0.4 * k)   # ventana crece un poco con la intensidad

    if transicion == "flash-blanco":
        return _flash("white", boundaries, half, _clamp(0.85 * k, 0.3, 1.0))
    if transicion == "flash-negro":
        return _flash("black", boundaries, half, _clamp(0.9 * k, 0.3, 1.0))
    if transicion == "flash-marca":
        return _flash(CIAN_HEX, boundaries, half, _clamp(0.7 * k, 0.25, 0.95))
    if transicion == "desenfoque":
        return _desenfoque(boundaries, half, 22 * k)
    if transicion == "glitch":
        return _glitch(boundaries, half, int(_clamp(14 * k, 4, 40)),
                       int(_clamp(22 * k, 6, 60)))
    if transicion == "barrido":
        return _barrido(boundaries, w, h, half)
    if transicion == "destello-glitch":
        return (_flash(CIAN_HEX, boundaries, half, _clamp(0.55 * k, 0.2, 0.9)) + "," +
                _glitch(boundaries, half, int(_clamp(12 * k, 4, 36)),
                        int(_clamp(18 * k, 6, 50))))
    if transicion == "zoom-punch":
        return _zoom_punch(boundaries, w, h, half, _clamp(0.18 * k, 0.05, 0.4), fps)
    if transicion == "zoom-desenfoque":
        return _zoom_punch(boundaries, w, h, half, _clamp(0.16 * k, 0.05, 0.4), fps,
                           con_blur=True, sigma=16 * k)
    if transicion == "shake":
        return _shake(boundaries, w, h, half, _clamp(14 * k, 4, 36), fps)
    return ""


def es_zoompan(transicion: str) -> bool:
    """El llamador necesita saberlo: zoompan reemplaza la cadena y hay que
    dejarlo al final del grafo, después de cualquier otro filtro de video."""
    return transicion in _ZOOMPAN


# ---------------------------------------------------------------------------
# Motor por empalme: cada corte con SU propia transición e intensidad
# ---------------------------------------------------------------------------
def _fragmento_cadena(tipo, t, half, k, w, h):
    """El fragmento de filtro ventaneado de UN corte de la familia 'cadena'."""
    if tipo == "flash-blanco":
        return _flash("white", [t], half, _clamp(0.85 * k, 0.3, 1.0))
    if tipo == "flash-negro":
        return _flash("black", [t], half, _clamp(0.9 * k, 0.3, 1.0))
    if tipo == "flash-marca":
        return _flash(CIAN_HEX, [t], half, _clamp(0.7 * k, 0.25, 0.95))
    if tipo == "desenfoque":
        return _desenfoque([t], half, 22 * k)
    if tipo == "glitch":
        return _glitch([t], half, int(_clamp(14 * k, 4, 40)), int(_clamp(22 * k, 6, 60)))
    if tipo == "barrido":
        return _barrido([t], w, h, half)
    if tipo == "destello-glitch":
        return (_flash(CIAN_HEX, [t], half, _clamp(0.55 * k, 0.2, 0.9)) + "," +
                _glitch([t], half, int(_clamp(12 * k, 4, 36)), int(_clamp(18 * k, 6, 50))))
    return ""


def _zoompan_multi(zoom_terms, shake_terms, w, h, fps):
    """UN zoompan que cubre todos los cortes de zoom y de sacudida.

    Fuera de sus ventanas z=1 y offset=0 (frames idénticos al origen). Cada
    término es un triángulo centrado en su corte. La sacudida añade un pelín de
    margen de zoom SOLO en su ventana, para no mostrar borde negro al desplazar.
    """
    def pulso(t, half):
        return f"max(0,1-abs((on/{fps})-{t:.3f})/{half:.3f})"
    z = "1"
    for t, f, half in zoom_terms:
        z += f"+{f:.3f}*{pulso(t, half)}"
    for t, a, half in shake_terms:
        z += f"+0.05*{pulso(t, half)}"        # margen para la sacudida
    dx, dy = "0", "0"
    for t, a, half in shake_terms:
        dx += f"+({a:.1f})*sin((on/{fps})*90)*{pulso(t, half)}"
        dy += f"+({a:.1f})*cos((on/{fps})*74)*{pulso(t, half)}"
    return (f"zoompan=d=1:s={w}x{h}:fps={fps}:z='{z}':"
            f"x='iw/2-(iw/zoom/2)+({dx})':y='ih/2-(ih/zoom/2)+({dy})'")


def construir_filtro_multi(specs: list, w: int, h: int, fps: int = None) -> str:
    """Filtro de video para una transición DISTINTA por empalme.

    `specs`: lista de {t, tipo, intensidad}. Un empalme con tipo 'ninguna' (o
    ausente) queda seco. Devuelve "" si no hay ninguna transición activa. Como
    todo el módulo, no cambia la duración.
    """
    fps = fps or config.FPS
    cadena = []
    zoom_terms = []      # (t, fuerza, half)
    shake_terms = []     # (t, amp, half)
    for s in specs or []:
        tipo = s.get("tipo", "ninguna")
        if tipo in (None, "", "ninguna"):
            continue
        if tipo not in TRANSICIONES:
            raise ValueError(f"Transición desconocida: {tipo!r}")
        t = float(s["t"])
        k = _clamp(float(s.get("intensidad", 1.0)), 0.3, 2.0)
        half = VENTANA_BASE_S * (0.8 + 0.4 * k)
        if tipo in _CADENA:
            frag = _fragmento_cadena(tipo, t, half, k, w, h)
            if frag:
                cadena.append(frag)
        elif tipo == "zoom-punch":
            zoom_terms.append((t, _clamp(0.18 * k, 0.05, 0.4), half))
        elif tipo == "zoom-desenfoque":
            zoom_terms.append((t, _clamp(0.16 * k, 0.05, 0.4), half))
            cadena.append(_desenfoque([t], half, 16 * k))
        elif tipo == "shake":
            shake_terms.append((t, _clamp(14 * k, 4, 36), half))
    partes = [c for c in cadena if c]
    if zoom_terms or shake_terms:
        partes.append(_zoompan_multi(zoom_terms, shake_terms, w, h, fps))
    return ",".join(partes)


# ---------------------------------------------------------------------------
# CLI / demo
# ---------------------------------------------------------------------------
def _dur(ruta):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration", "-of",
                          "default=noprint_wrappers=1:nokey=1", str(ruta)],
                         capture_output=True, text=True)
    return float(out.stdout.strip() or 0)


def _aplicar_a_archivo(entrada, salida, transicion, intensidad):
    """Aplica una transición a un archivo suelto. Detecta los cortes por los
    cambios de escena para tener algo que enseñar (en el pipeline los cortes
    vienen dados, aquí se estiman)."""
    dur = _dur(entrada)
    # cortes de muestra: cada segundo (solo para el demo/CLI)
    boundaries = [round(x, 2) for x in _frange(1.0, dur - 0.3, 1.0)]
    w, h = _resolucion(entrada)
    filtro = construir_filtro(transicion, boundaries, w, h, intensidad)
    if not filtro:
        print("Sin transición que aplicar.")
        return
    cmd = ["ffmpeg", "-y", "-i", str(entrada), "-vf", filtro,
           "-c:a", "copy", "-pix_fmt", "yuv420p", str(salida)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:], file=sys.stderr)
        raise RuntimeError("ffmpeg falló")
    print(f"{salida}  ({_dur(salida):.2f}s, original {dur:.2f}s)")


def _frange(a, b, paso):
    x = a
    while x < b:
        yield x
        x += paso


def _resolucion(ruta):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                          "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x",
                          str(ruta)], capture_output=True, text=True)
    w, h = out.stdout.strip().split("x")
    return int(w), int(h)


def main():
    ap = argparse.ArgumentParser(description="Transiciones entre cortes (nativas, sin cambiar duración)")
    ap.add_argument("entrada", nargs="?", help="video de entrada")
    ap.add_argument("--transicion", default="glitch", choices=list(TRANSICIONES))
    ap.add_argument("--intensidad", type=float, default=1.0)
    ap.add_argument("--salida", default=None)
    ap.add_argument("--demo", action="store_true", help="genera las diez sobre un clip sintético")
    args = ap.parse_args()

    if args.demo:
        destino = config.RAIZ_PROYECTO / "salida" / "transiciones"
        destino.mkdir(parents=True, exist_ok=True)
        base = destino / "_base.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                        "-i", "smptebars=s=540x960:r=30:d=1.5", "-f", "lavfi",
                        "-i", "testsrc=s=540x960:r=30:d=1.5", "-filter_complex",
                        "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]",
                        "-pix_fmt", "yuv420p", str(base)], check=True)
        for nombre in TRANSICIONES:
            if nombre == "ninguna":
                continue
            _aplicar_a_archivo(base, destino / f"{nombre}.mp4", nombre, args.intensidad)
        print(f"\nDemo en: {destino}")
        return

    if not args.entrada:
        ap.error("pasa un video o usa --demo")
    entrada = Path(args.entrada)
    salida = Path(args.salida) if args.salida else entrada.with_name(
        entrada.stem + f".{args.transicion}.mp4")
    _aplicar_a_archivo(entrada, salida, args.transicion, args.intensidad)


if __name__ == "__main__":
    main()
