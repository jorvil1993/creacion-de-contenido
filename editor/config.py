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
SUB_TAMANO_PX = 72
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
PUNCH_IN_DURACION_S = 0.3
ZOOM_PROGRESIVO_INICIO = 1.00
ZOOM_PROGRESIVO_FIN = 1.08
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
SFX_POR_EVENTO = {
    "hook":         {"archivos": ["impacto_dramatico.mp3"],                    "volumen": 0.90},
    "corte":        {"archivos": ["transicion_corte.mp3",
                                  "transicion_swipe.mp3"],                     "volumen": 0.75},
    "punch-in":     {"archivos": ["whoosh_simple.mp3", "whoosh_rapido.mp3",
                                  "whoosh_deep_1.mp3", "whoosh_deep_2.mp3"],   "volumen": 0.65},
    "pip-producto": {"archivos": ["pop.mp3"],                                  "volumen": 0.95},
    "sticker":      {"archivos": ["notificacion_chime.mp3"],                   "volumen": 0.80},
    "cta":          {"archivos": ["notificacion_success.mp3"],                 "volumen": 0.90},
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
    "sol": "sin reflejos al sol",
}
# Duración en pantalla de cada animación (coincide con el data-duration del HTML)
ANIMACION_DURACION = {"bateria": 2.4, "splash": 2.2, "moto": 2.6, "sol": 2.4}

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
    "agua": "splash", "resistente": "splash", "sumergir": "splash",
    "piscina": "splash", "lluvia": "splash",
    "sol": "sol", "solazo": "sol",
    "envio": "moto", "envío": "moto", "enviamos": "moto",
    "entrega": "moto", "delivery": "moto", "bolivia": "moto",
}

# Largo máximo de un SFX, con desvanecido al final. `impacto_dramatico.mp3`
# dura 8.5s: sin recorte se solapa con la frase siguiente en vez de puntuar
# un momento.
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
