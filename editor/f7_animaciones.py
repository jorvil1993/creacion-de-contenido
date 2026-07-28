"""
Fase 5b — Animaciones generadas por código.

Hay conceptos que ninguna foto del catálogo ilustra bien: una foto de cargador
no comunica "batería que dura semanas", y para "resistente al agua" no existe
una foto del Kindle sumergido. Estas animaciones se dibujan con PIL y se
codifican a ProRes 4444 (MOV), que es el formato con canal alfa que la sesión B
verificó píxel a píxel que sí conserva la transparencia con este ffmpeg
(el alfa de VP9/webm no sobrevivía).

Cada función devuelve la ruta del .mov listo para componer.

Uso:
    python f7_animaciones.py --demo   # genera las tres y las deja en salida/
"""
import argparse
import hashlib
import math
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

import config

NAVY = (10, 42, 62, 255)
CIAN = (79, 209, 217, 255)
BLANCO = (255, 255, 255, 255)
VERDE = (80, 220, 140, 255)
SOL = (255, 201, 60, 255)

# Tamaño del lienzo de cada animación. El pipeline lo necesita para colocarla
# sin que se salga del cuadro: antes usaba 420x420 fijo para todas y el sol,
# que es más ancho, se pasaba del margen derecho.
TAMANOS = {
    "bateria": (380, 200),
    "splash": (420, 420),
    "moto": (None, 260),        # None = ancho completo del lienzo
    "sol": (520, 560),
}


def _suave(t: float) -> float:
    """Curva de aceleración/desaceleración. Un movimiento lineal se ve robótico."""
    return t * t * (3 - 2 * t)


def _variacion(semilla, nombre: str, n: int) -> int:
    """Variante estable para esta animación en este video.

    Antes los parámetros eran fijos y el splash salía EXACTAMENTE igual en todos
    los videos. Ahora dependen de una semilla derivada del nombre del archivo,
    no de `random`: el plan exige render reproducible, así que el mismo video
    debe dar siempre el mismo resultado.
    """
    if semilla is None:
        return 0
    h = hashlib.sha1(f"{semilla}|{nombre}".encode("utf-8")).hexdigest()[:8]
    return int(h, 16) % n


def _fuente(nombre_archivo: str, tamano: int):
    """Poppins de assets/fuentes/, o la de PIL si faltara (nunca romper)."""
    try:
        return ImageFont.truetype(str(config.DIR_FUENTES / nombre_archivo), tamano)
    except Exception:
        return ImageFont.load_default()


def _etiqueta(d: ImageDraw.ImageDraw, texto: str, centro_x: float, y: float, tam: int = 34):
    """Texto con contorno negro — el mismo recurso que usan las plantillas HTML
    para que se lea sobre cualquier fondo de video."""
    if not texto:
        return
    fuente = _fuente("Poppins-ExtraBold.ttf", tam)
    caja = d.textbbox((0, 0), texto, font=fuente)
    x = centro_x - (caja[2] - caja[0]) / 2
    d.text((x, y), texto, font=fuente, fill=BLANCO,
           stroke_width=6, stroke_fill=(0, 0, 0, 216))


def _codificar(dir_frames: Path, ruta_mov: Path, fps: int):
    """Frames PNG con alfa -> ProRes 4444 (conserva transparencia)."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-framerate", str(fps),
        "-i", str(dir_frames / "f_%04d.png"),
        "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
        str(ruta_mov),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    shutil.rmtree(dir_frames, ignore_errors=True)
    return ruta_mov


# ---------------------------------------------------------------------------
# Batería que se carga
# ---------------------------------------------------------------------------
def animar_bateria(dir_tmp: Path, duracion: float = 2.5, w: int = 380, h: int = 200,
                   semilla=None, variante: int = None) -> Path:
    """Batería que se llena de vacía a completa, con un rayo al terminar.

    Comunica "dura semanas" mucho mejor que la foto de un cargador, que era lo
    que traía el catálogo para la palabra "batería".
    """
    fps = config.ANIMACION_FPS
    n = max(2, int(duracion * fps))
    var = variante if variante is not None else _variacion(semilla, "bateria", 3)
    frames = dir_tmp / f"_f_bateria_{var}"
    frames.mkdir(parents=True, exist_ok=True)

    # variación determinista por video: color de llegada y cuándo se completa
    color_lleno = [VERDE, CIAN, (126, 240, 212, 255)][var]
    punto_lleno = [0.75, 0.68, 0.82][var]

    cuerpo = (20, 30, w - 60, h - 30)
    borde = 8
    radio = 22

    for i in range(n):
        p = i / (n - 1)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # carcasa
        d.rounded_rectangle(cuerpo, radius=radio, fill=(10, 42, 62, 210), outline=BLANCO, width=borde)
        # borne
        bx = cuerpo[2] + 6
        d.rounded_rectangle((bx, h // 2 - 26, bx + 26, h // 2 + 26), radius=8, fill=BLANCO)

        # relleno: sube durante el primer 75% y se queda lleno
        nivel = _suave(min(1.0, p / punto_lleno))
        x0 = cuerpo[0] + borde + 6
        x1 = cuerpo[2] - borde - 6
        y0 = cuerpo[1] + borde + 6
        y1 = cuerpo[3] - borde - 6
        ancho_util = (x1 - x0) * nivel
        if ancho_util > 4:
            color = CIAN if nivel < 0.95 else color_lleno
            d.rounded_rectangle((x0, y0, x0 + ancho_util, y1), radius=12, fill=color)

        # rayo al completarse
        if p > punto_lleno:
            alfa = int(255 * _suave(min(1.0, (p - punto_lleno) / (1 - punto_lleno))))
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            rayo = [(cx + 14, cy - 44), (cx - 18, cy + 6), (cx + 2, cy + 6),
                    (cx - 14, cy + 46), (cx + 20, cy - 6), (cx, cy - 6)]
            d.polygon(rayo, fill=(255, 255, 255, alfa))

        img.save(frames / f"f_{i:04d}.png")

    return _codificar(frames, dir_tmp / f"anim_bateria_v{var}.mov", fps)


# ---------------------------------------------------------------------------
# Splash de agua
# ---------------------------------------------------------------------------
def animar_splash(dir_tmp: Path, duracion: float = 2.0, w: int = 420, h: int = 420,
                  semilla=None, variante: int = None) -> Path:
    """Ondas concéntricas + gotas saliendo. Para "resistente al agua"."""
    fps = config.ANIMACION_FPS
    n = max(2, int(duracion * fps))
    var = variante if variante is not None else _variacion(semilla, "splash", 3)
    frames = dir_tmp / f"_f_splash_{var}"
    frames.mkdir(parents=True, exist_ok=True)

    cx, cy = w / 2, h / 2 + 20
    n_gotas = [9, 7, 11][var]
    radio_max = [0.46, 0.52, 0.42][var]

    for i in range(n):
        p = i / (n - 1)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # tres ondas desfasadas, cada una crece y se desvanece.
        # Primera versión: se veían como un hilo tenue. Ondas más gruesas y
        # opacas, y desvanecido más lento, para que el gesto se lea a tamaño
        # de celular.
        for k in range(3):
            fase = p - k * 0.16
            if fase <= 0:
                continue
            fase = min(1.0, fase / 0.84)
            r = 34 + _suave(fase) * (w * radio_max - 34)
            alfa = int(255 * (1 - fase) ** 0.85)
            if alfa > 4:
                grosor = max(5, int(18 * (1 - fase) + 5))
                d.ellipse((cx - r, cy - r * 0.55, cx + r, cy + r * 0.55),
                          outline=(79, 209, 217, alfa), width=grosor)

        # gotas que salen en abanico y caen
        for g in range(n_gotas):
            ang = math.pi * (0.10 + 0.80 * g / (n_gotas - 1))
            vel = 0.85 + 0.40 * ((g * 37) % 10) / 10
            t = min(1.0, p / 0.88)
            dist = _suave(t) * w * 0.50 * vel
            gx = cx + math.cos(ang) * dist * -1
            gy = cy - math.sin(ang) * dist + (t ** 2) * 150   # gravedad
            rr = max(4.0, 26 * (1 - t * 0.75))
            alfa = int(255 * (1 - t) ** 0.55)
            if alfa > 6:
                d.ellipse((gx - rr, gy - rr * 1.3, gx + rr, gy + rr * 1.3),
                          fill=(79, 209, 217, alfa))
                # brillo interior, para que la gota tenga volumen
                d.ellipse((gx - rr * 0.35, gy - rr * 0.75, gx + rr * 0.1, gy - rr * 0.15),
                          fill=(255, 255, 255, int(alfa * 0.55)))

        img.save(frames / f"f_{i:04d}.png")

    return _codificar(frames, dir_tmp / f"anim_splash_v{var}.mov", fps)


# ---------------------------------------------------------------------------
# Moto de reparto cruzando la pantalla
# ---------------------------------------------------------------------------
def animar_moto(dir_tmp: Path, duracion: float = 2.6, w: int = None, h: int = 260,
                semilla=None, variante: int = None) -> Path:
    """Moto de delivery cruzando de izquierda a derecha, para "hacemos envíos".

    Silueta plana y simple: a este tamaño y a esta velocidad se lee como moto
    sin necesitar detalle, y encaja con el estilo limpio de la marca.
    """
    w = w or config.ANCHO
    fps = config.ANIMACION_FPS
    n = max(2, int(duracion * fps))
    var = variante if variante is not None else _variacion(semilla, "moto", 3)
    frames = dir_tmp / f"_f_moto_{var}"
    frames.mkdir(parents=True, exist_ok=True)

    vibracion = [9, 6, 12][var]      # frecuencia del rebote del motor
    largo = 300           # largo de la moto
    for i in range(n):
        p = i / (n - 1)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        x = -largo + _suave(p) * (w + largo * 2)
        bote = math.sin(p * math.pi * vibracion) * 4   # vibración del motor
        base = h - 62 + bote

        # estela de velocidad
        for k in range(4):
            lx = x - 30 - k * 46
            alfa = int(120 - k * 26)
            if alfa > 0 and lx > -60:
                d.rounded_rectangle((lx - 40, base - 62 - k * 13, lx, base - 56 - k * 13),
                                    radius=3, fill=(79, 209, 217, alfa))

        r = 34                                       # ruedas
        for wx in (x + 52, x + largo - 52):
            d.ellipse((wx - r, base - r, wx + r, base + r), fill=NAVY)
            # llanta clara opaca: con relleno semitransparente se veía el fondo
            # a través de la rueda y parecía un agujero
            d.ellipse((wx - r + 10, base - r + 10, wx + r - 10, base + r - 10), fill=BLANCO)
            d.ellipse((wx - 7, base - 7, wx + 7, base + 7), fill=NAVY)

        # cuerpo
        d.polygon([(x + 52, base - 26), (x + 118, base - 74), (x + 214, base - 74),
                   (x + largo - 52, base - 26)], fill=CIAN)
        # caja de reparto
        d.rounded_rectangle((x + 168, base - 138, x + 252, base - 72), radius=10, fill=NAVY)
        d.rounded_rectangle((x + 180, base - 126, x + 240, base - 86), radius=6, fill=CIAN)
        # manubrio y conductor simplificado
        d.line([(x + 214, base - 74), (x + 258, base - 118)], fill=NAVY, width=11)
        d.ellipse((x + 136, base - 168, x + 190, base - 114), fill=NAVY)

        img.save(frames / f"f_{i:04d}.png")

    return _codificar(frames, dir_tmp / f"anim_moto_v{var}.mov", fps)


def _dispositivo_pil(foto: Path | None, alto: int) -> Image.Image:
    """El aparato que se enseña en la animación de sol.

    Preferimos la foto REAL recortada (viene con alfa desde la Fase 0): está
    documentado que ninguna imagen generada sabe cómo es un Kindle de verdad.
    Si no hay foto, se dibuja un e-reader con renglones de texto — lo importante
    es que la pantalla se vea con contenido legible, porque ese contraste (sol
    encima, texto nítido) ES el argumento de la animación.
    """
    if foto is not None and Path(foto).exists():
        try:
            img = config.abrir_imagen(foto).convert("RGBA")
            escala = alto / img.height
            return img.resize((max(1, int(img.width * escala)), alto), Image.LANCZOS)
        except Exception:
            pass

    ancho = int(alto * 0.74)
    img = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, ancho - 1, alto - 1), radius=int(alto * 0.055),
                        fill=(16, 22, 30, 255), outline=(44, 59, 76, 255), width=5)
    m = int(ancho * 0.085)
    pantalla = (m, m, ancho - m, alto - int(alto * 0.11))
    d.rounded_rectangle(pantalla, radius=8, fill=(244, 242, 234, 255))
    # renglones: la pantalla tiene que verse CON texto, no vacía
    y = pantalla[1] + 26
    ancho_util = pantalla[2] - pantalla[0] - 36
    k = 0
    while y < pantalla[3] - 26:
        largo = ancho_util * (0.62 if k % 4 == 3 else 1.0)
        d.rounded_rectangle((pantalla[0] + 18, y, pantalla[0] + 18 + largo, y + 8),
                            radius=4, fill=(44, 44, 44, 210))
        y += 22
        k += 1
    return img


def animar_sol(dir_tmp: Path, duracion: float = 2.6, w: int = 520, h: int = 560,
               semilla=None, variante: int = None, foto_dispositivo: Path = None,
               etiqueta: str = None) -> Path:
    """Rayos de sol SOBRE el aparato: la pantalla sigue legible (§3a del plan v2).

    Decisión de José: no es un sol saliendo, es la prueba de que el e-ink se lee
    con el sol directo encima. Por eso toda la luz (halo, rayos, barrido) se
    dibuja ANTES que el dispositivo, o sea debajo: la luz inunda el fondo y se
    corta en el aparato. Lo único que lo toca es un halo cálido difuminado con
    su misma silueta — el destello del marco — que nunca cae sobre la pantalla.
    Si el destello fuera por encima, la animación diría lo contrario de lo que
    vende.
    """
    fps = config.ANIMACION_FPS
    n = max(2, int(duracion * fps))
    frames = dir_tmp / f"_f_sol_{variante or 0}"
    frames.mkdir(parents=True, exist_ok=True)

    var = variante if variante is not None else _variacion(semilla, "sol", 3)
    # Misma familia visual, otro gesto: de dónde viene la luz, cuántos rayos y
    # hacia dónde barre. Es lo que hace que la 2ª aparición no se lea como un
    # error de edición.
    cfg = [
        {"sol": (0.86, 0.06), "rayos": 9,  "abre": 150, "giro": 17,  "barre": 1},
        {"sol": (0.16, 0.04), "rayos": 7,  "abre": 128, "giro": -14, "barre": -1},
        {"sol": (0.54, -0.03), "rayos": 12, "abre": 178, "giro": 11, "barre": 1},
    ][var % 3]

    etiqueta = config.ANIMACION_ETIQUETAS.get("sol", "") if etiqueta is None else etiqueta

    alto_aparato = int(h * 0.72)
    aparato = _dispositivo_pil(foto_dispositivo, alto_aparato)
    ax = (w - aparato.width) // 2
    ay = int(h * 0.03)

    # El destello del marco: la misma silueta, teñida de cálido y difuminada.
    aura = Image.new("RGBA", aparato.size, (0, 0, 0, 0))
    aura.paste(SOL, (0, 0), aparato.split()[3])
    aura = aura.filter(ImageFilter.GaussianBlur(11))

    sx, sy = cfg["sol"][0] * w, cfg["sol"][1] * h

    for i in range(n):
        p = i / (n - 1)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))

        # --- CAPA 1: la luz, siempre detrás -------------------------------
        luz = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        dl = ImageDraw.Draw(luz)

        aparicion = _suave(min(1.0, p / 0.30))

        # halo: círculos concéntricos que hacen de degradado radial
        r_halo = 300 * aparicion
        pasos = 22
        for k in range(pasos, 0, -1):
            r = r_halo * k / pasos
            a = int(150 * (1 - k / pasos) ** 1.6 * aparicion)
            if a > 2 and r > 1:
                dl.ellipse((sx - r, sy - r, sx + r, sy + r), fill=(255, 214, 110, a))

        # abanico de rayos, que BARRE girando
        barrido_ang = (-cfg["giro"] / 2 + cfg["giro"] * _suave(p))
        largo = 620 * aparicion
        for k in range(cfg["rayos"]):
            t = 0.5 if cfg["rayos"] == 1 else k / (cfg["rayos"] - 1)
            ang = math.radians(90 - cfg["abre"] / 2 + cfg["abre"] * t + barrido_ang)
            dx, dy = math.cos(ang), math.sin(ang)
            px, py = -dy, dx                       # perpendicular, para el grosor
            grosor = 15 + 9 * ((k * 7) % 3)
            for seg in range(6):                   # el rayo se desvanece a lo largo
                d0, d1 = largo * seg / 6, largo * (seg + 1) / 6
                a = int(120 * (1 - seg / 6) ** 1.3 * aparicion)
                if a <= 2:
                    continue
                g0 = grosor * (1 - seg * 0.08)
                dl.polygon([
                    (sx + dx * d0 + px * g0, sy + dy * d0 + py * g0),
                    (sx + dx * d1 + px * g0, sy + dy * d1 + py * g0),
                    (sx + dx * d1 - px * g0, sy + dy * d1 - py * g0),
                    (sx + dx * d0 - px * g0, sy + dy * d0 - py * g0),
                ], fill=(255, 226, 138, a))

        # barrido de luz directa cruzando el fondo
        fase = min(1.0, max(0.0, (p - 0.18) / 0.72))
        if 0 < fase < 1:
            a = int(200 * math.sin(fase * math.pi))
            cx_b = (-0.3 + 1.6 * fase) * w * cfg["barre"] + (w if cfg["barre"] < 0 else 0)
            for k in range(-4, 5):
                aa = int(a * (1 - abs(k) / 5))
                if aa > 3:
                    dl.line([(cx_b + k * 11 - 90, -60), (cx_b + k * 11 + 90, h + 60)],
                            fill=(255, 250, 226, aa), width=13)

        # disco del sol
        rd = 46 * aparicion
        if rd > 1:
            dl.ellipse((sx - rd * 1.5, sy - rd * 1.5, sx + rd * 1.5, sy + rd * 1.5),
                       fill=(255, 236, 168, int(150 * aparicion)))
            dl.ellipse((sx - rd, sy - rd, sx + rd, sy + rd), fill=(255, 243, 190, 255))

        img.alpha_composite(luz)

        # --- CAPA 2: el aparato -------------------------------------------
        entra = _suave(min(1.0, p / 0.34))
        desp = int((1 - entra) * 26)
        # destello del marco: sube cuando la luz pasa por encima
        fuerza = math.sin(min(1.0, max(0.0, (p - 0.22) / 0.6)) * math.pi)
        if fuerza > 0.02:
            capa = aura.copy()
            capa.putalpha(capa.split()[3].point(lambda v: int(v * fuerza * entra)))
            img.alpha_composite(capa, (ax, ay + desp))
        capa_nitida = aparato
        if entra < 1.0:
            capa_nitida = aparato.copy()
            capa_nitida.putalpha(aparato.split()[3].point(lambda v: int(v * entra)))
        img.alpha_composite(capa_nitida, (ax, ay + desp))

        # --- CAPA 3: el texto ----------------------------------------------
        if p > 0.18:
            _etiqueta(ImageDraw.Draw(img), etiqueta, w / 2, h - 62)

        # cierre
        if p > 0.88:
            salida = 1 - _suave((p - 0.88) / 0.12)
            img.putalpha(img.split()[3].point(lambda v: int(v * salida)))

        img.save(frames / f"f_{i:04d}.png")

    return _codificar(frames, dir_tmp / f"anim_sol_v{var}.mov", fps)


GENERADORES = {
    "bateria": animar_bateria,
    "splash": animar_splash,
    "moto": animar_moto,
    "sol": animar_sol,
}


def generar(nombre: str, dir_tmp: Path, duracion: float = None,
            semilla=None, variante: int = None,
            foto_dispositivo: Path = None, etiqueta: str = None) -> Path | None:
    """Respaldo PIL. `variante` fija la toma (la elige el pipeline, no el azar).

    `foto_dispositivo` y `etiqueta` solo los usa el sol: es la única de las
    cuatro que lleva texto dibujado, porque en ella el mensaje ("se lee bajo el
    sol") es el argumento entero. Batería, splash y moto siguen sin texto en la
    versión PIL, igual que antes — el texto lo pone Hyperframes, que es el motor
    primario.
    """
    fn = GENERADORES.get(nombre)
    if fn is None:
        return None
    kwargs = {"duracion": duracion} if duracion else {}
    kwargs["semilla"] = semilla
    kwargs["variante"] = variante
    if nombre == "sol":
        kwargs["foto_dispositivo"] = foto_dispositivo
        kwargs["etiqueta"] = etiqueta
    try:
        return fn(dir_tmp, **kwargs)
    except Exception as e:
        print(f"AVISO: no se pudo generar la animación '{nombre}': {e}", file=sys.stderr)
        return None


def miniatura(ruta_clip: Path, dir_cache: Path = None) -> Path | None:
    """Fotograma representativo de un clip de animación, para el editor visual.

    Por qué existe: ningún navegador reproduce ProRes 4444, así que en el editor
    las animaciones se ven como un bloque con una imagen fija (§3c del plan).
    Sin esto la interfaz no tiene NADA que mostrar de ellas.

    **No es el primer fotograma, aunque el plan lo llame así**: todas estas
    animaciones arrancan con opacidad 0 (entran con un fade), así que el frame 0
    sale transparente y como miniatura no dice nada. Se toma al 45% de la
    duración, que es donde el gesto ya está completo.

    Se cachea por mtime del clip. Como los MOV de Hyperframes ya están
    cacheados por contenido, en la práctica se genera una sola vez por variante.
    """
    if ruta_clip is None:
        return None
    ruta_clip = Path(ruta_clip)
    if not ruta_clip.exists():
        return None

    dir_cache = dir_cache or (config.DIR_EDITOR_CACHE / "anim_frames")
    dir_cache.mkdir(parents=True, exist_ok=True)
    destino = dir_cache / f"{ruta_clip.stem}.png"
    if destino.exists() and destino.stat().st_mtime >= ruta_clip.stat().st_mtime:
        return destino

    # 45% de la duración; el alfa se aplana sobre gris para que se vea la forma
    try:
        dur = float(subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(ruta_clip)],
            capture_output=True, text=True, check=True).stdout.strip())
    except Exception:
        dur = 2.4
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{dur * 0.45:.3f}",
           "-i", str(ruta_clip), "-frames:v", "1",
           "-vf", "scale=270:-1", str(destino)]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except Exception as e:
        print(f"AVISO: no se pudo extraer la miniatura de {ruta_clip.name}: {e}", file=sys.stderr)
        return None
    return destino if destino.exists() else None


def main():
    ap = argparse.ArgumentParser(description="Genera las animaciones del editor")
    ap.add_argument("--demo", action="store_true", help="Genera las tres en salida/animaciones/")
    ap.add_argument("--nombre", type=str, default=None, choices=list(GENERADORES))
    args = ap.parse_args()

    destino = config.RAIZ_PROYECTO / "salida" / "animaciones"
    destino.mkdir(parents=True, exist_ok=True)

    nombres = [args.nombre] if args.nombre else list(GENERADORES)
    for n in nombres:
        ruta = generar(n, destino)
        if ruta:
            print(f"  {n:<10} -> {ruta}")


if __name__ == "__main__":
    main()
