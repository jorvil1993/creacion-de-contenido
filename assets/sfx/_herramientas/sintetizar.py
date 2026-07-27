"""Sintetiza los efectos que la librería CC0 no trae y que sí hacen falta.

La descarga de videoeditingsfx.com cubre muy bien whoosh / impacto / riser /
reverse / cámara / UI, que es la paleta que la investigación marca como la más
usada en corto. Lo que NO trae, y aquí se fabrica:

- caja registradora y monedas: el remate natural del reveal de precio en una
  tienda; sin esto no hay nada para el momento "cuesta X".
- glitch / stutter digital: transición corta de estética tecnológica.
- sub drop: la caída grave que sostiene un reveal de producto.
- sparkle, blips 8-bit, láser, tada: acentos de texto y remates.

Todo es síntesis propia, así que no hay licencia que respetar ni Content ID
posible. Se generan con semilla fija para que el pack sea reproducible.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy import signal

FFMPEG = r"C:\Users\devic\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
SR = 48000
PICO_OBJETIVO = 10 ** (-1.0 / 20)
RNG = np.random.default_rng(20260727)


def t(dur):
    return np.arange(int(SR * dur)) / SR


def adsr(n, ataque=0.005, decaimiento=0.25, forma=2.5):
    """Envolvente percusiva: ataque muy corto y caída exponencial."""
    e = np.ones(n)
    na = max(1, int(SR * ataque))
    e[:na] = np.linspace(0, 1, na)
    caida = np.exp(-np.arange(n - na) / (SR * decaimiento)) ** (forma / 2.5)
    e[na:] = caida
    return e


def ruido(n):
    return RNG.uniform(-1, 1, n)


def pasabajos(x, fc, orden=4):
    sos = signal.butter(orden, min(fc / (SR / 2), 0.99), btype="low", output="sos")
    return signal.sosfilt(sos, x)


def pasaaltos(x, fc, orden=4):
    sos = signal.butter(orden, min(fc / (SR / 2), 0.99), btype="high", output="sos")
    return signal.sosfilt(sos, x)


def pasabanda(x, f1, f2, orden=4):
    sos = signal.butter(orden, [max(f1, 20) / (SR / 2), min(f2, SR / 2 - 100) / (SR / 2)],
                        btype="band", output="sos")
    return signal.sosfilt(sos, x)


def barrido_filtro(x, f_ini, f_fin, bloques=160):
    """Filtro que se mueve a lo largo del sonido (lo que hace 'subir' un riser)."""
    n = len(x)
    salida = np.zeros(n)
    bordes = np.linspace(0, n, bloques + 1).astype(int)
    for i in range(bloques):
        a, b = bordes[i], bordes[i + 1]
        if b <= a:
            continue
        f = f_ini * (f_fin / f_ini) ** (i / max(1, bloques - 1))
        # se filtra un poco de contexto para que no se oiga el salto entre bloques
        ctx = max(0, a - 600)
        trozo = pasabanda(x[ctx:b], f * 0.6, f * 1.7)
        salida[a:b] = trozo[a - ctx:]
    return salida


def campana(frec, dur, decaimiento, parciales=(1.0, 2.76, 5.4, 8.93), pesos=None):
    """Suma de parciales inarmónicos: el timbre metálico de campana o moneda."""
    n = int(SR * dur)
    tt = t(dur)
    pesos = pesos or [1.0 / (i + 1) ** 1.2 for i in range(len(parciales))]
    x = np.zeros(n)
    for p, w in zip(parciales, pesos):
        x += w * np.sin(2 * np.pi * frec * p * tt) * np.exp(-tt / (decaimiento / (p ** 0.5)))
    return x


def cola_reverb(x, dur=0.35, mezcla=0.25):
    """Reverb barata por convolución con ruido que decae. Da cuerpo sin sonar a lata."""
    n = int(SR * dur)
    ir = ruido(n) * np.exp(-np.arange(n) / (SR * dur / 4))
    ir = pasabajos(ir, 6000)
    ir[0] = 1.0
    húmedo = signal.fftconvolve(x, ir)[:len(x) + n // 2]
    seco = np.pad(x, (0, len(húmedo) - len(x)))
    return seco * (1 - mezcla) + húmedo / (np.abs(húmedo).max() + 1e-9) * mezcla


def estereo(x, ancho=0.15):
    """Ensancha con un retardo mínimo entre canales (efecto Haas)."""
    d = int(SR * 0.008 * ancho / 0.15)
    izq = x
    der = np.concatenate([np.zeros(d), x[:-d]]) if d else x.copy()
    return np.stack([izq, der], axis=1)


# --------------------------------------------------------------------------
# Los efectos
# --------------------------------------------------------------------------

def caja_registradora():
    """Ka-ching: el 'ting' de la campana y el golpe del cajón al abrirse."""
    ting = campana(1180, 1.1, 0.55, parciales=(1.0, 2.1, 3.05, 4.7))
    ting += campana(1760, 1.1, 0.40, parciales=(1.0, 2.4, 3.9)) * 0.6
    ting *= adsr(len(ting), 0.001, 0.30, 2.0)

    cajon = pasabanda(ruido(int(SR * 0.35)), 200, 2600) * adsr(int(SR * 0.35), 0.002, 0.06, 3.0)
    golpe = np.sin(2 * np.pi * 90 * t(0.25)) * adsr(int(SR * 0.25), 0.001, 0.05, 3.0)

    x = np.zeros(int(SR * 1.3))
    x[:len(ting)] += ting
    d = int(SR * 0.09)
    x[d:d + len(cajon)] += cajon * 0.55
    x[d:d + len(golpe)] += golpe * 0.7
    return cola_reverb(x, 0.30, 0.18)


def moneda(frec, dur=0.9):
    """Ding metálico corto, para el momento del precio."""
    x = campana(frec, dur, 0.42, parciales=(1.0, 2.05, 3.4, 5.1))
    x *= adsr(len(x), 0.001, 0.28, 2.2)
    chispa = pasaaltos(ruido(int(SR * 0.03)), 6000) * adsr(int(SR * 0.03), 0.0005, 0.008, 3.0)
    x[:len(chispa)] += chispa * 0.35
    return cola_reverb(x, 0.25, 0.15)


def glitch_stutter(semillas=7, dur=0.55):
    """Trozos de ruido cortados a tijera: la transición 'digital' corta."""
    n = int(SR * dur)
    base = pasabanda(ruido(n), 300, 9000)
    tono = signal.square(2 * np.pi * 220 * t(dur)) * 0.35
    x = base * 0.7 + tono
    # puerta rítmica irregular
    puerta = np.zeros(n)
    pos = 0
    for i in range(semillas):
        largo = int(SR * RNG.uniform(0.012, 0.05))
        if pos + largo >= n:
            break
        puerta[pos:pos + largo] = RNG.uniform(0.45, 1.0)
        pos += largo + int(SR * RNG.uniform(0.008, 0.035))
    puerta = pasabajos(puerta, 900)
    return x * puerta * adsr(n, 0.001, 0.5, 1.2)


def glitch_bitcrush(dur=0.4):
    """Barrido cuantizado a pocos bits: error digital, para cortes secos."""
    n = int(SR * dur)
    f = np.linspace(1400, 260, n)
    fase = np.cumsum(2 * np.pi * f / SR)
    x = signal.sawtooth(fase)
    niveles = 6
    x = np.round(x * niveles) / niveles                     # cuantización dura
    diezmado = 90                                            # baja la tasa a mano
    x = np.repeat(x[::diezmado], diezmado)[:n]
    return x * adsr(n, 0.001, 0.12, 2.0)


def sub_drop(f_ini=140, f_fin=50, dur=1.6):
    """Caída de sub-graves: sostiene el reveal de producto sin tapar la voz.

    No baja de ~45 Hz a propósito. El video se ve casi siempre en el parlante de
    un celular, que no reproduce nada por debajo de eso: un drop a 30 Hz se ve
    precioso en el medidor y en el teléfono es silencio.
    """
    n = int(SR * dur)
    f = f_ini * (f_fin / f_ini) ** (np.arange(n) / n)
    x = np.sin(np.cumsum(2 * np.pi * f / SR))
    x = np.tanh(x * 1.8) / np.tanh(1.8)                      # saturación suave
    click = pasabanda(ruido(int(SR * 0.02)), 800, 7000) * adsr(int(SR * 0.02), 0.0005, 0.006, 3.0)
    x[:len(click)] += click * 0.4
    return x * adsr(n, 0.002, dur / 2.2, 1.4)


def riser_sweep(dur=2.2, f_ini=200, f_fin=9000, con_tono=True):
    """Riser de ruido con filtro que sube: el pico cae en el último frame."""
    n = int(SR * dur)
    x = barrido_filtro(ruido(n), f_ini, f_fin)
    if con_tono:
        f = 180 * (6.0 ** (np.arange(n) / n))
        x = x * 0.75 + np.sin(np.cumsum(2 * np.pi * f / SR)) * 0.25
    subida = (np.arange(n) / n) ** 2.0                       # crece hacia el final
    x *= subida
    x[-int(SR * 0.02):] *= np.linspace(1, 0, int(SR * 0.02))
    return x


def tape_stop(dur=0.9):
    """Frenada de cinta: el tono cae de golpe. Remate de corte."""
    n = int(SR * dur)
    caida = np.linspace(1.0, 0.04, n) ** 1.8
    f = 330 * caida
    x = signal.sawtooth(np.cumsum(2 * np.pi * f / SR), 0.4)
    x = pasabajos(x, 5200)
    hiss = pasabanda(ruido(n), 1500, 8000) * 0.12 * caida
    return (x * 0.8 + hiss) * adsr(n, 0.004, dur / 2.0, 1.3)


def blip(frec, dur=0.13, tipo="cuadrada"):
    """Blip de consola: aparición de texto o palabra de subtítulo."""
    n = int(SR * dur)
    tt = t(dur)
    onda = signal.square(2 * np.pi * frec * tt) if tipo == "cuadrada" \
        else signal.sawtooth(2 * np.pi * frec * tt)
    x = pasabajos(onda, frec * 6) * adsr(n, 0.002, 0.045, 2.0)
    return x


def laser_zap(dur=0.45):
    """Barrido descendente rápido: acento juguetón, muy de corto."""
    n = int(SR * dur)
    f = 2600 * (0.06 ** (np.arange(n) / n))
    # ciclo de trabajo 0.5: con 0.35 la onda tiene media distinta de cero y el
    # archivo sale con offset de continua, que se come headroom y no se oye
    x = signal.square(np.cumsum(2 * np.pi * f / SR), 0.5)
    x = pasabajos(x, 7000)
    return cola_reverb(x * adsr(n, 0.001, 0.10, 2.2), 0.20, 0.20)


def error_buzz(dur=0.5):
    """Zumbido disonante: el 'no' del formato lista o del antes/después."""
    n = int(SR * dur)
    x = (signal.square(2 * np.pi * 116 * t(dur), 0.5)
         + signal.square(2 * np.pi * 123 * t(dur), 0.5)) * 0.5
    x = pasabajos(x, 2400)
    puerta = (np.sin(2 * np.pi * 11 * t(dur)) > -0.3).astype(float)
    return x * puerta * adsr(n, 0.004, 0.35, 1.5)


def sparkle(dur=1.4, n_notas=13):
    """Cascada de campanitas agudas: brillo sobre un sticker o un logro."""
    n = int(SR * dur)
    x = np.zeros(n)
    escala = [1568, 1760, 2093, 2349, 2637, 3136, 3520, 4186]
    for i in range(n_notas):
        f = escala[RNG.integers(0, len(escala))] * RNG.choice([1.0, 1.0, 2.0])
        d = int(SR * RNG.uniform(0.0, dur * 0.45))
        nota = campana(f, min(0.7, (n - d) / SR), 0.30, parciales=(1.0, 2.7, 5.2))
        nota *= adsr(len(nota), 0.001, 0.16, 2.5) * RNG.uniform(0.35, 1.0)
        x[d:d + len(nota)] += nota
    return cola_reverb(x, 0.45, 0.30)


def tada(dur=1.3):
    """Arpegio mayor ascendente: cierre positivo, CTA."""
    n = int(SR * dur)
    x = np.zeros(n)
    for i, f in enumerate([523.25, 659.25, 783.99, 1046.50]):
        d = int(SR * 0.075 * i)
        largo = n - d
        tt = np.arange(largo) / SR
        nota = (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * f * 2 * tt)
                + 0.18 * np.sin(2 * np.pi * f * 3 * tt))
        nota *= adsr(largo, 0.006, 0.42, 2.0)
        x[d:] += nota * (0.9 - 0.1 * i)
    return cola_reverb(x, 0.40, 0.22)


def latido(dur=1.5):
    """Dos golpes de corazón: tensión antes de un dato o un precio."""
    n = int(SR * dur)
    x = np.zeros(n)
    for d, amp in ((0.0, 1.0), (0.34, 0.72)):
        i = int(SR * d)
        largo = int(SR * 0.45)
        tt = np.arange(largo) / SR
        f = 62 * np.exp(-tt * 7) + 38
        golpe = np.sin(np.cumsum(2 * np.pi * f / SR)) * adsr(largo, 0.004, 0.10, 2.0)
        x[i:i + largo] += golpe * amp
    return x


CATALOGO = [
    ("caja_registradora",   "venta",   lambda: caja_registradora()),
    ("moneda_1",            "venta",   lambda: moneda(2093)),
    ("moneda_2",            "venta",   lambda: moneda(1568)),
    ("tada_cierre",         "venta",   lambda: tada()),
    ("glitch_stutter_1",    "glitch",  lambda: glitch_stutter(7)),
    ("glitch_stutter_2",    "glitch",  lambda: glitch_stutter(11, 0.7)),
    ("glitch_digital",      "glitch",  lambda: glitch_bitcrush()),
    ("glitch_tape_stop",    "glitch",  lambda: tape_stop()),
    ("subdrop_1",           "impacto", lambda: sub_drop(140, 50, 1.6)),
    ("subdrop_2",           "impacto", lambda: sub_drop(190, 45, 2.2)),
    ("impacto_latido",      "impacto", lambda: latido()),
    ("riser_sweep_1",       "riser",   lambda: riser_sweep(2.2)),
    ("riser_sweep_2",       "riser",   lambda: riser_sweep(1.4, 300, 11000)),
    ("riser_sweep_3",       "riser",   lambda: riser_sweep(3.0, 140, 7000, con_tono=False)),
    ("ui_blip_1",           "ui",      lambda: blip(880)),
    ("ui_blip_2",           "ui",      lambda: blip(1320)),
    ("ui_blip_3",           "ui",      lambda: blip(660, 0.10, "sierra")),
    ("ui_laser",            "ui",      lambda: laser_zap()),
    ("ui_error",            "ui",      lambda: error_buzz()),
    ("ui_sparkle",          "ui",      lambda: sparkle()),
]

# Igual que en el pack descargado: dónde cae el clímax dentro del archivo.
CATEGORIAS_BUILD = {"riser"}


def envolvente(x, ventana_ms=20.0):
    mono = x.mean(axis=1) if x.ndim == 2 else x
    n = max(1, int(SR * ventana_ms / 1000))
    return np.sqrt(np.convolve(mono ** 2, np.ones(n) / n, mode="same"))


def punto_impacto(x, categoria):
    env = envolvente(x)
    if env.max() <= 0:
        return 0
    altos = np.nonzero(env >= env.max() * 0.85)[0]
    return int(altos[-1] if categoria in CATEGORIAS_BUILD else altos[0])


def familia(punto_s):
    if punto_s <= 0.12:
        return "golpe"
    return "swell" if punto_s <= 1.0 else "build"


def escribir(x, destino):
    if x.ndim == 1:
        x = estereo(x)
    # Bloqueo de continua antes de normalizar: un offset de DC no se oye pero
    # desplaza la forma de onda y roba margen de pico al sonido de verdad.
    x = pasaaltos(x, 18, orden=2)
    pico = np.abs(x).max()
    if pico > 0:
        x = x * (PICO_OBJETIVO / pico)
    n_in, n_out = int(SR * 0.003), int(SR * 0.020)
    if len(x) > n_in + n_out:
        x[:n_in] *= np.linspace(0, 1, n_in)[:, None]
        x[-n_out:] *= np.linspace(1, 0, n_out)[:, None]
    datos = np.clip(x, -1, 1).astype(np.float32).tobytes()
    subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "f32le", "-ar", str(SR),
                    "-ac", "2", "-i", "-", "-c:a", "libmp3lame", "-b:a", "192k",
                    "-ar", str(SR), str(destino)], input=datos, check=True)
    return x


def main():
    destino = Path(sys.argv[1])
    destino.mkdir(parents=True, exist_ok=True)
    catalogo = []
    for nombre, cat, hacer in CATALOGO:
        x = escribir(hacer(), destino / f"{nombre}.mp3")
        punto_s = round(punto_impacto(x, cat) / SR, 3)
        catalogo.append({
            "archivo": f"{nombre}.mp3", "categoria": cat, "familia": familia(punto_s),
            "punto": punto_s, "duracion": round(len(x) / SR, 3), "origen": "sintetizado",
        })
        print(f"{nombre:<22} {cat:<8} {len(x)/SR:5.2f}s  impacto@{punto_s:.2f}s "
              f"({catalogo[-1]['familia']})")
    (destino / "_catalogo_sintetizado.json").write_text(
        json.dumps(catalogo, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n{len(catalogo)} efectos sintetizados")


if __name__ == "__main__":
    main()
