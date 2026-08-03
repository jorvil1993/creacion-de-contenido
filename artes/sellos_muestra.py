"""Muestra los 3 sellos lado a lado para que Jose elija cual le convence.

    C:\\ai-video\\venv312\\Scripts\\python.exe artes/sellos_muestra.py
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from PIL import Image  # noqa: E402

from artes.a1_marca import Arte, render  # noqa: E402

SALIDA = RAIZ / "salida" / "artes"
TRABAJO = Path(r"C:\ai-video\artes")

CASOS = [
    ("anios", "navy", '¿UN REGALO QUE<br>SÍ VAYA A <span class="acento">USAR</span>?'),
    ("moto", "verde", 'TU BIBLIOTECA<br>SIN <span class="acento">ATADURAS</span>'),
    ("manos", "lila", 'COMPRÁ <span class="acento">SIN RIESGO</span><br>DESDE DONDE ESTÉS'),
    ("qr", "coral", 'COMPRÁ <span class="acento">SIN RIESGO</span><br>DESDE DONDE ESTÉS'),
]


def main() -> None:
    recorte = TRABAJO / "paperwhite-recortado.png"
    hechos = []
    for clave, escena, titular in CASOS:
        arte = Arte(
            titular=titular,
            producto="Kindle Paperwhite 16GB",
            escena=escena,
            recorte=recorte,
            recorte_alto=46,
            recorte_y=58,
            sello=clave,
        )
        hechos.append(render(arte, SALIDA / f"sello-{clave}.jpg"))
        print(f"{clave:6} {escena:7} {hechos[-1].name}")

    s = 560
    n = len(hechos)
    hoja = Image.new("RGB", (n * s + (n + 1) * 14, s + 28), "#151515")
    for i, f in enumerate(hechos):
        hoja.paste(Image.open(f).resize((s, s), Image.LANCZOS), (14 + i * (s + 14), 14))
    hoja.save(SALIDA / "CONTACTO-sellos.jpg", quality=92)
    print("hoja:", SALIDA / "CONTACTO-sellos.jpg")


if __name__ == "__main__":
    main()
