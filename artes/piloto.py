"""Arte piloto de punta a punta: Kindle Paperwhite, angulo regalo.

Se eligio ese angulo porque es el unico comprobado con datos propios: el mejor
anuncio historico de la cuenta de Meta fue "Buscas un excelente regalo a un precio
muy economico?" con CTR 6,89% y $0,10 por conversacion
(deviceshop/DOCUMENTOS MD DE LA EMPRESA/copys-anuncios-meta.md).

No usa IA. El producto sale recortado de una foto real de Amazon y se compone
sobre una escena de estudio, que es como estan hechos varios artes que Jose ya
publico. La IA (Qwen-Image-Edit) entra despues, solo para escenas fotorrealistas.

    C:\\ai-video\\venv312\\Scripts\\python.exe artes/piloto.py
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from artes.a1_marca import Arte, render  # noqa: E402
from artes.a2_recorte import fotos_de, recortar  # noqa: E402
from artes.a3_copy import PAPERWHITE, variantes  # noqa: E402

SALIDA = RAIZ / "salida" / "artes"
TRABAJO = Path(r"C:\ai-video\artes")


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    TRABAJO.mkdir(parents=True, exist_ok=True)

    fotos = fotos_de("kindle-paperwhite")
    if not fotos:
        raise SystemExit("no hay fotos de kindle-paperwhite en contexto/fotos amazon/")

    # img2 es el hero limpio sobre blanco: el mejor candidato para recortar.
    # Las de estilo de vida traen texto en ingles quemado sobre la foto misma,
    # asi que no sirven como fondo a sangre; sirven como referencia de escena.
    hero = next((f for f in fotos if f.stem.endswith("img2")), fotos[0])
    recorte = TRABAJO / "paperwhite-recortado.png"
    if not recorte.exists():
        recortar(hero, recorte)
    print(f"recorte  {hero.name} -> {recorte.name}")

    # El titular va a dos lineas cortas a proposito: con el sello ocupando la
    # esquina el bloque de texto trabaja al 75% del ancho, y un titular largo
    # se parte en cuatro lineas y se come el espacio del producto.
    arte = Arte(
        titular='¿UN REGALO QUE<br>SÍ VAYA A <span class="acento">USAR</span>?',
        producto="Kindle Paperwhite 16GB",
        escena="navy",
        recorte=recorte,
        # El texto termina cerca del 28% y la barra de confianza arranca al 82%:
        # 42% de alto centrado en 60% deja el producto justo en el hueco libre.
        recorte_alto=44,
        recorte_y=57,
        formato="cuadrado",
        sello_num="6",
        sello_lab="AÑOS EN<br>BOLIVIA",
        confianza=["Nuevo y sellado", "Garantía 1 mes", "Entrega inmediata"],
    )
    destino = render(arte, SALIDA / "piloto-paperwhite-regalo.jpg")
    print(f"arte     {destino}")

    copys = variantes(PAPERWHITE)
    txt = SALIDA / "piloto-paperwhite-regalo.copy.md"
    txt.write_text(
        "\n\n".join(f"## {k.upper()}\n\n{v}" for k, v in copys.items()),
        encoding="utf-8",
    )
    print(f"copy     {txt}  ({len(copys)} variantes)")


if __name__ == "__main__":
    main()
