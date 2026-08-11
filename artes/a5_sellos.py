"""Sellos del arte: la insignia redonda de arriba a la derecha.

Todo en SVG, nunca emoji: el Chrome que hace el render no siempre trae una fuente
de emoji a color instalada y un emoji sin fuente sale en blanco. Misma leccion que
ya esta anotada en plantillas/README.md para los stickers del video.

**Los iconos son siluetas rellenas, no trazos.** El circulo mide ~190 px en el
lienzo final y el icono ~110: a ese tamano un trazo de linea fina se ve como un
garabato (probado y descartado el 2026-08-01). Relleno macizo y pocas formas.
"""
from __future__ import annotations

# Colores oficiales de la bandera de Bolivia.
ROJO, AMARILLO, VERDE = "#D52B1E", "#F9E300", "#007934"
TINTA = "#011A2E"

BANDERA_BO = (
    '<svg viewBox="0 0 30 20">'
    f'<rect width="30" height="6.667" y="0" fill="{ROJO}"/>'
    f'<rect width="30" height="6.667" y="6.667" fill="{AMARILLO}"/>'
    f'<rect width="30" height="6.666" y="13.333" fill="{VERDE}"/>'
    "</svg>"
)

# Scooter de reparto con la caja atras. Silueta rellena: las ruedas son discos
# con el centro calado, el resto un solo contorno.
MOTO = (
    f'<svg viewBox="0 0 64 40" fill="{TINTA}">'
    '<path d="M13 40a9 9 0 1 1 0-18 9 9 0 0 1 0 18zm0-5a4 4 0 1 0 0-8 4 4 0 0 0 0 8z"/>'
    '<path d="M51 40a9 9 0 1 1 0-18 9 9 0 0 1 0 18zm0-5a4 4 0 1 0 0-8 4 4 0 0 0 0 8z"/>'
    '<path d="M24 4h11a3 3 0 0 1 3 3v11h-6V9h-8a2.5 2.5 0 0 1 0-5z"/>'
    '<path d="M38 18h6l6 6h-4l-4-4h-4z"/>'
    '<path d="M22 30h20v-5H30l-5-8h-7l7 11z"/>'
    '<rect x="2" y="12" width="13" height="4" rx="2"/>'
    "</svg>"
)

# Apreton de manos, tercer intento. Los dos anteriores fallaron: el relleno
# macizo dio un borron y el trazo grueso un garabato. Este es esquematico —
# dos manoplas que se agarran, sin dedos — que es lo unico que sobrevive a 110 px.
MANOS = (
    f'<svg viewBox="0 0 64 40" fill="{TINTA}">'
    '<path d="M2 12h11l10 6v10L13 22H2z"/>'
    '<path d="M62 12H51l-10 6v10l10-6h11z"/>'
    '<rect x="24" y="15" width="16" height="11" rx="3"/>'
    "</svg>"
)

# QR: en Bolivia el pago por QR es universal (cliente-ideal.md) y Jose cobra
# justo asi en la entrega. A este tamano gana a cualquier apreton de manos
# porque son cuadrados grandes, no formas organicas.
QR = (
    f'<svg viewBox="0 0 40 40" fill="{TINTA}">'
    '<path d="M2 2h14v14H2zm4 4v6h6V6z"/>'
    '<path d="M24 2h14v14H24zm4 4v6h6V6z"/>'
    '<path d="M2 24h14v14H2zm4 4v6h6v-6z"/>'
    '<rect x="22" y="22" width="5" height="5"/>'
    '<rect x="31" y="22" width="7" height="5"/>'
    '<rect x="22" y="31" width="7" height="7"/>'
    '<rect x="33" y="30" width="5" height="4"/>'
    '<rect x="32" y="36" width="6" height="2"/>'
    "</svg>"
)


def html(clave: str) -> str:
    """Devuelve el interior del sello, o '' si no lleva sello."""
    return _SELLOS.get(clave, "")


def ancho(clave: str) -> float:
    """% del ancho del lienzo. Los de icono necesitan mas aire que el numerico.

    Ajustado 2026-08-04: primero se agrando (20.5->22.5, 18->19.5) para darle
    aire al texto, pero Jose lo vio al reves de lo que pidio -- el circulo
    quedo grande con contenido chico adentro, mucho relleno vacio. Se achica
    el circulo Y se sube el % que ocupa el contenido (ver .sello padding e
    .ico en plantillas/hook-escena.html) para que el circulo quede ajustado
    al contenido, no al reves.
    """
    return 17.5 if clave in ("moto", "manos", "qr") else 15.5


_SELLOS = {
    # El "6" manda y la bandera lo ancla al pais. La bandera va ancha: a menos
    # del 50% del circulo deja de leerse como bandera.
    "anios": (
        '<span class="num">6</span>'
        '<span class="lab">AÑOS EN BOLIVIA</span>'
        f'<span class="bandera">{BANDERA_BO}</span>'
    ),
    "moto": (
        f'<span class="ico">{MOTO}</span>'
        '<span class="lab">ENVÍOS A<br>TODA BOLIVIA</span>'
    ),
    "manos": (
        f'<span class="ico">{MANOS}</span>'
        '<span class="lab">PAGAS<br>AL RECIBIR</span>'
    ),
    "qr": (
        f'<span class="ico">{QR}</span>'
        '<span class="lab">PAGAS<br>AL RECIBIR</span>'
    ),
    "": "",
}
