"""Rotacion de escena y de palancas de venta, para que dos artes seguidos no se parezcan.

El pedido de Jose (2026-08-01): "esas cifras no deben ir en todos los artes,
tenemos que ir variando" y "los colores del fondo no todos deben ser iguales".

La rotacion es **deterministica**, no al azar: se deriva del indice del arte. Dos
corridas del mismo arte dan el mismo resultado, que es la misma regla que ya sigue
el pipeline de video para las variantes de animacion. Si fuera aleatorio no se
podria reproducir un arte que gusto, ni saber cual toca despues.
"""
from __future__ import annotations

from dataclasses import dataclass

# Fondos. Se alternan frios, calidos y claros para que la grilla del perfil no
# quede toda del mismo color — que es como se ve hoy el feed.
ESCENAS_ROTACION = ["navy", "calida", "clara", "verde", "lila", "coral"]

# Palancas de confianza. NO van todas en todos los artes: se rota el par que
# entra. La barra completa en cada pieza satura y deja de leerse.
PALANCAS = [
    ["Nuevo y sellado", "Garantía 1 mes", "Envíos a todo el país"],
    ["Entrega inmediata", "Stock propio"],
    ["Nuevo y sellado", "Envíos a todo el país"],
    [],  # sin barra: el arte respira y el producto manda
    ["Garantía 1 mes", "Entrega inmediata"],
    [],
]

# Sellos. El vacio es a proposito y es mayoria: la prueba social pega cuando no
# esta siempre, y un sello en cada pieza lo convierte en decoracion.
SELLOS = [
    ("6", "AÑOS EN<br>BOLIVIA"),
    ("", ""),
    ("", ""),
    ("ENVÍO", "A TODA<br>BOLIVIA"),
    ("", ""),
    ("6", "AÑOS EN<br>BOLIVIA"),
]


@dataclass
class Variacion:
    escena: str
    sello_num: str
    sello_lab: str
    confianza: list[str]


def para(indice: int) -> Variacion:
    """Devuelve la variacion que le toca al arte numero `indice`."""
    s_num, s_lab = SELLOS[indice % len(SELLOS)]
    return Variacion(
        escena=ESCENAS_ROTACION[indice % len(ESCENAS_ROTACION)],
        sello_num=s_num,
        sello_lab=s_lab,
        confianza=PALANCAS[indice % len(PALANCAS)],
    )
