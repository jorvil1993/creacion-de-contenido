"""Instala el pack en assets/sfx y deja medido el punto de impacto de TODO.

Los 13 archivos que ya estaban también se miden: si no, el pipeline tendría
media biblioteca con alineación conocida y la otra media sin ella, y habría que
tratarlas distinto en el código.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

FFMPEG = r"C:\Users\devic\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
SR = 48000
CATEGORIAS_BUILD = {"riser", "reverso"}

# Los 13 originales del pack de la sesión B, que no pasaron por el procesado.
CATEGORIA_ORIGINALES = {
    "whoosh_deep_1.mp3": "whoosh", "whoosh_deep_2.mp3": "whoosh",
    "whoosh_rapido.mp3": "whoosh", "whoosh_simple.mp3": "whoosh",
    "transicion_corte.mp3": "whoosh", "transicion_swipe.mp3": "whoosh",
    "impacto_dramatico.mp3": "impacto", "impacto_grave.mp3": "impacto",
    "impacto_hit.mp3": "impacto",
    "notificacion_1.mp3": "notificacion", "notificacion_chime.mp3": "notificacion",
    "notificacion_success.mp3": "notificacion",
    "pop.mp3": "ui",
}


def leer(p):
    r = subprocess.run([FFMPEG, "-v", "error", "-i", str(p), "-f", "f32le",
                        "-ac", "2", "-ar", str(SR), "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def medir(p, categoria):
    x = leer(p)
    mono = x.mean(axis=1)
    n = max(1, int(SR * 0.02))
    env = np.sqrt(np.convolve(mono ** 2, np.ones(n) / n, mode="same"))
    if env.max() <= 0:
        return 0.0, len(x) / SR
    altos = np.nonzero(env >= env.max() * 0.85)[0]
    i = altos[-1] if categoria in CATEGORIAS_BUILD else altos[0]
    return round(i / SR, 3), round(len(x) / SR, 3)


def familia(punto_s):
    if punto_s <= 0.12:
        return "golpe"
    return "swell" if punto_s <= 1.0 else "build"


def main():
    origen_cc0, origen_sint, destino = (Path(a) for a in sys.argv[1:4])
    destino.mkdir(parents=True, exist_ok=True)

    entradas = {}
    for carpeta, cat_json in ((origen_cc0, "_catalogo.json"),
                              (origen_sint, "_catalogo_sintetizado.json")):
        for c in json.loads((carpeta / cat_json).read_text("utf-8")):
            shutil.copy2(carpeta / c["archivo"], destino / c["archivo"])
            entradas[c["archivo"]] = c

    for nombre, cat in CATEGORIA_ORIGINALES.items():
        punto, dur = medir(destino / nombre, cat)
        entradas[nombre] = {"archivo": nombre, "categoria": cat,
                            "familia": familia(punto), "punto": punto,
                            "duracion": dur, "origen": "pack-inicial"}

    alineacion = {
        n: {"punto": c["punto"], "familia": c["familia"],
            "categoria": c["categoria"], "duracion": c["duracion"]}
        for n, c in sorted(entradas.items())
    }
    (destino / "_alineacion.json").write_text(
        json.dumps(alineacion, indent=2, ensure_ascii=False), encoding="utf-8")

    por_cat = {}
    for c in entradas.values():
        por_cat.setdefault(c["categoria"], []).append(c["archivo"])
    for cat in sorted(por_cat):
        print(f"{cat:<14} {len(por_cat[cat]):3d}")
    print(f"\nTOTAL {len(entradas)} sonidos en {destino}")


if __name__ == "__main__":
    main()
