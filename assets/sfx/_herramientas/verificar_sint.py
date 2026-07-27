"""Comprueba de forma objetiva que cada sonido sintetizado hace lo que promete.

No puedo escucharlos, así que se mide lo que sí es medible: la trayectoria del
espectro. Un sub drop tiene que BAJAR de frecuencia, un riser tiene que SUBIR de
centroide y de energía, un blip tiene que tener su fundamental donde se pidió.
Si un archivo no cumple su propia descripción, el nombre miente y hay que
arreglarlo antes de meterlo al pack.
"""
import subprocess
import sys
from pathlib import Path

import numpy as np

FFMPEG = r"C:\Users\devic\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
SR = 48000

# archivo -> (qué debe pasar, comprobación)
ESPERADO = {
    "subdrop_1":        ("tono baja",     lambda r: r["f_fin"] < r["f_ini"] * 0.6 and r["f_fin"] < 70),
    "subdrop_2":        ("tono baja",     lambda r: r["f_fin"] < r["f_ini"] * 0.6 and r["f_fin"] < 70),
    "glitch_tape_stop": ("tono baja",     lambda r: r["f_fin"] < r["f_ini"] * 0.5),
    "ui_laser":         ("tono baja",     lambda r: r["f_fin"] < r["f_ini"] * 0.5),
    "riser_sweep_1":    ("brillo y energia suben", lambda r: r["c_fin"] > r["c_ini"] * 1.5 and r["e_fin"] > r["e_ini"] * 2),
    "riser_sweep_2":    ("brillo y energia suben", lambda r: r["c_fin"] > r["c_ini"] * 1.5 and r["e_fin"] > r["e_ini"] * 2),
    "riser_sweep_3":    ("brillo y energia suben", lambda r: r["c_fin"] > r["c_ini"] * 1.5 and r["e_fin"] > r["e_ini"] * 2),
    "moneda_1":         ("agudo y decae", lambda r: r["f_ini"] > 1200 and r["e_fin"] < r["e_ini"] * 0.3),
    "moneda_2":         ("agudo y decae", lambda r: r["f_ini"] > 1000 and r["e_fin"] < r["e_ini"] * 0.3),
    "caja_registradora": ("agudo y decae", lambda r: r["c_ini"] > 900 and r["e_fin"] < r["e_ini"] * 0.4),
    "ui_error":         ("grave",         lambda r: r["f_ini"] < 300),
    "impacto_latido":   ("muy grave",     lambda r: r["f_ini"] < 120),
    "ui_sparkle":       ("muy brillante", lambda r: r["c_ini"] > 1800),
    "ui_blip_1":        ("fundamental 880", lambda r: 800 < r["f_ini"] < 960),
    "ui_blip_2":        ("fundamental 1320", lambda r: 1200 < r["f_ini"] < 1440),
    "ui_blip_3":        ("fundamental 660", lambda r: 600 < r["f_ini"] < 720),
    "tada_cierre":      ("acorde y decae", lambda r: 400 < r["f_ini"] < 1200 and r["e_fin"] < r["e_ini"]),
    "glitch_digital":   ("tono baja",     lambda r: r["f_fin"] < r["f_ini"]),
    "glitch_stutter_1": ("ancho de banda", lambda r: r["c_ini"] > 700),
    "glitch_stutter_2": ("ancho de banda", lambda r: r["c_ini"] > 700),
}


def leer(p):
    r = subprocess.run([FFMPEG, "-v", "error", "-i", str(p), "-f", "f32le",
                        "-ac", "1", "-ar", str(SR), "-"],
                       capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)


def analizar(x):
    """Frecuencia dominante y centroide al principio y al final del sonido."""
    n = len(x)
    vent = min(int(SR * 0.12), n // 3)
    frec = np.fft.rfftfreq(vent, 1 / SR)

    def bloque(seg):
        if not len(seg) or np.abs(seg).max() < 1e-6:
            return 0.0, 0.0, 0.0
        esp = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        f_dom = frec[int(np.argmax(esp))]
        centro = float((frec * esp).sum() / max(esp.sum(), 1e-12))
        return f_dom, centro, float(np.sqrt((seg ** 2).mean()))

    # el arranque real, saltando el silencio de entrada
    audible = np.nonzero(np.abs(x) > np.abs(x).max() * 0.05)[0]
    a = audible[0] if len(audible) else 0
    b = audible[-1] if len(audible) else n - 1
    f_ini, c_ini, e_ini = bloque(x[a:a + vent])
    f_fin, c_fin, e_fin = bloque(x[max(a, b - vent):b])
    return {"f_ini": f_ini, "f_fin": f_fin, "c_ini": c_ini, "c_fin": c_fin,
            "e_ini": e_ini, "e_fin": e_fin}


def main():
    d = Path(sys.argv[1])
    fallos = 0
    print(f"{'archivo':<20} {'f_ini':>7} {'f_fin':>7} {'brillo_i':>9} {'brillo_f':>9} "
          f"{'rms_i':>6} {'rms_f':>6}  esperado")
    for p in sorted(d.glob("*.mp3")):
        x = leer(p)
        r = analizar(x)
        nombre = p.stem
        desc, prueba = ESPERADO.get(nombre, ("(sin comprobar)", lambda r: True))
        ok = prueba(r)
        if np.abs(x).max() < 0.2:
            ok, desc = False, desc + " [CASI MUDO]"
        if not ok:
            fallos += 1
        print(f"{nombre:<20} {r['f_ini']:7.0f} {r['f_fin']:7.0f} {r['c_ini']:9.0f} "
              f"{r['c_fin']:9.0f} {r['e_ini']:6.3f} {r['e_fin']:6.3f}  "
              f"{'OK ' if ok else 'MAL'} {desc}")
    print(f"\n{fallos} fallos")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
