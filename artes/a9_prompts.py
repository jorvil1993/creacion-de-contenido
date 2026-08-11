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
- La gente se tiene que ver **de clase media Y ALTA, urbana, con estetica
  contemporanea**: nunca un living escandinavo, pero tampoco vestimenta
  tradicional/regional ni un aspecto rural o campesino. Sin nacionalidad ni
  etnia forzada -- corregido tres veces el 2026-08-04: primero se saco
  pedirle al generador que "se vea boliviana" (empujaba a un look
  campesino/rural), despues Jose pidio sacar directamente "tiene que verse
  latinoamericana" tambien ("nos frenara mucho"), y por ultimo pidio sumar
  "clase alta" a secas "clase media" -- ver artes-guardrail-demografico.md.
- El comprador real es adulto, 25 a 60 anios, no una veinteañera --
  no fuerces que sea siempre mujer. Segun cliente-ideal.md, a nivel nacional
  compran mas HOMBRES online que mujeres, y el perfil "lector/estudiante
  funcional" es explicitamente hombre o mujer de 25-45. La mujer de 35-60
  ("la lectora regalona") es quien MAS RESPONDE EN ADS, no la unica que compra
  -- usala cuando el angulo sea puntualmente de regalo o lectura emocional,
  no como default automatico.
- **Manos vacias** en la mitad de la solucion: el aparato se compone despues con
  el recorte de la foto real. Si lo dibuja el modelo, inventa uno que no vendemos.
- Sin marcas, sin logos, sin texto legible: el modelo los deforma.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re

from artes import a8_conceptos, a11_agy

# Fotos de referencia real de personas (2026-08-04, pedido de Jose para tener
# consistencia de cara entre piezas y no depender de que agy invente rasgos
# desde una descripcion de texto -- ver artes-guardrail-demografico.md). Cada
# archivo suelto en esta carpeta es una persona disponible para el selector
# del panel; el nombre de archivo (sin extension) es la clave y la etiqueta
# que ve Jose. Sumar una foto nueva no pide tocar codigo.
PERSONAS_DIR = Path(__file__).parent / "personas"
_EXT_PERSONA = (".jpg", ".jpeg", ".png", ".webp")


def listar_personas() -> list[str]:
    if not PERSONAS_DIR.exists():
        return []
    return sorted(p.stem for p in PERSONAS_DIR.iterdir() if p.suffix.lower() in _EXT_PERSONA)


def ruta_persona(clave: str) -> Path | None:
    if not clave or not PERSONAS_DIR.exists():
        return None
    for p in PERSONAS_DIR.iterdir():
        if p.suffix.lower() in _EXT_PERSONA and p.stem == clave:
            return p
    return None


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


def _bullet_persona(persona_foto: Path | None, *, obligatorio: bool = False) -> str:
    """Bullet de "quien aparece en la escena" -- con foto de referencia real
    si `persona_foto` viene (2026-08-04), o la regla generica si no.

    Con foto: le decimos a agy que MIRE el archivo (mismo truco que
    a11_agy.generar_imagen() -- agy lee del disco solo con que se mencione la
    ruta absoluta en el texto, confirmado 2026-08-03) y describa ESE aspecto
    fisico real en el prompt en vez de inventar uno -- asi ni el texto
    intermedio reintroduce un sesgo (el que motivo sacar "boliviana" del
    bullet generico, ver artes-guardrail-demografico.md).
    """
    obliga = "Tiene" if obligatorio else "Si aparece una persona, tiene"
    if persona_foto:
        return (
            f"- Hay una foto de referencia real de la persona (mirala antes de "
            f"escribir el prompt): {persona_foto.resolve()}\n"
            f"  {obliga} que describirse con el aspecto fisico TAL CUAL se ve "
            "en esa foto (pelo, tono de piel, edad aproximada, contextura) -- "
            "no inventes otro aspecto ni le fuerces una nacionalidad puntual, "
            "la foto ya define quien es. Describi solo su pose, expresion, "
            "ropa y la accion que pide esta escena nueva."
        )
    return (
        f"- {obliga} que verse de clase media y alta, urbana, adulta (25 a 60 "
        "anios), con ropa y entorno contemporaneos -- nunca vestimenta "
        "tradicional/regional ni un aspecto rural o campesino. Sin "
        "nacionalidad ni etnia forzada -- elegi vos el aspecto fisico que "
        "mejor sirva a la escena. Puede ser mujer U HOMBRE, los dos compran "
        "de verdad (cliente-ideal.md: a nivel nacional compran mas hombres "
        "online que mujeres). Usa mujer de 35-60 SOLO si el angulo apunta "
        "puntualmente al regalo o la lectura emocional -- es el perfil que "
        "mas responde en ads, no el unico comprador real."
    )


def _instruccion_escena_ia(nombre_producto: str, titular: str, escena_base: str,
                            formato: str, persona_foto: Path | None = None) -> str:
    """Arma la instruccion para que agy escriba un prompt de escena mejor.

    Mismas reglas heredadas del negocio que ya rigen SPLIT mas arriba (ver el
    docstring de este archivo): gente adulta (mujer u hombre), sin
    nacionalidad ni etnia forzada, manos vacias, sin marcas ni texto legible.
    """
    aspecto = "9:16 vertical portrait" if formato == "vertical" else "1:1 square"
    return f"""Sos director de arte para DeviceShop Bolivia (vende lectores electronicos).
Escribi UN prompt en ingles para un generador de imagenes (Gemini), que sirva de
FONDO de un arte publicitario. Reglas que no se rompen, salen del negocio real:

- La gente tiene que verse de clase media y alta, urbana, con ropa y entorno
  contemporaneos -- nunca un living escandinavo, y tampoco vestimenta
  tradicional/regional ni un aspecto rural o campesino. Sin nacionalidad ni
  etnia forzada.
{_bullet_persona(persona_foto)}
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
- Arriba de todo (aprox. el 15-20% superior del encuadre, no mas) va el
  titular en texto grande, se agrega despues, vos no lo dibujas. Con que esa
  franja angosta este un poco mas tranquila alcanza -- sin objetos
  protagonicos ni detalle fino justo ahi. NO la dejes vacia ni la conviertas
  en un bloque de color aparte: sigue siendo parte natural de la misma escena,
  solo un poco mas calma. Encontrado 2026-08-03: si lo mas interesante de la
  escena queda justo ahi arriba, el texto lo tapa.
- Abajo de todo (aprox. el 15% inferior) va despues el logo y los botones de
  contacto, en una franja solida -- no hace falta dejarla vacia ni cambiar el
  encuadre por eso, solo evita que algo importante de la escena quede cortado
  justo en ese borde inferior.

Devolveme SOLO el prompt final en ingles, sin explicacion, sin comillas, sin markdown."""


def generar_prompt_ia(nombre_producto: str, titular: str, escena_base: str,
                       formato: str, correccion: str = "",
                       conversation_id: str | None = None,
                       persona: str = "") -> tuple[str, str]:
    """Prompt de escena redactado por agy en vez del armado fijo del panel.

    Si `correccion` y `conversation_id` vienen los dos, continua la conversacion
    anterior y le pide solo el ajuste -- no repite todo el contexto de nuevo.

    `persona` es la clave (nombre de archivo sin extension) de una foto en
    artes/personas/ -- si viene, agy la mira y describe ese aspecto real en
    vez de inventar uno (ver _bullet_persona()).
    """
    if conversation_id and correccion:
        instruccion = (
            f"Ajusta el prompt anterior con esta correccion: {correccion}\n"
            "Devolveme SOLO el prompt final corregido en ingles, sin explicacion, "
            "sin comillas, sin markdown."
        )
    else:
        instruccion = _instruccion_escena_ia(nombre_producto, titular, escena_base, formato,
                                              persona_foto=ruta_persona(persona))

    texto, cid = a11_agy.generar_con_respaldo(instruccion, conversation_id)
    return texto.strip().strip('"'), cid


def _instruccion_escena_con_producto(titular: str, escena_base: str, formato: str,
                                      persona_foto: Path | None = None) -> str:
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
{_bullet_persona(persona_foto)}
- Formato de salida: {aspecto}.
- Foco comercial -- la escena tiene que demostrar esta idea sin necesitar
  texto: "{titular}"
- Prohibido: texto legible que no sea el que ya tiene la pantalla del producto,
  logos, marcas de agua.
- Si una persona sostiene el producto, tiene que quedar en una pose FRONTAL Y
  PLANA -- como en la foto de referencia -- nunca en un angulo o perspectiva
  distinta. Encontrado 2026-08-03: pedir que alguien lo "sostenga" en una pose
  activa hace que el modelo tenga que reinterpretar la forma del aparato desde
  otro angulo, y ahi se deforma (bordes curvos, aparato "volcado"). Preferible
  que descanse plano sobre una mesa o falda a que alguien lo sostenga en alto.
- Arriba de todo (aprox. el 15-20% superior del encuadre, no mas) va el
  titular en texto grande, se agrega despues. Evita que el producto o la
  persona queden justo en esa franja angosta -- el resto del encuadre (la
  mayor parte) es libre para componerlos con naturalidad. Encontrado
  2026-08-03: si el producto queda arriba de todo, el texto lo tapa.
- Abajo de todo (aprox. el 15% inferior) va despues el logo y los botones de
  contacto, en una franja solida -- no hace falta dejarla vacia ni cambiar el
  encuadre por eso, solo evita que la parte mas importante del producto quede
  cortada justo en ese borde inferior.

Mante el diseno exacto y el contenido de pantalla del producto de la imagen de
referencia, pixel-identico -- no lo reinterpretes ni lo redibujes. No lo
gires ni lo inclines respecto de como se ve en la referencia."""


def generar_imagen_producto_ia(titular: str, escena_base: str, formato: str,
                                foto_producto: Path, destino: Path,
                                correccion: str = "",
                                conversation_id: str | None = None,
                                prompt_armado: str = "",
                                persona: str = "",
                                proveedor: str = "agy") -> tuple[Path, str]:
    """Genera el fondo CON el producto real ya compuesto (via agy + Imagen),
    a partir de la foto de referencia -- sin pasar por el recorte local de
    a2_recorte.recortar(). Ver a11_agy.generar_imagen() para el mecanismo.

    Si `correccion` y `conversation_id` vienen los dos, continua la
    conversacion anterior (agy ya tiene la referencia y las reglas en
    contexto) en vez de volver a mandar todo de nuevo -- tampoco hace falta
    volver a mandar `persona`, agy ya la tiene en esa conversacion.

    Si `prompt_armado` viene (revisado/editado a mano despues de
    generar_prompt_producto_ia()), se usa TAL CUAL en vez de rearmarlo con
    _instruccion_escena_con_producto() -- para que lo que Jose vio y aprobo
    en el paso de texto sea EXACTAMENTE lo que agy recibe para la imagen,
    no una version re-derivada.

    `persona` es la clave de una foto en artes/personas/ -- si viene, se
    adjunta como referencia real ADEMAS de mencionarse en el texto (si
    `prompt_armado` la menciona), para maxima fidelidad visual.

    OJO: esta funcion SIEMPRE usa agy (nunca Codex) -- confirmado
    2026-08-03 que Codex no genera imagenes en el plan gratis de ChatGPT
    (ver panel-artes-integracion-agy.md). No pasa por generar_con_respaldo().
    """
    proveedor = (proveedor or "agy").lower()
    if conversation_id and ":" in conversation_id:
        proveedor_cid, conversation_id = conversation_id.split(":", 1)
        if proveedor_cid in ("agy", "chatgpt"):
            proveedor = proveedor_cid
    if proveedor not in ("agy", "chatgpt"):
        raise ValueError("Proveedor inválido: elegí AGY o ChatGPT (Codex CLI).")
    persona_foto = ruta_persona(persona)
    if conversation_id and correccion:
        instruccion = (
            f"Ajusta la imagen anterior con esta correccion: {correccion}. "
            "Mantene el mismo producto de la referencia, pixel-identico, sin "
            "redibujarlo ni alterar el contenido de su pantalla."
        )
        if proveedor == "chatgpt":
            from artes import a12_codex
            ruta, cid = a12_codex.generar_imagen(instruccion, destino, thread_id=conversation_id)
            return ruta, f"chatgpt:{cid}"
        ruta, cid = a11_agy.generar_imagen(instruccion, destino, conversation_id=conversation_id)
        return ruta, f"agy:{cid}"
    instruccion = prompt_armado.strip() or _instruccion_escena_con_producto(
        titular, escena_base, formato, persona_foto=persona_foto)
    referencias = [foto_producto] + ([persona_foto] if persona_foto else [])
    if proveedor == "chatgpt":
        from artes import a12_codex
        ruta, cid = a12_codex.generar_imagen(instruccion, destino, referencias=referencias)
        return ruta, f"chatgpt:{cid}"
    ruta, cid = a11_agy.generar_imagen(instruccion, destino, referencias=referencias)
    return ruta, f"agy:{cid}"


def _instruccion_prompt_producto_ia(titular: str, escena_base: str, formato: str,
                                     persona_foto: Path | None = None) -> str:
    """Como _instruccion_escena_ia() (la de solo-fondo), pero pensada para
    usarse CON una foto de referencia real adjunta -- no pide "manos vacias"
    ni "centro vacio", porque el producto real se adjunta aparte, no se
    compone despues con recorte local.

    Esto es SOLO texto (para revisar/ajustar barato antes de gastar la
    llamada de imagen) -- la referencia real del PRODUCTO se adjunta recien
    en generar_imagen_producto_ia(), este prompt no la ve. La foto de
    PERSONA si se menciona aca (si `persona_foto` viene) porque agy la puede
    leer del disco igual en un llamado de solo texto -- ver _bullet_persona().
    """
    aspecto = "9:16 vertical portrait" if formato == "vertical" else "1:1 square"
    return f"""Sos director de arte para DeviceShop Bolivia (vende lectores electronicos).
Escribi UN prompt en ingles para generar una imagen publicitaria que va a recibir
ADEMAS una foto de referencia real del producto (se adjunta aparte al momento de
generar, vos no la ves ahora -- no la describas, solo dejale lugar en la escena).

- Ambiente: {escena_base}
{_bullet_persona(persona_foto)}
- Formato de salida: {aspecto}.
- Foco comercial -- la escena tiene que demostrar esta idea sin necesitar
  texto: "{titular}"
- Prohibido: texto legible que no sea el que ya tenga la pantalla del
  producto, logos, marcas de agua.
- Si alguien sostiene el producto, que sea en pose FRONTAL Y PLANA, nunca en
  un angulo -- pedir una pose activa hace que el modelo tenga que reinterpretar
  la forma del aparato y ahi se deforma (encontrado 2026-08-03: salio
  "volcado"). Mejor que descanse plano sobre una mesa o falda.
- Arriba de todo (aprox. el 15-20% superior del encuadre, no mas) va el
  titular en texto grande, se agrega despues. Evita que el producto o la
  persona queden justo en esa franja angosta -- el resto del encuadre (la
  mayor parte) es libre para componerlos con naturalidad.
- Abajo de todo (aprox. el 15% inferior) va despues el logo y los botones de
  contacto, en una franja solida -- no hace falta dejarla vacia ni cambiar el
  encuadre por eso, solo evita que la parte mas importante del producto quede
  cortada justo en ese borde inferior.
- Termina el prompt con esta instruccion textual: "Place the exact reference
  product into this scene, pixel-identical and at the same flat frontal
  angle as the reference, without redrawing, rotating, or altering it."

Devolveme SOLO el prompt final en ingles, sin explicacion, sin comillas, sin markdown."""


def generar_prompt_producto_ia(titular: str, escena_base: str, formato: str,
                                correccion: str = "",
                                conversation_id: str | None = None,
                                persona: str = "") -> tuple[str, str]:
    """Genera SOLO el texto del prompt (sin gastar la llamada de imagen) para
    que Jose lo revise o corrija antes de componer -- usa
    a11_agy.generar_con_respaldo() (agy o Codex, el que tenga cuota) porque
    esto es barato y se presta a iterar varias veces.
    """
    if conversation_id and correccion:
        instruccion = (
            f"Ajusta el prompt anterior con esta correccion: {correccion}\n"
            "Devolveme SOLO el prompt final corregido en ingles, sin "
            "explicacion, sin comillas, sin markdown."
        )
    else:
        instruccion = _instruccion_prompt_producto_ia(titular, escena_base, formato,
                                                        persona_foto=ruta_persona(persona))
    texto, cid = a11_agy.generar_con_respaldo(instruccion, conversation_id)
    return texto.strip().strip('"'), cid


def _bullet_producto_carrusel(fuente_producto: str, nombre_producto: str) -> str:
    """Las reglas de COMO aparece el e-reader -- el bloque que cambia entre los
    dos modos del selector "¿De donde sale el e-reader?" del carrusel.

    En los DOS modos lo ubica el modelo dentro de su propia escena, nunca
    nosotros: probado el 2026-08-05, componer el recorte local encima con
    porcentajes fijos (recorte_x/recorte_y) no sabe donde quedo el hueco de la
    escena y el aparato aterriza sobre la persona o los muebles. Jose lo dijo
    directo: "tenemos que pasarle nuestra foto de referencia al modelo y que el
    la coloque en su foto".

    - `fuente_producto="nuestras"` (default): la foto real viaja adjunta y el
      prompt le pide que ponga ESE equipo, pixel-identico.
    - `fuente_producto="ia"`: no se adjunta nada y el modelo dibuja un e-reader
      generico. Sirve para bocetar rapido, pero OJO: el aparato que salga no es
      el que vendemos.
    """
    if fuente_producto == "ia":
        return f"""- El e-reader lo INVENTA el modelo: no se adjunta ninguna foto nuestra. Pedí un
  lector electronico moderno y generico, sin ninguna marca ni logo visible.
- Dentro del encuadre que elijas, el plano de la pantalla va lo MAS PARALELO
  posible a la camara: nada de tres cuartos fuerte, ni girado, ni "volcado" en
  diagonal. En angulos raros el modelo reinterpreta la forma del aparato y lo
  deforma (encontrado 2026-08-03).
- La pantalla es e-ink MATE en escala de grises con texto de un libro -- no es
  una tablet ni un celular: nada de colores saturados, brillo de LCD, iconos ni
  interfaz de app. Solo la cara frontal tiene pantalla; el dorso es liso.
- En las slides donde el aparato NO aparece: manos vacias, mesa vacia, y nada
  de tablets ni celulares haciendo de reemplazo.
- Producto que se vende (asi lo nombras en el prompt): {nombre_producto}"""
    return f"""- El e-reader es el NUESTRO: al generar cada imagen se le adjunta una foto real
  del producto como referencia. En las slides donde el aparato aparece, el
  prompt tiene que pedirle que coloque ESE equipo de la foto adjunta dentro de
  la escena -- mismo diseno, mismas proporciones, mismo grosor, mismos bordes--
  y que lo ubique el modelo mismo donde quede natural (en la mano, sobre la
  mesa, en la falda). Nosotros no lo pegamos despues: lo pone el.
- Dentro del encuadre que elijas, el plano de la pantalla va lo MAS PARALELO
  posible a la camara: nada de tres cuartos fuerte, ni girado, ni "volcado" en
  diagonal. En angulos raros el modelo reinterpreta la forma del aparato y lo
  deforma (encontrado 2026-08-03).
- La pantalla es e-ink MATE en escala de grises con texto de un libro -- no es
  una tablet ni un celular: nada de colores saturados, brillo de LCD, iconos ni
  interfaz de app. Solo la cara frontal tiene pantalla; el dorso es liso.
- Terminá el prompt de cada slide donde el aparato aparezca con esta frase
  textual: "Place the exact reference e-reader from the attached photo into this
  scene: same design, same proportions, same bezels, same screen. Do not redraw
  it, do not restyle it, do not invent a different device. Keep it in the exact
  pose and orientation described above."
  OJO: esa frase de cierre NO dice "frontal" a proposito -- si el encuadre pide
  que la pantalla apunte al personaje (D) y el cierre pidiera frontalidad, el
  prompt se contradice solo y sale la anomalia de alguien leyendo el dorso.
- En las slides donde NO aparece: manos vacias, mesa vacia, y nada de tablets ni
  celulares haciendo de reemplazo.
- Producto que se vende (asi lo nombras en el prompt): {nombre_producto}"""


# Encuadres del carrusel. Nacen de un fallo concreto que vio Jose el
# 2026-08-05 en la primera slide real: la mujer "leyendo" con la pantalla
# apuntando a la camara, o sea leyendo el dorso del aparato. La causa era
# nuestra: le pediamos "pose frontal y plana siempre" (para que no deforme el
# equipo) al mismo tiempo que "esta leyendo", y son incompatibles. En vez de
# elegir una sola toma segura, se le da el menu y que reparta -- de paso
# rompe la monotonia de n fotos de la misma persona en el mismo sillon.
ENCUADRES_CARRUSEL = {
    "A": "por encima del hombro",
    "B": "te lo muestra (mirada a camara)",
    "C": "bodegon, sin persona",
    "D": "lectura real, sin pantalla visible",
    "E": "sin aparato en la escena",
}

_MENU_ENCUADRES = """Encuadres disponibles -- elegí UNO por slide, con su letra:

- A = POR ENCIMA DEL HOMBRO. La camara esta detras y un poco arriba del
  personaje, mirando la pantalla que el esta leyendo. Lee de verdad Y la
  pantalla se ve entera. Poné la camara casi paralela a la pantalla, no en
  diagonal.
- B = TE LO MUESTRA. El personaje NO esta leyendo: te lo muestra. Mirada A
  CAMARA, aparato de frente sostenido con las dos manos o apoyado. Es la unica
  forma correcta de que la pantalla mire a camara con alguien en la escena.
- C = BODEGON, SIN PERSONA. El aparato solo: sobre la mesa de luz con una taza,
  en una repisa, cenital sobre la cama. La pantalla se ve perfecta y no hay
  nadie a quien contradecir.
- D = LECTURA REAL. El personaje lee con el aparato inclinado hacia el: se ve el
  dorso o el canto, NO la pantalla. Es la mas honesta y la mas emotiva -- en las
  slides de dolor o de beneficio la pantalla no hace falta, lo que vende es la
  cara.
- E = SIN APARATO. No aparece ningun aparato en la escena (manos vacias, mesa
  vacia, nada de tablets ni celulares de reemplazo).

Como repartirlos:
- La 1 (hook) va en E o en D: el aparato todavia no entro en la historia.
- El CTA (la ultima) va en B, o en C si no hay persona.
- El medio alterna A y D, con alguna C de respiro. NO uses el mismo encuadre en
  dos slides seguidas.

REGLA QUE NO SE ROMPE NUNCA -- coherencia mirada/pantalla: si el personaje mira
el aparato, la camara tiene que estar DE SU LADO (encuadre A) o la pantalla no
se ve (D). Si la pantalla apunta a la camara, el personaje mira A CAMARA (B).
Que la pantalla mire a camara mientras el personaje mira hacia abajo es
imposible: estaria leyendo el dorso. Escribi el prompt en ingles de modo que
esto quede explicito (a donde mira el personaje y hacia donde apunta la
pantalla)."""


def _instruccion_carrusel_ia(nombre_producto: str, idea: str, n: int, formato: str,
                              persona_foto: Path | None = None,
                              fuente_producto: str = "nuestras",
                              producto_ia: bool | None = None) -> str:
    """Guion completo de un carrusel de TikTok de `n` imagenes -- UNA historia,
    no n escenas sueltas. Devuelve un objeto (no una lista suelta) para poder
    seguir usando a11_agy.json_de() tal cual esta, sin tocarlo -- ese parser
    busca '{' y '}' como fallback, no '[' y ']'.

    Si `persona_foto` viene, TODAS las slides describen el mismo aspecto
    fisico real de esa foto (no cada una inventando el suyo). La continuidad
    viene de esa identidad y del tono visual, no de repetir la imagen anterior
    como referencia directa: eso terminaba clonando el mismo encuadre.

    `fuente_producto` decide de donde sale el e-reader (nuestra foto adjunta o
    inventado por el modelo) -- ver _bullet_producto_carrusel. Quien lo UBICA
    en la escena es siempre el modelo, en los dos casos.

    `producto_ia` se conserva como alias de compatibilidad para paneles locales
    que todavia lo enviaban antes de que el selector pasara a
    `fuente_producto`. No debe llegar desde interfaces nuevas.
    """
    if producto_ia is not None:
        fuente_producto = "ia" if producto_ia else "nuestras"
    aspecto = "9:16 vertical portrait" if formato == "vertical" else "1:1 square"
    return f"""Sos director de arte y copywriter para DeviceShop Bolivia (vende
lectores electronicos). Armá el guion de un carrusel de TikTok de {n} imagenes
que cuenten UNA historia de principio a fin. Conservá la misma familia, el
mismo estilo de hogar y la luz general, pero hacé que cada imagen avance con
una acción, un encuadre y una zona del hogar claramente distintos. No hagas
{n} escenas sueltas, pero tampoco repitas la misma foto con cambios mínimos.

Estructura obligatoria, en este orden:
- Imagen 1 = el HOOK: el problema o la pregunta que hace parar el dedo del scroll.
- Imagenes del medio = el VALOR: desarrollan el problema y muestran la solucion
  (el producto entra ahi, no antes).
- Ultima imagen = el CTA: cierre claro, el producto bien a la vista -- no
  describas ningun pie de contacto, eso se agrega despues por fuera.

Reglas que no se rompen (mismas de siempre):
{_bullet_persona(persona_foto)}
{_bullet_producto_carrusel(fuente_producto, nombre_producto)}
- Prohibido: texto legible, logos, marcas, marcas de agua.
- Formato de salida de cada imagen: {aspecto}.
- Arriba de todo (aprox. el 15-20% superior) se le agrega despues el titular en
  texto grande, y abajo de todo (aprox. el 15% inferior) el logo y el contacto
  en una franja solida. Vos no dibujas ninguna de las dos cosas, pero NO pongas
  el aparato ni la cara de la persona justo en esas dos franjas: el texto les
  cae encima. El resto del encuadre es libre.
- Cada prompt debe pedir una toma visualmente nueva: alterná plano abierto,
  plano medio o detalle; cambiá la acción y, cuando aporte a la historia, el
  rincón del hogar (sofá, mesa de lectura, biblioteca, balcón). Nunca uses
  frases como "same exact composition", "continuation of the exact shot" o
  "same pose".
- El titular de cada slide va CORTO -- 3 a 6 palabras, UNA sola linea (sin
  <br>) y mayusculas. Es OBLIGATORIO resaltar exactamente una palabra o frase
  clave con <span class='acento'>...</span>; no dejes ningun titular sin ese
  span. TikTok indexa el texto de cada slide y premia texto corto, no parrafos.

{_MENU_ENCUADRES}

Idea/angulo de esta historia: {idea}

Devolveme SOLO un JSON valido (sin explicacion, sin markdown), con esta forma
exacta -- un objeto con la clave "slides", lista de exactamente {n} objetos en
orden:
{{"slides": [{{"titular": "...", "prompt": "...", "encuadre": "A"}}, ...]}}
El campo "prompt" va en ingles, listo para un generador de imagenes, y tiene que
describir el encuadre que elegiste para esa slide.
El campo "encuadre" es UNA sola letra de la lista de arriba (A, B, C, D o E)."""


def _json_carrusel_de(texto: str) -> dict:
    """Lee el JSON del guion y tolera el HTML comun de los titulares.

    Un modelo a veces pone ``<span class="acento">`` dentro de un string JSON
    sin escapar esas comillas. El navegador acepta comillas simples en HTML,
    asi que se normaliza solo ese fragmento antes de delegar al parser comun.
    Las respuestas JSON correctas no se modifican.
    """
    try:
        return a11_agy.json_de(texto)
    except json.JSONDecodeError:
        corregido = re.sub(r'class="acento"', "class='acento'", texto)
        if corregido == texto:
            raise
        return a11_agy.json_de(corregido)


_SPAN_ACENTO = re.compile(r"<span\s+class\s*=\s*['\"]acento['\"]\s*>.*?</span>", re.I | re.S)


def _titular_con_acento(titular: object) -> str:
    """Garantiza el acento visual en los titulares creados por IA.

    La instruccion lo exige, pero un modelo puede ignorarla. En ese caso se
    resalta la ultima palabra, que normalmente contiene la idea-fuerza del
    titulo (por ejemplo, ``BOLIVIA`` o ``FUTURO``). Los titulos que ya traen
    el span se preservan exactamente como los escribio la IA.
    """
    texto = str(titular or "").strip()
    if not texto or _SPAN_ACENTO.search(texto):
        return texto
    palabras = texto.split()
    palabra_clave = palabras.pop()
    palabras.append(f"<span class='acento'>{palabra_clave}</span>")
    return " ".join(palabras)


def generar_guion_carrusel_ia(nombre_producto: str, idea: str, n: int, formato: str,
                               correccion: str = "",
                               conversation_id: str | None = None,
                               persona: str = "",
                               proveedor: str = "agy",
                               fuente_producto: str = "nuestras") -> tuple[list[dict], str]:
    """Como generar_titular_ia()/generar_prompt_producto_ia(), pero devuelve
    las `n` slides de una historia completa en un solo llamado -- barato
    (texto, agy o Codex), pensado para revisar/corregir antes de gastar
    ninguna llamada de imagen.

    `fuente_producto` viene del selector del panel ("nuestras" | "ia") y solo
    cambia las reglas del producto dentro de la instruccion -- ver
    _bullet_producto_carrusel(). El mismo valor tiene que llegar despues a
    _generar_carrusel(), que es quien decide si adjunta la foto real: si el
    prompt dice "the attached photo" y la foto no viaja, el modelo inventa un
    aparato.
    """
    if conversation_id and correccion:
        instruccion = (
            f"Ajusta el guion anterior con esta correccion: {correccion}\n"
            'Devolveme SOLO el JSON con la misma forma exacta '
            '{"slides": [{"titular": "...", "prompt": "...", "encuadre": "A"}, ...]}, '
            "sin explicacion ni markdown."
        )
    else:
        instruccion = _instruccion_carrusel_ia(nombre_producto, idea, n, formato,
                                                persona_foto=ruta_persona(persona),
                                                fuente_producto=fuente_producto)
    proveedor = (proveedor or "agy").lower()
    if proveedor == "chatgpt":
        from artes import a12_codex
        id_real = conversation_id
        if conversation_id and ":" in conversation_id:
            proveedor_anterior, id_real = conversation_id.split(":", 1)
            if proveedor_anterior != "codex":
                id_real = None
        texto, cid = a12_codex.generar(instruccion, thread_id=id_real)
        cid = f"codex:{cid}"
    elif proveedor == "agy":
        texto, cid = a11_agy.generar_con_respaldo(instruccion, conversation_id)
    else:
        raise ValueError("Proveedor invalido: elegi Antigravity o ChatGPT (Codex CLI).")
    datos = _json_carrusel_de(texto)
    slides = datos.get("slides") if isinstance(datos, dict) else None
    if not isinstance(slides, list) or not slides:
        raise RuntimeError(f"agy no devolvio slides validas: {texto[:300]}")
    for slide in slides:
        if not isinstance(slide, dict):
            raise RuntimeError("agy no devolvio slides validas: cada slide debe ser un objeto")
        slide["titular"] = _titular_con_acento(slide.get("titular"))
        # El encuadre es informativo (el panel lo muestra como etiqueta): lo que
        # manda es el prompt, que ya lo describe. Si el modelo devuelve
        # cualquier otra cosa se deja vacio en vez de inventar una letra.
        letra = str(slide.get("encuadre") or "").strip().upper()[:1]
        slide["encuadre"] = letra if letra in ENCUADRES_CARRUSEL else ""
    return slides, cid


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
- TUTEO, nunca voseo ni usted ("tu biblioteca", no "su biblioteca"; "puedes",
  no "podés" ni "puede"). Es el espanol neutro de LatAm: se entiende igual en
  Santa Cruz, La Paz y Cochabamba. Los ejemplos de arriba son frases nominales,
  que tampoco fallan.
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
    texto, cid = a11_agy.generar_con_respaldo(instruccion, conversation_id)
    return texto.strip().strip('"'), cid
