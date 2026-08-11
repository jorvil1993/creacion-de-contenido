"""Genera una tanda de artes para ver la variacion de un vistazo.

Cada arte toma la variacion que le corresponde por indice (a4_variacion), asi que
seis artes seguidos salen con seis fondos distintos y con las palancas de venta
rotando en vez de repetirse en todos.

    C:\\ai-video\\venv312\\Scripts\\python.exe artes/tanda.py
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from artes.a1_marca import Arte, render  # noqa: E402
from artes.a2_recorte import fotos_de, recortar  # noqa: E402
from artes.a4_variacion import para  # noqa: E402

SALIDA = RAIZ / "salida" / "artes"
TRABAJO = Path(r"C:\ai-video\artes")

# Un angulo por arte. Ninguno repite palanca ni fondo con el anterior.
PIEZAS = [
    ("kindle-paperwhite", '¿UN REGALO QUE<br>SÍ VAYA A <span class="acento">USAR</span>?',
     "Kindle Paperwhite 16GB"),
    ("kindle-basic", 'MILES DE LIBROS<br>EN TU <span class="acento">BOLSILLO</span>',
     "Kindle Basic 2024"),
    ("colorsoft-32gb", 'LAS PORTADAS<br>COMO <span class="acento">MERECEN</span> VERSE',
     "Kindle Colorsoft 32GB"),
    ("kobo-libra-colour-32-gb", 'TU BIBLIOTECA<br>SIN <span class="acento">ATADURAS</span>',
     "Kobo Libra Colour 32GB"),
    ("kindle-scribe-2025-64-gb", 'DONDE TUS IDEAS<br><span class="acento">COBRAN VIDA</span>',
     "Kindle Scribe 64GB"),
    ("paperwhite-kids", 'QUE LEER SEA<br>SU <span class="acento">AVENTURA</span>',
     "Kindle Paperwhite Kids"),
]


def main() -> None:
    TRABAJO.mkdir(parents=True, exist_ok=True)
    for i, (producto, titular, nombre) in enumerate(PIEZAS):
        fotos = fotos_de(producto)
        if not fotos:
            print(f"[saltado] sin fotos de {producto}")
            continue
        # img2 suele ser el hero limpio sobre blanco: el mejor para recortar.
        hero = next((f for f in fotos if f.stem.endswith("img2")), fotos[0])
        recorte = TRABAJO / f"{producto}-recortado.png"
        if not recorte.exists():
            recortar(hero, recorte)

        v = para(i)
        arte = Arte(
            titular=titular,
            producto=nombre,
            escena=v.escena,
            recorte=recorte,
            recorte_alto=44,
            recorte_y=57 if v.confianza else 60,
            sello=v.sello,
            confianza=v.confianza,
        )
        destino = render(arte, SALIDA / f"tanda-{i+1}-{producto}.jpg")
        sello = v.sello or "—"
        print(f"{i+1}. {v.escena:7} sello={sello:6} palancas={len(v.confianza)}  {destino.name}")


if __name__ == "__main__":
    main()
