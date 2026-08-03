"""Copy del post: 3 variantes por arte, cada una con su bloque para copiar.

Las tres estructuras NO son inventadas: salen de
`deviceshop/DOCUMENTOS MD DE LA EMPRESA/copys-anuncios-meta.md`, que a su vez sale
de los datos reales de la cuenta de Meta. El patron ganador medido es
**pregunta directa + angulo regalo + CTA a conversar** (mejor anuncio historico:
CTR 6,89%, $0,10 por conversacion).

Reglas que no se rompen (mismas fuentes):
- CTA siempre a CONVERSAR ("escribinos"), nunca "compra ya" — asi es el flujo real.
- Una sola idea por pieza. No mezclar regalo + vista + comparacion.
- Beneficio emocional primero, specs despues.
- 1 a 3 emojis, no mas.
- No prometer descuentos: hoy no hay promocion activa.
"""
from __future__ import annotations

from dataclasses import dataclass

from artes import a11_agy

WHATSAPP = "692-14437"

# Hashtags NACIONALES. Jose corrigio (2026-08-01): no etiquetar Santa Cruz
# cuando se vende a todo el pais — el envio nacional es argumento de venta,
# y un hashtag de ciudad le dice al de Sucre o Tarija que no es para el.
HASHTAGS = (
    "#DeviceShopBo #Kindle #Kobo #LecturaDigital "
    "#Bolivia #EnviosBolivia #RegalosBolivia #Ebook"
)


@dataclass
class Producto:
    nombre: str
    beneficio: str        # el emocional, va primero
    spec_fuerte: str      # el dato duro que respalda
    objecion: str         # la que resuelve
    respuesta: str


def variantes(p: Producto, ocasion: str = "") -> dict[str, str]:
    """Devuelve las 3 variantes listas para pegar."""
    gancho_ocasion = f" {ocasion}" if ocasion else ""

    emocional = f"""¿Buscás un regalo que de verdad vaya a usar? 🎁

{p.beneficio}

Un {p.nombre} es miles de libros en un solo aparato: se lee como papel real, no cansa la vista y la batería dura semanas.

Nuevo, en caja sellada, con garantía de 1 mes y entrega inmediata desde stock propio — no esperás ninguna importación.

📱 Escribinos al {WHATSAPP} y te ayudamos a elegir el ideal.

{HASHTAGS}"""

    racional = f""""Con mi tablet leo igual"… ¿seguro? 🤔

Tablet: brilla al sol, te distrae con notificaciones, cansa la vista, se descarga en horas.
{p.nombre}: se lee como papel incluso a plena luz, cero distracciones, {p.spec_fuerte}.

{p.objecion}
→ {p.respuesta}

Si de verdad querés leer más, el aparato importa.

📱 Preguntanos al {WHATSAPP} cuál te conviene según lo que leés.

{HASHTAGS}"""

    oferta = f"""{p.nombre} — entrega inmediata{gancho_ocasion} 📚

{p.beneficio}

✅ Nuevo y sellado
✅ Garantía de 1 mes
✅ Stock propio: lo recibís ya, sin esperar importación
✅ Envíos a todo el país · QR contra entrega

6 años vendiendo lectores electrónicos en Bolivia. Solo esto: por eso sabemos cuál te sirve.

📱 Escribinos al {WHATSAPP} y te asesoramos.

{HASHTAGS}"""

    return {
        "emocional": emocional.strip(),
        "racional": racional.strip(),
        "oferta": oferta.strip(),
    }


def _instruccion_ia(p: Producto, ocasion: str = "") -> str:
    gancho_ocasion = f"\n- Ocasion: {ocasion}" if ocasion else ""
    return f"""Sos copywriter de DeviceShop Bolivia, vende lectores electronicos (Kindle, Kobo).
Escribi 3 variantes de copy para un post de Facebook/Instagram de este producto,
usando SOLO estos datos ya verificados -- no inventes specs ni beneficios que no esten aca:

- Producto: {p.nombre}
- Beneficio emocional: {p.beneficio}
- Dato duro (spec): {p.spec_fuerte}
- Objecion mas comun: {p.objecion}
- Respuesta a esa objecion: {p.respuesta}{gancho_ocasion}

Datos reales que tambien podes usar (son ciertos para cualquier producto de la tienda):
nuevo y sellado, garantia de 1 mes, entrega inmediata desde stock propio (sin
esperar importacion), 6 anios vendiendo lectores electronicos en Bolivia.

Reglas de la marca, no las rompas:
- El CTA siempre invita a CONVERSAR ("escribinos al {WHATSAPP}"), nunca "compra ya".
- Una sola idea por variante -- no mezcles regalo + specs + comparacion en la misma pieza.
- El beneficio emocional va primero, el dato duro despues.
- 1 a 3 emojis por variante, no mas.
- No prometas descuentos: hoy no hay promocion activa.
- Cada variante termina con estos hashtags exactos: {HASHTAGS}

Las 3 variantes:
1. "emocional": angulo regalo/emocion, cierra invitando a escribir para elegir el ideal.
2. "racional": contraste con leer en el celular/tablet, usa el dato duro y responde la objecion.
3. "oferta": lista de checks (nuevo y sellado, garantia, stock propio, envios), cierra
   mencionando los anos de la tienda en Bolivia.

Devolveme SOLO un JSON valido, sin explicacion ni markdown, con esta forma exacta:
{{"emocional": "...", "racional": "...", "oferta": "..."}}"""


def generar_con_ia(p: Producto, ocasion: str = "", correccion: str = "",
                    conversation_id: str | None = None) -> tuple[dict[str, str], str]:
    """Como variantes(), pero redactado por agy en vez de la plantilla fija.

    El LLM solo recibe los campos YA VERIFICADOS de `p` -- la misma regla que
    hace cumplir por_clave() mas abajo (no inventar specs ni beneficios).
    Si `correccion` y `conversation_id` vienen los dos, continua la conversacion
    anterior en vez de repetir todo el contexto de negocio.
    """
    if conversation_id and correccion:
        instruccion = (
            f"Ajusta las 3 variantes anteriores con esta correccion: {correccion}\n"
            'Devolveme SOLO el JSON con la forma exacta '
            '{"emocional": "...", "racional": "...", "oferta": "..."}, sin explicacion ni markdown.'
        )
    else:
        instruccion = _instruccion_ia(p, ocasion)

    texto, cid = a11_agy.generar(instruccion, conversation_id)
    copys = a11_agy.json_de(texto)
    faltan = {"emocional", "racional", "oferta"} - copys.keys()
    if faltan:
        raise RuntimeError(f"agy no devolvio las 3 variantes completas (faltan: {faltan})")
    return copys, cid


PAPERWHITE = Producto(
    nombre="Kindle Paperwhite 16GB",
    beneficio="Miles de libros en un aparato del grosor de una revista.",
    spec_fuerte="batería de semanas y resistencia al agua IPX8",
    objecion='"¿Para qué pago esto si puedo leer en el celular?"',
    respuesta="En el celular te distraen las notificaciones y cansa la vista. "
              "El Kindle es solo para leer — por eso sí terminás los libros.",
)

_OBJECION_CELULAR = '"¿Para qué pago esto si puedo leer en el celular?"'
_RESPUESTA_CELULAR = (
    "En el celular te distraen las notificaciones y cansa la vista. "
    "Este Kindle es solo para leer — por eso sí terminás los libros."
)

# Un Producto por CLAVE de carpeta de fotos (misma clave que a8_conceptos.FICHAS
# y a2_recorte.fotos_de). Bug corregido 2026-08-01: el panel generaba SIEMPRE el
# copy del Paperwhite sin importar el producto elegido, porque `variantes()` se
# llamaba con `PAPERWHITE` a mano en vez de buscar por `cfg["producto"]`.
PRODUCTOS: dict[str, Producto] = {
    "kindle-paperwhite": PAPERWHITE,
    "kindle-basic": Producto(
        nombre="Kindle Basic 2024",
        beneficio="El más liviano para arrancar a leer sin gastar de más.",
        spec_fuerte="16 GB y batería de hasta 6 semanas con una carga",
        objecion=_OBJECION_CELULAR,
        respuesta=_RESPUESTA_CELULAR,
    ),
    "colorsoft-32gb": Producto(
        nombre="Kindle Colorsoft 32GB",
        beneficio="Portadas y cómics como se ven en papel, ahora a color.",
        spec_fuerte="pantalla a color, 32 GB y hasta 8 semanas de batería",
        objecion=_OBJECION_CELULAR,
        respuesta=_RESPUESTA_CELULAR,
    ),
    "kindle-scribe-2025-64-gb": Producto(
        nombre="Kindle Scribe 64GB",
        beneficio="Tu cuaderno y tu biblioteca en un solo aparato, con lápiz incluido.",
        spec_fuerte="64 GB, pantalla grande y lápiz incluido sin cargarlo aparte",
        objecion=_OBJECION_CELULAR,
        respuesta=_RESPUESTA_CELULAR,
    ),
    "kobo-libra-colour-32-gb": Producto(
        nombre="Kobo Libra Colour 32GB",
        beneficio="Cualquier libro o cómic, sin depender de una sola tienda.",
        spec_fuerte="pantalla Kaleido 3 a color, 32 GB y resistente al agua",
        objecion=_OBJECION_CELULAR,
        respuesta=_RESPUESTA_CELULAR,
    ),
    # Los 5 de abajo se agregaron el 2026-08-01, con specs verificadas contra
    # la pagina oficial de cada producto.
    #
    # kobo-stylus queda AFUERA a proposito: es el lapiz accesorio, no un
    # lector, y la plantilla de variantes() da por hecho que el producto "es
    # miles de libros en un aparato" — publicar eso de un lapiz seria
    # exactamente el tipo de error que este archivo existe para evitar. Si se
    # necesita copy para el stylus, hace falta una plantilla propia, no
    # forzarlo en esta.
    "kindle-scribe-colorsoft-32-gb": Producto(
        nombre="Kindle Scribe Colorsoft 32GB",
        beneficio="El primer Scribe con pantalla a color: tu cuaderno y tu "
                  "biblioteca, ahora con portadas y notas como en papel.",
        spec_fuerte="32 GB, pantalla a color y lápiz incluido sin cargarlo aparte",
        objecion=_OBJECION_CELULAR,
        respuesta=_RESPUESTA_CELULAR,
    ),
    "kindle-scribe-colorsoft-64gb": Producto(
        nombre="Kindle Scribe Colorsoft 64GB",
        beneficio="El primer Scribe con pantalla a color: tu cuaderno y tu "
                  "biblioteca, ahora con portadas y notas como en papel.",
        spec_fuerte="64 GB, pantalla a color y lápiz incluido sin cargarlo aparte",
        objecion=_OBJECION_CELULAR,
        respuesta=_RESPUESTA_CELULAR,
    ),
    "kinlde-paperwhite-32gb": Producto(
        nombre="Kindle Paperwhite 32GB",
        beneficio="El doble de espacio del Paperwhite clásico, para no volver "
                  "a pensar en el almacenamiento.",
        spec_fuerte="32 GB, batería de hasta 12 semanas y resistencia al agua IPX8",
        objecion=_OBJECION_CELULAR,
        respuesta=_RESPUESTA_CELULAR,
    ),
    "kobo-clara-colour-16gb": Producto(
        nombre="Kobo Clara Colour 16GB",
        beneficio="Cómics y portadas como se ven en papel, en el Kobo más compacto.",
        spec_fuerte="pantalla Kaleido 3 a color, 16 GB y resistente al agua IPX8",
        objecion=_OBJECION_CELULAR,
        respuesta=_RESPUESTA_CELULAR,
    ),
    "paperwhite-kids": Producto(
        nombre="Kindle Paperwhite Kids",
        beneficio="6 meses de Amazon Kids+ incluidos: libros infantiles listos "
                  "para que arranque a leer.",
        spec_fuerte="control parental, resistencia al agua IPX8 y batería de "
                    "hasta 12 semanas",
        objecion='"¿Para qué le compro esto si puede leer en la tablet?"',
        respuesta="En la tablet hay juegos y videos a un toque. Este Kindle es "
                  "solo para leer — y vos controlás todo desde el Parental Dashboard.",
    ),
}


def por_clave(clave: str) -> Producto:
    """El Producto para el copy, buscado por clave de carpeta de fotos.

    Si el producto todavia no tiene ficha de copy verificada, se avisa con un
    error en vez de devolver el copy de otro producto — la regla de Jose es
    "severo con eso, no podemos inventarnos o equivocarnos".
    """
    p = PRODUCTOS.get(clave)
    if p is None:
        raise KeyError(
            f"'{clave}' todavia no tiene copy verificado en a3_copy.PRODUCTOS"
        )
    return p
