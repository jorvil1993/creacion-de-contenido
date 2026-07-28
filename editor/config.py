"""
Configuración central del editor de video DeviceShop.
Toda constante de estilo, retención y rutas vive aquí — no hardcodear en otros módulos.
Fuente: contexto/PLAN-EDITOR-VIDEO.md
"""
import os
import shutil
import subprocess
from pathlib import Path

# Windows a veces no propaga el PATH recién instalado (winget) a procesos hijos
# lanzados desde una terminal que ya estaba abierta. Si ffmpeg no aparece en el
# PATH heredado, se agrega la ubicación conocida de instalación como respaldo.
if shutil.which("ffmpeg") is None:
    _CANDIDATOS_FFMPEG = list(
        Path.home().glob(r"AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_*\ffmpeg-*-full_build\bin")
    )
    if _CANDIDATOS_FFMPEG:
        os.environ["PATH"] = str(_CANDIDATOS_FFMPEG[0]) + os.pathsep + os.environ.get("PATH", "")

# ---------------------------------------------------------------------------
# Datos de NLTK (los usa whisperx para alinear) — fuera de AppData
# ---------------------------------------------------------------------------
# nltk los descargaba a %APPDATA%\nltk_data. Cuando el pipeline se lanza desde
# la app de Claude (que es un paquete MSIX), Windows *redirige* esa escritura a
# AppData\Local\Packages\Claude_...\LocalCache\Roaming\ — una carpeta que se
# borra cuando la app se actualiza. Si eso pasa, whisperx deja de alinear y el
# pipeline entero se cae sin motivo aparente.
# Se fija aquí, antes de que nadie importe nltk, para que siempre lea de
# C:\ai-video\nltk_data (mismo criterio que los modelos: nada crítico dentro de
# AppData ni de OneDrive).
_NLTK_DATA = Path(r"C:\ai-video") / "nltk_data"
if _NLTK_DATA.is_dir():
    _previo = os.environ.get("NLTK_DATA", "")
    if str(_NLTK_DATA) not in _previo.split(os.pathsep):
        os.environ["NLTK_DATA"] = (
            str(_NLTK_DATA) + (os.pathsep + _previo if _previo else "")
        )

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
RAIZ_PROYECTO = Path(__file__).resolve().parent.parent
DIR_ENTRADA = RAIZ_PROYECTO / "entrada"
DIR_ASSETS = RAIZ_PROYECTO / "assets"
DIR_CONTEXTO = RAIZ_PROYECTO / "contexto"

# Los archivos de trabajo (intermedios de 100+ MB por corrida) van FUERA de
# OneDrive: la regla de la sección 3 del plan dice que OneDrive guarda solo
# código, guiones y videos finales. Tener los intermedios ahí hacía que cada
# corrida disparara la sincronización (medido: 1.7 GB acumulados y el proceso
# OneDrive con 20+ min de CPU). El video final SÍ se copia a DIR_PUBLICADOS.
DIR_SALIDA = Path(r"C:\ai-video") / "salida"
DIR_PUBLICADOS = RAIZ_PROYECTO / "salida"

# Todo lo pesado (modelos, venvs, cachés) vive fuera de OneDrive — nunca sincronizar
RAIZ_AI_VIDEO = Path(r"C:\ai-video")
DIR_MODELOS = RAIZ_AI_VIDEO / "models"
DIR_VENV = RAIZ_AI_VIDEO / "venv312"
DIR_COMFYUI = RAIZ_AI_VIDEO / "comfyui"

# Caché del editor visual v2: miniaturas del catálogo (compartidas entre
# corridas) y proxy de video (uno por corrida, vive en DIR_SALIDA/<nombre>/_editor/).
# Fuera de OneDrive como todo lo demás (sección 3 del plan).
DIR_EDITOR_CACHE = RAIZ_AI_VIDEO / "_editor_cache"

# Fase 0 (pantalla de preparación, f0_preparar.py): proxies de los clips crudos
# para poder arrastrarlos en el navegador y las previas de cómo quedan unidos.
# Todo desechable y regenerable, así que fuera de OneDrive como el resto.
DIR_PREPARACION = RAIZ_AI_VIDEO / "_preparacion"

VIDEO_PRUEBA = DIR_CONTEXTO / "tiktok video deviceshop.mp4"

# ---------------------------------------------------------------------------
# Formato de salida
# ---------------------------------------------------------------------------
ANCHO = 1080
ALTO = 1920
FPS = 30
DURACION_MIN_S = 30
DURACION_MAX_S = 40

# ---------------------------------------------------------------------------
# Codificación de video — GPU (NVENC) con fallback a CPU
# ---------------------------------------------------------------------------
# La RTX 5070 Ti tiene un chip NVENC dedicado, independiente de los núcleos
# CUDA: puede codificar video mientras WhisperX ocupa CUDA, sin competir por
# recursos. Codificar por software (libx264) satura el CPU y deja la GPU
# ociosa — que es exactamente lo que pasaba antes de este cambio (CPU 95%,
# GPU 3%).
#
# Contrapartida honesta: NVENC es levemente inferior a libx264 en calidad por
# bit. A CQ 19 la diferencia es invisible en formato vertical para redes, y
# TikTok recodifica todo al subir de todas formas.
USAR_NVENC = True

# ⚠️ NO SUBIR EL PRESET. Verificado el 2026-07-26 midiendo el conteo de frames:
# con los frames entrando por tubería (que es como renderiza f4_retencion),
# `p6`, `p7`, `-rc-lookahead` y `-temporal-aq` PIERDEN los últimos 3 frames del
# video — 0.1s del cierre, justo donde va la tarjeta de CTA. Codificando de
# archivo a archivo esas mismas banderas no pierden nada; es un fallo al vaciar
# la cola de análisis del codificador cuando se cierra la tubería.
# `spatial-aq` tampoco: medido, EMPEORA la calidad (VMAF 98.41 vs 98.83 al mismo
# CQ) y pesa más. La única vía segura para más calidad es bajar el CQ.
# Detalle completo en contexto/AUDITORIA-OPTIMIZACION.md, sección 4-bis.
NVENC_PRESET = "p5"          # p1 (rápido) .. p7 (lento) — NO cambiar, ver arriba

# El pipeline codifica 2 veces en cadena (cortar -> render único con zoom,
# overlays y subtítulos), así que la pérdida de recompresión se acumula poco.
# El tiempo de codificación es idéntico en cualquier CQ (medido), o sea que
# subir la calidad sale gratis en velocidad — solo cuesta peso de archivo.
NVENC_CQ_INTERMEDIO = "17"   # el corte no debe limitar la calidad del final
NVENC_CQ_FINAL = "22"        # ~11.5 Mbps. Medido vs referencia sin pérdida:
                             # VMAF 98.83 / PSNR 47.2 dB (CQ 26 daba 97.69 / 45.1)

X264_PRESET = "medium"       # solo se usa si NVENC no está disponible
X264_CRF_INTERMEDIO = "16"
X264_CRF_FINAL = "18"

_nvenc_disponible = None


def hay_nvenc() -> bool:
    """Detecta una sola vez si el ffmpeg instalado trae el codificador NVENC."""
    global _nvenc_disponible
    if _nvenc_disponible is None:
        try:
            r = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                capture_output=True, text=True, timeout=30,
            )
            _nvenc_disponible = "h264_nvenc" in r.stdout
        except Exception:
            _nvenc_disponible = False
    return _nvenc_disponible


def args_video(final: bool = False, pix_fmt: str = "yuv420p") -> list:
    """Argumentos de ffmpeg para codificar video.

    Usa NVENC (GPU) si está disponible; si no, cae a libx264 (CPU) para que el
    pipeline siga funcionando en cualquier máquina.

    final=False -> paso intermedio del pipeline (prioriza calidad)
    final=True  -> archivo que se publica (prioriza peso de subida)
    """
    if USAR_NVENC and hay_nvenc():
        return [
            "-c:v", "h264_nvenc",
            "-preset", NVENC_PRESET,
            "-rc", "vbr",
            "-cq", NVENC_CQ_FINAL if final else NVENC_CQ_INTERMEDIO,
            "-b:v", "0",
            "-pix_fmt", pix_fmt,
        ]
    return [
        "-c:v", "libx264",
        "-preset", X264_PRESET,
        "-crf", X264_CRF_FINAL if final else X264_CRF_INTERMEDIO,
        "-pix_fmt", pix_fmt,
    ]

# ---------------------------------------------------------------------------
# Transcripción (Fase 1)
# ---------------------------------------------------------------------------
WHISPER_MODELO = "large-v3"
WHISPER_IDIOMA = "es"
WHISPER_COMPUTE_TYPE = "float16"
WHISPER_DEVICE = "cuda"
WHISPER_BATCH_SIZE = 16

# ---------------------------------------------------------------------------
# Corte (Fase 1)
# ---------------------------------------------------------------------------
SILENCIO_UMBRAL_MS = 600       # huecos mayores a esto se recortan
SILENCIO_MARGEN_MS = 150       # margen que se deja a cada lado del corte

# Segundos de silencio que se conservan JUSTO ANTES de la primera palabra.
#
# Existe porque el corte de silencios se comía el hook físico: en la grabación
# del guion 7 había 7.9s entre el arranque del archivo y la primera palabra
# (José entra al cuadro y se sienta de golpe), el umbral de 600ms se los llevó
# enteros y el video arrancaba con él ya hablando — justo el gesto que hace de
# gancho. Medido en 02_cortado.json: quedaban 0.15s.
#
# Se cuentan HACIA ATRÁS desde la primera palabra, no desde el segundo 0: lo que
# hay que salvar es la entrada y el sentarse, no los segundos de silla vacía de
# antes. Con 3.0s el video empieza 3 segundos antes de que hable, y todo lo
# anterior se corta igual que siempre.
#
# El valor real sale del panel (`hooksegs` de cada guion en
# PANEL-PRODUCCION.html), para poder calibrarlo por guion sin tocar código.
# Este es solo el default cuando se corre sin --guion.
HOOK_CONSERVAR_INICIO_S = 0.0

# Simétrico a HOOK_CONSERVAR_INICIO_S pero en la otra punta: segundos de
# silencio que se conservan JUSTO DESPUÉS de la última palabra — el gesto de
# salida (levantarte, bajar el aparato) también es silencio puro y el corte
# se lo comía igual que el hook. El valor real sale del campo `cierresegs` de
# cada guion en PANEL-PRODUCCION.html; este es solo el default sin --guion.
HOOK_CONSERVAR_FIN_S = 0.0

# Punto de partida — calibrado una primera vez con grabación real de José (2026-07-26)
MULETILLAS = [
    "eh", "ehh", "mmm", "o sea", "digamos",
    "viste", "no ve", "ya pues", "nada", "tipo",
]
# Conectores ambiguos: solo se tratan como muletilla si además cumplen
# criterio de contexto (pausa larga alrededor, posición aislada en la frase).
# NO eliminar por coincidencia literal.
# "este" se movió aquí tras la primera grabación real: José dijo "más ESTE año"
# (demostrativo legítimo, "this year"), y la lista anterior lo cortó igual porque
# trataba cualquier "este" como muletilla sin mirar el contexto — rompió la
# gramática de la frase. "este" SÍ puede ser muletilla (p.ej. "eh... este...
# no sé") pero solo cuando está aislado por pausas, no siempre.
CONECTORES_AMBIGUOS = ["bueno", "entonces", "pues", "este"]

# Umbral de similitud difusa para detectar tomas repetidas (0-1)
TOMA_REPETIDA_SIMILITUD_MIN = 0.75
# Ventana de búsqueda hacia atrás para comparar frases (segundos)
TOMA_REPETIDA_VENTANA_S = 20

# ---------------------------------------------------------------------------
# Subtítulos (Fase 2)
# ---------------------------------------------------------------------------
SUB_COLOR_TEXTO = "&H00FFFFFF"       # blanco (formato ASS: AABBGGRR)
SUB_COLOR_CONTORNO = "&H00000000"    # negro
SUB_COLOR_RESALTADO = "&H00D9D14F"   # cian de marca #4FD1D9 en formato ASS (BGR)

# Resuelto en Fase 2 (sección 9, pregunta 6 del plan): sesión B entregó las
# fuentes reales en assets/fuentes/ (Poppins y Montserrat, ambas Bold, OFL).
# Se usa el archivo directamente vía `fontsdir` en el filtro ass de ffmpeg
# (ver editor.py) en vez de depender de que Windows la tenga instalada.
SUB_FUENTE = "Poppins"               # familia; el peso Bold lo aplica el estilo ASS (Bold=-1)
DIR_FUENTES = DIR_ASSETS / "fuentes"
SUB_TAMANO_PX = 88                   # subido de 72 (pedido de José, 2026-07-28: se leían chicos)
SUB_PALABRAS_POR_BLOQUE_MIN = 2
SUB_PALABRAS_POR_BLOQUE_MAX = 4
SUB_POSICION_ALTURA_PCT = 0.77       # 77% de ALTO = 1478px sobre lienzo 1920
SUB_MARGEN_INFERIOR_PCT = 0.15
SUB_MARGEN_SUPERIOR_PCT = 0.10

# ---------------------------------------------------------------------------
# Hook (banner de los primeros segundos)
# ---------------------------------------------------------------------------
# La regla del plan (sección 4.2) es "máximo 7 palabras, legible en <1.5s".
# Pero cortar por conteo de palabras dejaba frases partidas a la mitad
# ("¿Quieres leer más este año, pero te" — sin el "da pereza"), que se lee
# como error y arruina justo el momento de mayor retención.
#
# Criterio corregido: **la frase manda sobre el conteo**. Se recolecta hasta
# el signo de puntuación final y solo se recorta si supera este máximo. Para
# hooks realmente cortos y curados está `contexto/banco-hooks.md` (40 hooks
# escritos a ≤7 palabras) — pasarlos con --hook.
HOOK_MAX_PALABRAS = 14               # tope de seguridad, no el objetivo
HOOK_DURACION_S = 3.2
HOOK_VENTANA_BUSQUEDA_S = 5.0        # hasta dónde buscar el final de la frase

# ---------------------------------------------------------------------------
# Retención (Fase 3)
# ---------------------------------------------------------------------------
FACE_TRACK_SUAVIZADO_ALPHA = 0.15    # rango 0.1–0.2, EMA sobre posición de rostro
# Modelo de la Tasks API de MediaPipe (BlazeFace short-range, ~230 KB, gratuito).
# Si el archivo no existe, f4_retencion cae automáticamente a Haar Cascade.
FACE_TRACK_MODELO_MEDIAPIPE = DIR_MODELOS / "mediapipe" / "blaze_face_short_range.tflite"
# La detección se hace sobre el frame reducido a este ancho (las coordenadas
# salen normalizadas, así que no cambia el resultado — solo el costo).
FACE_TRACK_ANCHO_ANALISIS = 540
PUNCH_IN_ZOOM = 1.15
# Recalibrado 2026-07-27. Estaba en 0.3s: un salto del 15% que entraba y salía
# en menos de un tercio de segundo, o sea un tirón, no un acercamiento. Y como
# se disparaban por percentil de energía RMS cada 1.5s, en el guion 7 salieron
# 10 punch-ins en 24.8s — uno cada 2.4 segundos. Eso es lo que José describió
# como "cambia los zooms de manera desproporcionada a cada rato".
PUNCH_IN_DURACION_S = 1.2
PUNCH_IN_SEPARACION_MIN_S = 4.0      # antes 1.5s, y era el espaciado real
PUNCH_IN_MAX_POR_MINUTO = 8          # tope duro: en 25s no pueden salir más de 3

# Cuánto tarda en llegar arriba. El punch-in NO es simétrico: entra rápido,
# aguanta y sale suave, como un énfasis hablado. Con la curva triangular
# anterior el pico caía a la mitad de la duración, o sea 0.6s DESPUÉS de la
# palabra marcada — con los 0.3s viejos eso era medio pelo y no se notaba, pero
# a 1.2s el acento aterrizaba sobre la palabra siguiente. 0.30s son 9 fotogramas
# a 30 fps: se lee como inmediato sin ser un tirón.
PUNCH_IN_ATAQUE_S = 0.30
PUNCH_IN_SALIDA_PCT = 0.40           # el último 40% de la ventana es la bajada

ZOOM_PROGRESIVO_INICIO = 1.00
ZOOM_PROGRESIVO_FIN = 1.08

# Zoom sostenido de "plano cerrado": cuando el guion pide acercarse (columna
# "Qué se ve" del panel), el encuadre entra y SE QUEDA hasta el final del tramo,
# en vez de rebotar. Es la versión digital del "acercá la cámara" que la tabla
# de tomas pide como cambio de distancia real.
ZOOM_PLANO_CERRADO = 1.22
# Cuánto tarda el encuadre en entrar y salir de un tramo cerrado. Menos que esto
# se ve como un salto; más, y el movimiento se nota como movimiento.
ZOOM_TRANSICION_S = 0.6

REGLA_5S_MAX_BLOQUE_S = 5.0          # ningún bloque sin cambio visual mayor a esto

# ---------------------------------------------------------------------------
# Audio (Fase 4)
# ---------------------------------------------------------------------------
MUSICA_DUCKING_DB = -12
LOUDNORM_TARGET_LUFS = -14           # estándar TikTok/redes cortas
LOUDNORM_PEAK_DB = 0.0

# El DJI Mic Mini graba a 48 kHz. Toda la cadena se unifica a esa tasa para no
# remuestrear de más (antes bajaba a 44.1 kHz y volvía a subir).
# Además hay que forzarla explícitamente en la salida: el filtro `loudnorm` de
# ffmpeg trabaja internamente a 192 kHz y, si no se le indica la tasa de salida,
# el archivo termina en 96 kHz — pesa el doble sin ganar nada.
AUDIO_SAMPLE_RATE = 48000

# Volúmenes base (antes de ducking/loudnorm final) — puntos de partida, calibrar
# escuchando con audífonos y parlante de celular una vez haya grabación real.
MUSICA_VOLUMEN = 0.5
SFX_VOLUMEN = 0.7

# Pistas entregadas por sesión B en assets/musica/ (ver assets/musica/README.md).
# Default elegido: la única que "casi calza directo" con 30-40s. Cambiar aquí
# es la forma más simple de probar otro mood, no hace falta tocar el código.
MUSICA_ARCHIVO_DEFAULT = "03-corporate-funky.mp3"

# Mapeo SFX -> archivo real en assets/sfx/ (ver assets/sfx/README.md, que ya
# documenta el uso previsto de cada uno según la sección 4.4 del plan).
SFX_PUNCH_IN = "whoosh_deep_1.mp3"
SFX_HOOK = "impacto_dramatico.mp3"
SFX_POP_OVERLAY = "pop.mp3"
SFX_TRANSICION = "transicion_corte.mp3"
SFX_CIERRE = "notificacion_success.mp3"

# ---------------------------------------------------------------------------
# SFX por evento visual (rediseñado 2026-07-26)
# ---------------------------------------------------------------------------
# Antes sonaba SIEMPRE el mismo whoosh en cada pico de energía RMS — es decir,
# cada vez que José levantaba la voz. Ese criterio es mecánico, no editorial:
# correlaciona con el volumen del habla, no con que ocurra algo en pantalla.
# Por eso se percibía como "uso sin discreción, donde quiera".
#
# Criterio nuevo: **el sonido acompaña un evento VISUAL**. Regla de validación:
# ver el video sin audio y poder predecir dónde debería sonar algo.
#
# Varios archivos por evento = se rotan, para que no suene dos veces seguidas
# el mismo. Volumen propio por tipo: la transición casi subliminal, la
# aparición de producto sí destacada.
# Volúmenes calibrados el 2026-07-26 tras un error de la vuelta anterior: se
# habían puesto en 0.30-0.45 (antes todo era 0.7 uniforme) y los efectos
# quedaron enterrados bajo la voz y la música — José reportó que "se quitaron
# todos". El error fue confundir "sutil" con "inaudible": el ducking ya baja la
# música, pero los SFX compiten con la VOZ, que no se agacha nunca.
# Referencia: el hook (0.9) se oye claramente; nada debe bajar de ~0.55.
# Ampliado el 2026-07-27 con el pack nuevo (141 sonidos, ver assets/sfx/README.md).
# Solo se ampliaron las rotaciones: cada evento sigue sonando al mismo tipo de
# cosa que antes y con el MISMO volumen calibrado. Lo que cambia es que un video
# con 6 punch-ins ya no repite whoosh.
# Los risers y los reverses del pack nuevo NO están aquí a propósito: son de un
# solo uso por video (el reveal grande) y colocarlos automáticamente en cada
# corte los volvería ruido. Se usan a mano desde la hoja de sonido.
SFX_POR_EVENTO = {
    "hook":         {"archivos": ["impacto_dramatico.mp3", "impacto_bang_cine.mp3",
                                  "impacto_pesado.mp3", "impacto_boom_cine_2.mp3",
                                  "impacto_subdrop.mp3"],                      "volumen": 0.90},
    "corte":        {"archivos": ["transicion_corte.mp3", "transicion_swipe.mp3",
                                  "transicion_corte_2.mp3", "whoosh_swish_2.mp3",
                                  "whoosh_crash.mp3", "whoosh_rapido_golpe.mp3",
                                  "whoosh_swish_corte.mp3"],                   "volumen": 0.75},
    "punch-in":     {"archivos": ["whoosh_simple.mp3", "whoosh_rapido.mp3",
                                  "whoosh_deep_1.mp3", "whoosh_deep_2.mp3",
                                  "whoosh_simple_2.mp3", "whoosh_rapido_2.mp3",
                                  "whoosh_grave_3.mp3", "whoosh_grave_4.mp3",
                                  "whoosh_corto_grave.mp3", "whoosh_swoosh.mp3",
                                  "whoosh_aspero.mp3", "whoosh_metal.mp3"],    "volumen": 0.65},
    "pip-producto": {"archivos": ["pop.mp3", "ui_blip_1.mp3", "ui_boton.mp3",
                                  "ui_click.mp3"],                             "volumen": 0.95},
    # "sticker" es el cajón por defecto: aquí caen también las animaciones y la
    # ficha técnica. Con un solo archivo la rotación de arriba no podía hacer
    # nada y el mismo chime sonaba 4 veces en 37s (medido en el video de
    # prueba) — se oye como un tic del editor, no como una intención. Segundo
    # archivo añadido para que la rotación funcione; los volúmenes calibrados
    # NO se tocan.
    "sticker":      {"archivos": ["notificacion_chime.mp3", "notificacion_1.mp3",
                                  "ui_1.mp3", "ui_4.mp3", "ui_6.mp3", "ui_8.mp3",
                                  "ui_blip_2.mp3", "ui_blip_3.mp3",
                                  "camara_click_4.mp3", "camara_click_5.mp3"], "volumen": 0.80},
    "cta":          {"archivos": ["notificacion_success.mp3", "notificacion_pago.mp3",
                                  "tada_cierre.mp3", "whoosh_logro.mp3",
                                  "ui_game_start.mp3"],                        "volumen": 0.90},
}

# Cuántos punch-ins llevan sonido como máximo. Los demás hacen el zoom en
# silencio. Con 17 picos en 37s sonaba uno cada 2 segundos: saturado. Se
# priorizan los picos de mayor energía, que son los énfasis reales.
SFX_MAX_PUNCH_INS = 6

# Pico al que se lleva CADA sonido antes de aplicarle su volumen artístico.
# El pack trae 20 dB de dispersión entre archivos (medido), así que sin esto
# el volumen de arriba no significa nada: `pop.mp3` con volumen 0.95 sonaba
# más bajo que `whoosh_deep_1.mp3` con 0.30. -6 dBFS deja margen para que la
# voz siga mandando.
SFX_PICO_OBJETIVO_DB = -6.0

# ---------------------------------------------------------------------------
# Insertos visuales disparados por lo que se dice (Fase 5)
# ---------------------------------------------------------------------------
# Vocabulario -> etiqueta del catálogo (contexto/catalogo-assets.json).
# Cuando José dice una de estas palabras, el pipeline busca un asset con esa
# etiqueta y lo muestra. Antes el PiP aparecía al 40% del video, en un momento
# arbitrario sin relación con el guion.
PALABRAS_A_TAGS = {
    # agua / resistencia
    "agua": "#agua", "sumergir": "#agua", "piscina": "#agua", "tina": "#tina",
    "playa": "#agua", "lluvia": "#agua", "resistente": "#agua",
    # modelos
    "paperwhite": "#paperwhite", "colorsoft": "#colorsoft", "scribe": "#scribe",
    "kobo": "#kobo", "libra": "#botones", "clara": "#compacto",
    # características
    "color": "#color", "colores": "#color",
    "escribir": "#escribir", "anotar": "#escribir", "lapiz": "#stylus",
    "lápiz": "#stylus", "stylus": "#stylus",
    "pantalla": "#pantalla", "protector": "#protector",
    "bateria": "#bateria", "batería": "#bateria", "carga": "#carga",
    "cargador": "#carga",
    # comercial
    "caja": "#caja", "sellado": "#caja", "nuevo": "#caja",
    "funda": "#funda", "proteger": "#funda", "protege": "#funda",
    "regalo": "#regalo", "regalar": "#regalo",
    "niños": "#ninos", "nino": "#ninos",
    "comparar": "#comparativa", "diferencia": "#comparativa",
    "envio": "#broll", "envío": "#broll",
    # --- conceptos de AMBIENTE ---
    # El catálogo son fotos de producto: no tiene (ni tendrá) una foto de "sol",
    # "cama" o "café". Estas etiquetas son las que activan el respaldo de
    # generación (f9_generar.py) — es justo lo que pedía el punto 5 de
    # MEJORAS-PENDIENTES: "cuando él diga 'sol', 'tina', etc., que aparezca una
    # fotito ilustrando eso".
    "sol": "#sol", "solazo": "#sol", "verano": "#sol", "afuera": "#sol",
    "cama": "#cama", "dormir": "#cama", "acostado": "#cama",
    "noche": "#noche", "noches": "#noche", "oscuras": "#noche",
    "cafe": "#cafe", "café": "#cafe",
    "viaje": "#viaje", "viajar": "#viaje", "vacaciones": "#viaje",
    "avion": "#viaje", "avión": "#viaje", "maleta": "#viaje",
    "libros": "#libros", "pesados": "#libros",
    "biblioteca": "#biblioteca", "biblioteca?": "#biblioteca",
    "estudiar": "#estudio", "universidad": "#estudio", "apuntes": "#estudio",
}

# Cuántos insertos por palabra clave como máximo en un video. Más que esto
# satura y compite con el mensaje.
INSERTOS_MAX = 4
INSERTO_DURACION_S = 2.8
# Separación mínima entre dos insertos, para que no se pisen
INSERTO_SEPARACION_MIN_S = 4.0
# Altura del inserto (fracción del alto). Va ARRIBA: en un talking-head sentado
# la cabeza ocupa la franja media y la parte superior queda libre. Se probó
# colocarlo entre el rostro y los subtítulos y siempre rozaba la cara.
INSERTO_Y_PCT = 0.07
# Borde blanco con filo cian de la tarjeta de inserto. Vive aquí y no dentro
# de render_pip_producto porque el render de video necesita el MISMO número
# para que un PiP de video mida igual que uno de foto.
INSERTO_BORDE = 10
INSERTO_ANCHO = 400
INSERTO_ALTO = 520

# Franja donde viven TODOS los overlays (decisión ya tomada, ver INSERTO_Y_PCT).
# Las composiciones de Hyperframes ocupan el lienzo 1080x1920 completo y se
# posicionan solas dentro del HTML: esta constante documenta el acuerdo para que
# cualquier plantilla nueva lo respete y no vuelva a caer sobre la cara.
OVERLAY_BANDA_SUPERIOR_PCT = (0.10, 0.35)

# ---------------------------------------------------------------------------
# Animaciones generadas (Fase 5) — para conceptos que ninguna foto ilustra
# ---------------------------------------------------------------------------
# Una foto de cargador no comunica "batería que dura semanas"; una batería que
# se llena sí. Estas se dibujan por código, no salen del catálogo.
ANIMACION_FPS = 25

# Motor de animaciones. Hyperframes (HTML+GSAP) se ve claramente mejor que PIL:
# tipografía real, easing, degradados y sombras. PIL queda como respaldo para
# que el pipeline siga funcionando si Node/npx no estuvieran disponibles.
USAR_HYPERFRAMES = True

# Texto que acompaña a cada animación dentro de la composición
ANIMACION_ETIQUETAS = {
    "bateria": "semanas de batería",
    "splash": "resistente al agua",
    "moto": "Envíos a todo Bolivia",
    # No es "hace sol": el argumento es que la pantalla SIGUE legible con el sol
    # encima, que es la ventaja real del e-ink frente a una tablet.
    "sol": "se lee bajo el sol",
}

# Texto de la SEGUNDA aparición. Repetir literal la misma frase tres segundos
# después se lee como que el editor se trabó — se vio en el video de prueba, con
# "resistente al agua" dos veces entre 18.6s y 21.0s. El concepto no cambia,
# cambia cómo se dice.
ANIMACION_ETIQUETAS_REPETICION = {
    "bateria": "y sigue cargada",
    "splash": "sin miedo al agua",
    "moto": "Llega a tu puerta",
    "sol": "ni un reflejo",
}
# Duración en pantalla de cada animación (coincide con el data-duration del HTML)
ANIMACION_DURACION = {
    "bateria": 2.4, "splash": 2.2, "moto": 2.6, "sol": 2.6,
    "tarjeta-cta": 6.5, "comparativa": 5.0, "tarjeta-specs": 4.5,
    "stickers": 2.5, "banner-hook": 3.2, "pip-producto": 4.0, "anim-apps": 3.0
}

# Plantillas que el pipeline construye CON DATOS PROPIOS y coloca por su cuenta:
# el CTA lleva el mensaje, el WhatsApp y el eco del hook; la ficha y la
# comparativa salen del catálogo de especificaciones. El camino genérico de
# animaciones solo sabe pasar `variante`, `lado` y `etiqueta`, así que si un
# beat ANIM del guion pide una de estas, saldría la plantilla VACÍA y encima
# encimada con la que el pipeline ya puso. Pasó con `tarjeta-cta` en el guion 7:
# el beat 11 caía en 23.09s, dentro del CTA automático de 18.33s a 24.83s.
PLANTILLAS_CON_DATOS_PROPIOS = ("tarjeta-cta", "comparativa", "tarjeta-specs")

# Cuántas variantes distintas tiene cada animación. La variante la elige una
# semilla determinista (nombre del video + índice de aparición), nunca `random`:
# el mismo video renderizado dos veces tiene que dar exactamente lo mismo.
# anim-apps tiene 2 y no 3: son dos juegos de apps (TikTok/WhatsApp/Facebook a
# la derecha, Instagram/YouTube/X a la izquierda). Declararlo importa — con el
# default de 3 el sorteo podía dar dos veces el mismo índice y las dos
# apariciones del guion 7 habrían salido idénticas.
ANIMACION_VARIANTES = {"bateria": 3, "splash": 3, "moto": 3, "sol": 3, "anim-apps": 2}

# Cuántas veces puede salir la MISMA animación en un video.
# Antes era 1 (un `set` de animaciones ya usadas vetaba la segunda aparición) y
# el resultado era el que José rechazó: decir "agua" disparaba el splash, pero
# decir "tina" tres segundos después caía a una foto de producto. Ahora la
# segunda mención sí lleva animación, pero con OTRA variante — repetir la misma
# toma se lee como error de edición.
ANIMACION_MAX_POR_TIPO = 2

# Separación mínima entre dos animaciones. Es SUYA, ya no la de los insertos.
# Medido en el video de prueba: entre "resistente al agua" (17.7s) y "en la
# tina" (20.0s) hay 2.34s, así que con los 4.0s de INSERTO_SEPARACION_MIN_S la
# segunda animación nunca podía salir — no importaba cuánto se subiera
# ANIMACION_MAX_POR_TIPO. Los insertos son fotos y sí necesitan aire entre sí;
# dos animaciones de la misma frase son un mismo gesto en dos tiempos.
# El solape sigue prohibido: de eso se encarga `_libre()`.
ANIMACION_SEPARACION_MIN_S = 2.0

# Conceptos donde la ANIMACIÓN gana sobre la foto del catálogo.
# El problema medido: 30 assets llevan la etiqueta `#agua` (son los Kindle
# resistentes al agua), así que la regla general "catálogo primero, generación
# como respaldo" hacía que decir "agua"/"tina" trajera una foto de producto en
# vez del splash. Para estas etiquetas se invierte la preferencia.
# Importante: NO se tocan las etiquetas de esos 30 assets — siguen sirviendo
# para el resto de sus usos; lo único que cambia es que estas etiquetas ya no
# disparan un inserto de foto por sí solas.
CONCEPTOS_PREFIEREN_ANIMACION = {"#agua", "#tina", "#sol", "#bateria"}

# ---------------------------------------------------------------------------
# Diseño de loop (sección 4.5 del plan) — el rewatch es la señal más fuerte
# ---------------------------------------------------------------------------
# Hasta ahora f4_retencion solo escribía una NOTA de texto diciendo que el loop
# quedaba pendiente. Se implementa en dos capas:
#
#   1. VISUAL — durante los últimos segundos el encuadre (zoom + paneo) vuelve
#      suavemente al del primer frame, de modo que el final empalma con el
#      arranque y el rebobinado no se nota.
#   2. NARRATIVA — la tarjeta de CTA cierra repitiendo el hook ("eco"), así lo
#      último que se lee es la misma frase con la que abrió el video.
LOOP_ACTIVO = True
LOOP_DURACION_S = 1.2          # cuánto dura el regreso al encuadre inicial
LOOP_ECO_MAX_PALABRAS = 7      # el eco se recorta a un hook corto y legible

# ---------------------------------------------------------------------------
# Specs por producto -> alimentan la tarjeta de Hyperframes
# ---------------------------------------------------------------------------
# Datos verificados por la sesión B en contexto/catalogo-productos.md.
# La tarjeta se arma con el producto que detecta el guion, así que dos videos
# de modelos distintos producen tarjetas distintas — no un gráfico fijo.
ESPECIFICACIONES = {
    "#paperwhite": {
        "nombre": "Kindle Paperwhite",
        "specs": [("Pantalla", "7\" · 300 ppi"), ("Batería", "Hasta 12 semanas"),
                  ("Agua", "Resistente IPX8")],
    },
    "#basic": {
        "nombre": "Kindle Basic",
        "specs": [("Pantalla", "6\" · 300 ppi"), ("Memoria", "16 GB"),
                  ("Batería", "Semanas, no horas")],
    },
    "#colorsoft": {
        "nombre": "Kindle Colorsoft",
        "specs": [("Pantalla", "7\" a color"), ("Batería", "Hasta 8 semanas"),
                  ("Agua", "Resistente IPX8")],
    },
    "#scribe": {
        "nombre": "Kindle Scribe",
        "specs": [("Pantalla", "10.2\" · 300 ppi"), ("Lápiz", "Incluido"),
                  ("Uso", "Leer y escribir")],
    },
    "#kobo": {
        "nombre": "Kobo",
        "specs": [("Formatos", "EPUB nativo"), ("Tienda", "Sin bloqueo"),
                  ("Biblioteca", "OverDrive")],
    },
}

# Palabras que justifican mostrar la ficha técnica
PALABRAS_SPECS = {"especificaciones", "características", "caracteristicas", "ficha",
                  "pulgadas", "resolución", "resolucion", "memoria", "almacenamiento",
                  "gigas", "modelo", "versión", "version",
                  # frases de presentación: casi siempre el momento en que se
                  # enseña el aparato, buen lugar para la ficha técnica
                  "esta", "presento", "conoce", "miles", "bolsillo"}
ANIMACIONES_POR_PALABRA = {
    "bateria": "bateria", "batería": "bateria", "carga": "bateria",
    "semanas": "bateria", "dura": "bateria",
    # "tina", "bañera" y "mojar" faltaban: eran justo las palabras de la SEGUNDA
    # mención del agua en el video de prueba, y sin ellas la única salida
    # posible era la foto de producto que José no quiere.
    "agua": "splash", "resistente": "splash", "sumergir": "splash",
    "sumerge": "splash", "piscina": "splash", "lluvia": "splash",
    "tina": "splash", "bañera": "splash", "banera": "splash",
    "mojar": "splash", "moja": "splash",
    "sol": "sol", "solazo": "sol", "verano": "sol", "afuera": "sol",
    "playa": "sol", "directo": "sol",
    "envio": "moto", "envío": "moto", "enviamos": "moto",
    "entrega": "moto", "delivery": "moto", "bolivia": "moto",
}

# Cuánto se deja sonar un SFX DESPUÉS de su golpe, con desvanecido al final.
# `impacto_dramatico.mp3` dura 8.5s: sin recorte se solapa con la frase
# siguiente en vez de puntuar un momento.
#
# Se cuenta desde el punto de impacto, no desde el inicio del archivo. La
# diferencia importa desde que el pack tiene risers: `riser_1.mp3` tarda 2.4s en
# llegar a su clímax, así que recortarlo a 1.6s CONTANDO DESDE EL INICIO se
# llevaba justo la parte que vale. Ver assets/sfx/_alineacion.json.
SFX_DURACION_MAX_S = 1.6

# Distancia mínima entre dos SFX cualesquiera. Evita que se amontonen cuando
# un corte, un overlay y un punch-in caen casi juntos.
SFX_SEPARACION_MIN_S = 1.2

# ---------------------------------------------------------------------------
# Generación en GPU (Fase 6) — ComfyUI + Flux.1-schnell GGUF
# ---------------------------------------------------------------------------
# Se usa como RESPALDO: primero manda el catálogo de fotos reales
# (contexto/catalogo-assets.json). Solo cuando el guion nombra un concepto para
# el que no hay ninguna foto se genera una imagen.
# Motivo: Flux hace ambientes y conceptos creíbles, pero NO sabe cómo es un
# Kindle real (verificado por la sesión B) — para el producto siempre gana la
# foto real.
GENERAR_HABILITADO = True
COMFY_PYTHON = RAIZ_AI_VIDEO / "venv-comfy" / "Scripts" / "python.exe"
COMFY_MAIN = DIR_COMFYUI / "main.py"
COMFY_PUERTO = 8188
COMFY_ARRANQUE_TIMEOUT_S = 240   # primera vez tarda: importa torch y registra ~150 nodos
COMFY_GENERACION_TIMEOUT_S = 300 # la primera imagen carga 13 GB de modelos a la VRAM

# Modelos ya descargados por la sesión B (ver contexto/BITACORA-B.md punto 8)
COMFY_UNET_GGUF = "flux1-schnell-Q5_K_S.gguf"
COMFY_CLIP_L = "clip_l.safetensors"
COMFY_T5 = "t5xxl_fp8_e4m3fn.safetensors"
COMFY_VAE = "ae.safetensors"
# Configuración estándar de schnell (no es dev: 4 pasos, cfg 1)
COMFY_PASOS = 4
COMFY_CFG = 1.0
COMFY_GUIDANCE = 3.5
COMFY_SAMPLER = "euler"
COMFY_SCHEDULER = "simple"
# Los insertos se muestran en una tarjeta de 400x520 (~3:4): generar en 9:16
# completo desperdicia píxeles y obliga a recortar. Múltiplo de 16 para el VAE.
COMFY_ANCHO = 768
COMFY_ALTO = 1024

DIR_GENERADO = DIR_ASSETS / "generado"
DIR_GENERADO_AUTO = DIR_GENERADO / "auto"        # caché por hash del prompt

# Estilo común a todos los prompts: mantiene la coherencia visual entre videos
# y evita que Flux meta texto, marcas de agua o rostros (los rostros son de
# José, no de un modelo generado).
PROMPT_ESTILO = ("natural editorial photography, soft warm daylight, shallow depth of field, "
                 "clean minimal composition, no text, no watermark, no logo, no people's faces")

# Concepto -> qué pedirle a Flux. La clave es la MISMA etiqueta del catálogo,
# así el respaldo entra exactamente donde el catálogo se queda corto.
# Los modelos de e-reader NO están aquí a propósito: para el producto se usa
# foto real, nunca generada.
PROMPTS_POR_TAG = {
    "#agua": "close-up of clear water droplets splashing on a dark waterproof surface, "
             "poolside sunlight, refreshing summer mood",
    "#tina": "luxurious white porcelain bathtub filled with crystal clear water, relaxing spa atmosphere, soft daylight",
    "#bateria": "long exposure of a cozy reading lamp glowing through a whole evening, "
                "calendar weeks passing, warm amber light, sense of long lasting energy",
    "#viaje": "open suitcase on a bed next to a window, boarding pass and sunglasses, "
              "morning light, travel preparation mood",
    "#cama": "cozy unmade bed with white linen next to a window at night, warm bedside lamp",
    "#sol": "bright sunny terrace with a garden chair and dappled sunlight through leaves",
    "#cafe": "cup of coffee on a wooden table by a window, morning light, quiet cafe corner",
    "#playa": "sunny beach towel on golden sand with turquoise sea in the background",
    "#noche": "dark bedroom at night lit only by a soft warm reading light",
    "#biblioteca": "tall wooden bookshelves full of colorful books, warm library light",
    "#libros": "heavy stack of thick hardcover books on a table, dramatic side light",
    "#regalo": "elegant gift box with a satin ribbon on a clean table, festive warm light",
    "#estudio": "student desk with notebooks and a warm lamp, focused study atmosphere",
    "#broll": "delivery scene in a bolivian city street, motorbike courier with a backpack, "
              "warm afternoon light",
}

# ---------------------------------------------------------------------------
# Video generado en la GPU — LTX 2.3 22B (distilled 1.1) en GGUF Q4
# ---------------------------------------------------------------------------
# Mismo principio que Flux, un escalón más arriba: en vez de una foto fija para
# el ambiente, un clip de 2-3 s. Y para el PRODUCTO sigue ganando la foto real
# (verificado: ningún modelo generativo sabe cómo es un Kindle) — por eso el
# caso de más valor es imagen-a-video partiendo de los recortes reales de
# assets/productos/*/frontal.png, no texto-a-video del producto.
#
# APAGADO POR DEFECTO. Cada clip son minutos y hace falta RAM libre; se
# enciende a propósito con --video-ambiente o poniendo esto en True.
LTX_HABILITADO = False

# El cuello de botella es la RAM del sistema, no la VRAM: el modelo de 16.4 GB
# no entra en los 16 GB de la 5070 Ti, así que ComfyUI hace *block swap* y las
# capas que no están en VRAM viven en RAM. Con menos de este mínimo libre, el
# swap se va al archivo de paginación y el clip pasa de minutos a decenas de
# minutos. Se comprueba ANTES de arrancar y se avisa; no se bloquea, porque es
# una decisión de José si quiere igual.
LTX_RAM_LIBRE_MINIMA_GB = 18.0

# Los 5 archivos. El de audio hace falta aunque el audio se descarte: LTX 2.3
# es audio-video y el sampler recibe la pareja (video, audio) como un solo
# latente. Ver el comentario largo en editor/descargar_ltx.py.
LTX_UNET_GGUF = "ltx-2.3-22b-distilled-1.1-UD-Q4_K_M.gguf"
LTX_TEXT_ENCODER = "gemma_3_12B_it_fp8_e4m3fn.safetensors"
LTX_TEXT_PROJECTION = "ltx-2.3_text_projection_bf16.safetensors"
LTX_VAE_VIDEO = "LTX23_video_vae_bf16.safetensors"
LTX_VAE_AUDIO = "LTX23_audio_vae_bf16.safetensors"

# Geometría. width/height múltiplos de 32 (el VAE de LTX 2.3 comprime 32x en
# espacio, ver EmptyLTXVLatentVideo en comfy_extras/nodes_lt.py) y el nº de
# frames tiene que ser múltiplo de 8 más 1.
#
# 704x1280 y no 1080x1920: el costo del sampler crece con el nº de tokens, que
# es (W/32)x(H/32)x(frames/8+1). A 1080x1920 son ~2.5x más tokens que acá para
# un PiP que se muestra dentro de una tarjeta de 400x520 px. Se genera a esta
# resolución y el compositor lo escala. 704x1280 mantiene 9:16 exacto.
LTX_ANCHO = 704
LTX_ALTO = 1280
LTX_FRAMES = 73          # 73 = 8*9+1 -> 3.04 s a 24 fps
LTX_FPS = 24.0

# Pasos y sigmas del modelo *destilado*: el workflow oficial
# (custom_nodes/ComfyUI-LTXVideo/example_workflows/2.3/
#  LTX-2.3_T2V_I2V_Single_Stage_Distilled_Full.json) usa esta lista fija de
# sigmas con 8 pasos y cfg 1.0. No es un schedule genérico: es el que
# corresponde a la destilación 1.1. Copiado de ahí, no inventado.
LTX_SIGMAS = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
LTX_SAMPLER = "euler_ancestral_cfg_pp"
LTX_CFG = 1.0
LTX_PASOS = 8            # solo informativo: manda LTX_SIGMAS

# Fuerza del primer fotograma en imagen-a-video. 0.7 es el valor del workflow
# oficial: por debajo se despega demasiado de la foto real del producto, que es
# justo lo que queremos conservar.
LTX_STRENGTH_IMAGEN = 0.7

# Un clip tarda minutos, no segundos: la primera pasada además carga 16 GB de
# pesos con block swap desde la RAM.
LTX_GENERACION_TIMEOUT_S = 1800

# Negativo del workflow oficial, adaptado: fuera estética de videojuego y
# artefactos. Sin esto los ambientes salen con look de render 3D.
#
# La parte de subtítulos NO es decorativa: la primera prueba de `#libros` salió
# con SUBTÍTULOS FALSOS quemados arriba y abajo del cuadro, en los dos clips.
# El modelo imita el material con el que se entrenó, y los videos de libros
# suelen venir subtitulados. "text" solo no alcanzó; hay que nombrar la forma.
LTX_PROMPT_NEGATIVO = ("pc game, console game, video game, cartoon, childish, ugly, "
                       "watermark, text, logo, distorted, blurry, low quality, "
                       "subtitles, captions, closed captions, burned-in text, "
                       "overlay text, title card, lower third, letters, words")

# Estilo común, hermano de PROMPT_ESTILO pero con lenguaje de MOVIMIENTO: a un
# modelo de video hay que decirle qué se mueve, si no produce una foto quieta
# con ruido. "static camera" a propósito: el compositor ya hace punch-in y dos
# movimientos de cámara encima se pelean.
LTX_PROMPT_ESTILO = ("cinematic natural lighting, subtle gentle motion, static camera, "
                     "shallow depth of field, no text, no watermark, no people's faces")

# Qué se mueve en cada ambiente. Son los MISMOS conceptos de PROMPTS_POR_TAG,
# reescritos en términos de movimiento — un prompt de foto fija ("terraza
# soleada") le da a un modelo de video una postal quieta.
# Los modelos de e-reader NO están acá, misma razón que en Flux: para el
# producto, foto real.
LTX_PROMPTS_POR_TAG = {
    "#agua": "clear water droplets falling and splashing in slow motion on a dark "
             "waterproof surface, ripples spreading outward, poolside sunlight",
    "#tina": "steam rising slowly from a white porcelain bathtub full of clear water, "
             "gentle ripples on the surface, gentle spa light",
    "#bateria": "a warm reading lamp glowing steadily in a dark room while the light "
                "outside the window shifts from dusk to night, time passing",
    "#viaje": "an open suitcase on a bed by a window, curtains moving gently in the "
              "morning breeze, warm travel light",
    "#cama": "white bed linen breathing slightly in a dark bedroom, a warm bedside lamp "
             "flickering softly at night",
    "#sol": "dappled sunlight moving across a garden terrace as leaves sway in the "
            "breeze, bright warm summer afternoon",
    "#cafe": "steam curling up from a cup of coffee on a wooden table by a window, "
             "quiet morning light in a cafe corner",
    "#playa": "turquoise sea waves rolling gently onto golden sand, a beach towel "
              "fluttering in the wind, bright sunny day",
    "#noche": "a soft warm reading light glowing in a dark bedroom, faint shadows "
              "shifting slowly on the wall",
    "#biblioteca": "slow camera-free drift of dust motes floating in warm light between "
                   "tall wooden bookshelves full of books",
    # OJO con este: la primera versión ("pages of a thick hardcover book turning
    # slowly, dramatic side light") salió con SUBTÍTULOS FALSOS quemados en el
    # cuadro, las tres veces que se generó. Reforzar el prompt negativo NO
    # alcanzó. El encuadre "video de un libro" arrastra el sesgo del material
    # con el que se entrenó el modelo, que viene subtitulado. La salida es
    # pedirle un MACRO de textura, que no se parece a un video narrado.
    "#libros": "extreme macro close-up of the stacked paper edges of a thick book, "
               "warm side light grazing the paper texture, shallow depth of field, "
               "very slow drift",
    "#regalo": "a satin ribbon on an elegant gift box moving gently, warm festive light "
               "shifting across the surface",
    "#estudio": "a warm desk lamp lighting an open notebook, a page turning slowly, "
                "focused quiet study atmosphere",
    "#broll": "a motorbike courier with a backpack riding through a bolivian city "
              "street, warm afternoon light, traffic moving in the background",
}

# Movimiento para imagen-a-video partiendo de una foto REAL de producto. Acá el
# prompt NO describe la escena (ya está en la foto): describe solo cómo se
# mueve, para que el modelo no reinvente el aparato. Este es el caso de más
# valor de LTX en este pipeline.
LTX_PROMPT_DESDE_FOTO = ("the object stays exactly as it is while the light shifts "
                         "gently across its surface, subtle realistic motion, "
                         "no shape changes")

DIR_VIDEO_GENERADO = DIR_ASSETS / "generado" / "video"
DIR_VIDEO_GENERADO_AUTO = DIR_VIDEO_GENERADO / "auto"   # caché por hash del prompt
DIR_VIDEO_MANUAL = DIR_VIDEO_GENERADO / "manual"         # clips de Google Flow puestos a mano

# B-roll a pantalla completa: un clip manual que tapa TODO el frame durante su
# ventana. La voz de José sigue sonando (el audio no se toca), los subtítulos
# quedan encima (el ass= va después de los overlays en el filter_complex) y la
# transición es un fade suave — no un corte brusco.
# La duración NO es fija: se calcula de los timestamps de la transcripción
# (desde la palabra clave hasta el fin de la frase). Si el resultado es menor
# que BROLL_DURACION_MIN_S, no se muestra — sería un flashazo, no un B-roll.
BROLL_DURACION_MIN_S = 1.0     # debajo de esto no vale la pena mostrar el clip
BROLL_FADE_S = 0.20            # un pelo más largo que el 0.15 de PiP, más cinematográfico

# En el modo dirigido por guion (f13_guion.py), el B-roll y el PIP duran
# exactamente lo que dura la frase que los dispara — a veces ~1s, un flashazo.
#
# Decisión de José (2026-07-27): el inserto se queda TODO lo que pueda, hasta
# que el próximo beat ponga algo en pantalla. El factor sobre la duración de la
# frase quedó obsoleto — con él los B-rolls del guion 7 salieron de 2.12s y
# 2.41s (medido en 05_overlays.eventos.json) y se leían como flashazos.
BROLL_PIP_DURACION_MIN_S = 3.0  # piso: menos que esto no alcanza a leerse
BROLL_PIP_DURACION_MAX_S = 6.0  # techo: más que esto se vuelve el video, no un apoyo
BROLL_PIP_GAP_MIN_S = 0.10     # aire mínimo antes de que arranque el próximo evento

# Qué tipo de beat CORTA a un inserto que ya está en pantalla. Un B-roll ocupa
# el cuadro entero y un PIP una esquina, así que no compiten por el mismo sitio:
# una animación de esquina puede convivir encima de un B-roll a pantalla completa
# (el orden del filter_complex ya la compone por arriba), pero dos cosas en la
# misma esquina no.
BROLL_TIPOS_QUE_CORTAN = ("B-ROLL", "PIP")
PIP_TIPOS_QUE_CORTAN = ("B-ROLL", "PIP", "ANIM")

# Animaciones que, CON LA GENERACIÓN DE VIDEO ENCENDIDA, le ceden su lugar a un
# clip real. Se declara por NOMBRE DE ANIMACIÓN, no por etiqueta, y la diferencia
# no es cosmética — se midió:
#
# Declarándolo por etiqueta (`#agua`, `#sol`) no funcionaba. En VIDEOV2, las
# palabras "tina" y "directo" también disparan `splash` y `sol`, y aunque sus
# etiquetas fueran otras (o ninguna), la animación igual ocupaba la ventana de
# tiempo y el inserto de video se caía por solapamiento. Resultado: cero clips
# de agua y de sol, que era justo lo que se quería. Por nombre de animación se
# libera la franja entera y el clip entra.
#
# El criterio: un B-roll REAL de agua o de sol dice más que la animación
# dibujada, pero SOLO cuando se pagó el costo de generarlo. Con
# `--video-ambiente` apagado —el caso normal— este conjunto ni se consulta y las
# animaciones siguen mandando exactamente como antes.
#
# `bateria` y `moto` NO están: la de batería cuenta el paso del tiempo y la de
# moto es la entrega en Bolivia; ninguna de las dos es un ambiente que LTX pueda
# hacer mejor.
#
# Si José edita las animaciones a mano desde el editor visual, su lista gana:
# esto solo afecta al disparo automático.
LTX_ANIMACIONES_CEDEN_AL_VIDEO = {"splash", "sol"}

# ---------------------------------------------------------------------------
# Presentadores (sección 2 del plan: el sistema debe soportar 2)
# ---------------------------------------------------------------------------
# Hasta ahora ninguna fase tenía parámetro de presentador: todos los umbrales
# estaban calibrados para José. Su esposa habla distinto (otro ritmo, otras
# muletillas) y se sienta a otra distancia de la cámara, así que los mismos
# números no le sirven.
#
# Cada perfil solo declara lo que CAMBIA respecto a los valores por defecto de
# arriba; `perfil()` devuelve el diccionario ya resuelto. Los valores de la
# esposa son un punto de partida honesto: no hay grabación suya todavía, así que
# están marcados para calibrar con su primer video (misma regla que la sección
# 0.6 del plan: se ajustan viendo material real, no en teoría).
PRESENTADOR_DEFAULT = "jose"

PRESENTADORES = {
    "jose": {
        "nombre": "José",
        # calibrado con VIDEOV2.mp4 (grabación real del 2026-07-26)
        "muletillas": MULETILLAS,
        "conectores_ambiguos": CONECTORES_AMBIGUOS,
        "silencio_umbral_ms": SILENCIO_UMBRAL_MS,
        "face_track_alpha": FACE_TRACK_SUAVIZADO_ALPHA,
        "punch_in_percentil": 90,
        "calibrado": True,
    },
    "esposa": {
        "nombre": "Esposa de José",
        # SIN CALIBRAR — ajustar con su primera grabación real.
        # "ay", "pues" y "¿no?" son muletillas frecuentes en el habla femenina
        # boliviana coloquial; van como punto de partida, no como verdad.
        "muletillas": MULETILLAS + ["ay", "o sea pues", "ya"],
        "conectores_ambiguos": CONECTORES_AMBIGUOS + ["nove", "acaso"],
        # umbral de silencio algo mayor: cortar igual de agresivo a alguien que
        # habla más pausado suena entrecortado
        "silencio_umbral_ms": 700,
        "face_track_alpha": FACE_TRACK_SUAVIZADO_ALPHA,
        "punch_in_percentil": 88,
        "calibrado": False,
    },
}


def perfil(nombre: str = None) -> dict:
    """Perfil del presentador, con los valores por defecto ya resueltos."""
    clave = (nombre or PRESENTADOR_DEFAULT).strip().lower()
    if clave not in PRESENTADORES:
        raise ValueError(
            f"Presentador desconocido: '{nombre}'. Opciones: {', '.join(PRESENTADORES)}"
        )
    return PRESENTADORES[clave]


# ---------------------------------------------------------------------------
# Marca (sección 5.3) — SOLO como acento, nunca pintar el video completo
# ---------------------------------------------------------------------------
COLOR_NAVY = "#0A2A3E"
COLOR_CIAN = "#4FD1D9"
COLOR_BLANCO = "#FFFFFF"

WHATSAPP_NUMERO = "69214437"
TIKTOK_HANDLE = "@deviceshopbo"


def abrir_imagen(ruta):
    """Abre una foto YA GIRADA según su etiqueta EXIF de orientación.

    Las fotos del catálogo salen del teléfono en horizontal con una etiqueta que
    dice "esto va girado 90°": 169 de las 198 aptas para PiP la traen. PIL no la
    aplica sola, así que abrirlas con `Image.open()` a secas las deja volcadas —
    y no solo en la rejilla del editor: la tarjeta que se compone dentro del
    video salía volcada también, y el catálogo las anotaba como `horizontal`
    cuando son verticales.

    Devuelve una imagen suelta (ya cerrada la original), lista para usar en un
    `with`.
    """
    from PIL import Image, ImageOps
    # Fotos propias de 4000x3000+: no hay ninguna bomba de descompresión que
    # mitigar aquí, es la cámara de José.
    Image.MAX_IMAGE_PIXELS = None
    with Image.open(ruta) as im:
        im.load()
        corregida = ImageOps.exif_transpose(im)
        return corregida if corregida is not im else im.copy()


# Resolución del render de previsualización (`editor.py --preview`), como
# fracción de 1080x1920. A 0.5 son 540x960: la cuarta parte de los píxeles, que
# es donde está el tiempo — el render genera los frames en Python y los pasa
# crudos por tubería. La composición no cambia: mismos overlays, mismas
# posiciones y los mismos subtítulos, que escalan solos por el PlayRes del .ass.
PREVIEW_ESCALA = 0.5
