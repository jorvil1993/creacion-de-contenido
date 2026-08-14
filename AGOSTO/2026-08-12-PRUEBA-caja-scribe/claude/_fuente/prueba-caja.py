# -*- coding: utf-8 -*-
"""PRUEBA temporal: arte con la caja real del Kindle Paperwhite como segunda
referencia. Sigue el patron confirmado de las 2 fotos (aparato = ref 1, la
caja = ref 2), igual que FUNDA_BLINDAJE para las fundas.

Uso:
    C:\\ai-video\\venv312\\Scripts\\python.exe artes\\_prueba_caja.py

Genera la escena cruda (_fuente\\_escena.jpg) y el arte final (PRUEBA-CAJA-1.jpg)
para que Jose compare como quedo la caja sin el texto encima y con el arte.
"""
from __future__ import annotations

import json
import shutil
import sys
import traceback
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from artes import a1_marca  # noqa: E402
from artes import a12_codex as a11_agy  # noqa: E402
from artes import claude_artes_agosto as C  # noqa: E402

AGOSTO = RAIZ / "AGOSTO"
CARPETA = AGOSTO / "2026-08-12-PRUEBA-caja-scribe" / "claude"
FUENTE = CARPETA / "_fuente"

# Aparato (ref 1) y caja real (ref 2), ambas ya derechas en contexto/referencia.
APARATO = (RAIZ / "contexto" / "referencia" / "kindle-scribe"
           / "frontal.jpg")
CAJA = (RAIZ / "contexto" / "referencia" / "kindle-scribe"
        / "caja-negro-frontal.jpg")

# Refuerzo para CAJA, equivalente a FUNDA_BLINDAJE: la referencia 2 es la caja
# de venta, objeto separado, reproducir su impresion tal cual (no inventar
# texto nuevo). Sin esto el modelo promedia la caja con el aparato.
CAJA_BLINDAJE = (
    " There are TWO reference images. The FIRST is the device: its exact "
    "shape, proportions, thickness, bezels and buttons must be reproduced "
    "exactly as shown, never simplified or averaged toward a generic "
    "rectangular slate. The SECOND reference image is ONLY the retail box "
    "the device comes in: reproduce its exact size, shape, colour, finish "
    "and every printed element (the product photo on the front, the "
    "wordmark and the text) faithfully, exactly as printed in the "
    "reference image. The box is a SEPARATE object standing beside the "
    "device, never merged with it and never reshaped by it. No new text, "
    "logo or label may be added anywhere in the scene beyond what is "
    "already printed on the box in the reference image."
)

ESCENA = (
    "An e-reader lying flat on a warm wooden desk, its matte display facing up "
    "showing a readable book page, and beside it its retail packaging box "
    "standing upright with its printed cover facing the camera, soft natural "
    "window light from the left, a blurred bookshelf in the background. " 
    + C.BLINDAJE + CAJA_BLINDAJE
)

TITULAR = 'KINDLE SCRIBE<br><span class="acento">CON SU CAJA</span>'
MODELO = "KINDLE SCRIBE"
BAJADA = "Sellado y protegido, como sale de Amazon."


def main() -> None:
    FUENTE.mkdir(parents=True, exist_ok=True)
    escena = FUENTE / "_escena.jpg"

    print("Generando escena con 2 referencias (aparato + caja)...", flush=True)
    _, cid = a11_agy.generar_imagen(
        ESCENA, escena,
        referencias=[APARATO, CAJA], timeout=300)
    print(f"  escena OK (conversation agy: {cid})", flush=True)

    arte = a1_marca.Arte(
        titular=TITULAR, producto=MODELO, bajada=BAJADA,
        foto_fondo=escena, formato="cuadrado",
        titular_escala=0.88, sello=C.SELLO_1, sello_2=C.SELLO_2,
    )
    salida = CARPETA / "PRUEBA-CAJA-1.jpg"
    a1_marca.render(arte, salida)
    print(f"  arte OK -> {salida.relative_to(RAIZ)}", flush=True)

    (FUENTE / "pieza.json").write_text(json.dumps({
        "id": "PRUEBA-CAJA", "generado_por": "claude", "estado": "prueba",
        "fecha_generacion": "2026-08-12",
        "producto": "kindle-scribe",
        "motor": "escena agy + artes/a1_marca.py",
        "conversation_id_agy": cid,
        "foto_referencia": str(APARATO.relative_to(RAIZ)),
        "foto_referencia_2": str(CAJA.relative_to(RAIZ)),
        "prompt_escena": ESCENA,
        "sellos": [C.SELLO_1, C.SELLO_2],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(__file__, FUENTE / "prueba-caja.py")
    escena.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("MAL:", repr(e), flush=True)
        traceback.print_exc()
        sys.exit(1)
