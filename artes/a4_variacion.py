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
#
# Corregido el 2026-08-10: eran pares ("6", "AÑOS EN<br>BOLIVIA") de cuando el
# sello se dibujaba como numero + etiqueta. Desde que `a5_sellos` los hace con
# icono SVG, `Arte` recibe UNA clave ("anios" | "moto" | "qr" | ""), y estos
# pares reventaban el render con TypeError. Son las claves de a5_sellos.
SELLOS = ["anios", "", "", "moto", "", "qr"]

# Moldes. Andromeda fusiona en una sola entidad los anuncios que se parecen mas
# del 60% y los hace competir entre ellos en vez de ampliar alcance: seis veces
# el mismo molde con otro titular NO cuenta como seis creatividades. Por eso la
# tanda rota tambien el molde, no solo el fondo.
MOLDES = ["limpio", "chat", "limpio", "comparativa", "fichas", "limpio"]


@dataclass
class Variacion:
    escena: str
    sello: str
    modo: str
    confianza: list[str]


def para(indice: int) -> Variacion:
    """Devuelve la variacion que le toca al arte numero `indice`."""
    return Variacion(
        escena=ESCENAS_ROTACION[indice % len(ESCENAS_ROTACION)],
        sello=SELLOS[indice % len(SELLOS)],
        modo=MOLDES[indice % len(MOLDES)],
        confianza=PALANCAS[indice % len(PALANCAS)],
    )
