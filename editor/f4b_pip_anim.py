"""
Fase 4b — Animaciones de entrada y salida de los PiP.

Hasta ahora un PiP (la tarjeta de producto de la esquina, las animaciones, el
hook, el CTA) entraba y salía con un simple fundido de alfa de 0.15s. Esto le
da diez formas de entrar y otras diez de salir — deslizar, caer con rebote,
latigazo — que son las que se ven en los cortes de TikTok/Reels.

Cómo funciona, y por qué es seguro: NO se toca la duración ni el momento del
PiP. Solo se cambia la POSICIÓN (`x`, `y`) del overlay como función del tiempo
durante las ventanas de entrada y de salida; en el medio la tarjeta está quieta
en su sitio de siempre. Fuera de esas ventanas la expresión vale exactamente la
posición base, así que un PiP con animación "fundido" (la de por defecto) sale
idéntico a como salía antes.

La entrada y la salida se eligen por separado: se puede entrar deslizando desde
la izquierda y salir cayendo hacia abajo. La `intensidad` (0.5…1.5) escala la
distancia del desplazamiento y el rebote.

Las expresiones usan las variables que `overlay` de ffmpeg expone: `t` (tiempo),
`w`/`h` (ancho/alto de la tarjeta). Por eso "fuera de pantalla por la izquierda"
se escribe `-(w+40)`: no hace falta saber el tamaño de la tarjeta en píxeles.

Este módulo no llama a ffmpeg: solo construye texto de expresiones que
f4_retencion mete en el filter_complex. Es 100% testeable sin render.
"""

# Catálogo público: clave -> etiqueta legible (para el editor y el panel).
# El mismo catálogo vale para entrada y para salida.
ANIMACIONES = {
    "fundido":          "Fundido (solo opacidad)",
    "desliza-izquierda": "Desliza desde la izquierda",
    "desliza-derecha":  "Desliza desde la derecha",
    "desliza-arriba":   "Desliza desde arriba",
    "desliza-abajo":    "Desliza desde abajo",
    "diagonal":         "Diagonal (esquina inferior)",
    "resorte-arriba":   "Cae desde arriba con rebote",
    "resorte-lateral":  "Entra de lado con rebote",
    "latigazo":         "Latigazo rápido",
    "subir-fundido":    "Sube y aparece",
}

# Duración por defecto de la ventana de entrada/salida (segundos) a intensidad 1.
DUR_ANIM_S = 0.28


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


# Desplazamiento inicial (entrada) o final (salida) de cada preset, como texto de
# expresión ffmpeg. `k` = intensidad. `overshoot` marca si el easing rebota.
#   dx, dy: cuánto está DESPLAZADA la tarjeta respecto a su sitio al principio de
#           la entrada (o al final de la salida). "0" = no se mueve en ese eje.
def _desplazamiento(preset, k):
    m = 40 * k          # margen extra para que salga bien de cuadro
    if preset in (None, "", "fundido"):
        return "0", "0", False
    if preset == "desliza-izquierda":
        return f"-(w+{m:.0f})", "0", False
    if preset == "desliza-derecha":
        return f"(w+{m:.0f})", "0", False
    if preset == "desliza-arriba":
        return "0", f"-(h+{m:.0f})", False
    if preset == "desliza-abajo":
        return "0", f"(h+{m:.0f})", False
    if preset == "diagonal":
        return f"-(w+{m:.0f})", f"(h+{m:.0f})", False
    if preset == "resorte-arriba":
        return "0", f"-(h+{60 * k:.0f})", True
    if preset == "resorte-lateral":
        return f"(w+{60 * k:.0f})", "0", True
    if preset == "latigazo":
        return f"-(w+{90 * k:.0f})", "0", True
    if preset == "subir-fundido":
        return "0", f"({70 * k:.0f})", False
    raise ValueError(f"Animación de PiP desconocida: {preset!r}")


def _es_fundido(preset):
    return preset in (None, "", "fundido")


def _fundido_puro(preset_in, preset_out):
    """¿Ambas fases son fundido? Entonces no hay movimiento y el llamador puede
    dejar el overlay estático como siempre (camino de regresión)."""
    return _es_fundido(preset_in) and _es_fundido(preset_out)


def _pin(ini, dur):
    # progreso de la entrada, 0..1. Comas SIN escapar: va dentro de comillas
    # simples en el overlay (mismo patrón que enable='between(t,...)').
    return f"clip((t-{ini:.3f})/{dur:.3f},0,1)"


def _pout(fin, dur):
    # progreso de la salida, 0..1
    return f"clip((t-{fin - dur:.3f})/{dur:.3f},0,1)"


def _ease_out(p):
    # aceleración que frena al llegar (sin rebote): 1-(1-p)^3
    return f"(1-pow(1-{p},3))"


def _back_out(p):
    # rebote al aterrizar (back.out, s=1.70158): sobrepasa y vuelve
    return f"(1+2.70158*pow({p}-1,3)+1.70158*pow({p}-1,2))"


def _ease_in(p):
    # arranque suave para la salida: p^3
    return f"(pow({p},3))"


def _factor_entrada(preset, ini, dur):
    """1 = totalmente desplazada (inicio) -> 0 = en su sitio. Con rebote si toca."""
    _, _, overshoot = _desplazamiento(preset, 1.0)
    p = _pin(ini, dur)
    ease = _back_out(p) if overshoot else _ease_out(p)
    return f"(1-{ease})"


def _factor_salida(preset, fin, dur):
    """0 = en su sitio -> 1 = totalmente desplazada (fin)."""
    p = _pout(fin, dur)
    return _ease_in(p)


def expr_posicion(x_base, y_base, ini, fin,
                  anim_entrada="fundido", anim_salida="fundido",
                  intensidad=1.0, dur=None):
    """Devuelve (x_expr, y_expr) para el `overlay`, o (None, None) si ambas fases
    son fundido (el llamador deja la posición estática de siempre).

    `x_base`, `y_base` son la posición fija en píxeles (ya escalada). La ventana
    de animación se recorta a la mitad de la vida del PiP para que en insertos
    muy cortos la entrada y la salida no se pisen.
    """
    if _fundido_puro(anim_entrada, anim_salida):
        return None, None
    k = _clamp(float(intensidad), 0.3, 2.0)
    dur = dur or DUR_ANIM_S
    dur = min(dur, max(0.05, (fin - ini) / 2))

    dxe, dye, _ = _desplazamiento(anim_entrada, k)
    dxs, dys, _ = _desplazamiento(anim_salida, k)
    fe = _factor_entrada(anim_entrada, ini, dur)
    fs = _factor_salida(anim_salida, fin, dur)

    # posición = base + desplazamiento_entrada*factor_entrada
    #                 + desplazamiento_salida*factor_salida
    x = f"{x_base}+({dxe})*{fe}+({dxs})*{fs}"
    y = f"{y_base}+({dye})*{fe}+({dys})*{fs}"
    return x, y


def resumen():
    """Para la CLI/depuración: enseña las 10 opciones."""
    return "\n".join(f"  {k:18s} {v}" for k, v in ANIMACIONES.items())


if __name__ == "__main__":
    print("Animaciones de PiP disponibles (entrada y salida):\n")
    print(resumen())
    print("\nEjemplo de expresión (entra deslizando izq, sale cayendo abajo):")
    x, y = expr_posicion(820, 1180, 5.0, 9.0, "desliza-izquierda", "desliza-abajo", 1.0)
    print("  x =", x)
    print("  y =", y)
