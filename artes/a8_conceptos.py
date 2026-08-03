"""Conceptos: el titular y la escena nacen juntos, no se pegan uno sobre otra.

Pedido de Jose (2026-08-01): "los titulos tienen que tener sentido con el arte".
Su ejemplo: para "miles de libros en tu bolsillo", la imagen tiene que MOSTRAR
un libro gordo que no entra en el bolsillo al lado del Kindle que entra solo.
La imagen demuestra la frase; no la decora.

Por eso cada concepto trae su `escena` (el prompt para Qwen) pegada a su
`titular`. Cambiar uno sin el otro rompe la pieza.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Concepto:
    clave: str
    titular: str          # admite <span class="acento">
    escena: str           # prompt para Qwen; describe lo que DEMUESTRA el titular
    modo: str = "limpio"  # limpio | dolores | fichas
    nota: str = ""


CONCEPTOS = [
    Concepto(
        clave="bolsillo",
        titular='TU BIBLIOTECA<br>ENTRA EN UN <span class="acento">BOLSILLO</span>',
        escena=(
            "A thick heavy hardcover book being forced into a coat pocket and "
            "clearly not fitting, next to the same coat pocket with a slim "
            "e-reader sliding in easily. Side by side comparison on a clean "
            "neutral background, soft studio light. Photorealistic."
        ),
        nota="La idea de Jose: el libro gordo que NO entra vs el Kindle que si.",
    ),
    Concepto(
        clave="cafe",
        titular='TU PRÓXIMA HISTORIA<br>EMPIEZA <span class="acento">ACÁ</span>',
        escena=(
            "Empty warm wooden cafe table with a ceramic coffee cup, soft "
            "afternoon window light, blurred cozy cafe interior, shallow depth "
            "of field. No devices, no screens. Photorealistic."
        ),
        nota="Escena de cafe = momento de leer, no specs. El titular acompaña el clima.",
    ),
    Concepto(
        clave="sol",
        titular='SE LEE HASTA<br>CON EL <span class="acento">SOL ENCIMA</span>',
        escena=(
            "Bright sunny poolside terrace, strong direct midday sunlight, empty "
            "wooden lounge chair with a towel, sparkling water in the background. "
            "No devices, no screens. Photorealistic.",
        ),
        modo="dolores",
        nota="Demuestra la objecion #1 (la tablet brilla al sol).",
    ),
    Concepto(
        clave="noche",
        titular='LEER DE NOCHE<br>SIN <span class="acento">DESVELARTE</span>',
        escena=(
            "Dark cozy bedroom at night, warm bedside lamp, an empty pillow and "
            "soft blanket, very low warm light. No devices, no screens. "
            "Photorealistic."
        ),
        modo="dolores",
    ),
    Concepto(
        clave="viaje",
        titular='TODOS TUS LIBROS<br>SIN <span class="acento">CARGAR PESO</span>',
        escena=(
            "Open travel backpack on a wooden bench with a rolled sweater and a "
            "passport, outdoor natural light, blurred park background. "
            "No devices, no screens. Photorealistic."
        ),
    ),
    Concepto(
        clave="regalo",
        titular='EL REGALO QUE SÍ<br>VA A <span class="acento">USAR</span>',
        escena=(
            "Elegant gift wrapping scene: kraft paper, satin ribbon and a small "
            "gift tag on a warm wooden table, soft festive bokeh lights in the "
            "background. No devices, no screens. Photorealistic."
        ),
        nota="El angulo con datos propios: CTR 6,89% y $0,10 por conversacion.",
    ),
    # Comodin para la pestana Antigravity (panel_servidor_artes._generar()
    # exige un Concepto valido por clave): ahi el titular y la escena salen
    # SIEMPRE de la idea libre generada con agy, nunca de estos dos campos.
    # Existe solo para que por_clave() no tire KeyError y el nombre del
    # archivo de salida tenga un slug legible ("libre") en vez de reusar el
    # de otro concepto por error.
    Concepto(
        clave="libre",
        titular="",
        escena="",
        modo="limpio",
        nota="Comodin de la pestana Antigravity -- no se usa directo.",
    ),
]


# Dolores EMOCIONALES, no caracteristicas. Jose pidio 5-6 y que sean "los que
# llevan a la gente a comprarse un Kindle".
#
# Salen de fuentes propias, ninguno inventado:
#   - objeciones-respuestas.md (objecion #1: vista, distraccion, sol, bateria, sueño)
#   - hooks-ganadores.md (angulo 2 - dolor/problema)
#   - contexto/40-GUIONES-VIRALES.md ("el separador clavado en la pagina 30")
DOLORES = [
    ("Te arden los ojos leyendo en el celular",
     "Pantalla como papel: no te tira luz a los ojos"),
    ("Abrís a leer y terminás en TikTok",
     "Sin notificaciones. Es solo para leer"),
    ("Tenés un libro con el separador clavado hace meses",
     "Liviano y siempre encima: por eso sí los terminás"),
    ("Al sol la pantalla se vuelve un espejo",
     "Se lee a plena luz, como una hoja de papel"),
    ("De noche te desvela la luz de la tablet",
     "Luz cálida que no te corta el sueño"),
    ("Ya no te entran más libros en la casa",
     "Miles de libros en algo del grosor de una revista"),
]


# Fichas por producto. Cada dato esta verificado contra la pagina oficial del
# producto; si un dato no se pudo confirmar, NO entra (regla de Jose: "se severo
# con eso, no podemos inventarnos o equivocarnos").
FICHAS: dict[str, list[tuple[str, str, str]]] = {
    "kindle-paperwhite": [
        ("bateria", "Batería que dura semanas", "Hasta 12 semanas con una carga."),
        ("agua", "No le teme al agua", "IPX8: 2 m durante 60 minutos."),
        ("libros", "Tu biblioteca entera", "16 GB, miles de libros contigo."),
    ],
    "kindle-basic": [
        ("peso", "El más liviano de todos", "Cabe en cualquier cartera o mochila."),
        ("bateria", "Semanas sin cargador", "Hasta 6 semanas con una carga."),
        ("libros", "16 GB de espacio", "Miles de libros siempre encima."),
    ],
    "colorsoft-32gb": [
        ("color", "Portadas y cómics a color", "Pantalla a color tipo papel."),
        ("bateria", "Hasta 8 semanas", "Color sin el gasto de una tablet."),
        ("agua", "Diseño resistente al agua", "Llevalo a la piscina sin miedo."),
    ],
    "kindle-scribe-2025-64-gb": [
        ("lapiz", "Lápiz incluido", "No se carga ni se empareja: escribís y ya."),
        ("pantalla", "Pantalla grande", "Ideal para PDF, estudio y trabajo."),
        ("libros", "Leer y anotar en uno", "Tu cuaderno y tu biblioteca juntos."),
    ],
    "kobo-libra-colour-32-gb": [
        ("color", "Color para cómics", "Pantalla Kaleido 3 a color."),
        ("libros", "EPUB sin convertir", "No dependés de una sola tienda."),
        ("agua", "Resistente al agua", "Diseño impermeable."),
    ],
    # Los 6 de abajo se agregaron el 2026-08-01, verificados contra la pagina
    # oficial de cada producto (Amazon / us.kobobooks.com / help.kobo.com).
    "kindle-scribe-colorsoft-32-gb": [
        ("color", "Primer Scribe a color", "Pantalla Colorsoft: portadas, PDF y notas como en papel."),
        ("lapiz", "Lápiz incluido", "No se carga ni se empareja: escribís y ya."),
        ("pantalla", "Pantalla de 11\" grande", "32 GB para PDF, estudio y trabajo."),
    ],
    "kindle-scribe-colorsoft-64gb": [
        ("color", "Primer Scribe a color", "Pantalla Colorsoft: portadas, PDF y notas como en papel."),
        ("lapiz", "Lápiz incluido", "No se carga ni se empareja: escribís y ya."),
        ("memoria", "64 GB de espacio", "PDF, notas y libros, todo junto."),
    ],
    "kinlde-paperwhite-32gb": [
        ("libros", "32 GB de espacio", "El doble que el Paperwhite estándar: miles de libros de sobra."),
        ("agua", "No le teme al agua", "IPX8: 2 m durante 60 minutos."),
        ("bateria", "Batería que dura semanas", "Hasta 12 semanas con una carga."),
    ],
    "kobo-clara-colour-16gb": [
        ("color", "Cómics y portadas a color", "Pantalla E Ink Kaleido 3."),
        ("agua", "Resistente al agua", "IPX8: 2 m durante 60 minutos."),
        ("bateria", "Semanas sin cargador", "Hasta 6 semanas con 30 min de lectura diaria."),
    ],
    # Kobo Stylus 2: no es un lector, es el lapiz accesorio. Compatible con
    # Kobo Libra Colour, Sage, Elipsa y Elipsa 2E — NO con el Clara Colour
    # (confirmado en help.kobo.com, 2026-08-01).
    "kobo-stylus": [
        ("lapiz", "Sensible a la presión", "Línea más fina o gruesa según cuánto apretás."),
        ("bateria", "Se carga por USB-C", "Una hora de carga alcanza para semanas de uso."),
        ("pantalla", "Compatible con 4 modelos Kobo", "Libra Colour, Sage, Elipsa y Elipsa 2E."),
    ],
    "paperwhite-kids": [
        ("agua", "No le teme al agua", "IPX8: 2 m durante 60 minutos."),
        ("bateria", "Semanas de batería", "Hasta 12 semanas con una carga."),
        ("libros", "6 meses de Kids+ incluidos", "Miles de libros infantiles listos para leer."),
    ],
}


# Confianza. La frase larga que mas vende segun el analisis de 31 chats reales es
# "Hacemos entregas a domicilio sin costo adicional y paga cuando le entregan":
# aparece en casi TODAS las ventas de La Paz y Cochabamba. Jose pidio versiones
# cortas y que se vean bien.
CONFIANZA = {
    "pago": "Pagás cuando lo recibís",
    "envio": "Envío a domicilio sin costo",
    "sellado": "Nuevo y sellado",
    "garantia": "Garantía de 1 mes",
    "anios": "6 años en Bolivia",
    "hoy": "En Santa Cruz, hoy mismo",
}


def por_clave(clave: str) -> Concepto:
    for c in CONCEPTOS:
        if c.clave == clave:
            return c
    raise KeyError(clave)
