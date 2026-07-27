"""Descarga los pesos de LTX 2.3 22B (Q4) a los modelos de ComfyUI.

Se corre con el interprete de ComfyUI, NO con el del pipeline:

    C:\\ai-video\\venv-comfy\\Scripts\\python.exe editor/descargar_ltx.py

Son ~33 GB en 4 archivos. Es resumible: si se corta, volver a correrlo sigue
donde iba (huggingface_hub deja los parciales en la carpeta `.cache` del
destino). Los archivos que ya estan completos se saltan sin bajar nada.

Cada archivo baja a una carpeta de descarga aparte y recien despues se mueve
a su destino final dentro de `models/`. Asi ComfyUI nunca ve un archivo a
medio bajar, y el movimiento es instantaneo porque es el mismo disco.
"""

from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

from huggingface_hub import hf_hub_download

MODELOS = Path(r"C:\ai-video\comfyui\models")
DESCARGAS = Path(r"C:\ai-video\ltx-descarga")

# (repo, archivo dentro del repo, subcarpeta de models/, GB esperados)
ARCHIVOS = [
    (
        "Kijai/LTX2.3_comfy",
        "vae/LTX23_video_vae_bf16.safetensors",
        "vae",
        1.45,
    ),
    (
        "Kijai/LTX2.3_comfy",
        "text_encoders/ltx-2.3_text_projection_bf16.safetensors",
        "text_encoders",
        2.31,
    ),
    # El VAE de audio NO estaba en la lista de 4 archivos del traspaso, pero
    # hace falta igual aunque el audio se tire a la basura: LTX 2.3 es un
    # modelo audio-video y el sampler recibe UN latente que es la pareja
    # (video, audio) — ver LTXVConcatAVLatent en comfy_extras/nodes_lt.py.
    # El nodo que arma el latente de audio vacio (LTXVEmptyLatentAudio) exige
    # el VAE de audio solo para leerle la configuracion (canales, bins de
    # frecuencia). Son 0.36 GB: mas barato bajarlo que pelear contra el diseno
    # del modelo. El audio generado se descarta despues, al no conectarlo al
    # nodo que arma el video.
    #
    # Va a `checkpoints/`, NO a `vae/`, aunque sea un VAE: el nodo que lo carga
    # (LTXVAudioVAELoader, comfy_extras/nodes_lt_audio.py:19) lista la carpeta
    # `checkpoints`. Verificado ademas que el archivo trae los prefijos
    # `audio_vae.`/`vocoder.` y el `config` en metadata que ese nodo espera
    # (leido de la cabecera safetensors por rango HTTP, sin bajar el archivo).
    (
        "Kijai/LTX2.3_comfy",
        "vae/LTX23_audio_vae_bf16.safetensors",
        "checkpoints",
        0.36,
    ),
    (
        "GitMylo/LTX-2-comfy_gemma_fp8_e4m3fn",
        "gemma_3_12B_it_fp8_e4m3fn.safetensors",
        "text_encoders",
        13.21,
    ),
    (
        "unsloth/LTX-2.3-GGUF",
        "distilled-1.1/ltx-2.3-22b-distilled-1.1-UD-Q4_K_M.gguf",
        "unet",
        16.39,
    ),
]


def _log(mensaje: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {mensaje}", flush=True)


REINTENTOS = 20
ESPERA_ENTRE_REINTENTOS = 30  # segundos


def descargar_uno(repo: str, archivo: str, destino_sub: str, gb: float) -> Path:
    nombre = archivo.split("/")[-1]
    destino = MODELOS / destino_sub / nombre

    if destino.exists():
        real = destino.stat().st_size / 1e9
        # Tolerancia amplia: los GB de la tabla son aproximados a dos decimales.
        if abs(real - gb) < 0.2:
            _log(f"YA ESTA  {destino_sub}/{nombre}  ({real:.2f} GB)")
            return destino
        _log(
            f"OJO      {destino_sub}/{nombre} existe con {real:.2f} GB pero se "
            f"esperaban {gb:.2f} GB. Se vuelve a bajar."
        )
        destino.unlink()

    _log(f"BAJANDO  {repo} :: {archivo}  ({gb:.2f} GB)")

    # Esto corre de noche sin nadie mirando: un corte de red no puede dejar la
    # descarga muerta. hf_hub_download retoma desde el byte donde iba, asi que
    # reintentar es barato — no vuelve a empezar el archivo.
    ultimo_error: Exception | None = None
    for intento in range(1, REINTENTOS + 1):
        try:
            bajado = Path(
                hf_hub_download(
                    repo_id=repo,
                    filename=archivo,
                    local_dir=str(DESCARGAS / repo.replace("/", "__")),
                )
            )
            break
        except Exception as exc:  # noqa: BLE001 — red, 5xx, rate limit, disco
            ultimo_error = exc
            _log(
                f"         intento {intento}/{REINTENTOS} fallo "
                f"({type(exc).__name__}: {exc}). "
                f"Reintento en {ESPERA_ENTRE_REINTENTOS}s desde donde iba."
            )
            time.sleep(ESPERA_ENTRE_REINTENTOS)
    else:
        raise RuntimeError(
            f"{REINTENTOS} intentos fallidos con {repo} :: {archivo}"
        ) from ultimo_error

    destino.parent.mkdir(parents=True, exist_ok=True)
    # shutil.move dentro del mismo volumen es un rename: instantaneo.
    shutil.move(str(bajado), str(destino))
    _log(f"LISTO    -> {destino}  ({destino.stat().st_size / 1e9:.2f} GB)")
    return destino


def main() -> int:
    DESCARGAS.mkdir(parents=True, exist_ok=True)
    total = sum(gb for *_, gb in ARCHIVOS)
    _log(f"LTX 2.3 22B Q4 — {len(ARCHIVOS)} archivos, ~{total:.1f} GB en total")

    for repo, archivo, destino_sub, gb in ARCHIVOS:
        try:
            descargar_uno(repo, archivo, destino_sub, gb)
        except Exception as exc:  # noqa: BLE001 — se reporta y se sigue
            _log(f"FALLO    {repo} :: {archivo}\n         {type(exc).__name__}: {exc}")
            _log("         Volver a correr este script retoma donde iba.")
            return 1

    _log("Los 4 archivos estan en su lugar.")

    # La carpeta de descarga queda con los `.cache` de huggingface_hub; ya no
    # sirven para nada porque los archivos se movieron.
    try:
        shutil.rmtree(DESCARGAS)
        _log(f"Limpiada la carpeta de descarga {DESCARGAS}")
    except OSError as exc:
        _log(f"No se pudo limpiar {DESCARGAS}: {exc}. Se puede borrar a mano.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
