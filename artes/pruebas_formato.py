"""Renderiza el mismo arte en los tres formatos, para comparar de un vistazo.

Existe porque los % de colocacion del producto (`panel_servidor_artes._COLOCACION`)
NO salen de una formula: el bloque de texto y el pie miden lo mismo en pixeles
absolutos en los tres lienzos, pero el producto se posiciona en % del alto. La
unica forma de saber si un numero esta bien es renderizar y mirar.

Ademas dibuja encima de cada arte la caja 3:4 que deja ver la grilla del perfil
de Instagram (`a1_marca.caja_segura`), que desde enero de 2026 recorta al centro
toda miniatura sin importar la proporcion original.

    C:\\ai-video\\venv312\\Scripts\\python.exe artes/pruebas_formato.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from artes.a1_marca import FORMATOS, Arte, caja_segura, render  # noqa: E402
from artes.panel_servidor_artes import _colocacion  # noqa: E402

SALIDA = Path(r"C:\ai-video\artes\_pruebas-formato")
RECORTE = Path(r"C:\ai-video\artes\2026-08-03-test-kindle-paperwhite\recorte.png")

TITULAR = 'TU BIBLIOTECA<br>ENTRA EN UN <span class="acento">BOLSILLO</span>'


def con_guia(arte_jpg: Path, formato: str) -> Path:
    """Copia el arte con la caja 3:4 de la grilla de IG dibujada encima."""
    x, y, w, h = caja_segura(formato)
    with Image.open(arte_jpg) as im:
        im = im.convert("RGB")
        capa = im.copy()
        d = ImageDraw.Draw(capa)
        # Lo que la grilla DESCARTA se oscurece; lo que sobrevive queda limpio.
        for caja in ((0, 0, im.width, y), (0, y + h, im.width, im.height),
                     (0, y, x, y + h), (x + w, y, im.width, y + h)):
            if caja[2] > caja[0] and caja[3] > caja[1]:
                d.rectangle(caja, fill=(0, 0, 0))
        im = Image.blend(im, capa, 0.55)
        d = ImageDraw.Draw(im)
        d.rectangle((x, y, x + w - 1, y + h - 1), outline=(0, 199, 202), width=6)
        destino = arte_jpg.with_name(arte_jpg.stem + "-grilla.jpg")
        im.save(destino, quality=92)
    return destino


# Lo que la interfaz de Stories/Reels tapa en un 9:16: ~250 px arriba (foto de
# perfil, nombre, "x" de cerrar) y ~250 px abajo (caja de responder, compartir,
# los tres puntos). Todo lo que no se puede perder tiene que caer en el tercio
# del medio. Nuestro pie mide 15% del alto = 288 px en 1920: entra JUSTO en la
# franja de abajo, o sea que el logo y el WhatsApp quedan debajo de la interfaz.
UI_STORY = 250


def con_zona_segura(arte_jpg: Path) -> Path:
    """Dibuja encima las dos franjas que tapa la interfaz de Stories/Reels."""
    with Image.open(arte_jpg) as im:
        im = im.convert("RGB")
        capa = im.copy()
        d = ImageDraw.Draw(capa)
        d.rectangle((0, 0, im.width, UI_STORY), fill=(200, 40, 40))
        d.rectangle((0, im.height - UI_STORY, im.width, im.height), fill=(200, 40, 40))
        im = Image.blend(im, capa, 0.45)
        d = ImageDraw.Draw(im)
        for y in (UI_STORY, im.height - UI_STORY):
            d.line((0, y, im.width, y), fill=(255, 80, 80), width=6)
        destino = arte_jpg.with_name(arte_jpg.stem + "-story.jpg")
        im.save(destino, quality=92)
    return destino


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    if not RECORTE.exists():
        print(f"falta el recorte de prueba: {RECORTE}")
        return
    for formato in FORMATOS:
        alto_p, y_p, x_p = _colocacion(formato, "limpio")
        arte = Arte(
            titular=TITULAR,
            producto="Kindle Paperwhite 16GB",
            escena="navy",
            recorte=RECORTE,
            recorte_alto=alto_p,
            recorte_y=y_p,
            recorte_x=x_p,
            formato=formato,
            sello="anios",
        )
        jpg = render(arte, SALIDA / f"{formato}.jpg")
        extra = [con_guia(jpg, formato)]
        if formato == "vertical":
            extra.append(con_zona_segura(jpg))
        w, h = FORMATOS[formato]
        print(f"{formato:9} {w}x{h}  alto={alto_p} y={y_p} x={x_p}  -> {jpg.name}"
              f" + {' + '.join(e.name for e in extra)}")


if __name__ == "__main__":
    main()
