"""
Fase 0 — Preparar la grabación ANTES de que entre al pipeline.

Elegir qué archivos entran, recortarles el principio y el final, ordenarlos y
unirlos. Todo esto ocurre antes de f1_transcribir, y esa es la propiedad de
diseño que hace que sea seguro: cuando f1 arranca ya está mirando el archivo
definitivo, así que NINGUNA coordenada de tiempo de aguas abajo (palabras, SFX,
overlays, encuadre, ajustes.*.json) se entera de que hubo un recorte. Si esto se
hiciera después de transcribir habría que remapear media docena de listas.

Por qué hace falta:

  · La transcripción corría sobre el archivo entero, incluidos los segundos de
    caminar hasta la cámara y el carraspeo de antes de empezar. Medido en
    `entrada/video-crudo-kindle-paperwhite.mp4`: 49.4s de archivo para un video
    objetivo de 30-40s.
  · Las palabras basura del principio disparan insertos equivocados: los PiP se
    eligen por palabra dicha (config.PALABRAS_A_TAGS), así que un "a ver, ya"
    suelto antes del guion puede traer una foto a pantalla.
  · Si se grabaron varios planos, hasta ahora se pasaban por línea de comandos
    enteros, sin poder recortarlos.

La pantalla que consume este módulo vive en `f0_servidor_preparar.py`; acá solo
está la lógica, sin HTTP, para que se pueda probar sin levantar un servidor.

Uso desde código:
    import f0_preparar
    ruta, empalmes = f0_preparar.preparar_entrada(clips, destino)
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

EXTENSIONES_VIDEO = (".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm")

# Aire que se deja a cada lado del primer y el último sonido detectado. El
# `silencedetect` marca el instante exacto en que la señal cruza el umbral, o
# sea el ataque de la primera consonante: cortar ahí mismo se come el arranque
# de la palabra y se oye como un empujón. 0.40s es medio parpadeo — no se nota
# como pausa pero deja entrar la palabra completa.
MARGEN_PROPUESTA_S = 0.40

# El umbral de silencio NO es una constante: se mide del propio archivo.
#
# Un valor fijo no funciona y está comprobado. Con -35 dBFS sobre
# `entrada/video-crudo-kindle-paperwhite.mp4` (teléfono, mean_volume -15.7 dB y
# picos tocando 0) el detector no encontró NI UN silencio en 49s de grabación:
# el ruido de sala de esa toma vive por encima de -35, así que todo el archivo
# contaba como sonido. Con el mismo -35 sobre una grabación del DJI Mic Mini,
# que registra mucho más bajo, se habría comido media frase.
#
# Se toma `mean_volume` (una pasada de `volumedetect`, décimas de segundo
# porque es solo audio) y se baja este margen. Medido: -15.7 - 15 = -30.7 dB
# encuentra correctamente los 7 silencios reales de esa grabación.
SILENCIO_MARGEN_BAJO_MEDIA_DB = 15.0
# Topes de cordura por si `volumedetect` devuelve algo raro (un archivo mudo, o
# uno con un pitido constante).
SILENCIO_UMBRAL_MIN_DB = -50.0
SILENCIO_UMBRAL_MAX_DB = -20.0
SILENCIO_DUR_MIN_S = 0.40


# ---------------------------------------------------------------------------
# Sondas de archivo
# ---------------------------------------------------------------------------
def duracion(ruta: Path) -> float:
    """Duración en segundos según ffprobe."""
    salida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(ruta)],
        capture_output=True, text=True, encoding="utf-8", check=True).stdout.strip()
    return float(salida)


def _duracion(ruta: Path) -> float:
    """Alias del nombre que tenía en editor.py, donde vivía esta función."""
    return duracion(Path(ruta))


def listar_entrada(dir_entrada: Path = None) -> list:
    """Los videos crudos de `entrada/`, el más reciente primero.

    OJO con la carpeta: es `entrada/`, no `contexto/`. En `contexto/` hay un
    video de referencia (`tiktok video deviceshop.mp4`) que no es material de
    José y no tiene nada que hacer en esta lista.
    """
    dir_entrada = Path(dir_entrada or config.DIR_ENTRADA)
    if not dir_entrada.is_dir():
        return []
    videos = []
    for p in sorted(dir_entrada.iterdir()):
        if not p.is_file() or p.suffix.lower() not in EXTENSIONES_VIDEO:
            continue
        try:
            dur = duracion(p)
        except Exception:
            continue          # un archivo a medio copiar no debe tumbar la lista
        videos.append({
            "nombre": p.name,
            # `resolve()` y no `str(p)` a secas: `normalizar_clips` resuelve las
            # rutas antes de guardarlas en el .preparado.json, así que si esta
            # lista no resolviera igual, las dos cadenas no coincidirían y la
            # preparación guardada no se recuperaría. Falla en silencio: la
            # pantalla dice que la recuperó y aparece vacía.
            "ruta": str(p.resolve()),
            "duracion": round(dur, 3),
            "mb": round(p.stat().st_size / 1e6, 1),
            "mtime": p.stat().st_mtime,
        })
    videos.sort(key=lambda v: v["mtime"], reverse=True)
    return videos


def umbral_silencio(ruta: Path) -> float:
    """Umbral de silencio en dBFS, medido sobre este archivo concreto.

    Ver el comentario de SILENCIO_MARGEN_BAJO_MEDIA_DB: un umbral fijo falla en
    los dos sentidos según con qué micrófono se grabó.
    """
    res = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(ruta), "-vn",
         "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    m = re.search(r"mean_volume:\s*(-?[\d.]+) dB", (res.stderr or "") + (res.stdout or ""))
    if not m:
        return -35.0
    umbral = float(m.group(1)) - SILENCIO_MARGEN_BAJO_MEDIA_DB
    return max(SILENCIO_UMBRAL_MIN_DB, min(SILENCIO_UMBRAL_MAX_DB, umbral))


def detectar_bordes(ruta: Path, umbral_db: float = None,
                    dur_min_s: float = SILENCIO_DUR_MIN_S,
                    margen_s: float = MARGEN_PROPUESTA_S) -> dict:
    """Propone (desde, hasta) buscando el primer y el último sonido real.

    Usa `silencedetect` de ffmpeg y NO la transcripción: transcribir el archivo
    crudo son ~40s de GPU y es justo lo que este módulo existe para evitar. Con
    `-vn` (sin decodificar video) el escaneo de una grabación de 50s tarda
    alrededor de un segundo.

    Solo mira los silencios de los EXTREMOS. Una pausa larga a mitad del video
    no propone nada: eso ya lo recorta f2_cortar más adelante, con el criterio
    de silencios y muletillas que le corresponde.

    Devuelve {desde, hasta, duracion, detectado}. Si no encuentra nada (audio
    parejo de punta a punta), propone el archivo entero y `detectado: False`.
    """
    ruta = Path(ruta)
    total = duracion(ruta)
    if umbral_db is None:
        umbral_db = umbral_silencio(ruta)
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(ruta), "-vn",
           "-af", f"silencedetect=noise={umbral_db}dB:d={dur_min_s}",
           "-f", "null", "-"]
    # ffmpeg escribe silencedetect en stderr. `encoding="utf-8"` explícito: sin
    # él, `text=True` decodifica con la codificación regional de Windows y una
    # ruta con tilde rompe el parseo entero.
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                         errors="replace")
    salida = (res.stderr or "") + (res.stdout or "")

    inicios = [float(m) for m in re.findall(r"silence_start:\s*(-?[\d.]+)", salida)]
    finales = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", salida)]

    desde, hasta = 0.0, total
    detectado = False

    # Silencio de cabecera: el que arranca pegado al segundo 0. Su `silence_end`
    # es el primer sonido real del archivo.
    if inicios and inicios[0] <= 0.05 and finales:
        desde = max(0.0, finales[0] - margen_s)
        detectado = True

    # Silencio de cola: el que llega hasta el final. Puede venir sin
    # `silence_end` (ffmpeg no siempre cierra el último al llegar a EOF), así
    # que se detecta por conteo: hay un `silence_start` sin pareja.
    cola = None
    if len(inicios) > len(finales):
        cola = inicios[-1]
    elif inicios and finales and abs(finales[-1] - total) <= 0.05:
        cola = inicios[-1]
    if cola is not None and cola > desde:
        hasta = min(total, cola + margen_s)
        detectado = True

    if hasta - desde < 0.5:      # propuesta absurda: mejor no proponer nada
        return {"desde": 0.0, "hasta": round(total, 3),
                "duracion": round(total, 3), "detectado": False,
                "umbral_db": round(umbral_db, 1)}
    return {"desde": round(desde, 3), "hasta": round(hasta, 3),
            "duracion": round(total, 3), "detectado": detectado,
            "umbral_db": round(umbral_db, 1)}


# ---------------------------------------------------------------------------
# Proxy para la pantalla (scrubbing en el navegador)
# ---------------------------------------------------------------------------
def proxy_clip(ruta: Path, dir_cache: Path = None) -> Path:
    """Copia liviana del clip crudo para poder arrastrarlo en el navegador.

    No es un lujo: la grabación real es HEVC 1920x1080 a 60 fps con la etiqueta
    de rotación 90° (medido en `entrada/video-crudo-kindle-paperwhite.mp4`, 125
    MB). Chrome solo reproduce HEVC si Windows tiene instaladas las extensiones
    de pago, y Firefox no lo reproduce nunca — servir el original significaba
    una pantalla en negro sin ningún mensaje. El proxy es H.264 540x960, que
    reproduce cualquier navegador, y de paso aplica la rotación (ffmpeg gira
    solo al recodificar), así que se ve vertical como se grabó.

    Mismo criterio de caché que `f10.generar_proxy`: se invalida por mtime del
    original, no por tiempo ni por conteo.
    """
    ruta = Path(ruta)
    dir_cache = Path(dir_cache or (config.DIR_PREPARACION / "proxies"))
    dir_cache.mkdir(parents=True, exist_ok=True)
    # El mtime va en el nombre y no solo en la comparación: dos grabaciones
    # distintas pueden llamarse igual si vienen de carpetas distintas.
    proxy = dir_cache / f"proxy_{ruta.stem}_{int(ruta.stat().st_mtime)}.mp4"
    if proxy.exists() and proxy.stat().st_mtime >= ruta.stat().st_mtime:
        return proxy
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(ruta),
        "-vf", f"scale={config.ANCHO // 2}:{config.ALTO // 2}:"
               f"force_original_aspect_ratio=decrease,"
               f"pad={config.ANCHO // 2}:{config.ALTO // 2}:(ow-iw)/2:(oh-ih)/2",
        "-r", "30",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart", str(proxy),
    ], check=True, capture_output=True)
    return proxy


# ---------------------------------------------------------------------------
# Recorte y unión — el camino que comparten la previa y la corrida de verdad
# ---------------------------------------------------------------------------
def unir_tomas(rutas: list, destino: Path) -> tuple:
    """Une varias grabaciones en un solo archivo y devuelve (ruta, empalmes).

    Para cuando José graba el mismo guion en DOS PLANOS REALES — uno abierto y
    uno cerrado, como pide la columna "Tomas" del panel ("Plano cerrado, acercá
    la cámara. Cambio de distancia real, no zoom digital"). El pipeline entero
    trabaja sobre un archivo, así que se unen antes de transcribir y se anotan
    los segundos donde empalman: esos son los ÚNICOS cambios de plano de verdad
    del video, y f4_retencion los usa para reiniciar ahí la rampa de zoom (y solo
    ahí — un corte de silencio no es un cambio de plano).

    Primero se intenta el demuxer `concat` con `-c copy`: son tomas de la misma
    cámara con los mismos ajustes, así que copiar es instantáneo y no añade una
    generación de compresión. Si ffmpeg se queja (parámetros distintos entre
    archivos), se recodifica con el filtro concat, que sí normaliza.

    Vive acá y no en editor.py porque la pantalla de preparación tiene que unir
    con ESTA función y no con una parecida: si la previa uniera de otra manera,
    mostraría algo distinto de lo que después sale del pipeline. editor.py la
    importa desde este módulo.

    NO lleva ningún desvanecido ni cruce de audio en las uniones, a propósito.
    El pipeline ya empalma con trim+concat pelado (f2_cortar.cortar_video_ffmpeg)
    y hace decenas de cortes así sin que se oiga, porque todos caen en silencio.
    Además un cruce obligaría a recodificar y mataría el camino de `-c copy` que
    es lo que hace instantánea la previa.
    """
    empalmes, acumulado = [], 0.0
    for r in rutas[:-1]:
        acumulado += duracion(r)
        empalmes.append(round(acumulado, 3))

    lista = destino.with_suffix(".txt")
    lista.write_text(
        "".join(f"file '{Path(r).as_posix()}'\n" for r in rutas), encoding="utf-8")
    cmd_copia = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                 "-i", str(lista), "-c", "copy", str(destino)]
    if subprocess.run(cmd_copia, capture_output=True).returncode != 0:
        print("  (las tomas no son copiables tal cual — se recodifican para unirlas)")
        entradas, partes = [], []
        for i, r in enumerate(rutas):
            entradas += ["-i", str(r)]
            partes.append(f"[{i}:v][{i}:a]")
        filtro = f"{''.join(partes)}concat=n={len(rutas)}:v=1:a=1[v][a]"
        cmd_recod = ["ffmpeg", "-y", "-loglevel", "error", *entradas,
                     "-filter_complex", filtro, "-map", "[v]", "-map", "[a]",
                     *config.args_video(), "-c:a", "aac", "-b:a", "192k", str(destino)]
        r = subprocess.run(cmd_recod, capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        if r.returncode != 0:
            print((r.stderr or "")[-2000:], file=sys.stderr)
            sys.exit("ERROR: no se pudieron unir las tomas")
    lista.unlink(missing_ok=True)

    print(f"  {len(rutas)} tomas unidas en {destino.name}; "
          f"empalmes en {', '.join(f'{t:.2f}s' for t in empalmes)}")
    return destino, empalmes


def normalizar_clips(clips: list) -> list:
    """Valida y acota la lista de clips. Devuelve dicts {ruta, desde, hasta}.

    `hasta` a None o 0 significa "hasta el final". Los valores se recortan
    contra la duración real del archivo: un `hasta` heredado de un
    .preparado.json viejo puede apuntar más allá del final si el archivo se
    volvió a grabar, y ffmpeg no avisa — devuelve un clip más corto y el
    empalme queda mal.
    """
    salida = []
    for c in clips:
        ruta = Path(c["ruta"]).resolve()
        if not ruta.exists():
            raise FileNotFoundError(f"No existe el clip: {ruta}")
        total = duracion(ruta)
        desde = max(0.0, float(c.get("desde") or 0.0))
        hasta = c.get("hasta")
        hasta = total if hasta in (None, "", 0) else min(float(hasta), total)
        desde = min(desde, max(0.0, hasta - 0.1))
        salida.append({"ruta": ruta, "desde": round(desde, 3),
                       "hasta": round(hasta, 3), "total": round(total, 3)})
    if not salida:
        raise ValueError("No se eligió ningún clip")
    return salida


def _hay_recorte(c: dict) -> bool:
    return c["desde"] > 0.01 or c["hasta"] < c["total"] - 0.01


def recortar_clip(origen: Path, destino: Path, desde: float, hasta: float,
                  escala: float = None) -> Path:
    """Recorta [desde, hasta] de `origen` recodificando, exacto al fotograma.

    Se busca `-ss`/`-to` DESPUÉS de `-i` (búsqueda de salida) y no antes: la
    búsqueda de entrada es más rápida pero arranca en el fotograma clave
    anterior, y con clips de teléfono los claves están cada 2s. Un recorte que
    se pasa 2 segundos del punto elegido no sirve para nada acá — el punto es
    justamente elegirlo a mano.

    `escala` (0-1) baja la resolución para la previa. Además de la escala se
    RELLENA a un tamaño fijo: dos tomas del mismo teléfono pueden venir en
    distinta resolución si se grabaron en modos distintos, y si los recortes no
    salen todos iguales, `unir_tomas` pierde el camino de `-c copy` y la previa
    deja de ser instantánea.
    """
    origen, destino = Path(origen), Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(origen),
           "-ss", f"{desde:.3f}", "-to", f"{hasta:.3f}"]
    if escala:
        an, al = int(config.ANCHO * escala) // 2 * 2, int(config.ALTO * escala) // 2 * 2
        cmd += ["-vf", f"scale={an}:{al}:force_original_aspect_ratio=decrease,"
                       f"pad={an}:{al}:(ow-iw)/2:(oh-ih)/2",
                "-r", "30",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
                "-movflags", "+faststart"]
    else:
        cmd += [*config.args_video()]
    cmd += ["-c:a", "aac", "-b:a", "192k", "-ar", str(config.AUDIO_SAMPLE_RATE),
            str(destino)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        print((r.stderr or "")[-2000:], file=sys.stderr)
        raise RuntimeError(f"ffmpeg falló al recortar {origen.name}")
    return destino


def preparar_entrada(clips: list, destino: Path, escala: float = None,
                     dir_tmp: Path = None) -> tuple:
    """Recorta, ordena y une. Devuelve (ruta_resultante, empalmes).

    Es el ÚNICO camino: lo llaman igual la previa de la pantalla (con `escala`)
    y la corrida de verdad (sin ella). Si fueran dos caminos distintos, la
    previa mostraría una cosa y el pipeline sacaría otra, que es exactamente el
    fallo que esta función existe para no tener.

    Atajo importante: un solo clip sin recortar y sin escala se devuelve TAL
    CUAL, sin tocar ffmpeg. Es el caso normal («editame este video») y así
    sigue costando lo mismo que antes de que esta fase existiera — cero
    recodificaciones añadidas.

    Cuando hay varios clips y alguno se recorta, se recortan TODOS aunque a
    alguno no le sobre nada. Un clip recodificado (H.264, ya girado) y otro
    copiado del teléfono (HEVC, con etiqueta de rotación) no se pueden unir con
    `-c copy`, y peor: el que conserva la etiqueta se vería tumbado. Pasar
    todos por el mismo molde cuesta unos segundos y quita esa clase de fallo.
    """
    clips = normalizar_clips(clips)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)

    if len(clips) == 1 and not _hay_recorte(clips[0]) and not escala:
        return clips[0]["ruta"], []

    if not escala and not any(_hay_recorte(c) for c in clips):
        # Varios clips, ninguno recortado: es exactamente lo que editor.py hacía
        # antes de que existiera esta fase. Se une sin recortar nada, para no
        # meter una generación de compresión que antes no había.
        return unir_tomas([c["ruta"] for c in clips], destino)

    dir_tmp = Path(dir_tmp or (destino.parent / f"_recortes_{destino.stem}"))
    dir_tmp.mkdir(parents=True, exist_ok=True)
    recortados = []
    try:
        for i, c in enumerate(clips):
            parcial = dir_tmp / f"{i:02d}{destino.suffix}"
            print(f"  recortando {c['ruta'].name}: "
                  f"{c['desde']:.2f}s -> {c['hasta']:.2f}s "
                  f"({c['hasta'] - c['desde']:.2f}s)")
            recortar_clip(c["ruta"], parcial, c["desde"], c["hasta"], escala)
            recortados.append(parcial)

        if len(recortados) == 1:
            shutil.move(str(recortados[0]), str(destino))
            return destino, []
        return unir_tomas(recortados, destino)
    finally:
        shutil.rmtree(dir_tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# Memoria: el .preparado.json junto al archivo de entrada
# ---------------------------------------------------------------------------
def ruta_preparado(primera: Path) -> Path:
    """Dónde se guarda la preparación: al lado del PRIMER clip.

    Junto al archivo de entrada y no en la carpeta de trabajo porque la
    preparación es del MATERIAL, no de la corrida: sobrevive a borrar
    `C:\\ai-video\\salida\\<nombre>\\` y sirve igual si el mismo metraje se usa
    para dos guiones distintos.
    """
    primera = Path(primera)
    return primera.parent / f"{primera.stem}.preparado.json"


def guardar_preparado(clips: list, guion: int = None, nombre: str = None) -> Path:
    """Escribe el .preparado.json. Devuelve su ruta."""
    from datetime import datetime
    clips = normalizar_clips(clips)
    destino = ruta_preparado(clips[0]["ruta"])
    datos = {
        "clips": [{"ruta": str(c["ruta"]), "desde": c["desde"], "hasta": c["hasta"]}
                  for c in clips],
        "guion": guion,
        "nombre": nombre,
        "total_s": round(sum(c["hasta"] - c["desde"] for c in clips), 2),
        "guardado": datetime.now().isoformat(timespec="seconds"),
    }
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(destino)
    return destino


def leer_preparado(primera: Path) -> dict | None:
    """La preparación guardada para este material, o None si no hay.

    Devuelve None (en vez de reventar) si el archivo está corrupto o apunta a
    clips que ya no existen: una preparación vieja nunca debe impedir correr el
    pipeline, solo dejar de aportar.
    """
    ruta = ruta_preparado(primera)
    if not ruta.exists():
        return None
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        clips = datos.get("clips") or []
        if not clips or any(not Path(c["ruta"]).exists() for c in clips):
            return None
        return datos
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Guiones del panel
# ---------------------------------------------------------------------------
def listar_guiones() -> list:
    """Los guiones de PANEL-PRODUCCION.html, para el desplegable de la pantalla.

    `hooksegs` viaja hasta la pantalla porque manda sobre el recorte: son los
    segundos de silencio ANTES de la primera palabra que f2_cortar conserva a
    propósito (el hook físico: entrar al cuadro y sentarse). Si el recorte de
    esta pantalla se los lleva, `hooksegs` ya no tiene nada que conservar y el
    gesto de apertura desaparece sin que nada dé error.
    """
    try:
        import f13_guion
        datos = f13_guion.cargar_datos_html()
    except Exception as e:
        print(f"AVISO: no se pudo leer PANEL-PRODUCCION.html ({e})", file=sys.stderr)
        return []
    guiones = []
    for g in datos.get("G", []):
        if g.get("n") is None:
            continue
        try:
            hooksegs = float(g.get("hooksegs") or 0.0)
        except (TypeError, ValueError):
            hooksegs = 0.0
        try:
            cierresegs = float(g.get("cierresegs") or 0.0)
        except (TypeError, ValueError):
            cierresegs = 0.0
        guiones.append({
            "n": g.get("n"),
            "titulo": g.get("t", ""),
            "hook": g.get("hook", ""),
            "hooksegs": max(0.0, hooksegs),
            "cierresegs": max(0.0, cierresegs),
        })
    guiones.sort(key=lambda g: g["n"])
    return guiones
