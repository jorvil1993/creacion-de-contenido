# -*- coding: utf-8 -*-
"""PRUEBA temporal: arte SOLO con la caja real de la Kobo Clara Colour como
protagonista (sin el aparato en escena). Referencia unica: la caja.

Generado por opencode. Uso:
    C:\\ai-video\\venv312\\Scripts\\python.exe artes\\_prueba_caja_kobo.py

Genera la escena cruda (_fuente\\_escena.jpg) y el arte final
(PRUEBA-CAJA-KOBO-1.jpg) en la carpeta opencode/ de la prueba.
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
from artes import a11_agy  # noqa: E402
from artes import claude_artes_agosto as C  # noqa: E402

AGOSTO = RAIZ / "AGOSTO"
CARPETA = AGOSTO / "2026-08-12-PRUEBA-caja-kobo-clara" / "opencode"
FUENTE = CARPETA / "_fuente"

# La caja real de la Kobo Clara Colour, unica referencia de esta prueba.
CAJA = (RAIZ / "contexto" / "referencia" / "kobo-clara-colour-16gb"
        / "caja-frontal-negra.jpg")

# Blindaje para escena con UNA sola referencia: la caja. No hay aparato en el
# cuadro; reproducir la caja tal cual (forma, color, acabado, texto impreso),
# sin inventar letras ni logos, y sin que aparezca ningun lector en escena.
CAJA_SOLA_BLINDAJE = (
    " There is a SINGLE reference image: the retail box. Reproduce it "
    "exactly and faithfully -- its size, shape, colour, finish and every "
    "printed element (the product photo on the front, the wordmark and the "
    "text) exactly as shown in the reference, without adding, removing or "
    "rewriting any lettering. The box is a rigid cardboard box standing as "
    "an object in the scene. No e-reader, tablet or device appears in the "
    "scene at all: the box is the only product. No other text, logo or "
    "label appears anywhere in the image."
)

# Escena creativa: la caja protagonista, composicion editorial con luz calida.
ESCENA = (
    "A single retail box standing upright on a warm oak wooden table, "
    "its printed cover facing the camera at a slight three-quarter angle, "
    "soft golden afternoon light from a window on the left casting a long "
    "gentle shadow to the right, a small cup of coffee blurred in the far "
    "background and a hint of warm bokeh, editorial product photography, "
    "shallow depth of field, inviting cosy reading mood, vertical square "
    "1:1 framing. " + CAJA_SOLA_BLINDAJE
)

TITULAR = 'LA CAJA QUE<br><span class="acento">SE BEBE EL SOL</span>'
MODELO = "KOBO CLARA COLOUR"
BAJADA = "Color de verdad, desde la primera caja."


def main() -> None:
    FUENTE.mkdir(parents=True, exist_ok=True)
    escena = FUENTE / "_escena.jpg"

    print("Generando escena con la caja como unica referencia...", flush=True)
    proveedor = "agy"
    try:
        _, cid = a11_agy.generar_imagen(ESCENA, escena, referencias=[CAJA], timeout=300)
    except Exception as e:
        print(f"  agy fallo ({e}); voy por Codex", flush=True)
        from artes import a12_codex
        _, cid = a12_codex.generar_imagen(ESCENA, escena, referencias=[CAJA], timeout=480)
        proveedor = "codex"
    print(f"  escena OK ({proveedor}, id: {cid})", flush=True)

    arte = a1_marca.Arte(
        titular=TITULAR, producto=MODELO, bajada=BAJADA,
        foto_fondo=escena, formato="cuadrado",
        titular_escala=0.88, sello=C.SELLO_1, sello_2=C.SELLO_2,
    )
    salida = CARPETA / "PRUEBA-CAJA-KOBO-1.jpg"
    a1_marca.render(arte, salida)
    print(f"  arte OK -> {salida.relative_to(RAIZ)}", flush=True)

    (FUENTE / "pieza.json").write_text(json.dumps({
        "id": "PRUEBA-CAJA-KOBO", "generado_por": "opencode", "estado": "prueba",
        "fecha_generacion": "2026-08-12",
        "producto": "kobo-clara-colour-16gb",
        "motor": "escena agy+codex + artes/a1_marca.py",
        "conversation_id_agy": (cid if proveedor == "agy" else ""),
        "conversation_id_codex": (cid if proveedor == "codex" else ""),
        "foto_referencia": str(CAJA.relative_to(RAIZ)),
        "foto_referencia_2": None,
        "prompt_escena": ESCENA,
        "sellos": [C.SELLO_1, C.SELLO_2],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(__file__, FUENTE / "opencode-generar.py")
    escena.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("MAL:", repr(e), flush=True)
        traceback.print_exc()
        sys.exit(1)
