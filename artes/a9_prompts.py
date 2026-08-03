"""Prompts de imagen para Gemini Studio, escritos DESDE el objetivo comercial.

Jose corrigio esto el 2026-08-01: la primera version de estos prompts describia
una escena bonita pero no arrancaba de para que existe el arte ni a quien le
habla. Eran genericos y ni siquiera parecian Bolivia.

**Como se escribe un prompt aca.** Antes del texto en ingles van tres campos que
mandan sobre el prompt, no al reves:

  objetivo  — que tiene que lograr comercialmente esta pieza
  a_quien   — la persona concreta que la va a ver (de cliente-ideal.md)
  demuestra — que se tiene que entender de la imagen SIN leer el titular

Si el prompt no se puede justificar con esos tres, no sirve — por bonito que
salga. Y si cambia el objetivo, se reescribe el prompt entero.

**Reglas heredadas del negocio, no de un manual generico:**
- La gente se tiene que ver **boliviana**: rasgos latinoamericanos, casas de
  clase media boliviana. Un living escandinavo no le habla a nadie en Santa Cruz.
- La compradora real es **mujer de 45 a 60** (cliente-ideal.md), no una veinteañera.
- **Manos vacias** en la mitad de la solucion: el aparato se compone despues con
  el recorte de la foto real. Si lo dibuja el modelo, inventa uno que no vendemos.
- Sin marcas, sin logos, sin texto legible: el modelo los deforma.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from artes import a8_conceptos, a11_agy


@dataclass
class PromptImagen:
    clave: str
    para: str
    objetivo: str
    a_quien: str
    demuestra: str
    prompt: str
    chip: str = ""  # etiqueta corta que se imprime sobre la mitad, en el arte final


SPLIT = {
    # ------------------------------------------------------------------
    "ojos": (
        PromptImagen(
            clave="ojos-mal",
            para="Mitad izquierda — el dolor",
            objetivo="Frenar el scroll de quien lee en el celular todas las noches "
                     "y ya siente el cansancio, pero nunca lo relaciono con la pantalla.",
            a_quien="Mujer boliviana de 45-60, clase media, lee de noche en la cama "
                    "o en el sofa con el celular. Es la que mas responde a los "
                    "anuncios segun la cuenta de Meta.",
            demuestra="Que la molestia en los ojos viene de la pantalla que ilumina "
                      "la cara. Se tiene que entender sin leer una palabra.",
            prompt=(
                "Square framing, photorealistic. A Latin American woman in her "
                "fifties sitting on a sofa late at night in a modest, warm Latin "
                "American family living room. She has taken off her reading glasses "
                "and is rubbing her closed eyes with a tired, uncomfortable "
                "expression. Her face and chest are lit from below by the harsh "
                "cold blue light of a screen she holds low, below the frame. "
                "The rest of the room is dark. Cold blue light on her face, deep "
                "shadows, uncomfortable mood. Natural skin texture, real lived-in "
                "home, no text, no logos, no brand marks."
            ),
            chip="CANSA LA VISTA",
        ),
        PromptImagen(
            clave="ojos-bien",
            para="Mitad derecha — la solución",
            objetivo="Mostrar el mismo momento sin el problema, para que la compradora "
                     "se vea a si misma ahi. No vende specs: vende el rato tranquilo.",
            a_quien="La misma mujer, mismo sofa, misma hora. Si cambia la persona o "
                    "el lugar, deja de ser una comparacion y pasa a ser otra foto.",
            demuestra="Cero esfuerzo: hombros sueltos, cara relajada, luz calida. "
                      "El contraste con la izquierda es el argumento.",
            prompt=(
                "Square framing, photorealistic. The same Latin American woman in "
                "her fifties, same modest warm Latin American family living room, "
                "same sofa, same late evening. She sits comfortably with relaxed "
                "shoulders and a calm, softly pleased expression, wearing her "
                "reading glasses, looking down at her hands. Her hands rest open "
                "in a natural reading posture but they are completely empty. "
                "Warm amber light from a side table lamp falls evenly on her face. "
                "Cozy, calm, restful mood. Natural skin texture, real lived-in "
                "home, no text, no logos, no brand marks, no devices, no screens, "
                "no books, nothing in her hands."
            ),
            chip="LECTURA TRANQUILA",
        ),
    ),
    # ------------------------------------------------------------------
    "abandonado": (
        PromptImagen(
            clave="abandonado-mal",
            para="Mitad izquierda — el dolor",
            objetivo="Tocar la culpa del lector que compra libros y no los termina. "
                     "Es el dolor emocional mas fuerte del banco de hooks propio.",
            a_quien="Quien tiene la intencion de leer y no el habito. Se reconoce en "
                    "el libro parado en la pagina 30 desde hace meses.",
            demuestra="Abandono: polvo, separador clavado cerca del principio, el "
                      "libro cerrado y arrinconado.",
            prompt=(
                "Square framing, photorealistic close-up. A thick hardcover book "
                "lying closed and forgotten on a wooden bedside table in a Latin "
                "American home, a fabric bookmark clearly stuck near the very "
                "beginning of the book, a thin layer of dust on the cover, a "
                "half-empty glass of water beside it. Dim, cold, neglected "
                "atmosphere, muted colors. No text on the cover, no logos, "
                "no brand marks."
            ),
            chip="LIBRO ABANDONADO",
        ),
        PromptImagen(
            clave="abandonado-bien",
            para="Mitad derecha — la solución",
            objetivo="Mostrar el habito recuperado: leer todos los dias, sin ceremonia.",
            a_quien="El mismo lector, la misma mesa de luz. El cambio es de estado, "
                    "no de persona.",
            demuestra="Uso cotidiano: la mesa viva, luz calida encendida, todo listo "
                      "para leer esta noche.",
            prompt=(
                "Square framing, photorealistic close-up. The same wooden bedside "
                "table in the same Latin American home, now clean and warmly lit "
                "by a small bedside lamp, a folded reading blanket and a steaming "
                "cup of tea beside an empty clear space on the table where "
                "something flat usually rests. Inviting, warm, calm night "
                "atmosphere. No text, no logos, no brand marks, no devices, "
                "no screens, no books."
            ),
            chip="HÁBITO RECUPERADO",
        ),
    ),
    # ------------------------------------------------------------------
    # Los 4 pares que faltaban (2026-08-01): de los 6 dolores de DOLORES en
    # a8_conceptos.py, solo "ojos" y "abandonado" tenian comparativa partida.
    "distraccion": (
        PromptImagen(
            clave="distraccion-mal",
            para="Mitad izquierda — el dolor",
            objetivo="Que la lectora se reconozca abriendo el celular 'a leer' y "
                     "terminando en otra app. Es el dolor #2 del banco propio.",
            a_quien="Mujer boliviana de 45-60, clase media, intenta leer en el "
                    "celular en un sillon de living.",
            demuestra="La distraccion en el momento exacto: el dedo tocando un "
                      "icono de red social sobre la pantalla, no un libro.",
            prompt=(
                "Square framing, photorealistic. A Latin American woman in her "
                "fifties sitting in an armchair in a modest, warm Latin American "
                "living room, holding a phone low in her lap, her thumb mid-tap "
                "on a grid of colorful app icons on the screen, a distracted, "
                "slightly guilty expression on her face as she glances away from "
                "it. Cool screen glow on her hands and face, otherwise soft warm "
                "room light. Natural skin texture, real lived-in home, no visible "
                "app logos, no text, no brand marks."
            ),
            chip="SE VA A OTRA APP",
        ),
        PromptImagen(
            clave="distraccion-bien",
            para="Mitad derecha — la solución",
            objetivo="Mostrar la misma mujer absorta en la lectura, sin nada mas "
                     "compitiendo por su atencion.",
            a_quien="La misma mujer, mismo sillon. El cambio es de estado, no de "
                    "persona.",
            demuestra="Atencion completa: mirada fija hacia abajo, postura "
                      "relajada, manos vacias en posicion de sostener algo chato.",
            prompt=(
                "Square framing, photorealistic. The same Latin American woman in "
                "her fifties, same modest warm Latin American living room, same "
                "armchair. She sits with relaxed shoulders, fully absorbed, eyes "
                "looking down with a calm focused expression, holding her hands "
                "together in front of her in a natural reading posture but "
                "completely empty. Warm soft light, cozy focused mood. Natural "
                "skin texture, real lived-in home, no text, no logos, no brand "
                "marks, no devices, no screens, no books, nothing in her hands."
            ),
            chip="SOLO PARA LEER",
        ),
    ),
    # ------------------------------------------------------------------
    "sol": (
        PromptImagen(
            clave="sol-mal",
            para="Mitad izquierda — el dolor",
            objetivo="Demostrar la objecion #1 del negocio: al sol, la tablet se "
                     "vuelve un espejo y no se puede leer.",
            a_quien="Mujer boliviana de 45-60 en una terraza o patio, tratando de "
                    "leer afuera a plena luz.",
            demuestra="El reflejo: se tiene que ver la propia silueta o el cielo "
                      "reflejado en la pantalla, no el texto.",
            prompt=(
                "Square framing, photorealistic. A Latin American woman in her "
                "fifties sitting outdoors on a sunny terrace, holding a tablet up "
                "in front of her at reading distance, squinting with an annoyed "
                "expression, strong midday sunlight creating a harsh mirror-like "
                "glare across the screen that hides whatever is on it. Bright "
                "natural outdoor light, modest Latin American home terrace in the "
                "background. Natural skin texture, no text, no logos, no brand "
                "marks."
            ),
            chip="LA PANTALLA ES UN ESPEJO",
        ),
        PromptImagen(
            clave="sol-bien",
            para="Mitad derecha — la solución",
            objetivo="Mostrar que se puede leer comodo a pleno sol, sin pelear con "
                     "la pantalla.",
            a_quien="La misma mujer, la misma terraza. El cambio es de estado, no "
                    "de persona.",
            demuestra="Comodidad bajo la misma luz dura: cara relajada, sin "
                      "entrecerrar los ojos, manos vacias.",
            prompt=(
                "Square framing, photorealistic. The same Latin American woman in "
                "her fifties, same sunny terrace, same strong midday light. She "
                "sits comfortably with a relaxed, pleased expression, looking "
                "down with ease, no squinting, holding her hands together in a "
                "natural reading posture but completely empty. Bright natural "
                "outdoor light, calm comfortable mood. Natural skin texture, no "
                "text, no logos, no brand marks, no devices, no screens, no "
                "books, nothing in her hands."
            ),
            chip="SE LEE CON SOL ENCIMA",
        ),
    ),
    # ------------------------------------------------------------------
    "noche": (
        PromptImagen(
            clave="noche-mal",
            para="Mitad izquierda — el dolor",
            objetivo="Tocar el dolor de la luz de la tablet que corta el sueno.",
            a_quien="Mujer boliviana de 45-60 leyendo de noche en la cama antes de "
                    "dormir.",
            demuestra="Que la luz fria del dispositivo la mantiene despierta: cara "
                      "iluminada de forma dura en un cuarto oscuro.",
            prompt=(
                "Square framing, photorealistic. A Latin American woman in her "
                "fifties lying in bed at night in a dark modest Latin American "
                "bedroom, propped up on a pillow, her face lit harshly from below "
                "by the cold bright light of a tablet held close, a tired, "
                "wide-awake, strained expression. Rest of the room in deep "
                "darkness, cold blue light spill on the pillow and blanket. "
                "Natural skin texture, no text, no logos, no brand marks."
            ),
            chip="TE DESVELA LA LUZ",
        ),
        PromptImagen(
            clave="noche-bien",
            para="Mitad derecha — la solución",
            objetivo="Mostrar el mismo momento con una luz que invita a dormir, no "
                     "a quedarse despierta.",
            a_quien="La misma mujer, la misma cama. El cambio es de estado, no de "
                    "persona.",
            demuestra="Calma nocturna: luz calida y tenue, parpados pesados, manos "
                      "vacias sobre la colcha.",
            prompt=(
                "Square framing, photorealistic. The same Latin American woman in "
                "her fifties, same dark modest bedroom, same bed, same late hour. "
                "She lies propped on the pillow with heavy relaxed eyelids and a "
                "peaceful, sleepy expression, lit only by a warm dim bedside lamp, "
                "her hands resting open on the blanket in a natural reading "
                "posture but completely empty. Warm low light, cozy sleepy mood. "
                "Natural skin texture, no text, no logos, no brand marks, no "
                "devices, no screens, no books, nothing in her hands."
            ),
            chip="LUZ QUE NO DESVELA",
        ),
    ),
    # ------------------------------------------------------------------
    "espacio": (
        PromptImagen(
            clave="espacio-mal",
            para="Mitad izquierda — el dolor",
            objetivo="Mostrar que los libros fisicos ya no entran en la casa — el "
                     "dolor de quedarse sin espacio.",
            a_quien="Mujer boliviana de 45-60, lectora habitual, en su propia "
                    "casa de clase media.",
            demuestra="Saturacion: una repisa o rincon con libros apilados de mas, "
                      "sin lugar para uno nuevo.",
            prompt=(
                "Square framing, photorealistic. A small wooden bookshelf in a "
                "modest Latin American living room completely overflowing with "
                "books, stacked sideways on top of the upright rows because there "
                "is no more room, one extra book lying on the floor in front of "
                "it with no space left to place it. Warm but slightly cluttered "
                "and cramped atmosphere, natural indoor light. No text legible on "
                "spines, no logos, no brand marks."
            ),
            chip="YA NO ENTRAN LIBROS",
        ),
        PromptImagen(
            clave="espacio-bien",
            para="Mitad derecha — la solución",
            objetivo="Mostrar el mismo rincon liberado, en paz, sin la saturacion.",
            a_quien="La misma casa, el mismo rincon. El cambio es de estado, no de "
                    "lugar.",
            demuestra="Orden y aire: el mismo mueble ahora despejado, con espacio "
                      "de sobra.",
            prompt=(
                "Square framing, photorealistic. The same small wooden bookshelf "
                "in the same modest Latin American living room, now tidy with "
                "only a few books neatly upright and plenty of empty open space "
                "on the shelves, a small potted plant in the newly free space. "
                "Warm calm orderly atmosphere, natural indoor light. No text "
                "legible, no logos, no brand marks, no devices, no screens."
            ),
            chip="MILES DE LIBROS, UN APARATO",
        ),
    ),
}


def texto_para_html(clave: str) -> list[dict]:
    return [
        {
            "clave": p.clave, "para": p.para, "objetivo": p.objetivo,
            "a_quien": p.a_quien, "demuestra": p.demuestra, "prompt": p.prompt,
        }
        for p in SPLIT[clave]
    ]


def _instruccion_escena_ia(nombre_producto: str, titular: str, escena_base: str,
                            formato: str) -> str:
    """Arma la instruccion para que agy escriba un prompt de escena mejor.

    Mismas reglas heredadas del negocio que ya rigen SPLIT mas arriba (ver el
    docstring de este archivo): gente boliviana, mujer 45-60, manos vacias,
    sin marcas ni texto legible.
    """
    aspecto = "9:16 vertical portrait" if formato == "vertical" else "1:1 square"
    return f"""Sos director de arte para DeviceShop Bolivia (vende lectores electronicos).
Escribi UN prompt en ingles para un generador de imagenes (Gemini), que sirva de
FONDO de un arte publicitario. Reglas que no se rompen, salen del negocio real:

- La gente tiene que verse BOLIVIANA/latinoamericana, de clase media -- nunca
  un living escandinavo o gente que no representa a Bolivia.
- Si hay una persona, es mujer de 45 a 60 anios (es la compradora real segun
  la cuenta de Meta de la tienda).
- Manos VACIAS si alguien sostiene algo -- el aparato se compone DESPUES encima
  con el recorte de la foto real del producto. Si el modelo dibuja un aparato,
  arruina la pieza (inventa uno que no se vende).
- Prohibido: texto legible, logos, marcas, marcas de agua.
- Formato de salida: {aspecto}.
- Foco comercial -- la escena tiene que demostrar esta idea SIN necesitar texto:
  "{titular}"
- Referencia de ambiente (no la copies literal, es la base de la que partis):
  {escena_base}
- Producto que se vende (para que la escena tenga el tono correcto, no para
  que aparezca dibujado): {nombre_producto}
- Composicion: dejar el centro/primer plano completamente vacio y limpio, para
  componer despues un recorte 3D del producto encima.

Devolveme SOLO el prompt final en ingles, sin explicacion, sin comillas, sin markdown."""


def generar_prompt_ia(nombre_producto: str, titular: str, escena_base: str,
                       formato: str, correccion: str = "",
                       conversation_id: str | None = None) -> tuple[str, str]:
    """Prompt de escena redactado por agy en vez del armado fijo del panel.

    Si `correccion` y `conversation_id` vienen los dos, continua la conversacion
    anterior y le pide solo el ajuste -- no repite todo el contexto de nuevo.
    """
    if conversation_id and correccion:
        instruccion = (
            f"Ajusta el prompt anterior con esta correccion: {correccion}\n"
            "Devolveme SOLO el prompt final corregido en ingles, sin explicacion, "
            "sin comillas, sin markdown."
        )
    else:
        instruccion = _instruccion_escena_ia(nombre_producto, titular, escena_base, formato)

    texto, cid = a11_agy.generar(instruccion, conversation_id)
    return texto.strip().strip('"'), cid


def _instruccion_escena_con_producto(titular: str, escena_base: str, formato: str) -> str:
    """A diferencia de _instruccion_escena_ia(), esta SI quiere el producto en
    la imagen -- porque agy lo compone a partir de una foto de referencia real
    en vez de dibujarlo de cero. Por eso no pide "manos vacias" ni "sin
    dispositivos": esas reglas son para cuando el recorte local se compone
    despues, y aca no hay recorte local.
    """
    aspecto = "9:16 vertical portrait" if formato == "vertical" else "1:1 square"
    return f"""Sos director de arte para DeviceShop Bolivia (vende lectores electronicos).
Tenes una foto de referencia del producto real (mas abajo). Genera una imagen
publicitaria fotorrealista que coloque ESE producto -- sin redibujarlo, sin
alterar su pantalla -- dentro de esta escena:

- Ambiente: {escena_base}
- Si aparece una persona, tiene que verse boliviana/latinoamericana, de clase
  media, mujer de 45 a 60 anios (la compradora real segun la cuenta de Meta).
- Formato de salida: {aspecto}.
- Foco comercial -- la escena tiene que demostrar esta idea sin necesitar
  texto: "{titular}"
- Prohibido: texto legible que no sea el que ya tiene la pantalla del producto,
  logos, marcas de agua.

Mante el diseno exacto y el contenido de pantalla del producto de la imagen de
referencia, pixel-identico -- no lo reinterpretes ni lo redibujes."""


def generar_imagen_producto_ia(titular: str, escena_base: str, formato: str,
                                foto_producto: Path, destino: Path,
                                correccion: str = "",
                                conversation_id: str | None = None) -> tuple[Path, str]:
    """Genera el fondo CON el producto real ya compuesto (via agy + Imagen),
    a partir de la foto de referencia -- sin pasar por el recorte local de
    a2_recorte.recortar(). Ver a11_agy.generar_imagen() para el mecanismo.

    Si `correccion` y `conversation_id` vienen los dos, continua la
    conversacion anterior (agy ya tiene la referencia y las reglas en
    contexto) en vez de volver a mandar todo de nuevo.
    """
    if conversation_id and correccion:
        instruccion = (
            f"Ajusta la imagen anterior con esta correccion: {correccion}. "
            "Mantene el mismo producto de la referencia, pixel-identico, sin "
            "redibujarlo ni alterar el contenido de su pantalla."
        )
        return a11_agy.generar_imagen(instruccion, destino, conversation_id=conversation_id)
    instruccion = _instruccion_escena_con_producto(titular, escena_base, formato)
    return a11_agy.generar_imagen(instruccion, destino, referencias=[foto_producto])


def _instruccion_titular_ia(idea: str) -> str:
    """No reusa el titular del concepto anterior -- lo escribe de cero a partir
    de `idea`, pero copiando el estilo exacto de los titulares ya publicados
    (mayusculas, dos lineas, la ultima con la palabra clave resaltada). Sin
    esto el titular libre saldria con otro tono, otro largo, o sin el span de
    acento -- inconsistente con el resto de los artes.

    Ademas de imitar el ESTILO, se le suma el banco real de DOLORES y
    CONFIANZA (a8_conceptos.py) como material de fondo -- pedido explicito de
    Jose ("hay que alimentarlo con nuestra data tambien"): que el titular
    pueda anclarse en un dolor real del negocio si encaja con la idea, no solo
    imitar la forma de los titulares viejos sin sustancia.
    """
    ejemplos = "\n".join(f"- {c.titular}" for c in a8_conceptos.CONCEPTOS if c.titular)
    dolores = "\n".join(f"- {malo} -> {bien}" for malo, bien in a8_conceptos.DOLORES)
    confianza = ", ".join(a8_conceptos.CONFIANZA.values())
    return f"""Sos copywriter de DeviceShop Bolivia (vende lectores electronicos).
Escribi UN titular para un arte publicitario, copiando EXACTAMENTE el mismo
estilo de estos titulares ya publicados -- mayusculas, dos lineas separadas
por <br>, la ultima linea con la palabra o frase clave envuelta en
<span class="acento">...</span>, sin puntuacion final, corto y directo:

{ejemplos}

Banco real de dolores de los clientes (usalo SOLO si alguno encaja de verdad
con la idea de abajo, no lo fuerces):
{dolores}

Frases de confianza reales del negocio (idem, solo si suman):
{confianza}

La idea para este titular nuevo (no un concepto existente, uno nuevo): "{idea}"

Reglas de la marca:
- Tuteo neutro: nunca conjugues en voseo ("tenés", "podés", etc.) -- los
  ejemplos de arriba no lo usan, seguí ese patron (son frases nominales, no
  oraciones con vos).
- Beneficio o emocion primero, nunca una spec tecnica.

Devolveme SOLO el HTML del titular, en una sola linea, exactamente en el
formato de los ejemplos -- sin explicacion, sin comillas, sin markdown."""


def generar_titular_ia(idea: str, correccion: str = "",
                        conversation_id: str | None = None) -> tuple[str, str]:
    """Titular nuevo a partir de una idea libre (no de un Concepto fijo).

    Ver _instruccion_titular_ia(): no toma nada del titular que hubiera antes,
    parte solo de `idea` -- pero siempre con el mismo estilo de casa.
    """
    if conversation_id and correccion:
        instruccion = (
            f"Ajusta el titular anterior con esta correccion: {correccion}\n"
            "Devolveme SOLO el HTML del titular corregido, mismo formato, sin "
            "explicacion ni comillas."
        )
    else:
        instruccion = _instruccion_titular_ia(idea)
    texto, cid = a11_agy.generar(instruccion, conversation_id)
    return texto.strip().strip('"'), cid
