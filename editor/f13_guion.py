"""
Fase 1c / Orquestación — Pipeline dirigido por guion (`--guion N`).

Extrae el guion N de `PANEL-PRODUCCION.html`, alinea cada beat con las palabras de
`02_cortado.json` (ignorando los segundos del HTML), y emite los 4 JSONs de órdenes
(sfx, animaciones, eventos PIP y B-roll) más el reporte `10_guion-alineado.md`.

Uso:
    python f13_guion.py 7 "salida/Guion-7/02_cortado.json" "salida/Guion-7"
"""
import argparse
import difflib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import config


def normalize_text(txt: str) -> list[str]:
    """Normaliza texto para alineación: minúsculas, sin tildes, sin puntuación."""
    txt = unicodedata.normalize("NFD", txt)
    txt = "".join(c for c in txt if unicodedata.category(c) != "Mn")
    txt = re.sub(r"[^\w\s]", "", txt.lower())
    return [w for w in txt.split() if w]


def cargar_datos_html(ruta_html: Path = None) -> dict:
    """Extrae `CLIPS` y `G` desde PANEL-PRODUCCION.html.

    Intenta Node.js primero; si no está disponible, cae al parser regex de Python.
    """
    ruta_html = (ruta_html or (config.RAIZ_PROYECTO / "PANEL-PRODUCCION.html")).resolve()
    if not ruta_html.exists():
        raise FileNotFoundError(f"No existe {ruta_html}")

    # 1. Intentar Node.js
    try:
        js_code = """
        const fs = require('fs');
        const html = fs.readFileSync(process.argv[1], 'utf8');
        const clipsCode = html.match(/const CLIPS=([\\s\\S]*?);\\s*function/)[1];
        const gCode = html.match(/const G=([\\s\\S]*?\\n\\];)/)[1];
        eval('var CLIPS=' + clipsCode);
        eval('var G=' + gCode);
        console.log(JSON.stringify({CLIPS, G}));
        """
        res = subprocess.run(["node", "-e", js_code, str(ruta_html)], capture_output=True, text=True)
        if res.returncode == 0:
            return json.loads(res.stdout)
    except Exception:
        pass

    # 2. Fallback puro Python
    content = ruta_html.read_text(encoding="utf-8")
    clips_match = re.search(r"const CLIPS\s*=\s*(\{[\s\S]*?\});\s*function", content)
    g_match = re.search(r"const G\s*=\s*(\[[\s\S]*?\n\];)", content)

    if not (clips_match and g_match):
        raise ValueError(f"No se pudo extraer CLIPS o G de {ruta_html}")

    clips_str = clips_match.group(1)
    clips_str = re.sub(r"([A-Z0-9_]+)\s*:", r'"\1":', clips_str)
    clips_str = clips_str.replace("'", '"')
    clips_dict = json.loads(clips_str)

    g_str = g_match.group(1).rstrip(";")
    g_str = re.sub(r"([a-z]+)\s*:", r'"\1":', g_str)
    g_str = g_str.replace("'", '"')
    g_list = json.loads(g_str)

    return {"CLIPS": clips_dict, "G": g_list}


def leer_parametros_guion(numero_guion: int, ruta_html: Path = None) -> dict:
    """Parámetros del guion que hacen falta ANTES de cortar el video.

    El resto de `procesar_guion` corre después de f2_cortar, porque necesita la
    transcripción ya recortada para alinear los beats. Pero el corte de silencios
    tiene que saber de antemano cuánto hook físico conservar, así que ese dato se
    lee aparte y temprano. Es barato: solo parsea el HTML del panel.

    `hooksegs` es el campo que José edita en PANEL-PRODUCCION.html para calibrar
    cada guion sin tocar código.
    """
    datos_html = cargar_datos_html(ruta_html)
    g = obtener_guion(numero_guion, datos_html)
    try:
        hooksegs = float(g.get("hooksegs") or 0.0)
    except (TypeError, ValueError):
        print(f"AVISO: `hooksegs` del guion {numero_guion} no es un número "
              f"({g.get('hooksegs')!r}) — se ignora.", file=sys.stderr)
        hooksegs = 0.0
    return {
        "hooksegs": max(0.0, hooksegs),
        "titulo": g.get("t", ""),
        "tipo_hook": g.get("hook", ""),
    }


def obtener_guion(numero_guion: int, datos_html: dict) -> dict:
    """Obtiene el objeto del guion por su número `n`."""
    guiones = datos_html.get("G", [])
    for g in guiones:
        if g.get("n") == numero_guion:
            return g
    opciones = ", ".join(str(g.get("n")) for g in guiones)
    raise ValueError(f"Guion {numero_guion} no existe en PANEL-PRODUCCION.html. Disponibles: {opciones}")


# Un match por encima de esto se acepta en cuanto aparece, sin seguir buscando
# más adelante. Es lo que impide el salto lejano: si la frase está ahí nomás y
# se parece mucho, es esa — no una coincidencia casual 20 segundos después.
RATIO_ACEPTACION_INMEDIATA = 0.85

# Por debajo de esto el beat se declara no encontrado. Estaba en 0.50, que
# acepta "media frase parecida": demasiado laxo. Los guiones del panel coinciden
# 1.000 con el teleprompter, así que un match real ronda 0.9; 0.65 deja margen
# para que José improvise o WhisperX escuche mal una palabra, sin tragar ruido.
RATIO_MINIMO = 0.65


def alinear_guion_con_transcripcion(script_tl: list, palabras: list,
                                    ratio_threshold: float = RATIO_MINIMO) -> list[dict]:
    """Alinea cada beat del guion contra las palabras de 02_cortado.json.

    Los tiempos del HTML (ej. '3–5s') se ignoran por completo. La sincronización
    se basa en el texto y respeta estricta monotonía (cada beat se busca después
    del anterior).

    Dos salvaguardas contra el fallo en cascada: se acepta el match BUENO más
    temprano en vez del mejor global (un beat poco distintivo podía engancharse
    lejos por casualidad y arrastrar a todos los siguientes), y por debajo de
    `RATIO_MINIMO` el beat se omite en vez de forzar una ubicación dudosa.
    """
    words_trans = []
    for p in palabras:
        norm = normalize_text(p["texto"])
        words_trans.append(norm[0] if norm else "")

    aligned_beats = []
    curr_idx = 0
    num_words_trans = len(words_trans)

    for idx, beat in enumerate(script_tl):
        momento, dice, tipo, ve, sonido, musica = beat
        norm_beat = normalize_text(dice)
        if not norm_beat:
            aligned_beats.append({
                "index": idx, "beat": beat, "matched": False, "reason": "empty_text"
            })
            continue

        best_ratio = 0.0
        best_match = None
        len_b = len(norm_beat)
        anchos = range(max(1, len_b - 2), min(len_b + 4, num_words_trans - curr_idx + 1))

        # Monotonía estricta: se busca solo desde curr_idx en adelante.
        # La posición va POR FUERA para poder cortar en cuanto aparece un match
        # bueno: gana el más temprano, no el mejor global.
        for j in range(curr_idx, num_words_trans):
            mejor_aqui, ancho_aqui = 0.0, None
            for w_len in anchos:
                if j + w_len > num_words_trans:
                    break
                ratio = difflib.SequenceMatcher(None, norm_beat, words_trans[j : j + w_len]).ratio()
                if ratio > mejor_aqui:
                    mejor_aqui, ancho_aqui = ratio, w_len
            if ancho_aqui is not None and mejor_aqui > best_ratio:
                best_ratio = mejor_aqui
                best_match = (j, j + ancho_aqui)
            if best_ratio >= RATIO_ACEPTACION_INMEDIATA:
                break

        if best_ratio >= ratio_threshold and best_match:
            j_start, j_end = best_match
            t_ini = palabras[j_start]["inicio"]
            t_fin = palabras[j_end - 1]["fin"]
            if t_fin <= t_ini:
                t_fin = t_ini + 0.5

            matched_words = [palabras[k]["texto"] for k in range(j_start, j_end)]
            matched_text = " ".join(matched_words)

            aligned_beats.append({
                "index": idx,
                "beat": beat,
                "matched": True,
                "ini": round(t_ini, 3),
                "fin": round(t_fin, 3),
                "duracion": round(t_fin - t_ini, 3),
                "ratio": round(best_ratio, 3),
                "matched_text": matched_text,
                "range_words": (j_start, j_end)
            })
            curr_idx = j_end
        else:
            aligned_beats.append({
                "index": idx,
                "beat": beat,
                "matched": False,
                "ratio": round(best_ratio, 3) if best_match else 0.0,
                "reason": "low_confidence"
            })

    return aligned_beats


# Cuánto se puede correr un SFX para despegarlo del anterior antes de que deje
# de leerse como "el sonido de ESE momento". Más que esto, mejor omitirlo.
SFX_CORRIMIENTO_MAX_S = 0.35


def espaciar_sfx(ordenes: list) -> list:
    """Impone config.SFX_SEPARACION_MIN_S sobre TODA la lista, no beat por beat.

    Repartir los sonidos dentro de un beat no alcanza: el último de un beat
    puede quedar pegado al primero del siguiente. Acá se corre lo mínimo
    necesario y, si haría falta correrlo demasiado, se omite — un efecto
    desplazado medio segundo suena a error, no a intención.
    """
    ordenes.sort(key=lambda e: e["t"])
    salida, ultimo = [], None
    for e in ordenes:
        if ultimo is None or e["t"] - ultimo >= config.SFX_SEPARACION_MIN_S:
            salida.append(e)
            ultimo = e["t"]
            continue
        nuevo = ultimo + config.SFX_SEPARACION_MIN_S
        if nuevo - e["t"] <= SFX_CORRIMIENTO_MAX_S:
            print(f"  SFX {Path(e['archivo']).name} corrido {nuevo - e['t']:.2f}s "
                  f"({e['t']:.2f}s -> {nuevo:.2f}s) para no encimarse con el anterior")
            e["t"] = round(nuevo, 3)
            salida.append(e)
            ultimo = e["t"]
        else:
            print(f"  AVISO: SFX {Path(e['archivo']).name} en {e['t']:.2f}s omitido — "
                  f"cae a {e['t'] - ultimo:.2f}s del anterior y correrlo lo desincronizaría")
    return salida


_CACHE_DURACION = {}


def duracion_clip(ruta: Path) -> float | None:
    """Duración real del clip, cacheada. None si ffprobe no puede leerlo.

    Hace falta para no pedirle a un clip más metraje del que tiene: `rendicion.mp4`
    dura 4.84s y una ventana de 6s dejaba 1.16s sin imagen y el fade de salida
    calculado más allá del final del archivo.
    """
    ruta = Path(ruta)
    clave = str(ruta)
    if clave in _CACHE_DURACION:
        return _CACHE_DURACION[clave]
    try:
        salida = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(ruta)],
            capture_output=True, text=True, check=True).stdout.strip()
        dur = float(salida)
    except Exception:
        dur = None
    _CACHE_DURACION[clave] = dur
    return dur


def extender_fin_evento(t_ini: float, t_fin: float, idx: int, beats_alineados: list,
                        tipos_que_cortan: tuple = None, ruta_clip: Path = None) -> float:
    """Cuánto se queda en pantalla un B-roll o un PIP.

    Antes esta función estaba definida DOS VECES en este archivo y la segunda
    pisaba a la primera, así que el mínimo de 3s no se aplicaba nunca: mandaba
    `duracion * BROLL_PIP_DURACION_FACTOR` y los B-rolls del guion 7 salieron de
    2.12s y 2.41s. Ahora hay una sola.

    Criterio (decisión de José, 2026-07-27): el inserto se queda TODO lo que
    pueda. El tope es el `ini` del próximo beat que le dispute el sitio, no el
    fin de la frase que lo disparó — que la persona siga hablando debajo del
    B-roll es justamente la técnica.

    Quién le disputa el sitio depende de dónde vive cada cosa (ver
    config.BROLL_TIPOS_QUE_CORTAN): un B-roll ocupa el cuadro entero y una
    animación de esquina puede convivir encima de él, así que un ANIM no lo
    corta; a un PIP, que también es de esquina, sí.

    Los tres topes, en orden: el próximo beat que compite, el techo estético
    (BROLL_PIP_DURACION_MAX_S) y el metraje que realmente tiene el clip.
    """
    tipos_que_cortan = tipos_que_cortan or config.BROLL_TIPOS_QUE_CORTAN

    fin_tope = t_ini + config.BROLL_PIP_DURACION_MAX_S
    for r_sig in beats_alineados[idx + 1:]:
        if not r_sig["matched"] or r_sig["beat"][2] not in tipos_que_cortan:
            continue
        fin_tope = min(fin_tope, r_sig["ini"] - config.BROLL_PIP_GAP_MIN_S)
        break

    if ruta_clip is not None:
        dur_real = duracion_clip(ruta_clip)
        if dur_real:
            fin_tope = min(fin_tope, t_ini + dur_real)

    # Nunca menos que la frase que lo disparó: si el próximo evento cae antes,
    # el solapamiento lo resuelve quien compone, no acortamos por debajo del
    # motivo por el que el inserto existe.
    return round(max(t_fin, fin_tope), 3)


# Cómo se nombra un acercamiento en la columna "Qué se ve" y en la descripción
# de cada toma del panel. Se buscan sobre el texto normalizado (sin tildes).
_MARCAS_PUNCH_IN = ("punch in", "punchin", "punch-in")
_MARCAS_PLANO_CERRADO = ("plano cerrado", "primer plano", "plano corto", "mas cerca")
_MARCAS_PLANO_ABIERTO = ("plano medio", "plano abierto", "plano general")


def _tiene(texto: str, marcas: tuple) -> bool:
    plano = " ".join(normalize_text(texto or ""))
    return any(m.replace("-", " ") in plano for m in marcas)


def plan_encuadre(guion_dict: dict, palabras: list, beats_alineados: list) -> dict:
    """Traduce las indicaciones de cámara del panel a órdenes de zoom para f4.

    Existen dos columnas con información de encuadre y hasta ahora el pipeline
    ignoraba las dos: decidía los acercamientos por percentil de energía RMS del
    audio, o sea por cuándo José subió la voz. Ese criterio es mecánico, no
    editorial — el mismo error que ya se corrigió con los SFX.

      · `tl[i][3]` ("Qué se ve") marca los énfasis puntuales: "Punch-in sobre tu
        cara", 'Punch-in en "algoritmo"'.
      · `tomas[i][1]` marca la distancia de cámara de tramos enteros: "Plano
        cerrado (acercá la cámara)". Como `tomas[i][3]` trae el texto que se
        dice en esa toma, se alinea contra la transcripción igual que los beats
        y sale un rango real, no los segundos aproximados del HTML.

    Esto es la mitad digital de lo que José pidió: grabar un solo plano abierto
    y que el pipeline acerque donde el guion dice "plano cerrado". La otra mitad
    (grabar dos planos de verdad y unirlos) la hace editor.py.
    """
    punch_ins = []
    for r in beats_alineados:
        if not r.get("matched") or not _tiene(r["beat"][3], _MARCAS_PUNCH_IN):
            continue
        t = r["ini"]
        # Si la indicación entrecomilla una palabra ('Punch-in en "algoritmo"'),
        # el acercamiento va SOBRE esa palabra, no al principio de la frase.
        cita = re.search(r'"([^"]+)"|“([^”]+)”', r["beat"][3])
        if cita:
            objetivo = normalize_text(cita.group(1) or cita.group(2))
            j0, j1 = r.get("range_words", (0, 0))
            for k in range(j0, min(j1, len(palabras))):
                if normalize_text(palabras[k]["texto"]) == objetivo:
                    t = palabras[k]["inicio"]
                    break
        punch_ins.append({"t": round(float(t), 3), "razon": r["beat"][3][:60]})

    # --- tramos de plano cerrado ------------------------------------------
    tomas = guion_dict.get("tomas", [])
    pseudo_beats = [(t[0], t[3], "TOMA", t[1], "", "") for t in tomas]
    tomas_alineadas = alinear_guion_con_transcripcion(pseudo_beats, palabras)

    cerrados = []
    for r in tomas_alineadas:
        if not r.get("matched"):
            continue
        descripcion = r["beat"][3]
        if not _tiene(descripcion, _MARCAS_PLANO_CERRADO):
            continue
        if _tiene(descripcion, _MARCAS_PLANO_ABIERTO):
            continue          # "vuelves al plano medio" no es un acercamiento
        cerrados.append({
            "ini": round(r["ini"], 3),
            "fin": round(r["fin"], 3),
            "zoom": config.ZOOM_PLANO_CERRADO,
            "razon": descripcion[:60],
        })

    return {"punch_ins": punch_ins, "planos_cerrados": cerrados}


def resolver_codigo_asset(texto_ve: str, clips_map: dict) -> tuple[str | None, Path | None, str]:
    """Extrae el código (F16, P02) o el nombre de asset directo de 'qué se ve' y busca su archivo.

    Devuelve (codigo, ruta_archivo, slug).
    """
    if not texto_ve:
        return None, None, ""

    match = re.search(r"\b([FP]\d{2})\b", texto_ve)
    if match:
        codigo = match.group(1)
        entry = clips_map.get(codigo)
        slug = entry[0] if entry else codigo
    else:
        codigo = None
        # Buscar en video manual cualquier palabra/slug explícito mencionado en texto_ve
        dir_v_manual = config.DIR_VIDEO_MANUAL
        for word in re.findall(r"\b[a-zA-Z0-9_\-]+\b", texto_ve):
            for ext in (".mp4", ".mov", ".webm"):
                cand = dir_v_manual / f"{word}{ext}"
                if cand.exists():
                    return None, cand, word
        # Fallback al primer token
        first_word = re.search(r"\b[a-zA-Z0-9_\-]+\b", texto_ve)
        slug = first_word.group(0) if first_word else ""

    # Buscar primero en assets/generado/video/manual/
    dir_v_manual = config.DIR_VIDEO_MANUAL
    for ext in (".mp4", ".mov", ".webm"):
        cand = dir_v_manual / f"{slug}{ext}"
        if cand.exists():
            return codigo, cand, slug

    # Si no está en video manual, buscar en assets/generado/manual/ (imágenes)
    dir_img_manual = config.DIR_GENERADO / "manual"
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        cand = dir_img_manual / f"{slug}{ext}"
        if cand.exists():
            return codigo, cand, slug

    return codigo, None, slug


def extraer_sfx_de_texto(texto_sonido: str) -> list[Path]:
    """Extrae nombres de archivos de SFX válidos de la celda de sonido del HTML."""
    if not texto_sonido or texto_sonido.strip() == "—":
        return []

    tokens = re.findall(r"\b[a-zA-Z0-9_]+\b", texto_sonido)
    encontrados = []
    dir_sfx = config.DIR_ASSETS / "sfx"

    for token in tokens:
        cand = dir_sfx / f"{token}.mp3"
        if cand.exists() and cand not in encontrados:
            encontrados.append(cand)

    return encontrados


def extraer_plantilla_animacion(texto_ve: str, clips_map: dict = None) -> str:
    """Extrae la animación de 'qué se ve', soportando códigos H01-H08 y nombres directos.

    Devuelve el nombre CANÓNICO, o sea el que usa config: el panel dice H03 y el
    mapa de clips lo traduce a "anim-sol", pero config indexa esa animación como
    "sol". Sin normalizar aquí, el nombre llegaba a f6_overlays sin entrada en
    ANIMACION_DURACION y la animación se descartaba con un "animación
    desconocida" que nadie mira.
    """
    import f8_hyperframes

    if not texto_ve:
        return "tarjeta-cta"

    match_h = re.search(r"\b(H\d{2})\b", texto_ve)
    if match_h and clips_map:
        entry = clips_map.get(match_h.group(1))
        if entry:
            return f8_hyperframes.nombre_canonico(entry[0])

    # Nombre escrito a mano en la celda, sin código H0x. El orden importa:
    # "anim-splash" contiene "anim-s...", así que las más largas van primero.
    for p in sorted(f8_hyperframes.PLANTILLAS, key=len, reverse=True):
        if p in texto_ve:
            return f8_hyperframes.nombre_canonico(p)

    match = re.search(r"\b(tarjeta-[a-z]+|anim-[a-z]+)\b", texto_ve)
    if match:
        return f8_hyperframes.nombre_canonico(match.group(1))

    return "tarjeta-cta"  # fallback común si el tipo es ANIM


# Tipos de sticker que acepta la plantilla H07 (ver compositions/stickers.html).
STICKERS_VALIDOS = ("destello", "envio", "bandera")


def extraer_variables_animacion(nombre_anim: str, texto_ve: str) -> dict:
    """Variables que el guion le pasa a la plantilla, más allá de la variante.

    Hoy solo la usa `stickers`, que es la única con una variable de contenido
    (`tipo`) en vez de una de forma. Sin esto, escribir "H07 bandera" en el panel
    daba igual: la plantilla salía siempre con su default (destello), porque el
    camino de animaciones solo sabía pasar variante, lado y etiqueta.
    """
    if nombre_anim != "stickers":
        return {}
    plano = " ".join(normalize_text(texto_ve or ""))
    for tipo in STICKERS_VALIDOS:
        if tipo in plano:
            return {"tipo": tipo}
    return {}


def procesar_guion(numero_guion: int, json_cortado_path: Path, dir_trabajo: Path,
                   ruta_html: Path = None) -> dict:
    """Procesa el guion N, alinea con la transcripción y genera las 4 órdenes + reporte."""
    datos_html = cargar_datos_html(ruta_html)
    guion_dict = obtener_guion(numero_guion, datos_html)
    clips_map = datos_html.get("CLIPS", {})

    trans_data = json.loads(Path(json_cortado_path).read_text(encoding="utf-8"))
    palabras = trans_data.get("palabras", [])
    # Segundos de hook físico que f2_cortar dejó sin cortar al principio (0 si
    # el guion no lo pide en su campo `hooksegs`).
    hook_conservado_s = float(trans_data.get("hook_conservado_s") or 0.0)

    print(f"\n======================================================================")
    print(f"  PROCESANDO GUION {numero_guion}: \"{guion_dict.get('t')}\"")
    print(f"======================================================================")

    beats_alineados = alinear_guion_con_transcripcion(guion_dict["tl"], palabras)

    # Guarda contra el error más caro de todos: correr el guion equivocado sobre
    # una grabación. Si NADA alinea, el video saldría sin un solo inserto ni
    # efecto y sin que nada haya "fallado" — se vería como un problema del
    # pipeline cuando en realidad es que se pidió otro guion.
    n_ok = sum(1 for r in beats_alineados if r["matched"])
    if n_ok == 0:
        print(f"\n  {'!' * 68}")
        print(f"  AVISO GRAVE: NINGUNO de los {len(beats_alineados)} beats del guion "
              f"{numero_guion} aparece en el audio.")
        print(f"  Casi seguro esta grabación NO es del guion {numero_guion} "
              f"(\"{guion_dict.get('t')}\").")
        print(f"  El video va a salir SIN insertos, SIN B-roll y SIN los efectos del guion.")
        print(f"  Revisá el número de guion o mirá 10_guion-alineado.md.")
        print(f"  {'!' * 68}\n")
    elif n_ok < len(beats_alineados) / 2:
        print(f"\n  AVISO: solo {n_ok} de {len(beats_alineados)} beats alinearon. "
              f"Revisá 10_guion-alineado.md antes de publicar.\n")

    # Crear directorio temporal para renders PIP de video/imagen
    dir_tmp = dir_trabajo / "_tmp_guion"
    dir_tmp.mkdir(parents=True, exist_ok=True)

    ordenes_sfx = []
    ordenes_animaciones = []
    ordenes_eventos = []
    ordenes_broll = []
    reporte_filas = []

    import f6_overlays
    import f12_video_gen

    for r in beats_alineados:
        b = r["beat"]
        momento, dice, tipo, ve, sonido, musica = b
        idx = r["index"]

        if not r["matched"]:
            # Excepción: el PRIMER beat de un guion con hook físico no puede
            # alinear contra nada, porque mientras entras al cuadro y te sientas
            # todavía no se dice una palabra. Sus sonidos ("whoosh_rapido al
            # entrar + impacto_grave al sentarte") se colocan en la ventana de
            # silencio que f2_cortar dejó a propósito al principio.
            if idx == 0 and hook_conservado_s > 0:
                archivos_hook = extraer_sfx_de_texto(sonido)
                for i_sfx, sfx_file in enumerate(archivos_hook):
                    # El primero al aparecer, el resto repartidos hasta justo
                    # antes de la primera palabra.
                    n = max(1, len(archivos_hook))
                    t_sfx = 0.10 + (hook_conservado_s - 0.25) * i_sfx / n
                    ordenes_sfx.append({
                        "t": round(max(0.05, t_sfx), 3),
                        "archivo": str(sfx_file),
                        "volumen": 0.9,
                        "razon": "hook_fisico",
                    })
                print(f"  [Beat  0 - {tipo}]: hook físico sin habla -> {len(archivos_hook)} sonido(s) "
                      f"en los primeros {hook_conservado_s:.2f}s")
                reporte_filas.append(
                    f"| Beat {idx} | `{tipo}` | \"{dice}\" | **HOOK** | 0.00s | "
                    f"{hook_conservado_s:.2f}s | Sin habla: entras al cuadro |")
                continue
            print(f"  AVISO [Beat {idx:2d} - {tipo}]: \"{dice[:40]}\" NO encontrado en el audio -> OMITIDO")
            reporte_filas.append(f"| Beat {idx} | `{tipo}` | \"{dice}\" | **OMITIDO** | - | - | Frase no encontrada en audio |")
            continue

        t_ini, t_fin, dur = r["ini"], r["fin"], r["duracion"]
        reporte_filas.append(f"| Beat {idx} | `{tipo}` | \"{dice}\" | **OK** | {t_ini:.2f}s | {t_fin:.2f}s | conf {r['ratio']:.2f} |")

        # 1. SFX
        # Cuando una celda nombra VARIOS sonidos son momentos distintos, no un
        # acorde: "whoosh_rapido al entrar + impacto_grave al sentarte". Si se
        # emiten todos en t_ini quedan encimados y se enturbian entre sí (y
        # violan config.SFX_SEPARACION_MIN_S). Se reparten dentro del beat,
        # respetando esa separación mínima sin pasarse del final.
        archivos_sfx = extraer_sfx_de_texto(sonido)
        # Se reparten dentro del beat; la separación global la impone después
        # `espaciar_sfx()`, que ve también los beats vecinos.
        hueco = (dur / len(archivos_sfx)) if len(archivos_sfx) > 1 else 0.0
        for i_sfx, sfx_file in enumerate(archivos_sfx):
            t_sfx = t_ini + i_sfx * hueco
            if i_sfx and t_sfx > t_fin:
                # No cabe dentro del beat: se pega al final en vez de invadir el siguiente
                t_sfx = max(t_ini, t_fin - 0.05)
            ordenes_sfx.append({
                "t": round(t_sfx, 3),
                "archivo": str(sfx_file),
                "volumen": 0.8,
                "razon": f"guion_{idx}",
            })

        # 2. ANIMACIONES
        if tipo == "ANIM":
            nombre_anim = extraer_plantilla_animacion(ve, clips_map)
            if nombre_anim in config.PLANTILLAS_CON_DATOS_PROPIOS:
                # Estas las arma el pipeline con datos que este camino no tiene
                # (el mensaje y el WhatsApp del CTA, las specs del catálogo, los
                # dos modelos de la comparativa). Pedirlas por aquí las sacaría
                # vacías y encimadas con la que el pipeline ya puso.
                print(f"  [Beat {idx:2d} - ANIM]: '{nombre_anim}' la coloca el pipeline con sus "
                      f"propios datos -> no se duplica")
                reporte_filas[-1] = reporte_filas[-1].replace(
                    "| conf ", f"| {nombre_anim} automática · conf ")
                continue
            ordenes_animaciones.append({
                "nombre": nombre_anim,
                "ini": t_ini,
                "variables": extraer_variables_animacion(nombre_anim, ve),
                # A propósito SIN "dur": la animación dura lo que dura su
                # composición (data-duration del HTML, replicado en
                # config.ANIMACION_DURACION), no lo que dura la frase que la
                # dispara. Pasando la duración del beat, anim-apps (3.0s de
                # clip) se cortaba a los 1.08s que dura "Es que compites contra
                # una app…" y el gesto no llegaba a completarse.
            })

        # 3. PIP
        elif tipo == "PIP":
            codigo, asset_path, slug = resolver_codigo_asset(ve, clips_map)
            if asset_path is None:
                print(f"  AVISO [Beat {idx:2d} - PIP]: Clip {codigo} ({slug}) no encontrado en disco -> OMITIDO")
            else:
                ext = asset_path.suffix.lower()
                # Posición por defecto: si el texto menciona izquierda, a la izquierda
                pos_x = 60 if "izquierda" in ve.lower() else (config.ANCHO - 480)
                pos_y = int(config.ALTO * config.INSERTO_Y_PCT)
                # El PIP vive en una esquina: cualquier otro inserto de esquina
                # (otro PIP, una animación) le disputa el sitio y lo corta.
                t_fin = extender_fin_evento(
                    t_ini, t_fin, idx, beats_alineados,
                    tipos_que_cortan=config.PIP_TIPOS_QUE_CORTAN,
                    ruta_clip=asset_path if ext in (".mp4", ".mov", ".webm") else None)

                if ext in (".mp4", ".mov", ".webm"):
                    destino_mov = dir_tmp / f"pip_guion_{idx}_{slug}.mov"
                    try:
                        w_t, h_t = f12_video_gen.render_pip_video(asset_path, destino_mov)
                        ordenes_eventos.append({
                            "tipo": "pip-producto",
                            "medio": "video",
                            "archivo": str(destino_mov),
                            "x": pos_x,
                            "y": pos_y,
                            "ini": t_ini,
                            "fin": t_fin,
                            "palabra": dice[:30],
                            "tag": slug,
                            "asset": f"video:{slug}",
                        })
                    except Exception as e:
                        print(f"  AVISO: Error procesando PIP de video {asset_path.name}: {e}")
                else:
                    destino_png = dir_tmp / f"pip_guion_{idx}_{slug}.png"
                    try:
                        f6_overlays.render_pip_producto(asset_path, destino_png, ancho=400, alto=520, centrar_en_lienzo=False)
                        ordenes_eventos.append({
                            "tipo": "pip-producto",
                            "archivo": str(destino_png),
                            "x": pos_x,
                            "y": pos_y,
                            "ini": t_ini,
                            "fin": t_fin,
                            "palabra": dice[:30],
                            "tag": slug,
                            "asset": f"manual:{slug}",
                        })
                    except Exception as e:
                        print(f"  AVISO: Error procesando PIP de imagen {asset_path.name}: {e}")

        # 4. B-ROLL
        elif tipo == "B-ROLL":
            codigo, asset_path, slug = resolver_codigo_asset(ve, clips_map)
            if asset_path is None or asset_path.suffix.lower() not in (".mp4", ".mov", ".webm"):
                print(f"  AVISO [Beat {idx:2d} - B-ROLL]: Clip de video {codigo} ({slug}) no encontrado -> OMITIDO")
            else:
                ordenes_broll.append({
                    "tipo": "broll",
                    "medio": "video",
                    "broll_fullscreen": True,
                    "archivo": str(asset_path),
                    "x": 0,
                    "y": 0,
                    "ini": t_ini,
                    # A pantalla completa: solo otro B-roll o un PIP le quitan
                    # el cuadro. Una animación de esquina se compone encima.
                    "fin": extender_fin_evento(
                        t_ini, t_fin, idx, beats_alineados,
                        tipos_que_cortan=config.BROLL_TIPOS_QUE_CORTAN,
                        ruta_clip=asset_path),
                    "palabra": dice[:30],
                    "tag": slug,
                    "asset": f"broll-manual:{slug}",
                    "codigo": codigo,
                })

    # Guardar los JSONs de órdenes
    ruta_sfx = dir_trabajo / "guion.sfx.json"
    ruta_anim = dir_trabajo / "guion.animaciones.json"
    ruta_eventos = dir_trabajo / "guion.eventos.json"
    ruta_broll = dir_trabajo / "guion.broll.json"
    ruta_encuadre = dir_trabajo / "guion.encuadre.json"
    ruta_reporte = dir_trabajo / "10_guion-alineado.md"

    encuadre = plan_encuadre(guion_dict, palabras, beats_alineados)

    ordenes_sfx = espaciar_sfx(ordenes_sfx)
    ruta_sfx.write_text(json.dumps({"sfx": ordenes_sfx}, ensure_ascii=False, indent=2), encoding="utf-8")
    ruta_anim.write_text(json.dumps({"animaciones": ordenes_animaciones}, ensure_ascii=False, indent=2), encoding="utf-8")
    ruta_eventos.write_text(json.dumps({"eventos": ordenes_eventos}, ensure_ascii=False, indent=2), encoding="utf-8")
    ruta_broll.write_text(json.dumps({"broll": ordenes_broll}, ensure_ascii=False, indent=2), encoding="utf-8")
    ruta_encuadre.write_text(json.dumps(encuadre, ensure_ascii=False, indent=2), encoding="utf-8")

    # Guardar reporte en Markdown
    lineas_reporte = [
        f"# Reporte de Alineación de Guion {numero_guion}: \"{guion_dict.get('t')}\"",
        "",
        f"- **Beats totales en guion:** {len(guion_dict['tl'])}",
        f"- **Beats alineados exitosamente:** {len([r for r in beats_alineados if r['matched']])}",
        f"- **SFX ordenados:** {len(ordenes_sfx)}",
        f"- **Animaciones ordenadas:** {len(ordenes_animaciones)}",
        f"- **Insertos PIP ordenados:** {len(ordenes_eventos)}",
        f"- **B-Rolls fullscreen ordenados:** {len(ordenes_broll)}",
        f"- **Punch-ins del guion:** {len(encuadre['punch_ins'])}"
        + (f" ({', '.join(str(round(p['t'], 1)) + 's' for p in encuadre['punch_ins'])})"
           if encuadre["punch_ins"] else ""),
        f"- **Tramos de plano cerrado:** {len(encuadre['planos_cerrados'])}"
        + (f" ({', '.join('{:.1f}-{:.1f}s'.format(c['ini'], c['fin']) for c in encuadre['planos_cerrados'])})"
           if encuadre["planos_cerrados"] else ""),
        f"- **Hook físico conservado:** {hook_conservado_s:.2f}s"
        if hook_conservado_s else "- **Hook físico conservado:** no (hooksegs = 0)",
        "",
        "| Beat | Tipo | Texto Guion | Estado | Inicio | Fin | Detalles |",
        "|---|---|---|---|---|---|---|",
        *reporte_filas,
        "",
    ]
    ruta_reporte.write_text("\n".join(lineas_reporte), encoding="utf-8")

    # Extraer pista de música si se especifica en la columna de música
    pista_musica = None
    for beat in guion_dict["tl"]:
        m_txt = beat[5]
        match_m = re.search(r"\b(\d{2}-[a-z\-]+)\b", m_txt)
        if match_m:
            pista_musica = match_m.group(1)
            break

    print(f"  Reporte de alineación guardado: {ruta_reporte}")
    print(f"  Órdenes generadas: SFX ({len(ordenes_sfx)}), Animaciones ({len(ordenes_animaciones)}), "
          f"PIP ({len(ordenes_eventos)}), B-roll ({len(ordenes_broll)}), "
          f"Encuadre ({len(encuadre['punch_ins'])} punch-ins, "
          f"{len(encuadre['planos_cerrados'])} planos cerrados)")

    return {
        "sfx": ruta_sfx,
        "animaciones": ruta_anim,
        "eventos": ruta_eventos,
        "broll": ruta_broll,
        "encuadre": ruta_encuadre,
        "reporte": ruta_reporte,
        # OJO: el banner de hook sale de `t` (el titular del guion), NO de
        # `hooktxt`. En el panel, `hooktxt` es la acotación de dirección sobre
        # cómo entrar al plano ("Entras al plano y te sientas de golpe") — si se
        # usara esa, el video mostraría en pantalla una instrucción de rodaje.
        # `t` es el hook real y coincide casi textual con el primer beat hablado
        # en los 10 guiones (verificado).
        "hook": guion_dict.get("t", ""),
        "musica": pista_musica,
    }


def main():
    parser = argparse.ArgumentParser(description="Procesador de Guion para Pipeline Dirigido")
    parser.add_argument("guion", type=int, help="Número de guion (ej. 7)")
    parser.add_argument("json_cortado", type=str, help="Ruta a 02_cortado.json")
    parser.add_argument("dir_trabajo", type=str, help="Carpeta de trabajo de la corrida")
    args = parser.parse_args()

    procesar_guion(args.guion, Path(args.json_cortado), Path(args.dir_trabajo))


if __name__ == "__main__":
    main()
