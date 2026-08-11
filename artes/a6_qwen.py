"""Edicion de foto de producto con Qwen-Image-Edit-2511 via la API de ComfyUI.

Toma una foto real del producto y la recompone en otra escena. El aparato se
mantiene: es lo que Flux NO sabe hacer (esta documentado que no conoce el diseno
real de un Kindle, ver assets/generado/kindle-paperwhite/README.md).

Los nombres de nodo y de parametro salen de consultar /object_info del servidor
en marcha, no de memoria — misma regla que se siguio para el workflow de Flux
(contexto/BITACORA-B.md).

Requiere ComfyUI escuchando:
    C:\\ai-video\\venv-comfy\\Scripts\\python.exe C:\\ai-video\\comfyui\\main.py --port 8188
"""
from __future__ import annotations

import json
import time
import urllib.request
import uuid
from pathlib import Path

SERVIDOR = "http://127.0.0.1:8188"
ENTRADA_COMFY = Path(r"C:\ai-video\comfyui\input")
SALIDA_COMFY = Path(r"C:\ai-video\comfyui\output")

MODELO = "qwen_image_edit_2511_fp8mixed.safetensors"
TEXTO = "qwen_2.5_vl_7b_fp8_scaled.safetensors"
VAE = "qwen_image_vae.safetensors"

# Lo que NO queremos que aparezca. El primer punto es el que mas duele en este
# proyecto: los modelos tienden a escribir texto inventado en la pantalla, que es
# justo el defecto que ya tienen varios artes publicados.
NEGATIVO = (
    "texto ilegible, letras deformes, marca de agua, logotipo falso, "
    "manos deformes, baja calidad, borroso, distorsion del producto"
)


def _pedir(ruta: str, datos: dict | None = None) -> dict:
    cuerpo = json.dumps(datos).encode() if datos is not None else None
    req = urllib.request.Request(f"{SERVIDOR}{ruta}", data=cuerpo)
    if cuerpo:
        req.add_header("Content-Type", "application/json")
    return json.load(urllib.request.urlopen(req, timeout=120))


def workflow(imagen: str, prompt: str, semilla: int, pasos: int = 20,
             denoise: float = 1.0, mascara: str | None = None) -> dict:
    """Grafo en formato API. Cada clave es un nodo; los enlaces son [id, salida].

    Sin `mascara`: comportamiento original -- denoise se aplica parejo a toda
    la imagen (con denoise=1.0 el producto se redibuja, ver
    artes-qwen-pipeline.md).

    Con `mascara` (nombre de archivo ya copiado a ENTRADA_COMFY, tipicamente
    el alfa RGBA que ya saca a2_recorte.recortar() con rembg): se agrega
    SetLatentNoiseMask para que el sampler SOLO toque la zona de fondo,
    dejando el producto intacto sin importar el denoise. Nodos confirmados
    contra /object_info del servidor real, 2026-08-03 (LoadImageMask,
    InvertMask, GrowMask, SetLatentNoiseMask): el alfa de rembg es
    producto=opaco(1)/fondo=transparente(0), por eso se invierte antes de
    usarlo como mascara de ruido (1 = se regenera).
    """
    grafo = {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": MODELO, "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": TEXTO, "type": "qwen_image"}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": VAE}},
        "4": {"class_type": "LoadImage", "inputs": {"image": imagen}},
        # El nodo Plus recibe la foto por image1: asi el modelo edita ESA imagen
        # en vez de generar una nueva parecida.
        "5": {"class_type": "TextEncodeQwenImageEditPlus",
              "inputs": {"clip": ["2", 0], "prompt": prompt,
                         "vae": ["3", 0], "image1": ["4", 0]}},
        "6": {"class_type": "TextEncodeQwenImageEditPlus",
              "inputs": {"clip": ["2", 0], "prompt": NEGATIVO,
                         "vae": ["3", 0], "image1": ["4", 0]}},
        "7": {"class_type": "VAEEncode",
              "inputs": {"pixels": ["4", 0], "vae": ["3", 0]}},
        "9": {"class_type": "VAEDecode",
              "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "SaveImage",
               "inputs": {"images": ["9", 0], "filename_prefix": "arte_qwen"}},
    }

    latent_para_sampler = ["7", 0]
    if mascara:
        grafo["11"] = {"class_type": "LoadImageMask",
                        "inputs": {"image": mascara, "channel": "alpha"}}
        grafo["12"] = {"class_type": "InvertMask", "inputs": {"mask": ["11", 0]}}
        # +8px: sin esto queda una costura visible justo en el borde del
        # producto -- un margen chico deja que el fondo nuevo se funda con
        # el borde en vez de pegar contra un corte duro.
        grafo["13"] = {"class_type": "GrowMask",
                        "inputs": {"mask": ["12", 0], "expand": 8, "tapered_corners": True}}
        grafo["14"] = {"class_type": "SetLatentNoiseMask",
                        "inputs": {"samples": ["7", 0], "mask": ["13", 0]}}
        latent_para_sampler = ["14", 0]

    grafo["8"] = {"class_type": "KSampler",
                  "inputs": {"model": ["1", 0], "seed": semilla, "steps": pasos,
                             "cfg": 2.5, "sampler_name": "euler", "scheduler": "simple",
                             "positive": ["5", 0], "negative": ["6", 0],
                             "latent_image": latent_para_sampler, "denoise": denoise}}
    return grafo


def editar(foto: Path, prompt: str, semilla: int = 1, pasos: int = 20,
           espera: int = 900, denoise: float = 1.0,
           mascara: Path | None = None) -> Path:
    """Manda la foto a Qwen y devuelve la imagen editada.

    Si `mascara` viene (el PNG con alfa del recorte), preserva el producto
    con SetLatentNoiseMask en vez de dejar que denoise=1.0 lo redibuje.
    """
    ENTRADA_COMFY.mkdir(parents=True, exist_ok=True)
    copia = ENTRADA_COMFY / foto.name
    if copia.resolve() != foto.resolve():
        copia.write_bytes(foto.read_bytes())

    nombre_mascara = None
    if mascara:
        copia_mascara = ENTRADA_COMFY / mascara.name
        if copia_mascara.resolve() != mascara.resolve():
            copia_mascara.write_bytes(mascara.read_bytes())
        nombre_mascara = copia_mascara.name

    cliente = str(uuid.uuid4())
    grafo = workflow(copia.name, prompt, semilla, pasos, denoise=denoise,
                      mascara=nombre_mascara)
    r = _pedir("/prompt", {"prompt": grafo, "client_id": cliente})
    pid = r["prompt_id"]
    print(f"  encolado {pid}", flush=True)

    t0 = time.time()
    while time.time() - t0 < espera:
        hist = _pedir(f"/history/{pid}")
        if pid in hist:
            salidas = hist[pid]["outputs"]
            for nodo in salidas.values():
                for img in nodo.get("images", []):
                    return SALIDA_COMFY / img["subfolder"] / img["filename"]
            raise RuntimeError(f"sin imagen en la salida: {salidas}")
        time.sleep(5)
    raise TimeoutError(f"Qwen no termino en {espera}s")
