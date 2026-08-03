"""Recorte del producto y preparacion de las fotos de Amazon.

Dos trabajos distintos que suelen confundirse:

- `recortar()` saca el fondo y deja el producto con alfa, para recomponerlo en
  otro entorno (lo que pidio Jose: "que la IA saque el fondo tambien").
- `preparar_fondo()` NO recorta nada: toma una foto de Amazon completa y la deja
  lista como fondo del arte. Su trabajo real es quitar la franja de texto en
  ingles que Amazon quema arriba ("kindle paperwhite / 20% faster"), que no puede
  aparecer en un arte de DeviceShop.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
FOTOS_AMAZON = RAIZ / "contexto" / "fotos amazon"


def recortar(origen: Path, destino: Path) -> Path:
    """Saca el fondo y deja el producto con canal alfa."""
    from rembg import new_session, remove

    # isnet-general-use vence a u2net en bordes duros y rectos como el marco de
    # un e-reader; u2net los redondea y deja halo. Se instancia la sesion una vez
    # para no recargar el modelo en cada foto.
    sesion = new_session("isnet-general-use")
    with Image.open(origen) as im:
        salida = remove(im.convert("RGBA"), session=sesion)

    destino.parent.mkdir(parents=True, exist_ok=True)
    salida.save(destino)
    return destino


def _franja_texto(im: Image.Image) -> float:
    """Devuelve que fraccion del alto ocupa la franja de texto de Amazon.

    Amazon pone el texto sobre una banda de fondo casi uniforme arriba. Se recorre
    de arriba hacia abajo y se corta donde la imagen empieza a tener variacion
    real de color, que es donde arranca la foto.
    """
    gris = im.convert("L")
    an, al = gris.size
    limite = 0.0
    for y in range(0, int(al * 0.55), max(1, al // 200)):
        fila = gris.crop((0, y, an, y + 1)).getdata()
        vals = list(fila)
        rango = max(vals) - min(vals)
        # Una fila de texto negro sobre claro tambien tiene rango alto, asi que no
        # alcanza con el rango: se pide ademas que la mayoria del ancho sea claro.
        claros = sum(1 for v in vals if v > 205) / len(vals)
        if rango > 90 and claros < 0.80:
            limite = y / al
            break
    return limite


def preparar_fondo(
    origen: Path, destino: Path, formato: str = "cuadrado"
) -> tuple[Path, bool]:
    """Deja una foto de Amazon lista como fondo, sin el texto en ingles.

    Devuelve (ruta, se_recorto_texto).
    """
    from artes.a1_marca import FORMATOS

    ancho_obj, alto_obj = FORMATOS[formato]
    with Image.open(origen) as im:
        im = im.convert("RGB")
        corte = _franja_texto(im)
        recorto = corte > 0.04
        if recorto:
            # +2% de margen: el borde exacto del texto suele dejar un resto de la
            # banda clara que se nota como una linea al componer.
            y0 = int(im.height * min(corte + 0.02, 0.5))
            im = im.crop((0, y0, im.width, im.height))

        # Encuadre "cover": llena el lienzo sin deformar, centrado en horizontal y
        # sesgado hacia arriba en vertical (el producto suele estar en el centro
        # alto de la foto, no al pie).
        escala = max(ancho_obj / im.width, alto_obj / im.height)
        nuevo = (max(1, round(im.width * escala)), max(1, round(im.height * escala)))
        im = im.resize(nuevo, Image.LANCZOS)
        x = (im.width - ancho_obj) // 2
        y = int((im.height - alto_obj) * 0.38)
        im = im.crop((x, y, x + ancho_obj, y + alto_obj))

        destino.parent.mkdir(parents=True, exist_ok=True)
        im.save(destino, quality=96, subsampling=0)

    return destino, recorto


def fotos_de(producto: str) -> list[Path]:
    """Todas las fotos de Amazon de un producto, por nombre de carpeta."""
    return sorted(FOTOS_AMAZON.glob(f"fotos-amazon_{producto}_img*.jpg"))
