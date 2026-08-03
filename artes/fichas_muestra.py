"""Arquetipo de lista de fichas tecnicas, con y sin difuminado.

Jose lo pidio seleccionable (2026-08-01): le gusta pero no lo quiere en todos los
artes. Por eso `fichas` y `fichas_vidrio` son campos del Arte, no un modo global.

Los datos estan verificados contra la pagina oficial de Amazon del ASIN
B0CFPJYX7P el 2026-08-01. El arte que Jose tomo de referencia dice "10 semanas",
que es el dato del Paperwhite Signature VIEJO de 6.8": el de 7" son 12.

    C:\\ai-video\\venv312\\Scripts\\python.exe artes/fichas_muestra.py
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

FICHAS = [
    ("pantalla", 'Pantalla de 7" sin reflejos', "Lee cómodamente bajo cualquier luz."),
    ("agua", "Resistente al agua (IPX8)", "Sumergible 2 m durante 60 minutos."),
    ("bateria", "Batería de larga duración", "Hasta 12 semanas con una sola carga."),
    ("memoria", "16 GB de almacenamiento", "Miles de libros contigo a todas partes."),
]


def main() -> None:
    hechos = []
    for vidrio, escena, fondo in [
        (False, "clara", None),
        (True, "navy", SALIDA / "qwen-prueba-cafe.png"),
    ]:
        arte = Arte(
            titular='MILES DE LIBROS<br>EN TU <span class="acento">BOLSILLO</span>',
            producto="Kindle Paperwhite 16GB",
            escena=escena,
            foto_fondo=fondo,
            # El fondo generado con Qwen ya trae el aparato; agregarle el recorte
            # ponia dos Kindles en el mismo arte.
            recorte=None if fondo else TRABAJO / "paperwhite-recortado.png",
            recorte_alto=40,
            recorte_y=58,
            recorte_x=76,
            fichas=FICHAS,
            fichas_vidrio=vidrio,
        )
        nombre = "fichas-vidrio" if vidrio else "fichas-plana"
        hechos.append(render(arte, SALIDA / f"{nombre}.jpg"))
        print(f"{nombre:14} escena={escena:7} vidrio={vidrio}")

    s = 560
    hoja = Image.new("RGB", (2 * s + 3 * 14, s + 28), "#151515")
    for i, f in enumerate(hechos):
        hoja.paste(Image.open(f).resize((s, s), Image.LANCZOS), (14 + i * (s + 14), 14))
    hoja.save(SALIDA / "CONTACTO-fichas.jpg", quality=92)
    print("hoja:", SALIDA / "CONTACTO-fichas.jpg")


if __name__ == "__main__":
    main()
