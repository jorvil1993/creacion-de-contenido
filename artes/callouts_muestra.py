"""Arte con callouts flotantes: el arquetipo del "PAPERWHITE 32GB SIGNATURE".

TODAS las caracteristicas de aqui estan verificadas contra la pagina oficial de
Amazon del ASIN B0CFPJYX7P el 2026-08-01. Jose pidio ser severo con esto porque
ya hay un arte publicado que dice "10 semanas" cuando ese dato es del Paperwhite
Signature VIEJO de 6.8" — el de 7" actual son 12 semanas.

**Regla: si un dato no se pudo confirmar, no entra.** Por eso no aparece "300 ppi"
aunque el catalogo interno lo liste: no se confirmo para el Paperwhite en la
verificacion del 2026-08-01.

    C:\\ai-video\\venv312\\Scripts\\python.exe artes/callouts_muestra.py
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from artes.a1_marca import Arte, render  # noqa: E402

SALIDA = RAIZ / "salida" / "artes"
TRABAJO = Path(r"C:\ai-video\artes")

# (dato, texto, x%, y%). Se reparten a los lados del aparato, nunca encima de la
# pantalla: tapar la pantalla es tapar lo que se esta vendiendo.
CALLOUTS = [
    ("16 GB", "Miles de libros", 20, 44),
    ("12 semanas", "de batería", 79, 56),
    ("IPX8", "Sumergible 2 m", 19, 72),
]


def main() -> None:
    arte = Arte(
        titular='EL KINDLE<br>QUE <span class="acento">NO TE FRENA</span>',
        producto="Kindle Paperwhite 16GB",
        escena="navy",
        recorte=TRABAJO / "paperwhite-recortado.png",
        recorte_alto=52,
        recorte_y=58,
        sello="anios",
        callouts=CALLOUTS,
    )
    destino = render(arte, SALIDA / "callouts-paperwhite.jpg")
    print(f"arte {destino}")


if __name__ == "__main__":
    main()
