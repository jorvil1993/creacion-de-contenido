"""Puente a Antigravity CLI (agy) para el pipeline de VIDEO.

Reutiliza tal cual `artes/a11_agy.py` (genérico, sin nada específico de artes;
ver panel-artes-integracion-agy.md). Investigado el 2026-08-03 preguntándole a
agy sus propias tools: **no tiene ninguna herramienta de video** (nada tipo
Veo, ni animar una foto, ni editar un clip existente) — solo `generate_image`
(imagen fija) y modelos de texto/razonamiento. Por eso este módulo cubre
exactamente eso, ni más:

  1. Imagen de AMBIENTE (sin producto) para B-roll/PiP — alternativa a Flux
     (`f9_generar.py`) que no depende de ComfyUI encendido ni gasta GPU.
  2. Imagen CON el producto real compuesto en una escena, a partir de la foto
     de referencia — mismo mecanismo que ya resolvió en artes el problema de
     que Flux/Qwen no saben dibujar un Kindle real (ver artes-qwen-pipeline.md
     y panel-artes-integracion-agy.md). Sigue siendo una imagen FIJA: la
     usa el pipeline igual que ya usa las de Flux (Ken Burns, no video real).
  3. Prompt de VIDEO para Google Flow/Veo — solo texto. agy no genera el
     clip, pero redacta el prompt aplicando las reglas ya aprendidas a pulso
     en `contexto/PROMPTS-GOOGLE-FLOW.md` (blindaje del logo falso y las
     hojas, regla del primer frame) para que José no las repita a mano cada
     vez que aparece un concepto nuevo.

En los tres casos, si José reemplaza el resultado a mano después, esa versión
gana siempre — no se toca `f9_generar.version_manual()` /
`f12_video_gen.version_manual()`, que ya resuelven "manual > IA" por sí solos.

Dónde cae el archivo (mismo mecanismo para 1 y 2, a propósito): en
`assets/generado/manual/<nombre>.png`, donde `<nombre>` es la MISMA palabra o
código que aparece en la columna "Qué se ve" del guion — es lo que ya busca
`f13_guion.resolver_codigo_asset()` sin que haga falta tocar nada del lado del
render.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import config

sys.path.insert(0, str(config.RAIZ_PROYECTO))
from artes import a11_agy  # noqa: E402
from artes import a12_codex  # noqa: E402


def _log(msg):
    print(msg, flush=True)


_PROVEEDORES = {
    "agy": {"nombre": "AGY (Google)", "disponible": a11_agy.disponible},
    "chatgpt": {"nombre": "ChatGPT (Codex CLI)", "disponible": a12_codex.disponible},
}


def disponible() -> bool:
    """Compatibilidad con los llamadores anteriores: AGY sigue siendo el default."""
    return a11_agy.disponible()


def proveedores_disponibles() -> list[dict]:
    """Proveedores que puede elegir el panel, sin depender de una API key."""
    return [
        {"id": ident, "nombre": datos["nombre"], "disponible": bool(datos["disponible"]())}
        for ident, datos in _PROVEEDORES.items()
    ]


def _proveedor_y_id(proveedor: str, conversation_id: str | None) -> tuple[str, str | None]:
    """Una corrección conserva el proveedor que generó la imagen original."""
    proveedor = (proveedor or "agy").lower()
    if conversation_id and ":" in conversation_id:
        proveedor_cid, id_real = conversation_id.split(":", 1)
        if proveedor_cid in _PROVEEDORES:
            proveedor, conversation_id = proveedor_cid, id_real
    if proveedor not in _PROVEEDORES:
        raise ValueError("Proveedor de imagen inválido. Elegí AGY o ChatGPT (Codex CLI).")
    if not _PROVEEDORES[proveedor]["disponible"]():
        raise RuntimeError(f"{_PROVEEDORES[proveedor]['nombre']} no está disponible o no tiene sesión iniciada.")
    return proveedor, conversation_id


def _generar_imagen(proveedor: str, instruccion: str, destino: Path,
                    referencias: list[Path] | None = None,
                    conversation_id: str | None = None) -> tuple[Path, str]:
    proveedor, conversation_id = _proveedor_y_id(proveedor, conversation_id)
    if proveedor == "chatgpt":
        ruta, cid = a12_codex.generar_imagen(
            instruccion, destino, referencias=referencias, thread_id=conversation_id)
        return ruta, f"chatgpt:{cid}"
    ruta, cid = a11_agy.generar_imagen(
        instruccion, destino, referencias=referencias, conversation_id=conversation_id)
    return ruta, f"agy:{cid}"


def _slug(texto: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (texto or "").lower()).strip("-")
    return (s[:40] or "img").rstrip("-")


# ---------------------------------------------------------------------------
# Catálogo de productos con foto real (para la vía "con producto")
# ---------------------------------------------------------------------------
def productos_disponibles() -> list[dict]:
    """{producto, foto} por cada carpeta de assets/productos/ con una frontal.

    Misma búsqueda que ya hace `f6_overlays._buscar_foto_producto_default()`,
    pero devolviendo TODAS las opciones (para un selector), no solo la primera.
    """
    dir_productos = config.DIR_ASSETS / "productos"
    if not dir_productos.exists():
        return []
    salida = []
    for carpeta in sorted(dir_productos.iterdir()):
        if not carpeta.is_dir():
            continue
        candidatos = sorted(carpeta.glob("frontal*.jpg")) + sorted(carpeta.glob("frontal*.png"))
        if candidatos:
            salida.append({
                "producto": carpeta.name,
                "foto": str(candidatos[0].relative_to(config.RAIZ_PROYECTO)).replace("\\", "/"),
            })
    return salida


# ---------------------------------------------------------------------------
# 1. Imagen de ambiente (sin producto)
# ---------------------------------------------------------------------------
def fotos_de_producto(producto: str) -> list[str]:
    """Todas las fotos reales de ese producto (no solo la frontal), para elegir
    a mano cuál mandar de referencia -- mismo criterio que la galería de fotos
    de Amazon del panel de artes (ver PANEL-ARTES.html, función fotos()).

    Devuelve rutas ABSOLUTAS (no relativas a RAIZ_PROYECTO) a propósito:
    `editor/f11_servidor.py` sirve estas fotos reusando su endpoint `/archivo`
    ya existente, que resuelve `Path(ruta).resolve()` contra el cwd del
    PROCESO del servidor -- no siempre RAIZ_PROYECTO (depende de cómo se haya
    arrancado, ej. `abrir_editor.py` desde otra carpeta). Confirmado
    2026-08-04: con ruta relativa, `/archivo?ruta=assets/productos/...` daba
    404 en el editor visual real de José aunque funcionaba en una prueba
    propia con el cwd "correcto" por casualidad. Con ruta absoluta,
    `.resolve()` es un no-op y el resultado no depende de dónde se lanzó el
    proceso.
    """
    carpeta = config.DIR_ASSETS / "productos" / producto
    if not carpeta.is_dir():
        return []
    exts = (".jpg", ".jpeg", ".png", ".webp")
    return [str(f) for f in sorted(carpeta.iterdir()) if f.suffix.lower() in exts]


def prompt_ambiente(nombre: str, idea_libre: str = "", contexto_guion: str = "") -> str:
    """Idea libre > tabla de tags conocida (config.PROMPTS_POR_TAG) por el nombre."""
    base = (idea_libre or "").strip()
    if not base:
        base = config.PROMPTS_POR_TAG.get(f"#{nombre}") or config.PROMPTS_POR_TAG.get(nombre) or ""
    if not base:
        raise ValueError(
            "Escribe una idea libre, o usa un nombre que ya tenga prompt en "
            "config.PROMPTS_POR_TAG (ej. 'sol', 'cama', 'agua')."
        )
    frase = " ".join(contexto_guion.split())[:110].strip(" ,.")
    partes = [base, config.PROMPT_ESTILO]
    if frase:
        partes.append(f"scene inspired by what is being said: {frase}")
    return ", ".join(p for p in partes if p)


def generar_ambiente(nombre: str, idea_libre: str = "", contexto_guion: str = "",
                      conversation_id: str | None = None,
                      proveedor: str = "agy") -> tuple[Path, str]:
    """Genera la imagen de ambiente con agy y la deja en manual/ (gana sobre Flux).

    `nombre` es la palabra/código que José usa en "Qué se ve" de esa fila —
    define el nombre del archivo, no solo una etiqueta decorativa.
    """
    if conversation_id and idea_libre:
        instruccion = (
            f"Ajusta la imagen anterior con esta corrección: {idea_libre}. "
            "Mantené el mismo estilo fotográfico, sin gente, sin texto ni logos."
        )
    else:
        instruccion = prompt_ambiente(nombre, idea_libre, contexto_guion)
    destino = config.DIR_GENERADO / "manual" / f"{_slug(nombre)}.png"
    return _generar_imagen(proveedor, instruccion, destino, conversation_id=conversation_id)


# ---------------------------------------------------------------------------
# 2. Imagen con el producto real compuesto en una escena
# ---------------------------------------------------------------------------
def _instruccion_escena_producto(escena: str) -> str:
    """Reglas de composición para PiP/B-roll con el aparato real.

    Hereda dos lecciones ya pagadas en este proyecto, con las que agy no viene
    de fábrica:
    - El diseño y la pantalla tienen que salir PIXEL-IDÉNTICOS a la referencia
      (ver artes-qwen-pipeline.md: es lo que Qwen y Flux nunca lograron).
    - Nunca inventar un logo ni animar un "pase de página": son los dos fallos
      reales y repetidos que José reportó generando con Veo/Google Flow para
      este mismo catálogo de productos (ver veo-blindaje-producto.md) — el
      mismo modelo (Gemini/Imagen) comete el mismo error en una imagen fija.
    """
    return f"""Sos director de arte para DeviceShop Bolivia (vende lectores electrónicos).
Tenés una foto de referencia del producto real (más abajo). Generá una imagen
fotorrealista vertical 9:16 que coloque ESE producto -- sin redibujarlo, sin
alterar su pantalla -- dentro de esta escena:

- Escena: {escena}
- Si aparece una persona, tiene que verse boliviana/latinoamericana, de clase
  media, mujer de 45 a 60 años (la compradora real según la cuenta de Meta).
- El cuerpo del aparato queda exactamente como en la foto de referencia: sin
  logos ni marcas nuevas, sin grabados ni texto que la referencia no tenga.
- La pantalla se mantiene PLANA Y RÍGIDA como un vidrio en todo momento: nunca
  se dobla, ondula ni se comporta como una hoja de papel, y nada sale, se
  despega ni flota de ella.
- Si una persona sostiene el producto, en pose FRONTAL Y PLANA -- igual que en
  la referencia, nunca en un ángulo distinto. Mejor que descanse sobre una mesa
  o falda a que alguien lo sostenga en alto (un ángulo nuevo obliga al modelo a
  reinterpretar la forma del aparato y ahí se deforma).
- Prohibido: texto legible que no sea el que ya tiene la pantalla del
  producto, logos nuevos, marcas de agua, gente que no sea la descrita.
- Es una FOTO FIJA, no un fotograma de video: no describas movimiento de
  cámara ni de la escena.

Mantené el diseño exacto y el contenido de pantalla de la imagen de
referencia, pixel-idéntico -- no lo reinterpretes ni lo redibujes. No lo gires
ni lo inclines respecto de cómo se ve en la referencia."""


def _instruccion_prompt_producto_texto(escena: str) -> str:
    """Como _instruccion_escena_producto(), pero para el paso barato de SOLO
    texto (revisar/ajustar el prompt antes de gastar la llamada de imagen) --
    la foto de referencia se adjunta después, en generar_producto().
    """
    return f"""Sos director de arte para DeviceShop Bolivia (vende lectores electrónicos).
Escribí UN prompt en inglés para generar una imagen publicitaria fotorrealista
vertical 9:16 que va a recibir ADEMÁS una foto de referencia real del
producto (se adjunta aparte al generar, vos no la ves ahora -- no la
describas, solo dejale lugar en la escena).

- Escena: {escena}
- Si aparece una persona, tiene que verse boliviana/latinoamericana, de clase
  media, mujer de 45 a 60 años.
- Prohibido: texto legible que no sea el que ya tenga la pantalla del
  producto, logos nuevos, marcas de agua.
- La pantalla del producto se describe como un vidrio plano y rígido que jamás
  se dobla, ondula ni se comporta como papel; nada sale, se despega ni flota
  de ella.
- Si alguien sostiene el producto, que sea en pose FRONTAL Y PLANA, nunca en
  un ángulo -- pedir una pose activa hace que el modelo reinterprete la forma
  del aparato y se deforme.
- Es una foto fija: no describas movimiento de cámara ni de escena.
- Terminá el prompt con esta instrucción textual: "Place the exact reference
  product into this scene, pixel-identical and at the same flat frontal angle
  as the reference, without redrawing, rotating, or altering it. Its screen
  stays perfectly flat and rigid, never paper-like."

Devolveme SOLO el prompt final en inglés, sin explicación, sin comillas, sin markdown."""


def prompt_producto_texto(escena: str, correccion: str = "",
                          conversation_id: str | None = None) -> tuple[str, str]:
    """Solo el TEXTO del prompt, para revisar/corregir barato antes de generar
    la imagen (que sí gasta la llamada de `generate_image`)."""
    if conversation_id and correccion:
        instruccion = (
            f"Ajustá el prompt anterior con esta corrección: {correccion}\n"
            "Devolveme SOLO el prompt final corregido en inglés, sin "
            "explicación, sin comillas, sin markdown."
        )
    else:
        instruccion = _instruccion_prompt_producto_texto(escena)
    texto, cid = a11_agy.generar_con_respaldo(instruccion, conversation_id)
    return texto.strip().strip('"'), cid


def generar_producto(nombre: str, escena: str, foto_producto: Path,
                      correccion: str = "", conversation_id: str | None = None,
                      prompt_armado: str = "", proveedor: str = "agy") -> tuple[Path, str]:
    """Genera la imagen CON el producto real ya compuesto, y la deja en manual/.

    `nombre` es la palabra/código de "Qué se ve" (define el archivo). Si
    `prompt_armado` viene (lo que José vio y aprobó en prompt_producto_texto),
    se usa TAL CUAL -- para que la imagen sea exactamente lo que revisó, no una
    versión re-derivada a ciegas.
    """
    foto_producto = Path(foto_producto)
    if not foto_producto.exists():
        raise ValueError(f"No existe la foto de referencia: {foto_producto}")
    destino = config.DIR_GENERADO / "manual" / f"{_slug(nombre)}.png"

    if conversation_id and correccion:
        instruccion = (
            f"Ajustá la imagen anterior con esta corrección: {correccion}. "
            "Mantené el mismo producto de la referencia, pixel-idéntico, sin "
            "redibujarlo ni alterar el contenido de su pantalla."
        )
        return _generar_imagen(proveedor, instruccion, destino, conversation_id=conversation_id)

    instruccion = prompt_armado.strip() or _instruccion_escena_producto(escena)
    return _generar_imagen(proveedor, instruccion, destino, referencias=[foto_producto])


# ---------------------------------------------------------------------------
# 3. Prompt de video para Google Flow / Veo (solo texto — agy no genera video)
# ---------------------------------------------------------------------------
# Dos ejemplos reales del banco (contexto/PROMPTS-GOOGLE-FLOW.md) como anclas
# de estilo, igual que a9_prompts.generar_titular_ia() usa titulares reales
# para que el formato salga IDÉNTICO, no solo parecido.
_EJEMPLOS_VEO = """### Ejemplo 1 (concepto: notificaciones que bombardean)
Vertical 9:16. Abstract visualization of relentless digital interruption: dozens of soft glowing rounded rectangles crowding the frame like a swarm, blurred and out of focus, cool blue and white light, overwhelming and claustrophobic. The frame is already packed with them in the very first frame: the swarm starts at its densest and never builds up from an empty or nearly empty screen, and more keep pouring in from the edges the whole time. Cinematic, elegant, minimal, shallow depth of field. Camera slowly pulls back as more of them pour in. The shapes are completely blank: no text, no icons, no symbols, no letters, no numbers, no logos, no watermark. No dialogue, no voiceover, subtle rising hum only.

### Ejemplo 2 (concepto: ojos cansados de noche)
Vertical 9:16. Intimate close-up of tired eyes at night, a person slowly rubbing them with the heel of the hand, blinking heavily, faint blue screen light on the face. Warm dark bedroom in the background, out of focus. Shot on an 85mm lens, shallow depth of field, natural editorial photography, soft realistic skin. Subtle handheld camera. Face partially in shadow, not a recognizable person. No text, no lettering, no logos, no watermark. No dialogue, no voiceover, quiet room tone only."""


def _instruccion_prompt_veo(idea: str, contexto_guion: str = "") -> str:
    frase = " ".join(contexto_guion.split())[:140].strip(" ,.")
    contexto = f'\nFrase del guion que este clip acompaña: "{frase}"' if frase else ""
    return f"""Escribí UN prompt en inglés para Google Flow (modelo Veo 3.1 Fast, clips de
8 segundos, 9:16 vertical) para este concepto de B-roll/PiP de DeviceShop
(vende lectores electrónicos, NUNCA nombrés una marca):

Concepto: {idea}{contexto}

Reglas DURAS de este proyecto, aprendidas generando decenas de estos clips
(no son sugerencias, son restricciones que si se rompen el clip no sirve):

1. **Regla del primer frame** -- el pipeline solo muestra los primeros 2-3
   segundos de los 8 que genera Veo. El concepto tiene que estar YA armado en
   el primer fotograma (nunca "una lámpara que se enciende", sino "una lámpara
   ya encendida"). Anclá con la fórmula "in the very first frame". Si hay
   movimiento, que termine antes del segundo 2 y el resto sea una cola
   sostenida ("within the first second... by the second second... from there
   it stays like that for the rest of the clip"). Prohibí explícitamente el
   arranque lento ("the video never opens in darkness, never fades up from
   black...").
2. **Blindaje de producto** -- si aparece un dispositivo electrónico de
   lectura, su cuerpo tiene que quedar completamente liso y sin marcas: "the
   device body is completely smooth, blank and unmarked: bare material with no
   brand name, no logo, no lettering and no engraving anywhere on it". Nunca
   pidas "turn a page" ni describas un pase de hoja -- es el disparador directo
   de que el modelo haga salir hojas de papel reales de la pantalla. Si la
   pantalla se ve, es "a flat rigid glass surface" que "stays perfectly flat at
   all times: nothing ever lifts, peels, curls, flies or emerges from it".
3. **Estilo fotográfico** -- shot on [lente]mm lens, shallow depth of field,
   natural editorial photography, describí la iluminación (warm/cool,
   dirección). Un solo movimiento de cámara simple (push in, tilt, dolly,
   pull back) o cámara estática -- nunca varios combinados.
4. **Cierre obligatorio del prompt** -- terminá siempre con una línea sobre
   qué NO debe verse: "No text, no lettering, no logos, no watermark." y una
   sobre audio: "No dialogue, no voiceover, [ambiente de sonido apropiado]
   only."
5. Arrancá el prompt con "Vertical 9:16." literal.

Dos ejemplos reales de este mismo banco, para que el formato salga idéntico
(mismo estilo de frase, mismo orden de bloques), no solo parecido:

{_EJEMPLOS_VEO}

Devolveme SOLO el prompt final en inglés, sin explicación, sin comillas, sin markdown."""


def generar_prompt_veo(idea: str, contexto_guion: str = "", correccion: str = "",
                        conversation_id: str | None = None) -> tuple[str, str]:
    """Solo texto -- agy no genera video (confirmado preguntándole sus tools:
    no tiene ninguna herramienta de video). José pega este prompt a mano en
    Google Flow y sube el resultado como siempre
    (assets/generado/video/manual/<nombre>.mp4)."""
    if conversation_id and correccion:
        instruccion = (
            f"Ajustá el prompt anterior con esta corrección: {correccion}\n"
            "Devolveme SOLO el prompt final corregido en inglés, sin "
            "explicación, sin comillas, sin markdown."
        )
    else:
        instruccion = _instruccion_prompt_veo(idea, contexto_guion)
    texto, cid = a11_agy.generar_con_respaldo(instruccion, conversation_id)
    return texto.strip().strip('"'), cid
