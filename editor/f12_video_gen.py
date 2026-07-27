"""
Video generado en la GPU — LTX 2.3 22B (destilado 1.1) en GGUF Q4.

Es el hermano de `f9_generar.py` un escalón más arriba: donde ese produce una
FOTO fija para un concepto de ambiente, este produce un CLIP de ~3 s. Reutiliza
su `ServidorCompartido`, su patrón de caché por hash y su forma de hablar con
ComfyUI — acá solo cambia el workflow y el formato de salida.

Dónde encaja (igual de acotado que Flux, a propósito):

    1. El guion nombra un concepto  ->  foto REAL del catálogo
    2. Si el catálogo no tiene nada ->  imagen fija con Flux (f9_generar)
    3. Solo si se pide explícitamente -> clip con LTX (este módulo)

Para el PRODUCTO sigue ganando la foto real: está verificado que ningún modelo
generativo sabe cómo es un Kindle. Por eso hay dos caminos y el segundo es el
que vale la pena:

    - texto-a-video  : ambiente SIN producto (#sol, #cama, #noche, #cafe...)
    - imagen-a-video : parte de un recorte REAL del producto y solo le agrega
                       movimiento. El aparato sigue siendo el de la foto.

APAGADO POR DEFECTO (`config.LTX_HABILITADO = False`). Cada clip son minutos y
hace falta RAM libre de verdad.

⚠️ DISCIPLINA DE VRAM — por qué este módulo se ve más paranoico que f9:

El modelo pesa 16.4 GB y la tarjeta tiene 16 GB. ComfyUI lo corre con *block
swap*: unas capas en VRAM, el resto transmitido desde la RAM del sistema. Eso
significa dos cosas que están implementadas acá y no son opcionales:

  a) NUNCA Flux y LTX cargados a la vez. Antes de generar video se le pide a
     ComfyUI que descargue todo (`/free`), y lo mismo al terminar. ComfyUI ya
     descarga por LRU solo, pero el pico DURANTE el intercambio es justo donde
     revienta.
  b) Hace falta RAM libre real (`config.LTX_RAM_LIBRE_MINIMA_GB`). Con menos,
     el block swap cae al archivo de paginación y un clip de minutos pasa a
     decenas de minutos. Se avisa antes de empezar, no después.

⚠️ El audio de LTX se DESCARTA. El modelo es audio-video y genera las dos
cosas en la misma pasada, pero la cadena de audio del pipeline está calibrada
a −14 LUFS con ducking y SFX por evento visual: ese audio solo estorba. El
latente de audio se genera igual porque el sampler recibe la pareja
(video, audio) como un solo latente, pero nunca se decodifica ni se conecta al
video final.

Uso:
    python f12_video_gen.py --estado
    python f12_video_gen.py --tag "#sol"
    python f12_video_gen.py --imagen assets/productos/kindle-paperwhite/frontal.png
    python f12_video_gen.py --prompt "steam rising from a cup" --nombre cafe
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import config
import f9_generar

BASE = f9_generar.BASE
INDICE = None  # se resuelve en _indice_ruta(); config puede no tener la carpeta aún

# Techo de duración de una tarjeta de PiP en segundos. Un clip de ambiente dura
# ~3 s; esto es solo un freno de emergencia para que ningún fallo de filtros
# pueda escribir un archivo sin fin. Ver el comentario en render_pip_video.
_TOPE_SEGUNDOS_TARJETA = 15.0


def _log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Comprobaciones previas
# ---------------------------------------------------------------------------
def _dir_modelos() -> Path:
    return config.DIR_COMFYUI / "models"


def archivos_faltantes() -> list:
    """Los 5 pesos de LTX que no están donde se los espera.

    Devuelve una lista de (ruta, GB aproximados) — vacía si está todo.
    """
    m = _dir_modelos()
    esperados = [
        (m / "unet" / config.LTX_UNET_GGUF, 16.39),
        (m / "text_encoders" / config.LTX_TEXT_ENCODER, 13.21),
        (m / "text_encoders" / config.LTX_TEXT_PROJECTION, 2.31),
        (m / "vae" / config.LTX_VAE_VIDEO, 1.45),
        (m / "checkpoints" / config.LTX_VAE_AUDIO, 0.36),
    ]
    return [(p, gb) for p, gb in esperados if not p.exists()]


def instalado() -> bool:
    """¿Están ComfyUI y los 5 pesos de LTX?"""
    if not (config.COMFY_PYTHON.exists() and config.COMFY_MAIN.exists()):
        return False
    return not archivos_faltantes()


def ram_libre_gb() -> float | None:
    """RAM libre del sistema en GB, o None si no se pudo medir.

    Sin psutil (no está en venv312 y no vale la pena agregarlo por esto): se
    consulta a Windows con ctypes, que es exacto y no cuesta nada.
    """
    try:
        import ctypes

        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        est = MEMORYSTATUSEX()
        est.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(est))
        return est.ullAvailPhys / (1024 ** 3)
    except Exception:
        return None


def _avisar_ram() -> bool:
    """Avisa (no bloquea) si hay poca RAM. Devuelve True si está holgada."""
    libre = ram_libre_gb()
    if libre is None:
        return True
    if libre < config.LTX_RAM_LIBRE_MINIMA_GB:
        _log(
            f"  AVISO: solo {libre:.1f} GB de RAM libres "
            f"(se recomiendan {config.LTX_RAM_LIBRE_MINIMA_GB:.0f}). El modelo de "
            "16 GB no entra en la VRAM y se transmite desde la RAM; con esta "
            "poca el intercambio cae al archivo de paginación y el clip puede "
            "tardar 5-10x más. Cerrar navegador y editores ayuda de verdad."
        )
        return False
    _log(f"  RAM libre: {libre:.1f} GB — alcanza.")
    return True


def liberar_memoria():
    """Le pide a ComfyUI que descargue TODOS los modelos de VRAM y RAM.

    Se llama antes y después de generar video. Motivo (§6 del traspaso): Flux y
    LTX nunca pueden estar cargados a la vez; el pico durante el intercambio es
    donde revienta. ComfyUI descarga por LRU solo, pero el LRU actúa cuando ya
    hizo falta la memoria — acá se adelanta.
    """
    # OJO: no usar f9_generar._post_json acá. `/free` responde 200 con el
    # cuerpo VACÍO (server.py: `return web.Response(status=200)`), y esa función
    # hace json.loads de la respuesta — reventaba con "Expecting value: line 1
    # column 1" DESPUÉS de que el servidor ya había liberado, así que la memoria
    # sí se liberaba pero el log decía que había fallado.
    cuerpo = json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8")
    req = urllib.request.Request(f"{BASE}/free", data=cuerpo,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            if r.status != 200:
                _log(f"  (ComfyUI respondió {r.status} al pedir liberar memoria)")
                return
        _log("  VRAM/RAM liberadas.")
    except Exception as e:
        # No es fatal: si el servidor recién arrancó, no hay nada que liberar.
        _log(f"  (no se pudo pedir liberar memoria: {e})")


# ---------------------------------------------------------------------------
# Workflow en formato API
# ---------------------------------------------------------------------------
# Construido a partir del workflow OFICIAL del propio Lightricks:
#   custom_nodes/ComfyUI-LTXVideo/example_workflows/2.3/
#     LTX-2.3_T2V_I2V_Single_Stage_Distilled_Full.json
# con dos sustituciones deliberadas:
#
#   1. El oficial carga un checkpoint todo-en-uno (`CheckpointLoaderSimple` con
#      ltx-2.3-22b-dev.safetensors, 40+ GB) que trae modelo + VAE + proyección
#      de texto juntos. Acá se usan las piezas sueltas: el transformer en GGUF
#      Q4 (16.4 GB en vez de 42) más VAE y proyección por separado. Esa es toda
#      la razón por la que esto entra en una 5070 Ti.
#   2. El oficial le aplica encima un LoRA de destilación
#      (ltx-2.3-22b-distilled-lora-384-1.1). Acá no hace falta: el GGUF elegido
#      YA es la variante `distilled-1.1`, con la destilación incorporada.
#
# Los nombres de cada nodo y de cada input se verificaron leyendo el código
# instalado (comfy_extras/nodes_lt.py, nodes_lt_audio.py, nodes_custom_sampler.py,
# nodes_video.py y custom_nodes/ComfyUI-GGUF/nodes.py), no de memoria.
def workflow_api(prompt: str, semilla: int, ancho: int, alto: int, frames: int,
                 prefijo: str, imagen: str = None) -> dict:
    wf = {
        # --- modelos -------------------------------------------------------
        "10": {"class_type": "UnetLoaderGGUF",
               "inputs": {"unet_name": config.LTX_UNET_GGUF}},
        # type="ltxv" hace que ComfyUI funda los dos archivos en un solo
        # encoder: Gemma-3 12B + la proyección de texto. Los DOS salen de
        # models/text_encoders/ (verificado en nodes.py:1038-1039).
        "11": {"class_type": "DualCLIPLoader",
               "inputs": {"clip_name1": config.LTX_TEXT_ENCODER,
                          "clip_name2": config.LTX_TEXT_PROJECTION,
                          "type": "ltxv", "device": "default"}},
        "12": {"class_type": "VAELoader",
               "inputs": {"vae_name": config.LTX_VAE_VIDEO}},
        "13": {"class_type": "LTXVAudioVAELoader",
               "inputs": {"ckpt_name": config.LTX_VAE_AUDIO}},

        # --- texto ---------------------------------------------------------
        "20": {"class_type": "CLIPTextEncode",
               "inputs": {"clip": ["11", 0], "text": prompt}},
        "21": {"class_type": "CLIPTextEncode",
               "inputs": {"clip": ["11", 0], "text": config.LTX_PROMPT_NEGATIVO}},
        "22": {"class_type": "LTXVConditioning",
               "inputs": {"positive": ["20", 0], "negative": ["21", 0],
                          "frame_rate": config.LTX_FPS}},

        # --- latentes ------------------------------------------------------
        # El latente de audio existe solo porque el sampler recibe la pareja
        # (video, audio) como un solo latente anidado. Se genera vacío y su
        # salida nunca se decodifica: el audio se descarta.
        "31": {"class_type": "LTXVEmptyLatentAudio",
               "inputs": {"frames_number": frames,
                          "frame_rate": int(config.LTX_FPS),
                          "batch_size": 1, "audio_vae": ["13", 0]}},
        "32": {"class_type": "LTXVConcatAVLatent",
               "inputs": {"video_latent": ["30", 0], "audio_latent": ["31", 0]}},

        # --- muestreo ------------------------------------------------------
        # El modelo va DIRECTO del cargador al guider, sin ModelSamplingLTXV.
        # Es lo que hace el workflow oficial de 2.3, y hay dos razones:
        # (a) con LTX_SIGMAS fijas el shift que calcularía ese nodo es
        #     redundante, y (b) recibiría el latente ya concatenado, que es un
        #     NestedTensor (video, audio) y no un tensor plano.
        "41": {"class_type": "CFGGuider",
               "inputs": {"model": ["10", 0], "positive": ["22", 0],
                          "negative": ["22", 1], "cfg": config.LTX_CFG}},
        "42": {"class_type": "KSamplerSelect",
               "inputs": {"sampler_name": config.LTX_SAMPLER}},
        # Sigmas fijas, no un schedule genérico: son las que corresponden a la
        # destilación 1.1 y vienen del workflow oficial. Con un schedule normal
        # de 8 pasos el resultado sale lavado.
        "43": {"class_type": "ManualSigmas",
               "inputs": {"sigmas": config.LTX_SIGMAS}},
        "44": {"class_type": "RandomNoise",
               "inputs": {"noise_seed": semilla}},
        "45": {"class_type": "SamplerCustomAdvanced",
               "inputs": {"noise": ["44", 0], "guider": ["41", 0],
                          "sampler": ["42", 0], "sigmas": ["43", 0],
                          "latent_image": ["32", 0]}},

        # --- salida --------------------------------------------------------
        "50": {"class_type": "LTXVSeparateAVLatent",
               "inputs": {"av_latent": ["45", 0]}},
        # Solo la salida 0 (video). La 1 es el audio y muere acá.
        "51": {"class_type": "VAEDecode",
               "inputs": {"samples": ["50", 0], "vae": ["12", 0]}},
        # `audio` es opcional en CreateVideo (nodes_video.py:138): al no
        # conectarlo, el clip sale mudo, que es exactamente lo que se quiere.
        "52": {"class_type": "CreateVideo",
               "inputs": {"images": ["51", 0], "fps": config.LTX_FPS}},
        "53": {"class_type": "SaveVideo",
               "inputs": {"video": ["52", 0], "filename_prefix": prefijo,
                          "format": "auto", "codec": "auto"}},
    }

    if imagen:
        # imagen-a-video: el primer fotograma es la foto real y el modelo solo
        # le agrega movimiento. `strength` por debajo de 1.0 deja que el modelo
        # se despegue un poco; 0.7 es el valor del workflow oficial.
        wf["29"] = {"class_type": "LoadImage", "inputs": {"image": imagen}}
        wf["30"] = {"class_type": "LTXVImgToVideo",
                    "inputs": {"positive": ["22", 0], "negative": ["22", 1],
                               "vae": ["12", 0], "image": ["29", 0],
                               "width": ancho, "height": alto, "length": frames,
                               "batch_size": 1,
                               "strength": config.LTX_STRENGTH_IMAGEN}}
        # Con LTXVImgToVideo el condicionamiento sale del propio nodo, ya
        # ajustado al primer fotograma.
        wf["41"]["inputs"]["positive"] = ["30", 0]
        wf["41"]["inputs"]["negative"] = ["30", 1]
        wf["32"]["inputs"]["video_latent"] = ["30", 2]
    else:
        wf["30"] = {"class_type": "EmptyLTXVLatentVideo",
                    "inputs": {"width": ancho, "height": alto,
                               "length": frames, "batch_size": 1}}

    return wf


# ---------------------------------------------------------------------------
# Caché e índice
# ---------------------------------------------------------------------------
def _indice_ruta() -> Path:
    return config.DIR_VIDEO_GENERADO_AUTO / "_indice.json"


def _leer_indice() -> dict:
    ruta = _indice_ruta()
    if ruta.exists():
        try:
            return json.loads(ruta.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _guardar_indice(indice: dict):
    config.DIR_VIDEO_GENERADO_AUTO.mkdir(parents=True, exist_ok=True)
    _indice_ruta().write_text(json.dumps(indice, ensure_ascii=False, indent=2),
                              encoding="utf-8")


def _clave(prompt: str, ancho: int, alto: int, frames: int, imagen: str) -> str:
    # El prompt NEGATIVO entra en la clave. Parece un detalle y no lo es: al
    # afinarlo (por ejemplo para sacar los subtítulos falsos que salían en
    # `#libros`) la caché seguiría devolviendo el clip viejo y daría la
    # impresión de que el cambio no sirvió.
    crudo = (f"{prompt}|{config.LTX_PROMPT_NEGATIVO}|{ancho}x{alto}x{frames}"
             f"|{config.LTX_UNET_GGUF}|{config.LTX_SIGMAS}|{imagen or ''}")
    return hashlib.sha1(crudo.encode("utf-8")).hexdigest()[:12]


def _semilla_de(texto: str) -> int:
    """Misma regla que f9: el mismo prompt da siempre el mismo clip."""
    return int(hashlib.sha1(texto.encode("utf-8")).hexdigest()[:12], 16)


def _slug(texto: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")
    return (s[:40] or "clip").rstrip("-")


# ---------------------------------------------------------------------------
# Generación
# ---------------------------------------------------------------------------
def _copiar_a_input(origen: Path) -> str:
    """Deja la imagen donde LoadImage la puede ver y devuelve su nombre.

    LoadImage solo lee de `comfyui/input/`. Copiar es más simple y más
    robusto que el endpoint /upload/image (que exige multipart), y el archivo
    queda ahí para que un re-render con caché no lo vuelva a copiar.
    """
    destino_dir = config.DIR_COMFYUI / "input"
    destino_dir.mkdir(parents=True, exist_ok=True)
    # Nombre estable derivado de la ruta: dos productos distintos con
    # `frontal.png` no se pisan entre sí.
    marca = hashlib.sha1(str(origen.resolve()).encode("utf-8")).hexdigest()[:8]
    nombre = f"ltx_{_slug(origen.stem)}_{marca}{origen.suffix.lower()}"
    destino = destino_dir / nombre
    if not destino.exists() or destino.stat().st_mtime < origen.stat().st_mtime:
        shutil.copy2(origen, destino)
    return nombre


def generar(prompt: str, nombre: str = None, tag: str = None,
            imagen: Path = None, ancho: int = None, alto: int = None,
            frames: int = None, servidor=None) -> Path | None:
    """Genera un clip (o devuelve el cacheado) y la ruta donde quedó.

    `imagen`: si se pasa, es imagen-a-video partiendo de esa foto. Si no,
    texto-a-video.
    """
    ancho = ancho or config.LTX_ANCHO
    alto = alto or config.LTX_ALTO
    frames = frames or config.LTX_FRAMES

    # El nº de frames tiene que ser múltiplo de 8 más 1; se corrige en silencio
    # en vez de fallar, porque un valor "casi bien" es un descuido, no un bug.
    if (frames - 1) % 8 != 0:
        frames = ((frames - 1) // 8) * 8 + 1
        _log(f"  (frames ajustado a {frames}: tiene que ser múltiplo de 8 más 1)")
    if ancho % 32 or alto % 32:
        ancho, alto = (ancho // 32) * 32, (alto // 32) * 32
        _log(f"  (tamaño ajustado a {ancho}x{alto}: múltiplos de 32)")

    texto = f"{prompt}, {config.LTX_PROMPT_ESTILO}"
    nombre = nombre or _slug(tag or prompt)
    imagen = Path(imagen) if imagen else None
    clave = _clave(texto, ancho, alto, frames, str(imagen) if imagen else "")

    config.DIR_VIDEO_GENERADO_AUTO.mkdir(parents=True, exist_ok=True)
    destino = config.DIR_VIDEO_GENERADO_AUTO / f"{nombre}_{clave}.mp4"

    if destino.exists() and destino.stat().st_size > 4096:
        _log(f"  [caché] {destino.name}")
        return destino

    faltan = archivos_faltantes()
    if faltan:
        _log("AVISO: faltan pesos de LTX — no se puede generar video:")
        for p, gb in faltan:
            _log(f"        {p.name} ({gb:.2f} GB)")
        _log("        Correr:  C:\\ai-video\\venv-comfy\\Scripts\\python.exe "
             "editor/descargar_ltx.py")
        return None

    if imagen is not None and not imagen.exists():
        _log(f"AVISO: no existe la imagen de partida {imagen}")
        return None

    propio = servidor is None
    servidor = servidor or f9_generar.ServidorCompartido()
    try:
        servidor.usar()
        # Antes de cargar 16 GB, sacar de la memoria lo que haya (Flux).
        liberar_memoria()
        _avisar_ram()

        nombre_imagen = _copiar_a_input(imagen) if imagen else None
        semilla = _semilla_de(texto + (str(imagen) if imagen else ""))
        wf = workflow_api(texto, semilla, ancho, alto, frames,
                          f"deviceshop-video/{nombre}", nombre_imagen)

        t0 = time.time()
        respuesta = f9_generar._post_json(
            "/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        prompt_id = respuesta.get("prompt_id")
        if not prompt_id:
            _log(f"AVISO: ComfyUI rechazó el workflow: {respuesta}")
            return None

        _log(f"  generando {frames} frames a {ancho}x{alto} "
             f"(esto tarda minutos, no segundos)...")
        # SaveVideo publica su resultado bajo la clave `images` igual que
        # SaveImage (PreviewVideo.as_dict en comfy_api/latest/_ui.py:433), así
        # que la espera de f9 sirve tal cual.
        salidas = f9_generar._esperar_resultado(prompt_id,
                                                config.LTX_GENERACION_TIMEOUT_S)
        f9_generar._descargar(salidas[0], destino)
        _log(f"  clip generado en {time.time() - t0:.1f}s -> {destino.name}")
    except Exception as e:
        _log(f"AVISO: falló la generación del clip '{nombre}': {e}")
        return None
    finally:
        # Dejar la memoria limpia pase lo que pase: si después de esto corre
        # otra imagen con Flux, no puede encontrarse los 16 GB de LTX puestos.
        try:
            liberar_memoria()
        except Exception:
            pass
        if propio:
            servidor.cerrar()

    indice = _leer_indice()
    indice[clave] = {
        "archivo": str(destino.relative_to(config.RAIZ_PROYECTO)).replace("\\", "/"),
        "prompt": texto,
        "tag": tag or "",
        "nombre": nombre,
        "semilla": semilla,
        "tamano": f"{ancho}x{alto}",
        "frames": frames,
        "fps": config.LTX_FPS,
        "desde_imagen": str(imagen) if imagen else "",
    }
    _guardar_indice(indice)
    return destino


def prompt_para_tag(tag: str, contexto_guion: str = "") -> str | None:
    """Prompt de MOVIMIENTO para un concepto, enriquecido con el guion.

    Igual que en f9: sin el contexto, dos videos que mencionan "sol" darían
    exactamente el mismo clip.
    """
    base = config.LTX_PROMPTS_POR_TAG.get(tag)
    if not base:
        return None
    frase = " ".join(contexto_guion.split())[:110].strip(" ,.")
    return f"{base}, scene inspired by: {frase}" if frase else base


def version_manual(tag: str) -> Path | None:
    """Clip puesto a mano por José para esta etiqueta (gana sobre LTX).

    Mismo principio que `f9_generar.version_manual`: si el clip generado no
    convenció y lo rehizo en otra herramienta, ese es el bueno.
    """
    dir_manual = config.DIR_VIDEO_GENERADO / "manual"
    if not dir_manual.is_dir():
        return None
    nombre = _slug(tag.lstrip("#"))
    for ext in (".mp4", ".mov", ".webm"):
        cand = dir_manual / f"{nombre}{ext}"
        if cand.exists():
            return cand
    return None


def generar_para_tag(tag: str, contexto_guion: str = "", servidor=None) -> Path | None:
    """Clip de ambiente para una etiqueta. Prioridad: manual > LTX."""
    manual = version_manual(tag)
    if manual is not None:
        _log(f"  [manual] {manual.name} para {tag}")
        return manual
    prompt = prompt_para_tag(tag, contexto_guion)
    if prompt is None:
        _log(f"  (sin prompt de video para {tag}: se queda en imagen fija)")
        return None
    return generar(prompt, nombre=_slug(tag.lstrip("#")), tag=tag, servidor=servidor)


def generar_desde_foto(foto: Path, contexto_guion: str = "",
                       servidor=None) -> Path | None:
    """Le da movimiento a una foto REAL de producto.

    Este es el caso de más valor: el Kindle sigue siendo el Kindle de la foto,
    LTX solo mueve la luz. Nada de pedirle que invente el aparato.
    """
    foto = Path(foto)
    frase = " ".join(contexto_guion.split())[:110].strip(" ,.")
    prompt = config.LTX_PROMPT_DESDE_FOTO
    if frase:
        prompt = f"{prompt}, scene inspired by: {frase}"
    return generar(prompt, nombre=f"foto-{_slug(foto.stem)}", imagen=foto,
                   servidor=servidor)


# ---------------------------------------------------------------------------
# De clip suelto a tarjeta de PiP componible
# ---------------------------------------------------------------------------
def render_pip_video(ruta_clip: Path, ruta_salida: Path, ancho=400, alto=520):
    """Convierte un clip de LTX en una tarjeta de PiP con alfa, componible.

    El compositor (`f4_retencion.componer`) ya sabe manejar overlays de video,
    pero espera **alfa**: los usa para las animaciones, que son ProRes 4444.
    LTX no genera alfa y sus clips son rectángulos duros, así que hay que
    fabricarle el marco y las esquinas redondeadas — es exactamente lo que
    anticipaba la §6 del PLAN-EDITOR-VISUAL-V2.

    El resultado es visualmente el mismo que `f6_overlays.render_pip_producto`
    (esquinas redondeadas, borde blanco, acento cian), pero en movimiento. Se
    reutilizan sus constantes de color y sus medidas para que un PiP de foto y
    uno de video no se vean como de dos videos distintos.

    Devuelve (ancho, alto) de la tarjeta, igual que render_pip_producto.
    """
    from PIL import Image, ImageDraw

    import f6_overlays  # perezoso: f6 también importa de acá

    radio, borde = 36, 10
    w_tarjeta, h_tarjeta = ancho + borde * 2, alto + borde * 2

    # Marco CON UN HUECO: blanco redondeado con filo cian, y transparente justo
    # donde va el video. Al superponerlo encima del clip, el hueco deja ver el
    # video y el blanco tapa las esquinas cuadradas que le sobran.
    marco = Image.new("RGBA", (w_tarjeta, h_tarjeta), (0, 0, 0, 0))
    d = ImageDraw.Draw(marco)
    d.rounded_rectangle([0, 0, w_tarjeta - 1, h_tarjeta - 1],
                        radius=radio + borde, fill=f6_overlays.BLANCO)
    d.rounded_rectangle([0, 0, w_tarjeta - 1, h_tarjeta - 1],
                        radius=radio + borde, outline=f6_overlays.CIAN, width=3)
    hueco = Image.new("L", (w_tarjeta, h_tarjeta), 0)
    ImageDraw.Draw(hueco).rounded_rectangle(
        [borde, borde, borde + ancho - 1, borde + alto - 1], radius=radio, fill=255)
    # Restar el hueco del alfa del marco: donde el hueco vale 255, alfa 0.
    alfa = marco.getchannel("A")
    marco.putalpha(Image.composite(Image.new("L", marco.size, 0), alfa, hueco))

    ruta_marco = ruta_salida.with_suffix(".marco.png")
    marco.save(ruta_marco)

    # scale con force_original_aspect_ratio=increase + crop = "cubrir y recortar
    # al centro", el mismo encuadre que hace render_pip_producto con PIL.
    filtro = (
        f"[0:v]scale={ancho}:{alto}:force_original_aspect_ratio=increase,"
        f"crop={ancho}:{alto},format=rgba,"
        f"pad={w_tarjeta}:{h_tarjeta}:{borde}:{borde}:color=#00000000[vid];"
        # El marco entra como UN SOLO fotograma (sin `-loop 1`) y overlay lo
        # sostiene con su `eof_action=repeat`, que es el comportamiento por
        # defecto. Así manda el video, que es finito.
        #
        # ⚠️ NO volver a poner `-loop 1` en el marco. Se probó y el PNG en
        # bucle es un stream INFINITO que pasa a mandar sobre el video:
        # `-shortest` no lo frena, y la primera prueba escribió 39 GB con
        # 1h24m de video a partir de un clip de 3 segundos antes de cortarla.
        f"[vid][1:v]overlay=0:0:format=auto:eof_action=repeat[out]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", str(ruta_clip),
        "-i", str(ruta_marco),
        "-filter_complex", filtro, "-map", "[out]",
        # ProRes 4444 (profile 4) con yuva444p10le: es el formato con alfa que
        # el compositor ya consume para las animaciones. No cambiar por webm:
        # f4_retencion espera este.
        "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
        "-an",                       # el audio de LTX se descarta acá también
        # Tope duro, cinturón además de tirantes: un clip de ambiente nunca
        # pasa de unos segundos, así que si algo vuelve a hacer que el stream
        # no termine, ffmpeg corta acá en vez de llenar el disco de noche.
        "-t", f"{_TOPE_SEGUNDOS_TARJETA:.2f}",
        str(ruta_salida),
    ]
    # stderr a un archivo, nunca a un pipe sin lector (trampa #5).
    log = ruta_salida.with_suffix(".ffmpeg.log")
    with open(log, "wb") as flog:
        r = subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=flog, stderr=flog)
    if r.returncode != 0 or not ruta_salida.exists():
        cola = log.read_text(encoding="utf-8", errors="replace")[-1200:]
        raise RuntimeError(f"ffmpeg no pudo armar la tarjeta de video:\n{cola}")

    ruta_marco.unlink(missing_ok=True)
    log.unlink(missing_ok=True)
    return w_tarjeta, h_tarjeta


def tarjeta_para_tag(tag: str, contexto_guion: str, dir_tmp: Path, indice: int,
                     servidor=None) -> tuple | None:
    """Clip de ambiente ya convertido en tarjeta de PiP lista para componer.

    Devuelve (ruta_mov, ancho, alto) o None. Es lo que consume f6_overlays.
    """
    clip = generar_para_tag(tag, contexto_guion, servidor=servidor)
    if clip is None:
        return None
    destino = dir_tmp / f"ov_inserto_video_{indice}.mov"
    try:
        w, h = render_pip_video(clip, destino)
    except Exception as e:
        _log(f"AVISO: no se pudo armar la tarjeta de video para {tag}: {e}")
        return None
    return destino, w, h


def main():
    ap = argparse.ArgumentParser(
        description="Generación de clips de video con ComfyUI + LTX 2.3")
    ap.add_argument("--estado", action="store_true", help="Diagnóstico de la instalación")
    ap.add_argument("--prompt", type=str, default=None)
    ap.add_argument("--tag", type=str, default=None, help="Etiqueta de ambiente, ej. '#sol'")
    ap.add_argument("--imagen", type=str, default=None,
                    help="Foto de partida para imagen-a-video")
    ap.add_argument("--guion", type=str, default="", help="Contexto del guion")
    ap.add_argument("--nombre", type=str, default=None)
    ap.add_argument("--frames", type=int, default=None)
    args = ap.parse_args()

    if args.estado:
        libre = ram_libre_gb()
        print(f"LTX habilitado por defecto: {config.LTX_HABILITADO}")
        print(f"ComfyUI:                    {config.COMFY_MAIN} "
              f"({config.COMFY_MAIN.exists()})")
        print(f"Servidor vivo:              {f9_generar.servidor_vivo()}")
        print(f"RAM libre:                  "
              f"{f'{libre:.1f} GB' if libre is not None else '?'} "
              f"(mínimo recomendado {config.LTX_RAM_LIBRE_MINIMA_GB:.0f} GB)")
        faltan = archivos_faltantes()
        m = _dir_modelos()
        print("Pesos:")
        for p, gb in [(m / "unet" / config.LTX_UNET_GGUF, 16.39),
                      (m / "text_encoders" / config.LTX_TEXT_ENCODER, 13.21),
                      (m / "text_encoders" / config.LTX_TEXT_PROJECTION, 2.31),
                      (m / "vae" / config.LTX_VAE_VIDEO, 1.45),
                      (m / "checkpoints" / config.LTX_VAE_AUDIO, 0.36)]:
            real = p.stat().st_size / 1e9 if p.exists() else 0
            print(f"  [{'x' if p.exists() else ' '}] {p.name:<52} "
                  f"{real:6.2f}/{gb:.2f} GB")
        print(f"Instalado completo:         {not faltan}")
        cache = config.DIR_VIDEO_GENERADO_AUTO
        n = len(list(cache.glob("*.mp4"))) if cache.exists() else 0
        print(f"Caché:                      {cache} ({n} clips)")
        print(f"Etiquetas con movimiento:   "
              f"{', '.join(sorted(config.LTX_PROMPTS_POR_TAG))}")
        return

    if args.imagen:
        ruta = generar_desde_foto(Path(args.imagen), args.guion)
    elif args.tag:
        ruta = generar_para_tag(args.tag, args.guion)
    elif args.prompt:
        ruta = generar(args.prompt, nombre=args.nombre, frames=args.frames)
    else:
        ap.error("indica --tag, --prompt, --imagen o --estado")
        return

    print(f"-> {ruta}" if ruta else "-> falló")
    sys.exit(0 if ruta else 1)


if __name__ == "__main__":
    main()
