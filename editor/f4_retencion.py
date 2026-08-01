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
    espaciado_min_s = config.PUNCH_IN_SEPARACION_MIN_S
    candidatos = []
    ultimo_t = -999
    for t, valor in zip(tiempos, rms):
        if valor >= umbral and (t - ultimo_t) >= espaciado_min_s:
            candidatos.append({"t": round(float(t), 3), "energia": round(float(valor), 4)})
            ultimo_t = t

    # Tope duro por duración. El espaciado mínimo solo pone un piso; en un video
    # con la voz pareja el percentil sigue disparando en cuanto pasa ese piso.
    # Se conservan los de MÁS energía, que son los énfasis de verdad, y se
    # devuelven en orden de tiempo.
    duracion_s = float(tiempos[-1]) if len(tiempos) else 0.0
    tope = max(1, int(round(duracion_s / 60 * config.PUNCH_IN_MAX_POR_MINUTO)))
    picos = sorted(candidatos, key=lambda p: -p["energia"])[:tope]
    picos.sort(key=lambda p: p["t"])

    if len(candidatos) > len(picos):
        _log(f"Picos de énfasis: {len(candidatos)} candidatos -> {len(picos)} punch-ins "
             f"(tope {config.PUNCH_IN_MAX_POR_MINUTO}/min sobre {duracion_s:.1f}s)")
    else:
        _log(f"Picos de énfasis detectados: {len(picos)}")
    return picos


# ---------------------------------------------------------------------------
# 3+4. Construir línea de tiempo de zoom + detectar huecos (regla de 5s)
# ---------------------------------------------------------------------------
def construir_planos(duracion_total: float, tomas_s: list = None) -> list:
    """Un 'plano' = un tramo con encuadre propio, sobre el que corre la rampa de
    zoom progresivo.

    Antes se construía uno por cada intervalo conservado de f2_cortar, es decir
    **uno por cada corte de silencio**. Eso hacía que el zoom volviera a 1.00 y
    empezara a subir otra vez en cada corte: en el guion 7 salieron 8 planos en
    24.8s, uno de ellos de 0.15s (una rampa de 1.00 a 1.08 en seis fotogramas,
    o sea un tirón). Sumado a los punch-ins, ese era el "cambia los zooms de
    manera desproporcionada a cada rato".

    Un jump cut de silencio NO es un cambio de plano: la cámara no se movió, se
    quitó una pausa. Que el encuadre siga su curso a través del corte es
    justamente lo que hace que el jump cut se lea como ritmo y no como error.

    Ahora un plano solo empieza donde hay un cambio de encuadre DE VERDAD: los
    tiempos de `tomas_s`, que son los empalmes entre grabaciones distintas
    (José graba el plano abierto y el cerrado por separado). Sin eso, todo el
    video es un solo plano y el zoom hace un único recorrido lento.
    """
    limites = [0.0]
    for t in sorted(tomas_s or []):
        if 0.2 < t < duracion_total - 0.2 and t - limites[-1] > 0.2:
            limites.append(round(float(t), 3))
    limites.append(round(duracion_total, 3))
    return [{"inicio": a, "fin": b} for a, b in zip(limites, limites[1:]) if b > a]


def _suave(u: float) -> float:
    """Smoothstep. Un movimiento de cámara lineal se ve mecánico: arranca y
    frena de golpe. Es la misma curva que usa f7_animaciones."""
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def calcular_zoom_en_t(t: float, planos: list, picos: list, cerrados: list = None) -> float:
    """Zoom en el segundo `t`: rampa del plano + tramos cerrados + punch-ins.

    Las tres capas se combinan tomando el máximo, no sumando: dos efectos que
    coinciden dan el más fuerte de los dos, nunca un acercamiento del 40%.
    """
    zoom = config.ZOOM_PROGRESIVO_INICIO
    for plano in planos:
        if plano["inicio"] <= t <= plano["fin"]:
            dur = plano["fin"] - plano["inicio"]
            progreso = (t - plano["inicio"]) / dur if dur > 0 else 0
            zoom = config.ZOOM_PROGRESIVO_INICIO + progreso * (
                config.ZOOM_PROGRESIVO_FIN - config.ZOOM_PROGRESIVO_INICIO
            )
            break

    # Plano cerrado pedido por el guion: entra, SE QUEDA y sale. La diferencia
    # con un punch-in no es de tamaño sino de intención — el punch-in subraya
    # una palabra, esto sostiene un tramo entero más íntimo.
    trans = config.ZOOM_TRANSICION_S
    for c in (cerrados or []):
        ini, fin = c["ini"], c["fin"]
        if not (ini - trans <= t <= fin + trans):
            continue
        if t < ini:
            factor = _suave((t - (ini - trans)) / trans)
        elif t > fin:
            factor = 1 - _suave((t - fin) / trans)
        else:
            factor = 1.0
        objetivo = c.get("zoom", config.ZOOM_PLANO_CERRADO)
        zoom = max(zoom, config.ZOOM_PROGRESIVO_INICIO
                   + factor * (objetivo - config.ZOOM_PROGRESIVO_INICIO))

    # Punch-in: entra rápido, aguanta y sale suave. Dos versiones anteriores y
    # por qué ninguna servía:
    #   · rampa triangular LINEAL de 0.3s: 9 fotogramas de ida y 9 de vuelta,
    #     que se percibe como un golpe de imagen, no como cámara.
    #   · la misma rampa alargada a 1.2s: el pico caía a la mitad, o sea 0.6s
    #     después de la palabra marcada, y el acento aterrizaba sobre la
    #     siguiente.
    # Ahora el énfasis llega en PUNCH_IN_ATAQUE_S y se sostiene: el acento cae
    # donde el guion lo pide.
    dur_punch = config.PUNCH_IN_DURACION_S
    ataque = min(config.PUNCH_IN_ATAQUE_S, dur_punch * 0.4)
    salida = dur_punch * config.PUNCH_IN_SALIDA_PCT
    inicio_salida = dur_punch - salida
    for pico in picos:
        dt = t - pico["t"]
        if not (0 <= dt <= dur_punch):
            continue
        if dt < ataque:
            factor = _suave(dt / ataque)
        elif dt > inicio_salida:
            factor = 1 - _suave((dt - inicio_salida) / salida)
        else:
            factor = 1.0
        zoom = max(zoom, config.ZOOM_PROGRESIVO_INICIO
                   + factor * (config.PUNCH_IN_ZOOM - config.ZOOM_PROGRESIVO_INICIO))

    return round(zoom, 4)


def encuadre_en_t(t: float, tiempos_track: np.ndarray, cx_track: np.ndarray, cy_track: np.ndarray,
                   planos: list, picos: list, hacer_loop: bool = False, t_loop: float = None,
                   cx_ini: float = None, cy_ini: float = None, zoom_ini: float = None,
                   cerrados: list = None):
    """(cx, cy, zoom) del encuadre en el segundo t: interpolación del track de
    rostro + calcular_zoom_en_t(), con el blend de loop de los últimos
    LOOP_DURACION_S si aplica. La usa tanto el render real
    (renderizar_con_zoom) como el preview del editor visual (f11_servidor) —
    una sola implementación para que no puedan divergir."""
    cx = float(np.interp(t, tiempos_track, cx_track))
    cy = float(np.interp(t, tiempos_track, cy_track))
    zoom = calcular_zoom_en_t(t, planos, picos, cerrados)

    if hacer_loop and t_loop is not None and t >= t_loop:
        u = min(1.0, (t - t_loop) / config.LOOP_DURACION_S)
        s = u * u * (3 - 2 * u)
        cx += (cx_ini - cx) * s
        cy += (cy_ini - cy) * s
        zoom += (zoom_ini - zoom) * s

    return cx, cy, zoom


def detectar_huecos_regla_5s(duracion_total: float, planos: list, picos: list,
                             jump_cuts: list = None) -> list:
    """Eventos de 'cambio visual' = límites de plano + jump cuts + punch-ins.
    Cualquier tramo >= REGLA_5S_MAX_BLOQUE_S sin evento queda marcado como hueco.

    Los jump cuts van aparte desde que los planos dejaron de construirse a partir
    de ellos (ver `construir_planos`): el zoom ya no se reinicia en cada corte de
    silencio, pero la pantalla SÍ cambia ahí, así que para esta regla siguen
    contando igual que antes."""
    eventos = {0.0, duracion_total}
    for p in planos:
        eventos.add(p["inicio"])
        eventos.add(p["fin"])
    for t in (jump_cuts or []):
        eventos.add(t)
    for pico in picos:
        eventos.add(pico["t"])

    eventos = sorted(eventos)
    huecos = []
    for a, b in zip(eventos, eventos[1:]):
        if b - a >= config.REGLA_5S_MAX_BLOQUE_S:
            huecos.append({"inicio": round(a, 3), "fin": round(b, 3), "duracion": round(b - a, 3)})
    return huecos


# ---------------------------------------------------------------------------
# 4.9 B-roll DETRÁS de José (modo "recorte")
# ---------------------------------------------------------------------------
# El B-roll ocupa una franja de arriba (70% del alto) en vez de tapar el cuadro,
# y José se compone ENCIMA recortado de su cuarto. Son tres capas apiladas:
#
#     1. el video, con el cuarto atenuado bajo la franja   <- en el bucle Python
#     2. el B-roll, con el borde de abajo desvanecido      <- .mov con alfa
#     3. José recortado, con el mismo zoom que la capa 1    <- .mov con alfa (RVM)
#
# Las capas 2 y 3 se preparan como archivos antes de armar el comando de ffmpeg
# y entran como dos overlays normales. Así el resto del filtro no cambia y los
# índices de entrada siguen siendo `2 + i`.
def _preparar_recorte(eventos: list, ruta_video: Path, dir_trabajo: Path,
                      w_out: int, h_out: int, fps: float, encuadrar) -> tuple[list, list]:
    """Cambia cada B-roll en modo recorte por sus dos capas ya renderizadas.

    Devuelve (eventos, ventanas). `ventanas` es lo que el bucle de render
    necesita para atenuar el cuarto debajo de cada B-roll.
    """
    if not any(ev.get("modo_broll") == "recorte" for ev in eventos):
        return eventos, []

    import f17_matte

    alto_franja = int(h_out * config.BROLL_RECORTE_ALTO_PCT) // 2 * 2
    degradado = int(config.BROLL_RECORTE_DEGRADADO_PX * (h_out / config.ALTO))
    dir_tmp = dir_trabajo / "_tmp_matte"
    dir_tmp.mkdir(parents=True, exist_ok=True)
    mascara = f17_matte.mascara_degradado(
        w_out, alto_franja, degradado, dir_tmp / f"degradado_{w_out}x{alto_franja}.png")

    # El perfil de opacidad que usa la atenuación del fondo es EL MISMO archivo
    # que el alfa del B-roll: si fueran dos curvas distintas se vería un segundo
    # borde donde una termina y la otra no.
    from PIL import Image
    perfil = (np.asarray(Image.open(mascara).convert("L"), dtype=np.float32)[:, :1] / 255.0)
    perfil = perfil[:, :, None]

    matte = None
    salida, ventanas = [], []
    for i, ev in enumerate(eventos):
        if ev.get("modo_broll") != "recorte":
            salida.append(ev)
            continue

        dur = float(ev["fin"]) - float(ev["ini"])
        # La resolución va en el nombre: sin ella, un --preview (media
        # resolución) reutilizaría las capas cacheadas del render final y las
        # compondría al doble de tamaño, o al revés.
        base = f"recorte_{i}_{int(float(ev['ini']) * 1000)}_{w_out}x{h_out}"

        # Capa 2: el clip llevado a la franja, con el borde inferior desvanecido.
        clip = dir_tmp / f"{base}_broll.mov"
        if not clip.exists():
            cmd = ["ffmpeg", "-y", "-v", "error"]
            r_ini = float(ev.get("recorte_inicio") or 0.0)
            if r_ini > 0:
                cmd += ["-ss", f"{r_ini:.3f}"]
            cmd += [
                "-i", str(ev["archivo"]), "-loop", "1", "-i", str(mascara),
                "-filter_complex",
                f"[0:v]scale={w_out}:{alto_franja}:force_original_aspect_ratio=increase,"
                f"crop={w_out}:{alto_franja},setpts=PTS-STARTPTS,format=gbrp[br];"
                f"[1:v]format=gray,scale={w_out}:{alto_franja}[m];"
                f"[br][m]alphamerge[out]",
                "-map", "[out]", "-t", f"{dur:.3f}",
                "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
                str(clip),
            ]
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                               errors="replace")
            if r.returncode != 0:
                _log(f"AVISO: no se pudo preparar el B-roll recortado de "
                     f"{ev['ini']:.1f}s ({r.stderr[-300:]}) — se deja a pantalla completa.")
                salida.append({**ev, "broll_fullscreen": True, "modo_broll": "completo"})
                continue

        # Capa 3: José recortado, con el encuadre de la capa 1.
        capa_jose = dir_tmp / f"{base}_persona.mov"
        if not capa_jose.exists():
            try:
                matte = matte or f17_matte.Matte()
                capa_jose = f17_matte.render_ventana(
                    ruta_video, float(ev["ini"]), float(ev["fin"]), capa_jose,
                    w_out, h_out, fps, encuadrar=encuadrar, matte=matte)
            except Exception as e:
                _log(f"AVISO: falló el recorte de la persona ({e}). El B-roll de "
                     f"{ev['ini']:.1f}s se compone SIN recortar a José por delante.")
                capa_jose = None

        # `recorte_inicio/fin` ya se aplicaron al preparar el clip: dejarlos
        # haría que ffmpeg los aplicara una segunda vez sobre el archivo nuevo.
        ev_broll = {k: v for k, v in ev.items()
                    if k not in ("recorte_inicio", "recorte_fin")}
        ev_broll.update({"archivo": str(clip), "tipo": "broll-recorte",
                         "medio": "video", "broll_fullscreen": False, "x": 0, "y": 0})
        salida.append(ev_broll)
        if capa_jose is not None:
            # Va DESPUÉS del B-roll en la lista, que es lo que la deja encima en
            # el filter_complex.
            salida.append({"tipo": "matte-persona", "medio": "video",
                           "archivo": str(capa_jose), "x": 0, "y": 0,
                           "ini": ev["ini"], "fin": ev["fin"], "asset": "matte"})
        ventanas.append({"ini": float(ev["ini"]), "fin": float(ev["fin"]),
                         "alto": alto_franja, "perfil": perfil})

    return salida, ventanas


def _atenuar_franja(frame, t: float, ventana: dict):
    """Apaga el cuarto bajo la franja del B-roll, sobre el frame ya encuadrado.

    Se desvanece con la misma curva que el alfa del B-roll (de ahí el `perfil`
    compartido) y con la misma rampa de entrada y salida que su fade, para que
    aparezca y se vaya junto con él y no por su cuenta.
    """
    import cv2

    ini, fin = ventana["ini"], ventana["fin"]
    if not (ini <= t < fin):
        return
    fade = config.BROLL_FADE_S
    k = 1.0 if fade <= 0 else min(1.0, (t - ini) / fade, (fin - t) / fade)
    if k <= 0:
        return

    alto = ventana["alto"]
    franja = frame[:alto].astype(np.float32)
    b = max(1, int(config.BROLL_RECORTE_FONDO_BLUR))
    ajustada = cv2.blur(frame[:alto], (b, b)).astype(np.float32)
    # saturación y brillo como los aplicaría `eq` de ffmpeg (luma BT.601 sobre
    # BGR, que es el orden en que cv2 entrega los píxeles)
    luma = (ajustada[:, :, 0] * 0.114 + ajustada[:, :, 1] * 0.587
            + ajustada[:, :, 2] * 0.299)[:, :, None]
    ajustada = luma + (ajustada - luma) * config.BROLL_RECORTE_FONDO_SATURACION
    ajustada += config.BROLL_RECORTE_FONDO_BRILLO * 255.0
    np.clip(ajustada, 0, 255, out=ajustada)

    a = ventana["perfil"] * k
    frame[:alto] = (franja * (1.0 - a) + ajustada * a).astype(np.uint8)


# ---------------------------------------------------------------------------
# 5. Render: aplica zoom + pan centrado en rostro, frame a frame
# ---------------------------------------------------------------------------
def renderizar_con_zoom(ruta_video: Path, ruta_salida: Path, track_rostro: list, planos: list, picos: list,
                        eventos_overlay: list = None, ruta_subs: Path = None, final: bool = False,
                        cerrados: list = None, escala: float = 1.0, pip_anim_default: dict = None):
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

    # `escala` < 1 es el modo previsualización: se compone EXACTAMENTE igual
    # (mismos overlays, mismas posiciones, mismos subtítulos) pero a media
    # resolución. El grueso del tiempo de render es esta función generando
    # frames y pasándolos crudos por tubería —a 1080x1920 son 6 MB por frame—,
    # así que bajar la resolución es lo único que lo mueve de verdad.
    # Los píxeles se dividen por 4; la composición no cambia.
    w_out = int(config.ANCHO * escala) // 2 * 2      # par: NVENC no acepta impares
    h_out = int(config.ALTO * escala) // 2 * 2

    eventos_overlay = eventos_overlay or []
    # Un video (B-roll o PiP) no puede durar en pantalla más de lo que el
    # tramo elegido del archivo fuente permite (bloque 4 del plan de mejoras:
    # modal para elegir el tramo de un clip). Sin este tope, si el hueco de la
    # línea de tiempo quedó más largo que el tramo, ffmpeg se queda sin frames
    # y `overlay` (con su `eof_action` por defecto, `repeat`) congela el
    # último cuadro — se ve como un error, no como una decisión. El editor ya
    # frena al estirar el hueco, pero esto cubre también un ajuste.eventos/
    # broll.json tocado a mano por fuera del editor.
    eventos_overlay = [
        {**ev, "fin": min(ev["fin"], ev["ini"] + (ev["recorte_fin"] - ev["recorte_inicio"]))}
        if ev.get("medio") == "video" and ev.get("recorte_inicio") is not None
           and ev.get("recorte_fin") is not None
        else ev
        for ev in eventos_overlay
    ]
    # ----- Encuadre -----------------------------------------------------------
    # Se resuelve ACÁ ARRIBA, y no junto al bucle de render como antes, porque el
    # modo "recorte" necesita generar la capa de José antes de armar el comando
    # de ffmpeg (es una entrada más). Esa capa tiene que llevar exactamente el
    # mismo zoom y paneo que el fondo: si se calculara aparte, José saldría
    # desplazado respecto de sí mismo.
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
    t_loop = cx_ini = cy_ini = zoom_ini = None
    if hacer_loop:
        cx_ini = float(np.interp(0.0, tiempos_track, cx_track))
        cy_ini = float(np.interp(0.0, tiempos_track, cy_track))
        zoom_ini = calcular_zoom_en_t(0.0, planos, picos, cerrados)
        t_loop = duracion_total - config.LOOP_DURACION_S
        _log(f"  loop: el encuadre vuelve al del primer frame desde {t_loop:.1f}s "
             f"(zoom {zoom_ini:.3f}, centro {cx_ini:.3f}/{cy_ini:.3f})")

    def encuadrar(frame, t):
        """El frame con el zoom y el paneo que le tocan en el segundo `t`."""
        cx, cy, zoom = encuadre_en_t(
            t, tiempos_track, cx_track, cy_track, planos, picos,
            hacer_loop, t_loop, cx_ini, cy_ini, zoom_ini, cerrados=cerrados,
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
        return cv2.resize(recorte, (w_out, h_out), interpolation=cv2.INTER_LINEAR)

    # ----- B-roll DETRÁS de José (modo "recorte") -----------------------------
    eventos_overlay, ventanas_recorte = _preparar_recorte(
        eventos_overlay, ruta_video, ruta_salida.parent, w_out, h_out, fps, encuadrar)

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
            # Si se eligió un tramo del archivo (bloque 4), `-ss` ANTES del
            # -i arranca la LECTURA ahí — sin esto, el clip siempre se leía
            # desde su segundo 0 sin importar qué tramo se hubiera elegido.
            recorte_inicio = float(ev.get("recorte_inicio") or 0.0)
            semilla = ["-ss", f"{recorte_inicio:.3f}"] if recorte_inicio > 0 else []
            inputs += semilla + ["-itsoffset", f"{ev['ini']:.3f}", "-i", str(ev["archivo"])]
        else:
            # Igual que en f6_overlays.componer_overlays: sin -loop 1 -t el PNG sería
            # un solo frame en t=0 y el fade quedaría congelado casi transparente.
            inputs += ["-loop", "1", "-framerate", str(config.FPS),
                       "-t", f"{dur_stream:.3f}", "-i", str(ev["archivo"])]

    filtro_partes = []
    etiqueta = "0:v"
    # En previsualización el lienzo es más chico, así que los overlays —que
    # vienen medidos en píxeles de 1080x1920— hay que encogerlos con él y mover
    # su posición en la misma proporción. Sin esto saldrían al doble de tamaño
    # y fuera de sitio, y el preview no valdría para decidir nada.
    reducir = f"scale=iw*{escala:.4f}:ih*{escala:.4f}," if escala != 1.0 else ""
    # Tamaño de la tarjeta de inserto, borde incluido: es a lo que
    # f6_overlays.render_pip_producto lleva una foto, y un PiP de video tiene
    # que medir lo mismo o no se lee como el mismo elemento.
    w_tarjeta_pip = config.INSERTO_ANCHO + config.INSERTO_BORDE * 2
    h_tarjeta_pip = config.INSERTO_ALTO + config.INSERTO_BORDE * 2
    for i, ev in enumerate(eventos_overlay):
        idx_input = 2 + i
        ev_x, ev_y = int(ev["x"] * escala), int(ev["y"] * escala)
        if ev.get("broll_fullscreen"):
            # B-roll a pantalla completa: escala el clip al lienzo (cubre y
            # recorta al centro, sin barras), con fade más largo y suave.
            # format=rgba le agrega alfa al clip opaco para que el fade por
            # alpha funcione — no es por transparencia del contenido.
            dur_fade = config.BROLL_FADE_S
            filtro_partes.append(
                f"[{idx_input}:v]scale={w_out}:{h_out}:"
                f"force_original_aspect_ratio=increase,"
                f"crop={w_out}:{h_out},"
                f"setpts=PTS-STARTPTS+{ev['ini']:.3f}/TB,"
                f"format=rgba,"
                f"fade=t=in:st={ev['ini']:.3f}:d={dur_fade}:alpha=1,"
                f"fade=t=out:st={ev['fin'] - dur_fade:.3f}:d={dur_fade}:alpha=1[ov{i}]"
            )
        elif ev.get("tipo") == "matte-persona":
            # La capa de José NO lleva fade. Debajo está el mismo José, en el
            # mismo sitio y con el mismo encuadre, así que entrar y salir de
            # golpe no se ve. Con fade se lo vería medio transparente sobre el
            # B-roll mientras dura la transición, que sí se nota.
            # Tampoco lleva `reducir`: _preparar_recorte ya la generó a la
            # resolución de salida, encogerla otra vez la dejaría a la mitad.
            filtro_partes.append(
                f"[{idx_input}:v]format=rgba,"
                f"setpts=PTS-STARTPTS+{ev['ini']:.3f}/TB[ov{i}]"
            )
        elif ev.get("tipo") == "broll-recorte":
            # Mismo fade que usa la atenuación del cuarto en el bucle de Python:
            # con dos duraciones distintas, el fondo se apagaría antes o después
            # que el clip y se vería el desfase.
            dur_fade = config.BROLL_FADE_S
            filtro_partes.append(
                f"[{idx_input}:v]format=rgba,setpts=PTS-STARTPTS+{ev['ini']:.3f}/TB,"
                f"fade=t=in:st={ev['ini']:.3f}:d={dur_fade}:alpha=1,"
                f"fade=t=out:st={ev['fin'] - dur_fade:.3f}:d={dur_fade}:alpha=1[ov{i}]"
            )
        elif ev.get("medio") == "video":
            dur_fade = 0.15
            if ev.get("tipo") == "pip-producto":
                # Un PiP de video es una TARJETA, del mismo tamaño que la de una
                # foto. Antes se componía a su resolución nativa: un clip de Flow
                # de 720x1280 puesto como PiP tapaba media pantalla. Se lleva al
                # tamaño de tarjeta cubriendo y recortando al centro, que es lo
                # mismo que hace render_pip_producto con una foto.
                w_c = max(2, int(w_tarjeta_pip * escala) // 2 * 2)
                h_c = max(2, int(h_tarjeta_pip * escala) // 2 * 2)
                ajuste = (f"scale={w_c}:{h_c}:force_original_aspect_ratio=increase,"
                          f"crop={w_c}:{h_c},")
            else:
                # Animaciones, hook y CTA ocupan el cuadro entero a propósito.
                ajuste = reducir
            # La animación ya trae su propio movimiento y ya está desplazada en
            # el tiempo por -itsoffset; solo se le suaviza la entrada y salida.
            filtro_partes.append(
                f"[{idx_input}:v]{ajuste}format=rgba,setpts=PTS-STARTPTS+{ev['ini']:.3f}/TB,"
                f"fade=t=in:st={ev['ini']:.3f}:d={dur_fade}:alpha=1,"
                f"fade=t=out:st={ev['fin'] - dur_fade:.3f}:d={dur_fade}:alpha=1[ov{i}]"
            )
        else:
            dur_fade = 0.15
            filtro_partes.append(
                f"[{idx_input}:v]{reducir}format=rgba,fade=t=in:st={ev['ini']:.3f}:d={dur_fade}:alpha=1,"
                f"fade=t=out:st={ev['fin'] - dur_fade:.3f}:d={dur_fade}:alpha=1[ov{i}]"
            )
        # Animación de entrada/salida del PiP: cambia SOLO la posición durante
        # las ventanas de entrada y salida (ver f4b_pip_anim). Fuera de ellas la
        # expresión vale la posición base, así que un PiP con "fundido" (lo de
        # siempre) sale idéntico. No se anima el fondo (B-roll a pantalla
        # completa, matte de José, recorte de B-roll): esos tienen que quedarse
        # quietos o se despega el plano.
        pos = f"{ev_x}:{ev_y}"
        if not (ev.get("broll_fullscreen") or
                ev.get("tipo") in ("matte-persona", "broll-recorte")):
            import f4b_pip_anim
            defec = pip_anim_default or {}
            a_in = ev.get("anim_entrada") or defec.get("entrada") or "fundido"
            a_out = ev.get("anim_salida") or defec.get("salida") or "fundido"
            a_k = ev.get("anim_intensidad") or defec.get("intensidad") or 1.0
            x_expr, y_expr = f4b_pip_anim.expr_posicion(
                ev_x, ev_y, ev["ini"], ev["fin"], a_in, a_out, a_k)
            if x_expr:
                pos = f"x='{x_expr}':y='{y_expr}'"
        filtro_partes.append(
            f"[{etiqueta}][ov{i}]overlay={pos}:"
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

    with open(log_ffmpeg, "wb") as flog:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=flog, stderr=flog, cwd=cwd_proceso)
        idx = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                t = idx / fps

                salida = encuadrar(frame, t)
                # El cuarto que queda DEBAJO del B-roll se atenúa acá y no en
                # ffmpeg: acá el frame ya está encuadrado, así que la franja cae
                # siempre donde debe. Sin esto el B-roll sale lavado — la pared
                # clara y el producto claro se confunden.
                for v in ventanas_recorte:
                    _atenuar_franja(salida, t, v)
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
    parser.add_argument("--escala", type=float, default=1.0, metavar="F",
                        help="Factor de resolución del render. 0.5 = previsualización a media "
                             "resolución: misma composición exacta (mismos overlays, mismas "
                             "posiciones, mismos subtítulos), la cuarta parte de los píxeles")
    parser.add_argument("--encuadre", type=str, default=None, metavar="JSON",
                        help="Plan de encuadre del guion (guion.encuadre.json de f13_guion): "
                             "punch-ins y tramos de plano cerrado marcados en el panel. "
                             "Cuando está, manda sobre los picos de energía del audio")
    parser.add_argument("--pip-anim-json", type=str, default=None, metavar="JSON",
                        help="ajustes.pip_anim.json del editor visual: animación de entrada "
                             "y salida por defecto de los PiP (y su intensidad). Cada evento "
                             "puede además traer sus propios campos anim_entrada/anim_salida")
    args = parser.parse_args()

    global PERFIL
    PERFIL = config.perfil(args.presentador)

    ruta_video = Path(args.video)
    ruta_salida = Path(args.salida) if args.salida else ruta_video.with_name(ruta_video.stem + "_retencion.mp4")

    encuadre_guion = {}
    if args.encuadre:
        encuadre_guion = json.loads(Path(args.encuadre).read_text(encoding="utf-8"))

    if args.solo_render:
        plan = json.loads(Path(args.solo_render).read_text(encoding="utf-8"))
        planos, picos, track_rostro = plan["planos"], plan["picos_energia"], plan["track_rostro"]
        # El --encuadre recién calculado manda sobre el que quedó guardado en el
        # plan: con --reaplicar el plan es de una corrida anterior y puede ser
        # de antes de tocar el guion.
        # `in` y no `or`: una lista VACÍA es una orden ("este video no lleva
        # acercamientos"), no un dato ausente. Con `or`, borrar todos los
        # punch-ins o todos los planos cerrados en el editor no hacía nada —
        # volvían los automáticos y el render no coincidía con la vista previa.
        cerrados = (encuadre_guion["planos_cerrados"]
                    if "planos_cerrados" in encuadre_guion
                    else plan.get("planos_cerrados", []))
        if "punch_ins" in encuadre_guion:
            picos = [{"t": float(p["t"]), "energia": 1.0, "razon": p.get("razon", "guion")}
                     for p in encuadre_guion["punch_ins"]]
    else:
        ruta_transcripcion = Path(args.transcripcion)
        datos = json.loads(ruta_transcripcion.read_text(encoding="utf-8"))

        cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=noprint_wrappers=1:nokey=1", str(ruta_video)]
        duracion_total = float(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout.strip())

        # `tomas_s` solo existe si se grabaron varios planos reales y editor.py
        # los unió. Sin él, todo el video es un plano y el zoom hace un solo
        # recorrido — que es justo lo que hay que hacer con una toma continua.
        tomas_s = datos.get("tomas_s", [])
        planos = construir_planos(duracion_total, tomas_s)
        if tomas_s:
            detalle = ", ".join("{:.1f}-{:.1f}s".format(p["inicio"], p["fin"]) for p in planos)
            _log(f"Planos reales (empalmes entre grabaciones): {len(planos)} -> {detalle}")

        # Los jump cuts siguen contando como cambio visual para la regla de 5s,
        # aunque ya no reinicien el zoom: la pantalla SÍ cambia en ellos.
        intervalos_originales = datos.get("intervalos_conservados_original", [])
        jump_cuts, cursor = [], 0.0
        for iv in intervalos_originales:
            cursor += iv["fin"] - iv["inicio"]
            jump_cuts.append(round(cursor, 3))

        cerrados = encuadre_guion.get("planos_cerrados", [])
        if cerrados:
            detalle = ", ".join("{:.1f}-{:.1f}s".format(c["ini"], c["fin"]) for c in cerrados)
            _log(f"Planos cerrados pedidos por el guion: {detalle}")

        picos_guion = encuadre_guion.get("punch_ins")
        if picos_guion is not None:
            # El guion marca los énfasis en la columna "Qué se ve" del panel.
            # Es un criterio editorial; el percentil de RMS solo mide cuándo
            # subió la voz, que no es lo mismo.
            picos = [{"t": float(p["t"]), "energia": 1.0, "razon": p.get("razon", "guion")}
                     for p in picos_guion]
            _log(f"Punch-ins tomados del guion: {len(picos)} "
                 f"(se ignoran los picos de energía del audio)")
        else:
            _log("Analizando picos de energía de audio...")
            picos = detectar_picos_energia(ruta_video)

        _log("Rastreando rostro...")
        track_rostro = rastrear_rostro(ruta_video)

        huecos = detectar_huecos_regla_5s(duracion_total, planos, picos, jump_cuts)
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
            "planos_cerrados": cerrados,
            "jump_cuts": jump_cuts,
            "huecos_regla_5s": huecos,
            "nota_loop": nota_loop,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        _log(f"\nPlan de retención guardado: {plan_json}")

    if not args.sin_render:
        eventos_overlay = None
        if args.overlays:
            eventos_overlay = json.loads(Path(args.overlays).read_text(encoding="utf-8"))
        ruta_subs = Path(args.subs) if args.subs else None

        pip_anim_default = None
        if args.pip_anim_json and Path(args.pip_anim_json).exists():
            cfg_anim = json.loads(Path(args.pip_anim_json).read_text(encoding="utf-8"))
            pip_anim_default = cfg_anim.get("default", cfg_anim)
            _log(f"Animación de PiP por defecto: entrada '{pip_anim_default.get('entrada','fundido')}', "
                 f"salida '{pip_anim_default.get('salida','fundido')}'")

        if args.escala != 1.0:
            _log(f"\nPrevisualización a {args.escala:g}x: misma composición, menos píxeles.")
        else:
            _log("\nRenderizando video con zoom/face-tracking (puede tardar varios minutos)...")
        renderizar_con_zoom(ruta_video, ruta_salida, track_rostro, planos, picos,
                            eventos_overlay=eventos_overlay, ruta_subs=ruta_subs, final=args.final,
                            cerrados=cerrados, escala=args.escala, pip_anim_default=pip_anim_default)
        _log(f"Video con retención: {ruta_salida}")


if __name__ == "__main__":
    main()
