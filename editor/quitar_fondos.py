"""
Deriva una biblioteca de producto SIN FONDO para los insertos del video.

Lee `contexto/catalogo-assets.json`, elige las mejores fotos por modelo y les
quita el fondo con rembg, guardando PNG con transparencia en
`assets/productos/<modelo>/`.

Reglas importantes:
  - La biblioteca original (`contexto/fotos y videos/`) NO se toca ni se
    reorganiza: está en uso por la página web. Aquí solo se DERIVA.
  - No se procesan las 262 fotos: el pipeline necesita 2-3 buenas por modelo,
    no el catálogo entero.
  - Se excluye lo marcado `#no-usar-en-video` (fotos de proveedor con marca
    de agua) y los videos.

Uso:
    python quitar_fondos.py                 # procesa lo que falte
    python quitar_fondos.py --por-modelo 3  # cuántas fotos por modelo
    python quitar_fondos.py --rehacer       # reprocesa aunque ya exista
"""
import argparse
import json
import os
import sys
from pathlib import Path

from PIL import Image

import config

# El modelo de rembg (~176 MB) va fuera de OneDrive, como todo lo pesado
os.environ.setdefault("U2NET_HOME", str(config.DIR_MODELOS / "rembg"))

DIR_DESTINO = config.DIR_ASSETS / "productos"
RUTA_CATALOGO = config.DIR_CONTEXTO / "catalogo-assets.json"


def _puntaje(a: dict) -> int:
    """Qué foto sirve más como inserto de producto."""
    p = 0
    p += {"producto": 60, "caja": 30, "funda": 20, "accesorio": 15}.get(a["tipo"], 0)
    # el fondo liso recorta mucho mejor que una escena con contexto
    p += {"blanco": 40, "transparente": 50, "ambiente": 5}.get(a["fondo"], 0)
    p += {"vertical": 20, "cuadrada": 14, "horizontal": 6}.get(a["orientacion"], 0)
    dims = a.get("dimensiones") or [0, 0]
    p += 10 if (dims[0] or 0) >= 800 else 0
    return p


def seleccionar(catalogo: list, por_modelo: int) -> dict:
    """{producto: [assets]} con las mejores candidatas de cada modelo."""
    grupos = {}
    for a in catalogo:
        if a["medio"] != "imagen":
            continue
        if "#no-usar-en-video" in a.get("tags", []):
            continue
        # "funda" y "accesorio" entran también: son 2 de los 4 tipos que la
        # Fase 2 del editor visual promete poder filtrar (funda/producto/
        # accesorio/caja) y _puntaje() ya les tenía peso asignado — quedaban
        # fuera solo por este filtro, no por diseño.
        if a["tipo"] not in ("producto", "caja", "funda", "accesorio"):
            continue
        grupos.setdefault(a["producto"], []).append(a)

    return {k: sorted(v, key=_puntaje, reverse=True)[:por_modelo]
            for k, v in grupos.items()}


def main():
    ap = argparse.ArgumentParser(description="Quita el fondo de las fotos de producto")
    ap.add_argument("--por-modelo", type=int, default=2)
    ap.add_argument("--rehacer", action="store_true")
    args = ap.parse_args()

    if not RUTA_CATALOGO.exists():
        print("Falta contexto/catalogo-assets.json — corre primero catalogo_assets.py",
              file=sys.stderr)
        sys.exit(1)

    catalogo = json.loads(RUTA_CATALOGO.read_text(encoding="utf-8"))["assets"]
    seleccion = seleccionar(catalogo, args.por_modelo)
    total = sum(len(v) for v in seleccion.values())
    print(f"{len(seleccion)} modelos, {total} fotos seleccionadas de {len(catalogo)} del catálogo.\n")

    from rembg import new_session, remove
    sesion = new_session("u2net")

    hechas = saltadas = fallidas = 0
    for producto, assets in sorted(seleccion.items()):
        destino = DIR_DESTINO / producto
        destino.mkdir(parents=True, exist_ok=True)
        for i, a in enumerate(assets, start=1):
            salida = destino / f"{'frontal' if i == 1 else f'vista{i}'}.png"
            if salida.exists() and not args.rehacer:
                saltadas += 1
                continue
            origen = config.RAIZ_PROYECTO / a["ruta"]
            if not origen.exists():
                fallidas += 1
                continue
            try:
                with config.abrir_imagen(origen) as im:
                    im = im.convert("RGBA")
                    # limitar tamaño: el inserto se ve a 400px, no hace falta 4K
                    im.thumbnail((1400, 1400), Image.LANCZOS)
                    sin_fondo = remove(im, session=sesion)
                    # recortar al contenido real, para que el inserto no traiga
                    # aire transparente alrededor y el producto se vea grande
                    caja = sin_fondo.getbbox()
                    if caja:
                        sin_fondo = sin_fondo.crop(caja)
                    sin_fondo.save(salida)
                hechas += 1
                print(f"  {producto:<34} {salida.name}")
            except Exception as e:
                fallidas += 1
                print(f"  FALLO {producto}: {e}", file=sys.stderr)

    print(f"\nListas: {hechas} · ya existían: {saltadas} · fallidas: {fallidas}")
    print(f"Destino: {DIR_DESTINO}")
    print("\nEl catálogo las detecta como #sin-fondo al volver a correr "
          "catalogo_assets.py, y el pipeline las prefiere sobre las de fondo blanco.")


if __name__ == "__main__":
    main()
