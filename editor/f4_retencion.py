"""
Fase 3 — Capa de retención.

1. Face tracking (MediaPipe) con suavizado exponencial.
2. Punch-ins por picos de energía RMS del audio.
3. Zoom progresivo continuo dentro de cada plano.
4. Motor de la regla de 5s: detecta huecos >=5s sin cambio visual y los
   deja marcados en un JSON para que la Fase 5 los rellene con overlays.
5. Nota de diseño de loop (comparación primer/último plano) para Fase 5.

Requiere: opencv-python, mediapipe, numpy, scipy (en venv312).

Uso:
    python f4_retencion.py "video_cortado.mp4" "video_cortado.json" [--salida video_retencion.mp4]
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

import config


# Perfil del presentador activo (ver config.PRESENTADORES). Lo fija main() con
# --presentador; por defecto, el de José.
PERFIL = config.perfil()


def _log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# 1. Face tracking
# ---------------------------------------------------------------------------
def _crear_detector_rostro():
    """Devuelve ("mediapipe", detector) o ("haar", cascade), en ese orden de preferencia.

    mediapipe 0.10.35 no trae la API legacy `mp.solutions`; se usa la Tasks API
    con el modelo BlazeFace short-range (descargado una vez a C:\\ai-video\\models).
    Si el modelo o la API no están, se cae a Haar Cascade de OpenCV.
    """
    import cv2

    ruta_modelo = config.FACE_TRACK_MODELO_MEDIAPIPE
    if ruta_modelo.exists():
        try:
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision

            opciones = vision.FaceDetectorOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(ruta_modelo)),
                running_mode=vision.RunningMode.VIDEO,
                min_detection_confidence=0.5,
            )
            return "mediapipe", vision.FaceDetector.create_from_options(opciones)
        except Exception as e:  # ImportError o cambio de API entre versiones
            _log(f"ADVERTENCIA: no se pudo iniciar MediaPipe Tasks ({e}). "
                 "Usando Haar cascade de OpenCV como fallback.")
    else:
        _log(f"ADVERTENCIA: no existe {ruta_modelo} — usando Haar cascade de OpenCV. "
             "(Descargar blaze_face_short_range.tflite ahí para mejor tracking.)")
    return "haar", cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def rastrear_rostro(ruta_video: Path, fps_muestreo: float = 5.0) -> list:
    """Devuelve lista [(t, cx, cy, ancho_rostro)] normalizados 0-1, suavizados con EMA."""
    import cv2

    tipo_detector, detector = _crear_detector_rostro()

    cap = cv2.VideoCapture(str(ruta_video))
    fps_video = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    salto = max(1, round(fps_video / fps_muestreo))

    puntos = []
    alpha = PERFIL["face_track_alpha"]
    cx_ema, cy_ema = 0.5, 0.4  # arranque: centro-superior (encuadre típico de talking-head)

    idx = 0
    while True:
        # Se analiza a 5 fps sobre un video de 30-60 fps, así que la mayoría de
        # los frames se descartan. grab() avanza el decodificador sin construir
        # el array de numpy ni convertir color — que es la parte cara. Antes se
        # usaba read() para todos y se tiraba el resultado.
        if idx % salto != 0:
            if not cap.grab():
                break
            idx += 1
            continue

        ret, frame = cap.read()
        if not ret:
            break

        t = idx / fps_video

        # El detector no necesita el frame completo: se reduce a un ancho fijo
        # antes de detectar. Con Haar sobre el frame completo de 1080x1920 cada
        # detección costaba ~145 ms (medido); reducido + minSize baja a pocos ms.
        # Las coordenadas se devuelven normalizadas, así que la reducción no
        # afecta el resultado.
        h, w = frame.shape[:2]
        escala = config.FACE_TRACK_ANCHO_ANALISIS / w
        chico = cv2.resize(frame, (config.FACE_TRACK_ANCHO_ANALISIS, round(h * escala)),
                           interpolation=cv2.INTER_AREA)
        hc, wc = chico.shape[:2]
        cx, cy, ancho_rel = None, None, None

        if tipo_detector == "mediapipe":
            import mediapipe as mp
            rgb = cv2.cvtColor(chico, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            resultado = detector.detect_for_video(mp_img, round(t * 1000))
            if resultado.detections:
                d = max(resultado.detections, key=lambda d: d.categories[0].score)
                caja = d.bounding_box  # en píxeles del frame reducido
                cx = (caja.origin_x + caja.width / 2) / wc
                cy = (caja.origin_y + caja.height / 2) / hc
                ancho_rel = caja.width / wc
        else:
            gris = cv2.cvtColor(chico, cv2.COLOR_BGR2GRAY)
            # minSize: en un talking-head el rostro nunca es menor a ~1/8 del ancho;
            # sin este límite Haar rastrilla escalas desde 30px y tarda 20x más.
            min_lado = max(24, wc // 8)
            caras = detector.detectMultiScale(gris, 1.1, 5, minSize=(min_lado, min_lado))
            if len(caras) > 0:
                x, y, cw, ch = max(caras, key=lambda c: c[2] * c[3])
                cx, cy = (x + cw / 2) / wc, (y + ch / 2) / hc
                ancho_rel = cw / wc

        if cx is not None:
            cx_ema = alpha * cx + (1 - alpha) * cx_ema
            cy_ema = alpha * cy + (1 - alpha) * cy_ema

        puntos.append({"t": round(t, 3), "cx": round(cx_ema, 4), "cy": round(cy_ema, 4),
                        "ancho_rostro": round(ancho_rel, 4) if ancho_rel else None})
        idx += 1

    cap.release()
    _log(f"Face tracking ({tipo_detector}): {len(puntos)} muestras sobre {total_frames} frames ({fps_video:.1f} fps)")
    return puntos


# ---------------------------------------------------------------------------
# 2. Picos de energía RMS -> punch-ins
# ---------------------------------------------------------------------------
def detectar_picos_energia(ruta_video: Path) -> list:
    import scipy.io.wavfile as wavfile

    wav_tmp = ruta_video.with_suffix(".rms_tmp.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(ruta_video), "-ac", "1", "-ar", "16000", "-vn", str(wav_tmp)],
        capture_output=True, check=True,
    )
    sr, audio = wavfile.read(wav_tmp)
    wav_tmp.unlink(missing_ok=True)

    audio = audio.astype(np.float32)
    if audio.max() > 0:
        audio /= np.abs(audio).max()

    ventana = int(sr * 0.05)  # 50ms
    hop = ventana // 2
    rms = np.array([
        np.sqrt(np.mean(audio[i:i + ventana] ** 2))
        for i in range(0, len(audio) - ventana, hop)
    ])
    tiempos = np.arange(len(rms)) * hop / sr

    if len(rms) == 0:
        return []

    umbral = np.percentile(rms, PERFIL["punch_in_percentil"])
    espaciado_min_s = 1.5
    picos = []
    ultimo_t = -999
    for t, valor in zip(tiempos, rms):
        if valor >= umbral and (t - ultimo_t) >= espaciado_min_s:
            picos.append({"t": round(float(t), 3), "energia": round(float(valor), 4)})
            ultimo_t = t

    _log(f"Picos de énfasis detectados: {len(picos)}")
    return picos


# ---------------------------------------------------------------------------
# 3+4. Construir línea de tiempo de zoom + detectar huecos (regla de 5s)
# ---------------------------------------------------------------------------
def construir_planos(duracion_total: float, cortes_previos: list) -> list:
    """Un 'plano' = tramo continuo entre jump-cuts aplicados en f2_cortar.
    Si no hay info de cortes, se trata todo el video como un solo plano."""
    if not cortes_previos:
        return [{"inicio": 0.0, "fin": duracion_total}]
    # cortes_previos aquí representa duraciones de intervalos conservados (ver f2); se
    # reconstruyen límites acumulados
    planos = []
    cursor = 0.0
    for c in cortes_previos:
        dur = c["fin"] - c["inicio"]
        planos.append({"inicio": round(cursor, 3), "fin": round(cursor + dur, 3)})
        cursor += dur
    return planos


def calcular_zoom_en_t(t: float, planos: list, picos: list) -> float:
    zoom = config.ZOOM_PROGRESIVO_INICIO
    for plano in planos:
        if plano["inicio"] <= t <= plano["fin"]:
            dur = plano["fin"] - plano["inicio"]
            progreso = (t - plano["inicio"]) / dur if dur > 0 else 0
            zoom = config.ZOOM_PROGRESIVO_INICIO + progreso * (
                config.ZOOM_PROGRESIVO_FIN - config.ZOOM_PROGRESIVO_INICIO
            )
            break

    for pico in picos:
        dt = t - pico["t"]
        if 0 <= dt <= config.PUNCH_IN_DURACION_S:
            factor_pico = 1 - abs(dt - config.PUNCH_IN_DURACION_S / 2) / (config.PUNCH_IN_DURACION_S / 2)
            zoom = max(zoom, config.ZOOM_PROGRESIVO_INICIO + factor_pico * (config.PUNCH_IN_ZOOM - config.ZOOM_PROGRESIVO_INICIO))

    return round(zoom, 4)


def encuadre_en_t(t: float, tiempos_track: np.ndarray, cx_track: np.ndarray, cy_track: np.ndarray,
                   planos: list, picos: list, hacer_loop: bool = False, t_loop: float = None,
                   cx_ini: float = None, cy_ini: float = None, zoom_ini: float = None):
    """(cx, cy, zoom) del encuadre en el segundo t: interpolación del track de
    rostro + calcular_zoom_en_t(), con el blend de loop de los últimos
    LOOP_DURACION_S si aplica. La usa tanto el render real
    (renderizar_con_zoom) como el preview del editor visual (f11_servidor) —
    una sola implementación para que no puedan divergir."""
    cx = float(np.interp(t, tiempos_track, cx_track))
    cy = float(np.interp(t, tiempos_track, cy_track))
    zoom = calcular_zoom_en_t(t, planos, picos)

    if hacer_loop and t_loop is not None and t >= t_loop:
        u = min(1.0, (t - t_loop) / config.LOOP_DURACION_S)
        s = u * u * (3 - 2 * u)
        cx += (cx_ini - cx) * s
        cy += (cy_ini - cy) * s
        zoom += (zoom_ini - zoom) * s

    return cx, cy, zoom


def detectar_huecos_regla_5s(duracion_total: float, planos: list, picos: list) -> list:
    """Eventos de 'cambio visual' = límites de plano (jump cuts) + punch-ins.
    Cualquier tramo >= REGLA_5S_MAX_BLOQUE_S sin evento queda marcado como hueco."""
    eventos = {0.0, duracion_total}
    for p in planos:
        eventos.add(p["inicio"])
        eventos.add(p["fin"])
    for pico in picos:
        eventos.add(pico["t"])

    eventos = sorted(eventos)
    huecos = []
    for a, b in zip(eventos, eventos[1:]):
        if b - a >= config.REGLA_5S_MAX_BLOQUE_S:
            huecos.append({"inicio": round(a, 3), "fin": round(b, 3), "duracion": round(b - a, 3)})
    return huecos


# ---------------------------------------------------------------------------
# 5. Render: aplica zoom + pan centrado en rostro, frame a frame
# ---------------------------------------------------------------------------
def renderizar_con_zoom(ruta_video: Path, ruta_salida: Path, track_rostro: list, planos: list, picos: list,
                        eventos_overlay: list = None, ruta_subs: Path = None, final: bool = False):
    """Aplica zoom/pan frame a frame y codifica en UNA sola pasada.

    Los frames procesados se mandan crudos por tubería a ffmpeg, que codifica
    con NVENC (GPU) y muxea el audio original en la misma corrida.

    Si se pasan `eventos_overlay` (lista de f6_overlays.planificar_overlays) y/o
    `ruta_subs` (.ass), los overlays y los subtítulos se componen DENTRO de esta
    misma codificación. Así el pipeline pasa de 4 codificaciones en cadena
    (cortar -> retención -> overlays -> subtítulos) a solo 2 (cortar -> esta),
    con menos pérdida de calidad acumulada y menos tiempo.

    Versión anterior: escribía un archivo intermedio con cv2.VideoWriter en
    fourcc "mp4v" (MPEG-4 Part 2, solo software) y después re-codificaba ese
    archivo con libx264 — dos codificaciones por CPU, un temporal pesado en
    disco y la GPU sin tocar. Ahí estaba el CPU al 95% con la GPU al 3%.
    """
    import cv2

    cap = cv2.VideoCapture(str(ruta_video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    w_in = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h_in = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duracion_total = total_frames / fps if fps else 0

    w_out, h_out = config.ANCHO, config.ALTO

    eventos_overlay = eventos_overlay or []
    # los streams de PNG deben durar al menos hasta el fin del último overlay
    # (el conteo de frames puede quedar unas décimas por debajo de la duración
    # del contenedor con la que f6 planificó los eventos)
    dur_stream = max([duracion_total] + [ev["fin"] for ev in eventos_overlay])
    inputs = [
        # entrada 0: frames crudos que le vamos pasando por stdin
        "-f", "rawvideo", "-pix_fmt", "bgr24",
        "-s", f"{w_out}x{h_out}", "-r", f"{fps}",
        "-i", "pipe:0",
        # entrada 1: el video original, solo para tomarle el audio
        "-i", str(ruta_video),
    ]
    for ev in eventos_overlay:
        if ev.get("medio") == "video":
            # Animaciones (ProRes 4444 con alfa): se desplazan en el tiempo con
            # -itsoffset para que empiecen en su momento, en vez de en t=0.
            inputs += ["-itsoffset", f"{ev['ini']:.3f}", "-i", str(ev["archivo"])]
        else:
            # Igual que en f6_overlays.componer_overlays: sin -loop 1 -t el PNG sería
            # un solo frame en t=0 y el fade quedaría congelado casi transparente.
            inputs += ["-loop", "1", "-framerate", str(config.FPS),
                       "-t", f"{dur_stream:.3f}", "-i", str(ev["archivo"])]

    filtro_partes = []
    etiqueta = "0:v"
    for i, ev in enumerate(eventos_overlay):
        idx_input = 2 + i
        dur_fade = 0.15
        if ev.get("medio") == "video":
            # La animación ya trae su propio movimiento y ya está desplazada en
            # el tiempo por -itsoffset; solo se le suaviza la entrada y salida.
            filtro_partes.append(
                f"[{idx_input}:v]format=rgba,setpts=PTS-STARTPTS+{ev['ini']:.3f}/TB,"
                f"fade=t=in:st={ev['ini']:.3f}:d={dur_fade}:alpha=1,"
                f"fade=t=out:st={ev['fin'] - dur_fade:.3f}:d={dur_fade}:alpha=1[ov{i}]"
            )
        else:
            filtro_partes.append(
                f"[{idx_input}:v]format=rgba,fade=t=in:st={ev['ini']:.3f}:d={dur_fade}:alpha=1,"
                f"fade=t=out:st={ev['fin'] - dur_fade:.3f}:d={dur_fade}:alpha=1[ov{i}]"
            )
        filtro_partes.append(
            f"[{etiqueta}][ov{i}]overlay={ev['x']}:{ev['y']}:"
            f"enable='between(t,{ev['ini']:.3f},{ev['fin']:.3f})'[v{i}]"
        )
        etiqueta = f"v{i}"

    # cwd del proceso ffmpeg: el filtro `ass=` no tolera ':' de unidad ni espacios
    # en la ruta (mismo problema documentado en editor.py), así que se corre con
    # cwd en la carpeta del .ass y nombres relativos.
    cwd_proceso = str(ruta_salida.parent)
    if ruta_subs is not None:
        fontsdir_rel = os.path.relpath(config.DIR_FUENTES, start=ruta_salida.parent)
        filtro_partes.append(f"[{etiqueta}]ass={ruta_subs.name}:fontsdir={fontsdir_rel}[vfin]")
        etiqueta = "vfin"

    if filtro_partes:
        mapeo_video = ["-filter_complex", ";".join(filtro_partes), "-map", f"[{etiqueta}]"]
    else:
        mapeo_video = ["-map", "0:v"]

    cmd = [
        "ffmpeg", "-y", *inputs,
        *mapeo_video, "-map", "1:a",
        *config.args_video(final=final),
        # el audio del video cortado ya viene en AAC 192k (f2): copiarlo evita
        # otra generación de compresión de audio — f5 lo recodifica al mezclar.
        "-c:a", "copy", "-shortest",
        str(ruta_salida.name),
    ]
    extras = []
    if eventos_overlay:
        extras.append(f"{len(eventos_overlay)} overlays")
    if ruta_subs is not None:
        extras.append("subtítulos")
    _log(f"  codificador: {'NVENC (GPU)' if config.hay_nvenc() and config.USAR_NVENC else 'libx264 (CPU)'}"
         + (f" + {' + '.join(extras)} en la misma pasada" if extras else ""))

    # stdout/stderr van a un archivo, NO a un pipe: si nadie lee un pipe,
    # ffmpeg se bloquea al llenarse el buffer del sistema operativo.
    log_ffmpeg = ruta_salida.with_suffix(".ffmpeg.log")
    tiempos_track = np.array([p["t"] for p in track_rostro]) if track_rostro else np.array([0.0])
    cx_track = np.array([p["cx"] for p in track_rostro]) if track_rostro else np.array([0.5])
    cy_track = np.array([p["cy"] for p in track_rostro]) if track_rostro else np.array([0.4])

    aspecto_salida = w_out / h_out

    # ----- Diseño de loop (sección 4.5 del plan) -----------------------------
    # El rewatch es la señal más fuerte del algoritmo, y hasta ahora esto era
    # solo una NOTA de texto en el plan JSON: no había ninguna lógica.
    # Implementación: durante el último tramo el encuadre (zoom + paneo) vuelve
    # suavemente al del primer frame, así el último frame empalma con el primero
    # y el video "engancha" consigo mismo al reiniciarse. La otra mitad del loop
    # (repetir el hook en el cierre) la pone f6_overlays en la tarjeta de CTA.
    hacer_loop = (config.LOOP_ACTIVO and duracion_total > config.LOOP_DURACION_S * 3)
    if hacer_loop:
        cx_ini = float(np.interp(0.0, tiempos_track, cx_track))
        cy_ini = float(np.interp(0.0, tiempos_track, cy_track))
        zoom_ini = calcular_zoom_en_t(0.0, planos, picos)
        t_loop = duracion_total - config.LOOP_DURACION_S
        _log(f"  loop: el encuadre vuelve al del primer frame desde {t_loop:.1f}s "
             f"(zoom {zoom_ini:.3f}, centro {cx_ini:.3f}/{cy_ini:.3f})")

    with open(log_ffmpeg, "wb") as flog:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=flog, stderr=flog, cwd=cwd_proceso)
        idx = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                t = idx / fps

                cx, cy, zoom = encuadre_en_t(
                    t, tiempos_track, cx_track, cy_track, planos, picos,
                    hacer_loop, t_loop if hacer_loop else None,
                    cx_ini if hacer_loop else None, cy_ini if hacer_loop else None,
                    zoom_ini if hacer_loop else None,
                )

                # recorte centrado en rostro, con relación de aspecto de salida (9:16)
                h_crop = h_in / zoom
                w_crop = h_crop * aspecto_salida
                if w_crop > w_in:
                    w_crop = w_in
                    h_crop = w_crop / aspecto_salida

                x0 = np.clip(cx * w_in - w_crop / 2, 0, w_in - w_crop)
                y0 = np.clip(cy * h_in - h_crop / 2, 0, h_in - h_crop)

                recorte = frame[int(y0):int(y0 + h_crop), int(x0):int(x0 + w_crop)]
                salida = cv2.resize(recorte, (w_out, h_out), interpolation=cv2.INTER_LINEAR)
                proc.stdin.write(salida.tobytes())

                idx += 1
                if idx % 150 == 0:
                    _log(f"  render: {idx}/{total_frames} frames")
        except BrokenPipeError:
            # ffmpeg murió antes de tiempo; el motivo queda en el log
            pass
        finally:
            cap.release()
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
            proc.wait()

    if proc.returncode != 0:
        cola = log_ffmpeg.read_text(encoding="utf-8", errors="replace")[-4000:]
        print(cola, file=sys.stderr)
        raise RuntimeError(f"ffmpeg falló al codificar la Fase 3 (ver {log_ffmpeg})")

    log_ffmpeg.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description="Capa de retención: face tracking, punch-ins, zoom progresivo")
    parser.add_argument("video", type=str)
    parser.add_argument("transcripcion", type=str, help="JSON de f2_cortar.py (usa intervalos_conservados_original)")
    parser.add_argument("--salida", type=str, default=None)
    parser.add_argument("--sin-render", action="store_true", help="Solo analiza y genera el plan JSON, no renderiza video")
    parser.add_argument("--solo-render", type=str, default=None, metavar="PLAN_JSON",
                        help="Salta el análisis y renderiza usando un plan JSON ya generado (--sin-render previo)")
    parser.add_argument("--overlays", type=str, default=None, metavar="EVENTOS_JSON",
                        help="JSON de eventos de f6_overlays --solo-planificar: se componen en la misma codificación")
    parser.add_argument("--subs", type=str, default=None, metavar="ASS",
                        help="Archivo .ass: los subtítulos se queman en la misma codificación")
    parser.add_argument("--final", action="store_true",
                        help="Codificar con calidad de publicación (CQ final) en vez de intermedia")
    parser.add_argument("--presentador", type=str, default=None,
                        choices=sorted(config.PRESENTADORES),
                        help="Perfil de retención (suavizado de rostro y umbral de punch-ins)")
    args = parser.parse_args()

    global PERFIL
    PERFIL = config.perfil(args.presentador)

    ruta_video = Path(args.video)
    ruta_salida = Path(args.salida) if args.salida else ruta_video.with_name(ruta_video.stem + "_retencion.mp4")

    if args.solo_render:
        plan = json.loads(Path(args.solo_render).read_text(encoding="utf-8"))
        planos, picos, track_rostro = plan["planos"], plan["picos_energia"], plan["track_rostro"]
    else:
        ruta_transcripcion = Path(args.transcripcion)
        datos = json.loads(ruta_transcripcion.read_text(encoding="utf-8"))

        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", str(ruta_video)]
        duracion_total = float(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip())

        intervalos_originales = datos.get("intervalos_conservados_original", [])
        planos = construir_planos(duracion_total, intervalos_originales)

        _log("Analizando picos de energía de audio...")
        picos = detectar_picos_energia(ruta_video)

        _log("Rastreando rostro...")
        track_rostro = rastrear_rostro(ruta_video)

        huecos = detectar_huecos_regla_5s(duracion_total, planos, picos)
        if huecos:
            _log(f"\nADVERTENCIA regla de 5s: {len(huecos)} hueco(s) sin cambio visual, quedan para Fase 5:")
            for h in huecos:
                _log(f"  [{h['inicio']:.1f}s - {h['fin']:.1f}s] ({h['duracion']:.1f}s)")
        else:
            _log("\nRegla de 5s: OK, ningún hueco detectado.")

        nota_loop = None
        if planos:
            if config.LOOP_ACTIVO:
                nota_loop = (
                    f"Loop ACTIVO: los últimos {config.LOOP_DURACION_S:.1f}s devuelven el encuadre "
                    f"(zoom + paneo) al del primer frame, y la tarjeta de CTA cierra repitiendo el "
                    f"hook. Así el final empalma con el arranque y el rebobinado no se nota."
                )
            else:
                nota_loop = "Loop desactivado (config.LOOP_ACTIVO = False)."
            _log(f"\n{nota_loop}")

        plan_json = ruta_salida.with_suffix(".plan.json")
        plan_json.write_text(json.dumps({
            "planos": planos,
            "picos_energia": picos,
            "track_rostro": track_rostro,
            "huecos_regla_5s": huecos,
            "nota_loop": nota_loop,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        _log(f"\nPlan de retención guardado: {plan_json}")

    if not args.sin_render:
        eventos_overlay = None
        if args.overlays:
            eventos_overlay = json.loads(Path(args.overlays).read_text(encoding="utf-8"))
        ruta_subs = Path(args.subs) if args.subs else None

        _log("\nRenderizando video con zoom/face-tracking (puede tardar varios minutos)...")
        renderizar_con_zoom(ruta_video, ruta_salida, track_rostro, planos, picos,
                            eventos_overlay=eventos_overlay, ruta_subs=ruta_subs, final=args.final)
        _log(f"Video con retención: {ruta_salida}")


if __name__ == "__main__":
    main()
