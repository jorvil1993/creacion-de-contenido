"""
Fase 14 — Datos de la tira de capas apiladas del editor visual.

La tira dibuja seis carriles sobre UNA sola escala de tiempo: voz, subtítulos,
B-Roll/PiP, animaciones, SFX y música. Casi todo lo que necesita ya viaja en
`/datos` (`palabras`, `movibles`, `overlays`, `sfx`, `musica_*`), así que este
módulo NO lo repite: aporta solo lo que no existía en ningún sitio.

1. Los BLOQUES de subtítulo. El carril de subtítulos no muestra palabras sueltas
   sino los grupos de 2-4 que el ASS dibuja juntos. Se calculan aquí llamando a
   `f3_subtitulos.agrupar_en_bloques()` — la misma función del render, no una
   copia — para que el carril no pueda desviarse de lo que se quema en el video.
2. Los BEATS del guion alineado, para el imán del bloque C.
3. Los PUNTOS DE IMÁN ya ordenados y sin duplicados.
4. Las constantes de la tira (zoom, tolerancia del imán, carriles). Viven aquí y
   viajan por `/datos`, como los picos de SFX y la zona segura: el JavaScript no
   hardcodea ninguna.

Todo se calcula a la defensiva: una corrida a la que le falte un archivo tiene
que devolver la estructura vacía pero completa, nunca reventar `recolectar()`.
"""
import json
import re
from pathlib import Path

import config
import f3_subtitulos


# --- Constantes de la tira -------------------------------------------------
# Los seis carriles, en el orden en que se apilan de arriba abajo. `editable`
# dice si se pueden arrastrar sus bloques (bloque C): la voz y los subtítulos
# salen de la transcripción y la música cubre el video entero, así que moverlos
# ahí no querría decir nada.
CARRILES = [
    {"id": "voz",        "etiqueta": "Voz",          "editable": False},
    {"id": "subtitulos", "etiqueta": "Subtítulos",   "editable": False},
    {"id": "broll",      "etiqueta": "B-Roll / PiP", "editable": True},
    {"id": "anim",       "etiqueta": "Animaciones",  "editable": True},
    {"id": "sfx",        "etiqueta": "SFX",          "editable": True},
    {"id": "musica",     "etiqueta": "Música",       "editable": False},
]

# Zoom de la escala de tiempo. 1 = el video entero entra en el ancho visible;
# 40 deja ~0.6s de un video de 25s ocupando toda la tira, que es donde el imán
# de bordes de palabra deja de hacer falta porque ya se apunta a mano.
ZOOM_MIN = 1.0
ZOOM_MAX = 40.0
ZOOM_FACTOR = 1.25   # cada golpe de rueda multiplica o divide por esto

# El imán agarra dentro de esta distancia EN PANTALLA, no en segundos: así al
# ampliar el zoom la ayuda se vuelve más fina sola, en vez de seguir pegando
# todo a medio segundo de distancia cuando ya se ve el fotograma.
IMAN_TOLERANCIA_PX = 8
IMAN_ACTIVO_DEFECTO = True

# Nombres de los archivos de órdenes que escribe f13_guion.py. De ellos salen
# los beats: son los momentos del guion que SÍ alinearon contra la transcripción.
ARCHIVOS_GUION = (
    "guion.sfx.json",
    "guion.broll.json",
    "guion.animaciones.json",
    "guion.eventos.json",
    "guion.encuadre.json",
)

# Dos instantes más cercanos que esto se consideran el mismo punto de imán. No
# es cosmético: un beat del guion casi siempre produce a la vez un SFX y un
# B-Roll en el mismo segundo, y sin esto el imán tendría tres candidatos
# empatados en el mismo sitio.
TOLERANCIA_DEDUPE_S = 0.02

# Fila OK del reporte legible que escribe f13_guion.py:
#   | Beat 3 | `ANIM` | "…" | **OK** | 2.78s | 6.40s | conf 0.77 |
# Se parsea a propósito, aunque sea un .md: es la ÚNICA fuente que conoce los
# beats alineados que no dejaron ningún artefacto (los de tipo `YO`, que no
# generan SFX ni inserto ni animación). Esos beats son cortes editoriales
# igual de válidos para el imán que los demás. El formato lo genera código,
# no una persona, así que no se desalinea solo.
_FILA_REPORTE = re.compile(
    r"^\|\s*Beat\s+(\d+)\s*\|\s*`([^`]*)`\s*\|.*?\|\s*\*\*OK\*\*\s*\|"
    r"\s*([\d.]+)s\s*\|\s*([\d.]+)s\s*\|"
)


def _json_seguro(ruta: Path):
    """Lee un JSON y devuelve None si no está o está roto."""
    try:
        if ruta.exists():
            return json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def bloques_subtitulos(dir_trabajo: Path) -> list:
    """Los bloques de 2-4 palabras que el ASS dibuja juntos.

    Cada bloque trae los índices GLOBALES de sus palabras además del texto: es
    la misma clave con la que `f3_subtitulos.generar_ass()` aplica las
    correcciones de ortografía, así que el carril puede mostrar el texto ya
    corregido sin volver a inventar el mapeo.
    """
    datos = _json_seguro(Path(dir_trabajo) / "02_cortado.json") or {}
    palabras = datos.get("palabras") or []
    if not palabras:
        return []

    indice_de = {id(p): i for i, p in enumerate(palabras)}
    bloques = []
    for grupo in f3_subtitulos.agrupar_en_bloques(palabras):
        if not grupo:
            continue
        bloques.append({
            "ini": round(float(grupo[0]["inicio"]), 3),
            "fin": round(float(grupo[-1]["fin"]), 3),
            "texto": " ".join(p["texto"] for p in grupo),
            # Las palabras sueltas además del texto ya unido: el carril tiene
            # que poder sustituir UNA por su corrección, y volver a partir
            # `texto` por espacios fallaría con cualquier token que traiga uno.
            "palabras": [p["texto"] for p in grupo],
            "indices": [indice_de[id(p)] for p in grupo],
        })
    return bloques


def beats_guion(dir_trabajo: Path) -> list:
    """Los momentos del guion que alinearon contra la transcripción.

    Salen de los `guion.*.json` (datos estructurados, 3 decimales) y del
    reporte `10_guion-alineado.md` (que además conoce los beats sin artefacto).
    Si la corrida se hizo sin `--guion N` no hay ninguno y el imán se queda
    solo con los bordes de palabra.
    """
    dir_trabajo = Path(dir_trabajo)
    crudos = []   # [(t, etiqueta, origen, precision)] — precision 1 = json

    def _añadir(t, etiqueta, origen, precision):
        try:
            t = float(t)
        except (TypeError, ValueError):
            return
        if t >= 0:
            crudos.append((round(t, 3), etiqueta, origen, precision))

    sfx = _json_seguro(dir_trabajo / "guion.sfx.json")
    if isinstance(sfx, dict):
        for e in sfx.get("sfx") or []:
            _añadir(e.get("t"), e.get("razon") or "sfx", "sfx", 1)

    broll = _json_seguro(dir_trabajo / "guion.broll.json")
    if isinstance(broll, dict):
        for e in broll.get("broll") or []:
            etiqueta = e.get("tag") or e.get("asset") or "b-roll"
            _añadir(e.get("ini"), etiqueta, "broll", 1)
            _añadir(e.get("fin"), etiqueta + " (fin)", "broll", 1)

    anim = _json_seguro(dir_trabajo / "guion.animaciones.json")
    if isinstance(anim, dict):
        for e in anim.get("animaciones") or []:
            _añadir(e.get("ini"), e.get("nombre") or "animación", "anim", 1)

    eventos = _json_seguro(dir_trabajo / "guion.eventos.json")
    if isinstance(eventos, dict):
        for e in eventos.get("eventos") or []:
            etiqueta = e.get("tag") or e.get("asset") or "inserto"
            _añadir(e.get("ini"), etiqueta, "evento", 1)
            _añadir(e.get("fin"), etiqueta + " (fin)", "evento", 1)

    enc = _json_seguro(dir_trabajo / "guion.encuadre.json")
    if isinstance(enc, dict):
        for e in enc.get("punch_ins") or []:
            _añadir(e.get("t"), "punch-in", "encuadre", 1)
        for e in enc.get("planos_cerrados") or []:
            _añadir(e.get("ini"), "plano cerrado", "encuadre", 1)
            _añadir(e.get("fin"), "plano cerrado (fin)", "encuadre", 1)

    reporte = dir_trabajo / "10_guion-alineado.md"
    if reporte.exists():
        try:
            for linea in reporte.read_text(encoding="utf-8").splitlines():
                m = _FILA_REPORTE.match(linea.strip())
                if m:
                    idx, tipo = m.group(1), m.group(2)
                    _añadir(m.group(3), f"beat {idx} · {tipo}", "guion", 0)
                    _añadir(m.group(4), f"beat {idx} · {tipo} (fin)", "guion", 0)
        except Exception:
            pass

    # Deduplicado por cercanía. Dentro de cada grupo gana el más PRECISO, no el
    # más temprano: el reporte dice 6.70s y `guion.broll.json` 6.704s del mismo
    # beat, y quedarse con el del reporte por ser 4 milésimas menor tiraría a la
    # basura el dato exacto sin ninguna razón.
    crudos.sort(key=lambda x: x[0])
    grupos = []
    for beat in crudos:
        if grupos and abs(beat[0] - grupos[-1][0][0]) <= TOLERANCIA_DEDUPE_S:
            grupos[-1].append(beat)
        else:
            grupos.append([beat])

    beats = []
    for grupo in grupos:
        t, etiqueta, origen, _precision = max(grupo, key=lambda x: x[3])
        beats.append({"t": t, "etiqueta": etiqueta, "origen": origen})
    return beats


def puntos_iman(dir_trabajo: Path, beats: list = None) -> dict:
    """Los instantes a los que se pega un marcador al arrastrarlo.

    Dos familias separadas a propósito, no una lista mezclada: la tira las
    pinta distinto y hace falta saber a cuál se enganchó para decirlo en el
    aviso ("pegado al fin de «celular»" no es lo mismo que "pegado al beat 5").
    """
    datos = _json_seguro(Path(dir_trabajo) / "02_cortado.json") or {}
    palabras = datos.get("palabras") or []

    bordes = []
    for p in palabras:
        for clave in ("inicio", "fin"):
            try:
                bordes.append(round(float(p[clave]), 3))
            except (KeyError, TypeError, ValueError):
                continue
    bordes.sort()

    unicos = []
    for t in bordes:
        if unicos and abs(t - unicos[-1]) <= TOLERANCIA_DEDUPE_S:
            continue
        unicos.append(t)

    if beats is None:
        beats = beats_guion(dir_trabajo)
    return {"palabras": unicos, "beats": [b["t"] for b in beats]}


def datos_tira(dir_trabajo: Path) -> dict:
    """Todo lo que la tira necesita y que no viaja ya en el resto de /datos."""
    dir_trabajo = Path(dir_trabajo)
    try:
        beats = beats_guion(dir_trabajo)
        return {
            "carriles": CARRILES,
            "zoom": {"min": ZOOM_MIN, "max": ZOOM_MAX, "factor": ZOOM_FACTOR},
            "iman": {
                "tolerancia_px": IMAN_TOLERANCIA_PX,
                "activo_defecto": IMAN_ACTIVO_DEFECTO,
            },
            "subtitulos": bloques_subtitulos(dir_trabajo),
            "beats": beats,
            "imanes": puntos_iman(dir_trabajo, beats),
            "agrupado_sub": {
                "min": config.SUB_PALABRAS_POR_BLOQUE_MIN,
                "max": config.SUB_PALABRAS_POR_BLOQUE_MAX,
            },
        }
    except Exception:
        # Un dato que falte no puede tumbar el editor entero: sin tira se sigue
        # editando en las secciones de siempre.
        return {
            "carriles": CARRILES,
            "zoom": {"min": ZOOM_MIN, "max": ZOOM_MAX, "factor": ZOOM_FACTOR},
            "iman": {
                "tolerancia_px": IMAN_TOLERANCIA_PX,
                "activo_defecto": IMAN_ACTIVO_DEFECTO,
            },
            "subtitulos": [], "beats": [],
            "imanes": {"palabras": [], "beats": []},
            "agrupado_sub": {
                "min": config.SUB_PALABRAS_POR_BLOQUE_MIN,
                "max": config.SUB_PALABRAS_POR_BLOQUE_MAX,
            },
        }
