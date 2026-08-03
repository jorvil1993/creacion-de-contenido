"""Descarga Qwen-Image-Edit-2511 a las carpetas de ComfyUI.

Nombres y tamanos verificados contra la API de Hugging Face el 2026-08-01, no
contra blogs. Se eligio fp8mixed sobre bf16 porque bf16 son 40,9 GB y no hay
forma de que corra en 16 GB de VRAM ni con descarga a RAM.

Es reanudable: si se corta, volver a correrlo sigue donde quedo.

    C:\\ai-video\\venv312\\Scripts\\python.exe artes/bajar_qwen.py
"""
from __future__ import annotations

import os
import sys
import time
import urllib.request
from pathlib import Path

COMFY = Path(r"C:\ai-video\comfyui\models")

ARCHIVOS = [
    (
        "Comfy-Org/Qwen-Image-Edit_ComfyUI",
        "split_files/diffusion_models/qwen_image_edit_2511_fp8mixed.safetensors",
        COMFY / "diffusion_models",
        20.53,
    ),
    (
        "Comfy-Org/Qwen-Image_ComfyUI",
        "split_files/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors",
        COMFY / "text_encoders",
        9.38,
    ),
    (
        "Comfy-Org/Qwen-Image_ComfyUI",
        "split_files/vae/qwen_image_vae.safetensors",
        COMFY / "vae",
        0.25,
    ),
]


def bajar(repo: str, remoto: str, carpeta: Path, gb: float) -> None:
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / Path(remoto).name
    url = f"https://huggingface.co/{repo}/resolve/main/{remoto}"

    # os.stat y no un listado del directorio: en Windows el tamano que reporta
    # el explorador de un archivo abierto en escritura miente.
    ya = destino.stat().st_size if destino.exists() else 0

    req = urllib.request.Request(url)
    if ya:
        req.add_header("Range", f"bytes={ya}-")

    try:
        resp = urllib.request.urlopen(req, timeout=120)
    except urllib.error.HTTPError as e:
        if e.code == 416:  # ya esta completo
            print(f"[ok] {destino.name} ya completo ({ya/1e9:.2f} GB)", flush=True)
            return
        raise

    total = ya + int(resp.headers.get("Content-Length", 0))
    modo = "ab" if ya else "wb"
    print(f"[bajando] {destino.name}  {ya/1e9:.2f}/{total/1e9:.2f} GB", flush=True)

    t0 = time.time()
    ultimo = 0.0
    with open(destino, modo) as f:
        while True:
            trozo = resp.read(1 << 22)  # 4 MB
            if not trozo:
                break
            f.write(trozo)
            ya += len(trozo)
            ahora = time.time()
            if ahora - ultimo > 20:
                vel = ya / max(ahora - t0, 1) / 1e6
                print(
                    f"    {ya/1e9:6.2f}/{total/1e9:.2f} GB  ({ya/total*100:4.1f}%)"
                    f"  {vel:5.1f} MB/s",
                    flush=True,
                )
                ultimo = ahora

    print(f"[ok] {destino.name}  {ya/1e9:.2f} GB", flush=True)


def main() -> None:
    total_gb = sum(a[3] for a in ARCHIVOS)
    print(f"Qwen-Image-Edit-2511 -> {COMFY}  ({total_gb:.1f} GB)", flush=True)
    for repo, remoto, carpeta, gb in ARCHIVOS:
        for intento in range(1, 6):
            try:
                bajar(repo, remoto, carpeta, gb)
                break
            except Exception as e:
                print(f"    fallo {intento}/5: {e}", flush=True)
                time.sleep(10)
        else:
            print(f"[ERROR] no se pudo bajar {remoto}", flush=True)
            sys.exit(1)
    print("LISTO", flush=True)


if __name__ == "__main__":
    main()
