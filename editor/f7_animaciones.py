"""
Fase 5b — Animaciones generadas por código.

Hay conceptos que ninguna foto del catálogo ilustra bien: una foto de cargador
no comunica "batería que dura semanas", y para "resistente al agua" no existe
una foto del Kindle sumergido. Estas animaciones se dibujan con PIL y se
codifican a ProRes 4444 (MOV), que es el formato con canal alfa que la sesión B
verificó píxel a píxel que sí conserva la transparencia con este ffmpeg
(el alfa de VP9/webm no sobrevivía).

Cada función devuelve la ruta del .mov listo para componer.

Uso:
    python f7_animaciones.py --demo   # genera las tres y las deja en salida/
"""
import argparse
import hashlib
import math
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

import config

NAVY = (10, 42, 62, 255)
CIAN = (79, 209, 217, 255)
BLANCO = (255, 255, 255, 255)
VERDE = (80, 220, 140, 255)


def _suave(t: float) -> float:
    """Curva de aceleración/desaceleración. Un movimiento lineal se ve robótico."""
    return t * t * (3 - 2 * t)


def _variacion(semilla, nombre: str, n: int) -> int:
    """Variante estable para esta animación en este video.

    Antes los parámetros eran fijos y el splash salía EXACTAMENTE igual en todos
    los videos. Ahora dependen de una semilla derivada del nombre del archivo,
    no de `random`: el plan exige render reproducible, así que el mismo video
    debe dar siempre el mismo resultado.
    """
    if semilla is None:
        return 0
    h = hashlib.sha1(f"{semilla}|{nombre}".encode("utf-8")).hexdigest()[:8]
    return int(h, 16) % n


def _codificar(dir_frames: Path, ruta_mov: Path, fps: int):
    """Frames PNG con alfa -> ProRes 4444 (conserva transparencia)."""
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-framerate", str(fps),
        "-i", str(dir_frames / "f_%04d.png"),
        "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
        str(ruta_mov),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    shutil.rmtree(dir_frames, ignore_errors=True)
    return ruta_mov


# ---------------------------------------------------------------------------
# Batería que se carga
# ---------------------------------------------------------------------------
def animar_bateria(dir_tmp: Path, duracion: float = 2.5, w: int = 380, h: int = 200,
                   semilla=None) -> Path:
    """Batería que se llena de vacía a completa, con un rayo al terminar.

    Comunica "dura semanas" mucho mejor que la foto de un cargador, que era lo
    que traía el catálogo para la palabra "batería".
    """
    fps = config.ANIMACION_FPS
    n = max(2, int(duracion * fps))
    frames = dir_tmp / "_f_bateria"
    frames.mkdir(parents=True, exist_ok=True)

    # variación determinista por video: color de llegada y cuándo se completa
    var = _variacion(semilla, "bateria", 3)
    color_lleno = [VERDE, CIAN, (126, 240, 212, 255)][var]
    punto_lleno = [0.75, 0.68, 0.82][var]

    cuerpo = (20, 30, w - 60, h - 30)
    borde = 8
    radio = 22

    for i in range(n):
        p = i / (n - 1)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # carcasa
        d.rounded_rectangle(cuerpo, radius=radio, fill=(10, 42, 62, 210), outline=BLANCO, width=borde)
        # borne
        bx = cuerpo[2] + 6
        d.rounded_rectangle((bx, h // 2 - 26, bx + 26, h // 2 + 26), radius=8, fill=BLANCO)

        # relleno: sube durante el primer 75% y se queda lleno
        nivel = _suave(min(1.0, p / punto_lleno))
        x0 = cuerpo[0] + borde + 6
        x1 = cuerpo[2] - borde - 6
        y0 = cuerpo[1] + borde + 6
        y1 = cuerpo[3] - borde - 6
        ancho_util = (x1 - x0) * nivel
        if ancho_util > 4:
            color = CIAN if nivel < 0.95 else color_lleno
            d.rounded_rectangle((x0, y0, x0 + ancho_util, y1), radius=12, fill=color)

        # rayo al completarse
        if p > punto_lleno:
            alfa = int(255 * _suave(min(1.0, (p - punto_lleno) / (1 - punto_lleno))))
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            rayo = [(cx + 14, cy - 44), (cx - 18, cy + 6), (cx + 2, cy + 6),
                    (cx - 14, cy + 46), (cx + 20, cy - 6), (cx, cy - 6)]
            d.polygon(rayo, fill=(255, 255, 255, alfa))

        img.save(frames / f"f_{i:04d}.png")

    return _codificar(frames, dir_tmp / "anim_bateria.mov", fps)


# ---------------------------------------------------------------------------
# Splash de agua
# ---------------------------------------------------------------------------
def animar_splash(dir_tmp: Path, duracion: float = 2.0, w: int = 420, h: int = 420,
                  semilla=None) -> Path:
    """Ondas concéntricas + gotas saliendo. Para "resistente al agua"."""
    fps = config.ANIMACION_FPS
    n = max(2, int(duracion * fps))
    frames = dir_tmp / "_f_splash"
    frames.mkdir(parents=True, exist_ok=True)

    var = _variacion(semilla, "splash", 3)
    cx, cy = w / 2, h / 2 + 20
    n_gotas = [9, 7, 11][var]
    radio_max = [0.46, 0.52, 0.42][var]

    for i in range(n):
        p = i / (n - 1)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # tres ondas desfasadas, cada una crece y se desvanece.
        # Primera versión: se veían como un hilo tenue. Ondas más gruesas y
        # opacas, y desvanecido más lento, para que el gesto se lea a tamaño
        # de celular.
        for k in range(3):
            fase = p - k * 0.16
            if fase <= 0:
                continue
            fase = min(1.0, fase / 0.84)
            r = 34 + _suave(fase) * (w * radio_max - 34)
            alfa = int(255 * (1 - fase) ** 0.85)
            if alfa > 4:
                grosor = max(5, int(18 * (1 - fase) + 5))
                d.ellipse((cx - r, cy - r * 0.55, cx + r, cy + r * 0.55),
                          outline=(79, 209, 217, alfa), width=grosor)

        # gotas que salen en abanico y caen
        for g in range(n_gotas):
            ang = math.pi * (0.10 + 0.80 * g / (n_gotas - 1))
            vel = 0.85 + 0.40 * ((g * 37) % 10) / 10
            t = min(1.0, p / 0.88)
            dist = _suave(t) * w * 0.50 * vel
            gx = cx + math.cos(ang) * dist * -1
            gy = cy - math.sin(ang) * dist + (t ** 2) * 150   # gravedad
            rr = max(4.0, 26 * (1 - t * 0.75))
            alfa = int(255 * (1 - t) ** 0.55)
            if alfa > 6:
                d.ellipse((gx - rr, gy - rr * 1.3, gx + rr, gy + rr * 1.3),
                          fill=(79, 209, 217, alfa))
                # brillo interior, para que la gota tenga volumen
                d.ellipse((gx - rr * 0.35, gy - rr * 0.75, gx + rr * 0.1, gy - rr * 0.15),
                          fill=(255, 255, 255, int(alfa * 0.55)))

        img.save(frames / f"f_{i:04d}.png")

    return _codificar(frames, dir_tmp / "anim_splash.mov", fps)


# ---------------------------------------------------------------------------
# Moto de reparto cruzando la pantalla
# ---------------------------------------------------------------------------
def animar_moto(dir_tmp: Path, duracion: float = 2.6, w: int = None, h: int = 260,
                semilla=None) -> Path:
    """Moto de delivery cruzando de izquierda a derecha, para "hacemos envíos".

    Silueta plana y simple: a este tamaño y a esta velocidad se lee como moto
    sin necesitar detalle, y encaja con el estilo limpio de la marca.
    """
    w = w or config.ANCHO
    fps = config.ANIMACION_FPS
    n = max(2, int(duracion * fps))
    frames = dir_tmp / "_f_moto"
    frames.mkdir(parents=True, exist_ok=True)

    var = _variacion(semilla, "moto", 3)
    vibracion = [9, 6, 12][var]      # frecuencia del rebote del motor
    largo = 300           # largo de la moto
    for i in range(n):
        p = i / (n - 1)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        x = -largo + _suave(p) * (w + largo * 2)
        bote = math.sin(p * math.pi * vibracion) * 4   # vibración del motor
        base = h - 62 + bote

        # estela de velocidad
        for k in range(4):
            lx = x - 30 - k * 46
            alfa = int(120 - k * 26)
            if alfa > 0 and lx > -60:
                d.rounded_rectangle((lx - 40, base - 62 - k * 13, lx, base - 56 - k * 13),
                                    radius=3, fill=(79, 209, 217, alfa))

        r = 34                                       # ruedas
        for wx in (x + 52, x + largo - 52):
            d.ellipse((wx - r, base - r, wx + r, base + r), fill=NAVY)
            # llanta clara opaca: con relleno semitransparente se veía el fondo
            # a través de la rueda y parecía un agujero
            d.ellipse((wx - r + 10, base - r + 10, wx + r - 10, base + r - 10), fill=BLANCO)
            d.ellipse((wx - 7, base - 7, wx + 7, base + 7), fill=NAVY)

        # cuerpo
        d.polygon([(x + 52, base - 26), (x + 118, base - 74), (x + 214, base - 74),
                   (x + largo - 52, base - 26)], fill=CIAN)
        # caja de reparto
        d.rounded_rectangle((x + 168, base - 138, x + 252, base - 72), radius=10, fill=NAVY)
        d.rounded_rectangle((x + 180, base - 126, x + 240, base - 86), radius=6, fill=CIAN)
        # manubrio y conductor simplificado
        d.line([(x + 214, base - 74), (x + 258, base - 118)], fill=NAVY, width=11)
        d.ellipse((x + 136, base - 168, x + 190, base - 114), fill=NAVY)

        img.save(frames / f"f_{i:04d}.png")

    return _codificar(frames, dir_tmp / "anim_moto.mov", fps)


def animar_sol(dir_tmp: Path, duracion: float = 2.4, w: int = 420, h: int = 420,
               semilla=None) -> Path:
    fps = config.ANIMACION_FPS
    n = max(2, int(duracion * fps))
    frames = dir_tmp / "_f_sol"
    frames.mkdir(parents=True, exist_ok=True)

    for i in range(n):
        p = i / (n - 1)
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)

        # Kindle silueta
        kx0, ky0, kx1, ky1 = 110, 140, 310, 380
        d.rounded_rectangle((kx0, ky0, kx1, ky1), radius=16, fill=(17, 26, 36, 240), outline=BLANCO, width=6)
        d.rounded_rectangle((kx0 + 16, ky0 + 16, kx1 - 16, ky1 - 16), radius=6, fill=(232, 230, 223, 255))

        # Sol radiante
        sx, sy = 330, 110
        sr = int(35 + math.sin(p * math.pi * 4) * 5)
        d.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=(255, 208, 52, 255))

        img.save(frames / f"f_{i:04d}.png")

    return _codificar(frames, dir_tmp / "anim_sol.mov", fps)


GENERADORES = {
    "bateria": animar_bateria,
    "splash": animar_splash,
    "moto": animar_moto,
    "sol": animar_sol,
}


def generar(nombre: str, dir_tmp: Path, duracion: float = None,
            semilla=None) -> Path | None:
    fn = GENERADORES.get(nombre)
    if fn is None:
        return None
    kwargs = {"duracion": duracion} if duracion else {}
    kwargs["semilla"] = semilla
    try:
        return fn(dir_tmp, **kwargs)
    except Exception as e:
        print(f"AVISO: no se pudo generar la animación '{nombre}': {e}", file=sys.stderr)
        return None


def main():
    ap = argparse.ArgumentParser(description="Genera las animaciones del editor")
    ap.add_argument("--demo", action="store_true", help="Genera las tres en salida/animaciones/")
    ap.add_argument("--nombre", type=str, default=None, choices=list(GENERADORES))
    args = ap.parse_args()

    destino = config.RAIZ_PROYECTO / "salida" / "animaciones"
    destino.mkdir(parents=True, exist_ok=True)

    nombres = [args.nombre] if args.nombre else list(GENERADORES)
    for n in nombres:
        ruta = generar(n, destino)
        if ruta:
            print(f"  {n:<10} -> {ruta}")


if __name__ == "__main__":
    main()
