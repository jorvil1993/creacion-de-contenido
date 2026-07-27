"""Convierte la descarga cruda CC0 en un pack usable por el pipeline.

Lo medido sobre la descarga real, que obliga a procesar y no solo copiar:

1. Silencio inicial de hasta 2s. El pipeline coloca cada SFX con `adelay` al
   milisegundo del evento visual; con silencio delante el golpe suena tarde.

2. Hay archivos que son PACKS: `analog-shutter` dura 9s porque trae 7 tomas
   separadas por silencio, y `hover` dura 14s con 0.18s de sonido y el resto
   vacío.

3. **Punto de impacto.** Es el concepto que ordena todo lo demás. No todos los
   efectos golpean al principio:
     - golpe   (impacto, click, cámara):    el pico está en los primeros ms
     - swell   (whoosh, swish):             el pico está en el MEDIO
     - build   (riser, buildup, reverse):   el pico está al FINAL
   Alinear los tres por el inicio del archivo es lo que hace que un riser "no se
   note": su pico cae 2s después del reveal en vez de encima. Por eso cada
   archivo se guarda con su `punto` medido, y el pipeline lo coloca en
   `t - punto` para que el pico caiga sobre el evento visual.

   El punto se busca dentro de la zona que supera el 85% del pico: su final si
   la categoría crece hacia el clímax (riser, reverso), su comienzo si no.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

FFMPEG = r"C:\Users\devic\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
SR = 48000
PICO_OBJETIVO = 10 ** (-1.0 / 20)     # -1 dBFS
PREROLL_MAX_S = 3.0                   # más build que esto no cabe en un video de 30s
COLA_MAX_S = 2.5                      # cuánta cola se guarda después del impacto
TOTAL_MAX_S = 4.0

# slug -> (nombre final, categoría). La familia (golpe/swell/build) no se declara:
# sale de dónde quedó el punto de impacto ya medido sobre el archivo recortado.
# Los 13 que ya están en assets/sfx no aparecen: se comprobó por md5 que son
# byte a byte los mismos, volver a bajarlos sería duplicarlos.
MAPA = {
    # --- whooshes / swooshes / swishes: la categoría #1 en corto ---
    "deep-whoosh-3":            ("whoosh_grave_3",        "whoosh"),
    "deep-whoosh-4":            ("whoosh_grave_4",        "whoosh"),
    "simple-whoosh-2":          ("whoosh_simple_2",       "whoosh"),
    "swoosh":                   ("whoosh_swoosh",         "whoosh"),
    "swoosh-1":                 ("whoosh_swoosh_1",       "whoosh"),
    "swoosh2":                  ("whoosh_swoosh_2",       "whoosh"),
    "swoosh-3":                 ("whoosh_swoosh_3",       "whoosh"),
    "swoosh-4":                 ("whoosh_swoosh_4",       "whoosh"),
    "swoosh-5":                 ("whoosh_swoosh_5",       "whoosh"),
    "swoosh-crash":             ("whoosh_crash",          "whoosh"),
    "swoosh-fast-1":            ("whoosh_rapido_2",       "whoosh"),
    "swoosh-fast-with-thud":    ("whoosh_rapido_golpe",   "whoosh"),
    "swoosh-quick-low":         ("whoosh_corto_grave",    "whoosh"),
    "short-whoosh-metal":       ("whoosh_metal",          "whoosh"),
    "whoosh-coarse-harsh":      ("whoosh_aspero",         "whoosh"),
    "whoosh-achievement":       ("whoosh_logro",          "whoosh"),
    "swish-1":                  ("whoosh_swish_1",        "whoosh"),
    "swish-2":                  ("whoosh_swish_2",        "whoosh"),
    "swish-3":                  ("whoosh_swish_3",        "whoosh"),
    "swish-slicing":            ("whoosh_swish_corte",    "whoosh"),
    "swoosh-sharp-hit-2":       ("transicion_corte_2",    "whoosh"),

    # --- impactos: reveals y remates, 1-2 por video como máximo ---
    "cinematic-bang":           ("impacto_bang_cine",     "impacto"),
    "cinematic-boom":           ("impacto_boom_cine",     "impacto"),
    "cinematic-glass-hit":      ("impacto_vidrio",        "impacto"),
    "cinematic-heavy-hit":      ("impacto_pesado",        "impacto"),
    "deep-hit-2":               ("impacto_grave_2",       "impacto"),
    "deep-hit-3":               ("impacto_grave_3",       "impacto"),
    "impact-hit":               ("impacto_hit_5",         "impacto"),
    "impact-hit-2":             ("impacto_hit_2",         "impacto"),
    "impact-hit-3":             ("impacto_hit_3",         "impacto"),
    "impact-hit-4":             ("impacto_hit_4",         "impacto"),
    "impact-hit-launch":        ("impacto_lanzamiento",   "impacto"),
    "inception-thump":          ("impacto_inception",     "impacto"),
    "impact-and-subdrop":       ("impacto_subdrop",       "impacto"),

    # --- risers / buildups: el hueco más grande del pack actual ---
    "riser-1":                  ("riser_1",               "riser"),
    "riser-2":                  ("riser_2",               "riser"),
    "riser-3":                  ("riser_3",               "riser"),
    "cinematic-riser-wildfire": ("riser_wildfire",        "riser"),
    "cyberpunk-stutter-riser":  ("riser_cyberpunk",       "riser"),
    "tremolo-riser-big-hit":    ("riser_tremolo",         "riser"),
    "dramatic-buildup-1":       ("riser_buildup_1",       "riser"),
    "dramatic-buildup-2":       ("riser_buildup_2",       "riser"),
    "dramatic-buildup-3":       ("riser_buildup_3",       "riser"),
    "dramatic-buildup-4":       ("riser_buildup_4",       "riser"),
    "dramatic-buildup-reveal":  ("riser_reveal",          "riser"),
    "dramatic-buildup-sliced":  ("riser_cortado",         "riser"),
    "dramatic-buildup-whip-1":  ("riser_whip_1",          "riser"),
    "dramatic-buildup-whip-2":  ("riser_whip_2",          "riser"),
    "dramatic-buildup-whip-3":  ("riser_whip_3",          "riser"),

    # --- reverses: succión antes del corte, rebobinado ---
    "cinematic-reverse-1":      ("reverso_1",             "reverso"),
    "cinematic-reverse-2":      ("reverso_2",             "reverso"),
    "cinematic-reverse-3":      ("reverso_3",             "reverso"),
    "cinematic-reverse-4":      ("reverso_4",             "reverso"),
    "cinematic-reverse-5":      ("reverso_5",             "reverso"),
    "cinematic-reverse-6":      ("reverso_6",             "reverso"),
    "cinematic-reverse-7":      ("reverso_7",             "reverso"),
    "cinematic-reverse-8":      ("reverso_8",             "reverso"),
    "cinematic-reverse-9":      ("reverso_9",             "reverso"),
    "cinematic-reverse-10":     ("reverso_10",            "reverso"),
    "cinematic-reverse-11":     ("reverso_11",            "reverso"),
    "cinematic-whoosh-reverse": ("reverso_whoosh",        "reverso"),

    # --- cámara: cortes tipo foto, muy Reels ---
    "camera-1":                 ("camara_click_1",        "camara"),
    "camera-2":                 ("camara_click_2",        "camara"),
    "camera-3":                 ("camara_click_3",        "camara"),
    "camera-4":                 ("camara_click_4",        "camara"),
    "camera-5":                 ("camara_click_5",        "camara"),
    "camera-6":                 ("camara_click_6",        "camara"),
    "camera-focus-and-shutter": ("camara_enfoque",        "camara"),
    "shutter-5dm4":             ("camara_dslr",           "camara"),
    "shutter-zenit":            ("camara_zenit",          "camara"),
    "analog-shutter":           ("camara_analogica",      "camara"),
    "vintage-flash":            ("camara_flash",          "camara"),
    # 37s con 12 disparos de flash separados por silencio: son 12 sonidos, no uno
    "vintage-flash-long":       ("camara_flash_pop",      "camara"),

    # --- UI: apariciones de texto, listas, stickers ---
    "button-pressed":           ("ui_boton",              "ui"),
    "click-button":             ("ui_click",              "ui"),
    "hover":                    ("ui_hover",              "ui"),
    "ui-back-sound":            ("ui_atras",              "ui"),
    "ui-sound":                 ("ui_1",                  "ui"),
    "ui-sound-3":               ("ui_3",                  "ui"),
    "ui-sound-4":               ("ui_4",                  "ui"),
    "ui-sound-6":               ("ui_6",                  "ui"),
    "ui-sound-7":               ("ui_7",                  "ui"),
    "ui-sound-8":               ("ui_8",                  "ui"),
    "ui-sound-off":             ("ui_apagar",             "ui"),
    "game-start":               ("ui_game_start",         "ui"),
    "game-ui":                  ("ui_game",               "ui"),

    # --- notificación / éxito: hito y CTA de cierre ---
    "apple-pay-success":        ("notificacion_pago",     "notificacion"),
}


def leer(p: Path) -> np.ndarray:
    r = subprocess.run(
        [FFMPEG, "-v", "error", "-i", str(p), "-f", "f32le", "-ac", "2",
         "-ar", str(SR), "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).reshape(-1, 2).astype(np.float64)


def escribir(x: np.ndarray, destino: Path):
    datos = np.clip(x, -1.0, 1.0).astype(np.float32).tobytes()
    subprocess.run(
        [FFMPEG, "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2",
         "-i", "-", "-c:a", "libmp3lame", "-b:a", "192k", "-ar", str(SR),
         str(destino)], input=datos, check=True)


def envolvente(x: np.ndarray, ventana_ms: float = 20.0) -> np.ndarray:
    mono = x.mean(axis=1)
    n = max(1, int(SR * ventana_ms / 1000))
    return np.sqrt(np.convolve(mono ** 2, np.ones(n) / n, mode="same"))


# Categorías cuyo clímax está al FINAL: el efecto crece y se corta justo en el
# evento. Un reverse que succiona hacia el corte tiene que TERMINAR en el corte;
# un riser tiene que reventar en el reveal, no empezar ahí.
CATEGORIAS_BUILD = {"riser", "reverso"}


def punto_impacto(x: np.ndarray, categoria: str) -> int:
    """Instante del archivo que hay que hacer coincidir con el evento visual.

    Se localiza la zona por encima del 85% del pico y se toma su final si la
    categoría crece hacia el clímax, o su comienzo (ataque o cresta) si no.

    La categoría manda sobre la forma de la envolvente porque la forma sola no
    los distingue: `cinematic-reverse-2` sube y se queda en meseta dos segundos,
    exactamente igual que `impact-and-subdrop`, y a uno hay que alinearlo por el
    final y al otro por el principio.
    """
    env = envolvente(x)
    if env.max() <= 0:
        return 0
    altos = np.nonzero(env >= env.max() * 0.85)[0]
    return int(altos[-1] if categoria in CATEGORIAS_BUILD else altos[0])


def tomas(x: np.ndarray) -> list:
    """Tramos con sonido de un mp3 que en realidad trae varias tomas dentro."""
    env = envolvente(x, 10.0)
    pico = env.max()
    if pico <= 0:
        return []
    activo = env > pico * 0.012
    bordes = np.diff(activo.astype(np.int8))
    inicios = list(np.nonzero(bordes == 1)[0] + 1)
    finales = list(np.nonzero(bordes == -1)[0] + 1)
    if activo[0]:
        inicios.insert(0, 0)
    if activo[-1]:
        finales.append(len(activo))

    tramos = []
    for a, b in zip(inicios, finales):
        if tramos and a - tramos[-1][1] < 0.30 * SR:
            tramos[-1] = (tramos[-1][0], b)       # el hueco es cola, no otra toma
        else:
            tramos.append((a, b))

    # Un tramo mucho más flojo que el resto no es una toma: es un chasquido
    # suelto o la reverberación que quedó aislada. `cinematic-boom` traía uno
    # así al inicio y partía el boom en dos.
    fuertes = [(a, b) for a, b in tramos
               if (b - a) >= 0.10 * SR and env[a:b].max() >= pico * 0.10]
    return fuertes


def recortar(x: np.ndarray, categoria: str) -> np.ndarray:
    """Deja el archivo con pre-roll y cola acotados alrededor del impacto."""
    p = punto_impacto(x, categoria)
    ini = max(0, p - int(SR * PREROLL_MAX_S))
    fin = min(len(x), p + int(SR * COLA_MAX_S))
    trozo = x[ini:fin]
    if len(trozo) > SR * TOTAL_MAX_S:
        trozo = trozo[:int(SR * TOTAL_MAX_S)]

    # Recortar la cola muerta: silencio final que solo engorda el archivo.
    env = envolvente(trozo, 10.0)
    audible = np.nonzero(env > env.max() * 0.01)[0]
    if len(audible):
        trozo = trozo[:min(len(trozo), audible[-1] + int(SR * 0.15))]
    return trozo


def rematar(x: np.ndarray) -> np.ndarray:
    """Normaliza a -1 dBFS y pone micro-fades para que no chasquee."""
    x = x.copy()
    pico = np.abs(x).max()
    if pico > 0:
        x *= PICO_OBJETIVO / pico
    n_in, n_out = int(SR * 0.004), int(SR * 0.030)
    if len(x) > n_in + n_out:
        x[:n_in] *= np.linspace(0, 1, n_in)[:, None]
        x[-n_out:] *= np.linspace(1, 0, n_out)[:, None]
    return x


def familia(punto_s: float) -> str:
    if punto_s <= 0.12:
        return "golpe"
    return "swell" if punto_s <= 1.0 else "build"


def main():
    origen, destino = Path(sys.argv[1]), Path(sys.argv[2])
    destino.mkdir(parents=True, exist_ok=True)
    for viejo in destino.glob("*.mp3"):
        viejo.unlink()

    catalogo = []
    for slug, (nombre, cat) in sorted(MAPA.items()):
        p = origen / f"{slug}.mp3"
        if not p.exists():
            print(f"FALTA {slug}")
            continue
        x = leer(p)
        tramos = tomas(x)
        if not tramos:
            print(f"VACIO {slug} — se descarta")
            continue

        for i, (a, b) in enumerate(tramos):
            a = max(0, a - int(SR * 0.005))            # 5 ms de aire antes del ataque
            b = min(len(x), b + int(SR * 0.20))
            audio = rematar(recortar(x[a:b], cat))
            punto_s = round(punto_impacto(audio, cat) / SR, 3)
            sufijo = "" if len(tramos) == 1 else f"_{i + 1}"
            final = f"{nombre}{sufijo}.mp3"
            escribir(audio, destino / final)
            catalogo.append({
                "archivo": final, "categoria": cat, "familia": familia(punto_s),
                "punto": punto_s, "duracion": round(len(audio) / SR, 3),
                "origen": slug,
            })

        c0 = catalogo[-len(tramos)]
        marca = f"  ({len(tramos)} tomas)" if len(tramos) > 1 else ""
        print(f"{slug:<28} -> {nombre:<22} {c0['familia']:<5} "
              f"{len(x)/SR:6.2f}s -> {c0['duracion']:5.2f}s "
              f"impacto@{c0['punto']:.2f}s{marca}")

    (destino / "_catalogo.json").write_text(
        json.dumps(catalogo, indent=2, ensure_ascii=False), encoding="utf-8")
    conteo = {}
    for c in catalogo:
        conteo[c["familia"]] = conteo.get(c["familia"], 0) + 1
    print(f"\n{len(catalogo)} archivos desde {len(MAPA)} descargas — "
          + ", ".join(f"{v} {k}" for k, v in sorted(conteo.items())))


if __name__ == "__main__":
    main()
