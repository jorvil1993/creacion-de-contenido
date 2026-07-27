"""Descarga los pesos de LTX 2.3 22B (Q4) a los modelos de ComfyUI.

Se corre con el interprete de ComfyUI, NO con el del pipeline:

    C:\\ai-video\\venv-comfy\\Scripts\\python.exe editor/descargar_ltx.py

Son ~33.7 GB en 5 archivos. Es resumible: si se corta, volver a correrlo sigue
donde iba (huggingface_hub deja los parciales en la carpeta `.cache` del
destino). Los archivos que ya estan completos se saltan sin bajar nada.

Cada archivo baja a una carpeta de descarga aparte y recien despues se mueve
a su destino final dentro de `models/`. Asi ComfyUI nunca ve un archivo a
medio bajar, y el movimiento es instantaneo porque es el mismo disco.

⚠️ POR QUE ESTO ES MAS COMPLICADO QUE UN `hf download` A SECAS

Corre de noche sin nadie mirando, y la primera version murio en silencio: el
transporte Xet de huggingface_hub 1.24 se colgo bajando el encoder de Gemma
con CERO conexiones TCP abiertas y 0 bytes escritos durante 22 minutos. No
lanzo ninguna excepcion, asi que un `try/except` con reintentos NO lo salva:
la llamada simplemente no vuelve nunca.

Por eso cada descarga corre en un SUBPROCESO vigilado por este proceso padre,
que mira crecer el archivo en disco. Si deja de crecer, mata al hijo y
reintenta — retomando desde el byte donde iba, no desde cero. Un cuelgue es
indistinguible de una descarga muy lenta desde adentro; desde afuera, mirando
el disco, se ve enseguida.

Se fuerza ademas el transporte HTTP clasico (HF_HUB_DISABLE_XET=1), que es el
que si funciono para los dos primeros archivos.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

MODELOS = Path(r"C:\ai-video\comfyui\models")
DESCARGAS = Path(r"C:\ai-video\ltx-descarga")
LOG_HIJO = Path(r"C:\ai-video\ltx-descarga.hijo.log")

REINTENTOS = 20
ESPERA_ENTRE_REINTENTOS = 20     # segundos antes de volver a intentar
ESTANCADO_S = 180                # sin crecer un solo byte -> se da por colgado
INTERVALO_VIGILANCIA_S = 10

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


def _carpeta_de(repo: str) -> Path:
    return DESCARGAS / repo.replace("/", "__")


def _bytes_en(carpeta: Path) -> int:
    """Todo lo escrito hasta ahora, incluidos los `.incomplete` del `.cache`."""
    if not carpeta.exists():
        return 0
    total = 0
    for p in carpeta.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            pass
    return total


def _lanzar_hijo(repo: str, archivo: str, carpeta: Path) -> subprocess.Popen:
    guion = (
        "import sys\n"
        "from huggingface_hub import hf_hub_download\n"
        "print(hf_hub_download(repo_id=sys.argv[1], filename=sys.argv[2], "
        "local_dir=sys.argv[3]))\n"
    )
    entorno = dict(os.environ)
    # El transporte Xet es el que se colgo. El HTTP clasico bajo bien los dos
    # primeros archivos.
    entorno["HF_HUB_DISABLE_XET"] = "1"
    entorno["HF_HUB_DOWNLOAD_TIMEOUT"] = "30"
    entorno["PYTHONUNBUFFERED"] = "1"

    # stdout/stderr a un ARCHIVO, nunca a un pipe sin lector: es la trampa #5
    # ya pagada en este proyecto (un hijo que llena el buffer del SO se
    # bloquea para siempre).
    flog = open(LOG_HIJO, "ab")
    proc = subprocess.Popen(
        [sys.executable, "-c", guion, repo, archivo, str(carpeta)],
        stdin=subprocess.DEVNULL, stdout=flog, stderr=flog,
    )
    proc._flog = flog  # type: ignore[attr-defined]
    return proc


def _matar(proc: subprocess.Popen) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=15)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=15)
    flog = getattr(proc, "_flog", None)
    if flog is not None and not flog.closed:
        flog.close()


def _intentar_descarga(repo: str, archivo: str, gb: float) -> bool:
    """Un intento vigilado. True si el hijo termino bien."""
    carpeta = _carpeta_de(repo)
    carpeta.mkdir(parents=True, exist_ok=True)

    proc = _lanzar_hijo(repo, archivo, carpeta)
    ultimo_tamano = _bytes_en(carpeta)
    ultimo_avance = time.time()
    ultimo_aviso = 0.0

    try:
        while True:
            try:
                proc.wait(timeout=INTERVALO_VIGILANCIA_S)
                return proc.returncode == 0
            except subprocess.TimeoutExpired:
                pass

            ahora = time.time()
            tamano = _bytes_en(carpeta)
            if tamano > ultimo_tamano:
                ultimo_tamano = tamano
                ultimo_avance = ahora
                if ahora - ultimo_aviso >= 60:
                    ultimo_aviso = ahora
                    _log(f"         {tamano / 1e9:5.2f} / {gb:.2f} GB")
            elif ahora - ultimo_avance > ESTANCADO_S:
                _log(
                    f"         COLGADO: {ESTANCADO_S}s sin escribir un byte. "
                    "Se corta y se reintenta desde donde iba."
                )
                _matar(proc)
                return False
    finally:
        if proc.poll() is None:
            _matar(proc)
        flog = getattr(proc, "_flog", None)
        if flog is not None and not flog.closed:
            flog.close()


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
    for intento in range(1, REINTENTOS + 1):
        if _intentar_descarga(repo, archivo, gb):
            break
        _log(f"         intento {intento}/{REINTENTOS} sin exito; "
             f"otro en {ESPERA_ENTRE_REINTENTOS}s")
        time.sleep(ESPERA_ENTRE_REINTENTOS)
    else:
        raise RuntimeError(f"{REINTENTOS} intentos fallidos con {repo} :: {archivo}")

    bajado = _carpeta_de(repo) / archivo
    if not bajado.exists():
        raise RuntimeError(f"El hijo dijo que termino pero no esta {bajado}")

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
        except Exception as exc:  # noqa: BLE001 — se reporta y se corta
            _log(f"FALLO    {repo} :: {archivo}\n         {type(exc).__name__}: {exc}")
            _log("         Volver a correr este script retoma donde iba.")
            return 1

    _log(f"Los {len(ARCHIVOS)} archivos estan en su lugar.")

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
