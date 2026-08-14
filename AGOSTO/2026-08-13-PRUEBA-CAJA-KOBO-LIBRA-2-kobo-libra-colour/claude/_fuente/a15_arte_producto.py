# -*- coding: utf-8 -*-
"""Motor compartido para armar UN arte de imagen unica con el producto real
adentro (agy o Codex, con la foto real como referencia multimodal). Lo usa
CUALQUIER mes -- agosto, septiembre, lo que venga -- y cualquier variante
(la pieza base, una version con la funda real, una prueba con la caja...).

Que va en este archivo vs. en el script de cada mes:

  ESTE ARCHIVO (a15_arte_producto.py)     <mes>_artes.py (ej. claude_artes_agosto.py)
  ---------------------------------       ----------------------------------------
  ArteSpec (la forma de una pieza)        especificaciones() -- la LISTA de piezas
  BLINDAJE / FUNDA_BLINDAJE /              de ESE mes: sus titulares, su copy, sus
    CAJA_BLINDAJE / CAJA_SOLA_BLINDAJE     escenas -- eso SI cambia mes a mes
  generar() -- arma la escena + compone
    la marca + escribe copy.txt/pieza.json
  siguiente_version() -- la version libre

Si escribis un script nuevo para un mes nuevo, importa de aca -- no copies
pegues BLINDAJE ni generar() de nuevo. Antes (hasta el 2026-08-12) todo esto
vivia adentro de claude_artes_agosto.py, y cada script que necesitaba el
mismo motor (claude_artes_v3v4.py, las pruebas de funda/caja) importaba de
un archivo que se llama "agosto" -- confuso, y en septiembre hubiera
invitado a reescribir el motor de cero en vez de reusarlo.

    from artes import a15_arte_producto as motor
    motor.generar(spec, "claude")
"""
from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from artes import a1_marca, a11_agy  # noqa: E402
from artes import a14_referencia as referencia  # noqa: E402

BRAIN = Path.home() / ".gemini" / "antigravity-cli" / "brain"
WA = "692-14437"

SELLO_1 = "escudo"        # COMPRA SEGURA
SELLO_2 = "efectivo_a"    # PAGAS AL RECIBIR, con el fajo de billetes

_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def carpeta_mes(fecha: str) -> Path:
    """'2026-08-13' -> RAIZ/AGOSTO, '2026-09-03' -> RAIZ/SEPTIEMBRE. Cada
    pieza cae sola en la carpeta de SU mes -- el motor no tiene que saber en
    que mes estamos, ni hay que tocar esta funcion cuando cambia el mes."""
    mes = int(fecha.split("-")[1])
    return RAIZ / _MESES[mes - 1].upper()


BLINDAJE = (
    "The device is a modern e-reader with a matte, non-glossy electronic ink "
    "display that looks like printed paper under the ambient light. The screen "
    "is a flat rigid surface and stays perfectly flat at all times: nothing "
    "lifts, peels, curls, flies or emerges from it, and there are no paper "
    "sheets anywhere in the frame. Only the front face has a display; the back "
    "is a plain solid shell with no screen. The device shape, buttons, bezels "
    "and proportions match the reference image exactly. The screen shows normal "
    "readable book content. Text is allowed ONLY inside the screen, as the book "
    "content itself, and the device's own manufacturer wordmark exactly as it "
    "is printed on its body in the reference image (reproduce that mark "
    "faithfully, do not remove it and do not invent a different one); "
    "everywhere else in the image there are no brand names, no invented "
    "logos, no lettering, no watermark and no text overlay. The camera stays in "
    "a fixed position, no orbit. Vertical square 1:1 framing, natural editorial "
    "product photography, shot on a 50mm lens, shallow depth of field, soft "
    "realistic light."
)

# Se agrega SOLO cuando hay una segunda referencia (la funda real). Encontrado
# el 2026-08-12 comparando dos tiradas identicas del Kobo Libra Colour: la que
# tenia este refuerzo salio con el grip asimetrico y los botones intactos, la
# que no lo tenia salio "aplanada" a una tablet rectangular generica -- el
# modelo promedia la forma del aparato con la de la funda si no se le dice
# explicitamente que no lo haga (la regla ya estaba en AGENTS.md, pero no se
# aplicaba parejo en todos los prompts que usan dos referencias).
#
# CONFIRMADO el 2026-08-12 (AGOSTO/2026-08-19-A6-kobo-libra-colour/claude-v12):
# con este refuerzo Y las dos fotos de referencia bien orientadas (ver el
# aviso sobre fotos "volcadas" mas abajo), ni agy ni Codex tienen problema
# real en tomar DOS fotos a la vez -- el aparato y la funda salieron
# perfectos, cada uno con su forma, sin mezclarse. El input de 2 fotos
# (aparato = referencia 1, funda = referencia 2) FUNCIONA: es el patron a
# seguir para cualquier pieza nueva que quiera mostrar la funda real, no un
# experimento. El problema de antes nunca fue una limitacion del modelo, era
# de este lado: falta de refuerzo parejo + fotos de funda de canto.
#
# OJO CON FOTOS "VOLCADAS": varias fundas en contexto/referencia/ llegaron de
# canto (rotadas 90) porque el recorte que les sacaba la mano se hizo sobre
# el pixel crudo sin aplicar la rotacion EXIF primero, y al guardar de nuevo
# se perdio la bandera. Si agregas una foto nueva a mano (funda, caja, lo que
# sea), revisa que este derecha ANTES de usarla como referencia -- no asumas
# que porque se ve bien en el explorador de Windows esta bien: la bandera
# EXIF puede estar mintiendo. Chequeo rapido: `PIL.Image.open(f).size` -- un
# producto vertical con ancho > alto es sospechoso.
FUNDA_BLINDAJE = (
    " There are TWO reference images. The FIRST is the device: its exact "
    "shape, proportions, thickness, bezels, buttons and any asymmetric "
    "feature must be reproduced exactly as shown, never simplified, "
    "averaged or blended toward a generic rectangular slate. The SECOND "
    "reference image is ONLY the folio case: reproduce its exact material, "
    "colour and closed shape, but it must NOT influence, resize or reshape "
    "the device in any way. The case is a separate object -- sitting beside "
    "the device or with the device resting on top of it -- never merged "
    "with it, never molded onto its body as a second layer."
)

# Mismo patron que FUNDA_BLINDAJE, para cuando la segunda referencia es la
# CAJA de venta en vez de la funda. Probado el 2026-08-12 en tres piezas
# (AGOSTO/2026-08-12-PRUEBA-caja-paperwhite, -scribe y -kobo-clara, esta
# ultima de opencode): la caja sale con su impresion real -- nombre, specs,
# franja de color -- intacta y separada del aparato. Confirmado: funciona
# igual de bien que la funda, mismo mecanismo (dos referencias + repartir
# los papeles en el prompt).
#
# BUG encontrado el 2026-08-13 en la prueba del Kobo Libra Colour: el modelo
# igualaba la ilustracion impresa en la caja con la que se le pedia mostrar
# en la pantalla del equipo (las dos terminaron mostrando "The Tale of the
# Whispering Woods"). Es al reves de lo que pasa de verdad: la caja sale de
# fabrica con SU foto ya impresa, fija para siempre; la pantalla del equipo
# en la escena es la que elegimos nosotros para cada pieza y puede ser
# cualquier cosa. Son dos cosas independientes. Se lo dice el ultimo parrafo.
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
    "already printed on the box in the reference image. The illustration "
    "or book cover printed on the box's own product photo was fixed at the "
    "factory and comes ONLY from the second reference image: it must NOT "
    "be changed, redrawn or matched to whatever content is shown on the "
    "actual device's screen elsewhere in this scene -- the box's printed "
    "picture and the device's on-screen content are independent and may "
    "show completely different things."
)

# Variante para cuando la CAJA es la UNICA referencia (sin el aparato en la
# escena, ej. "la caja que se bebe el sol"). Probado el 2026-08-12 con la
# Kobo Clara Colour.
CAJA_SOLA_BLINDAJE = (
    " There is a SINGLE reference image: the retail box. Reproduce it "
    "exactly and faithfully -- its size, shape, colour, finish and every "
    "printed element (the product photo on the front, the wordmark and the "
    "text) exactly as shown in the reference, without adding, removing or "
    "rewriting any lettering, including the illustration or book cover "
    "printed on the box's own product photo: it was fixed at the factory "
    "and is copied exactly from the reference, never redrawn or replaced "
    "with different content. The box is a rigid cardboard box standing as "
    "an object in the scene. No e-reader, tablet or device appears in the "
    "scene at all: the box is the only product. No other text, logo or "
    "label appears anywhere in the image."
)


def escena_blindada(descripcion: str, *, funda: bool = False,
                    caja: bool = False, solo_caja: bool = False) -> str:
    """Arma el texto completo de la escena (descripcion + el blindaje que
    corresponda) para las 4 combinaciones que soporta el motor. Evita el
    error de concatenar el blindaje equivocado a mano -- paso el
    CAJA_BLINDAJE se olvido en varios prompts hasta que se hizo este helper.

        escena_blindada("...", ) -> solo el producto (BLINDAJE)
        escena_blindada("...", funda=True) -> producto + funda real
        escena_blindada("...", caja=True) -> producto + caja real
        escena_blindada("...", solo_caja=True) -> SOLO la caja, sin producto

    En los tres primeros casos `descripcion` tiene que describir el
    producto (y la funda/caja si aplica) en la escena. En `solo_caja` NO
    describas ningun aparato -- la caja es lo unico que aparece.
    """
    if sum((funda, caja, solo_caja)) > 1:
        raise ValueError("elegi UNA sola de funda / caja / solo_caja")
    if solo_caja:
        return descripcion + CAJA_SOLA_BLINDAJE
    if funda:
        return descripcion + BLINDAJE + FUNDA_BLINDAJE
    if caja:
        return descripcion + BLINDAJE + CAJA_BLINDAJE
    return descripcion + BLINDAJE


@dataclass
class ArteSpec:
    id: str
    fecha: str
    producto: str     # sufijo de carpeta
    titular: str
    modelo: str       # la franja de acento. NO se repite en la bajada
    # Emocional, sin precio y sin nombrar el modelo. UN SOLO RENGLON: mas de
    # ~40 caracteres salta a una segunda linea y sobrecarga el arte (Jose,
    # 2026-08-12). El limite se midio sobre el render, no se estimo.
    bajada: str
    escena: str
    foto: Path
    # Segunda referencia opcional (la funda real, la caja real...). NUNCA
    # describas un accesorio sin pasar su foto: el modelo se lo inventa y
    # saca uno que no vendemos (paso el 2026-08-12 con una funda estuche).
    foto_2: Path | None
    copy: str
    hashtags: list[str] = field(default_factory=list)


def _del_cache(cid: str, destino: Path) -> bool:
    """Recupera la escena que agy dejo en su cache. Devuelve False si ya no esta."""
    carpeta = BRAIN / (cid or "")
    if not cid or not carpeta.exists():
        return False
    imgs = [p for p in carpeta.glob("*")
            if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    if not imgs:
        return False
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(max(imgs, key=lambda f: f.stat().st_mtime).read_bytes())
    return True


def nueva_escena(spec: ArteSpec, destino: Path) -> tuple[Path, str]:
    """agy primero; si agy no puede, Codex."""
    try:
        return a11_agy.generar_imagen(spec.escena, destino,
                                      referencias=[r for r in (spec.foto, spec.foto_2) if r], timeout=300)
    except Exception as e:
        print(f"      agy fallo ({e}); voy por Codex", flush=True)
        from artes import a12_codex
        for nombre in ("generar_imagen", "imagen", "generar"):
            fn = getattr(a12_codex, nombre, None)
            if callable(fn):
                fn(spec.escena, destino,
                   referencias=[r for r in (spec.foto, spec.foto_2) if r])
                return destino, "codex"
        raise RuntimeError("Codex no expone ninguna funcion de imagen") from e


def siguiente_version(carpeta_pieza: Path) -> str:
    """La primera 'claude-vN' que no existe todavia ('claude' solo, sin
    numero, es la v1: N arranca en 2). Nunca pisa lo que ya esta -- regla de
    Jose (2026-08-12): perdio una version que le gustaba porque una corrida
    la sobreescribio, y una imagen generada no se puede rehacer igual."""
    n = 2
    while (carpeta_pieza / f"claude-v{n}").exists():
        n += 1
    return f"claude-v{n}"


def generar(spec: ArteSpec, sufijo: str, *, recrear: bool = False,
            sin_pisar: bool = False, estado: str = "generado",
            tipo: str = "arte_individual", nota: str = "") -> Path:
    """Arma la escena (agy/Codex, con la foto real como referencia) y compone
    la marca encima (a1_marca). Escribe en <carpeta_mes>/<pieza>/<sufijo>/.

    `sin_pisar=True` (usalo para versiones extra, v3 en adelante): si la
    carpeta ya tiene arte, falla en vez de pisar -- combinalo con
    `siguiente_version()` para que cada corrida caiga sola en la version
    libre.

    `sin_pisar=False` (default, para las piezas base "claude"/"claude-v2"):
    permite volver a correr sobre la MISMA carpeta para actualizar titular o
    copy sin gastar cuota de nuevo -- reusa la escena del cache de agy
    (`conversation_id_agy` en pieza.json) salvo que pidas `recrear=True`.
    Esto no pisa una imagen generada por otra: es releer un texto sobre la
    MISMA escena ya elegida, la excepcion que ya documenta AGENTS.md ("el
    texto si se puede reescribir").
    """
    carpeta = carpeta_mes(spec.fecha) / f"{spec.fecha}-{spec.id}-{spec.producto}" / sufijo
    if sin_pisar and (carpeta / f"{spec.id}-1.jpg").exists():
        raise RuntimeError(
            f"{carpeta.name} ya tiene arte: no se pisa. Llama sin `sufijo` fijo "
            "y usa siguiente_version() para la proxima libre.")
    fuente = carpeta / "_fuente"
    fuente.mkdir(parents=True, exist_ok=True)
    ficha = fuente / "pieza.json"

    escena = fuente / "_escena.jpg"
    cid = ""
    if ficha.exists() and not recrear:
        cid = json.loads(ficha.read_text(encoding="utf-8-sig")).get("conversation_id_agy", "")
    origen = "cache de agy"
    if not (cid and _del_cache(cid, escena)):
        _, cid = nueva_escena(spec, escena)
        origen = "agy" if cid != "codex" else "codex"

    arte = a1_marca.Arte(
        titular=spec.titular, producto=spec.modelo, bajada=spec.bajada,
        foto_fondo=escena, formato="cuadrado",
        titular_escala=0.88,          # un punto mas chico, pedido de Jose
        sello=SELLO_1, sello_2=SELLO_2,
    )
    salida = carpeta / f"{spec.id}-1.jpg"
    a1_marca.render(arte, salida)

    (carpeta / "copy.txt").write_text(
        spec.copy + "\n\n" + " ".join(spec.hashtags) + "\n", encoding="utf-8")
    datos_ficha = {
        "id": spec.id, "version": sufijo, "generado_por": "claude",
        "fecha_generacion": "2026-08-12", "fecha_publicacion": spec.fecha,
        "estado": estado, "tipo": tipo,
        "producto": spec.producto, "titular": spec.titular, "modelo": spec.modelo,
        "bajada": spec.bajada, "hashtags": spec.hashtags,
        "formato": "cuadrado", "medidas": "1080x1080",
        "motor": f"escena {origen} + artes/a1_marca.py",
        "conversation_id_agy": cid if cid != "codex" else "",
        "foto_referencia": str(spec.foto.relative_to(RAIZ)),
        "foto_referencia_2": (str(spec.foto_2.relative_to(RAIZ))
                              if spec.foto_2 else None),
        "prompt_escena": spec.escena,
        "sellos": [SELLO_1, SELLO_2],
        "sin_precio": True, "sello_ia": False, "voz": "tuteo",
        "regla": "el producto aparece una sola vez, puesto por el modelo en la "
                 "escena; el modelo se nombra una vez y la bajada no lo repite",
        "archivos": [f"{spec.id}-1.jpg", "copy.txt"],
    }
    if nota:
        datos_ficha["nota"] = nota
    ficha.write_text(json.dumps(datos_ficha, ensure_ascii=False, indent=2), encoding="utf-8")
    # Copiamos el motor (este archivo) Y quien armo las especificaciones (el
    # script que llamo a generar(), ej. claude_artes_agosto.py) -- entre los
    # dos alcanza para reproducir la pieza exacta. Si generar() se llamo desde
    # una consola interactiva o un -c suelto (no un archivo real, ej. "<string>"),
    # no hay script de llamador que copiar -- no es un error, solo no hay nada
    # que guardar ahi.
    shutil.copy2(Path(__file__), fuente / "a15_arte_producto.py")
    import inspect
    llamador = inspect.stack()[1].filename
    if Path(llamador).is_file() and Path(llamador).resolve() != Path(__file__).resolve():
        shutil.copy2(llamador, fuente / "claude-generar.py")
    escena.unlink(missing_ok=True)
    return salida
