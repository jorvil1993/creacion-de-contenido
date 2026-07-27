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


def extender_fin_evento(t_ini: float, t_fin: float, idx: int, beats_alineados: list, min_dur: float = 3.0) -> float:
    """Garantiza que B-Rolls y PIPs duren al menos `min_dur` segundos (ej. 3.0s).

    Si la frase del audio es muy corta, extiende el fin sobre el silencio o pausa
    hasta alcanzar `min_dur` segundos (o hasta el inicio del siguiente beat),
    evitando que los B-Rolls se corten de forma brusca o demasiado rápida.
    """
    dur_actual = t_fin - t_ini
    if dur_actual < min_dur:
        t_limite = t_ini + min_dur
        for sig in beats_alineados[idx + 1:]:
            if sig.get("matched"):
                sig_ini = sig["ini"]
                t_limite = min(t_limite, max(t_fin, sig_ini))
                break
        t_fin = max(t_fin, t_limite)
    return round(t_fin, 3)



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


def extender_fin_evento(t_ini: float, t_fin: float, idx: int, beats_alineados: list) -> float:
    """PIP y B-roll duran solo lo que dura la frase que los dispara — a veces
    ~1s, un flashazo. Se extiende el `fin` a config.BROLL_PIP_DURACION_FACTOR
    veces esa duración, topado por el `ini` del próximo beat que TAMBIÉN
    ponga algo en pantalla (PIP/B-ROLL/ANIM) — no por un `YO` intermedio: el
    B-roll puede seguir tapando la pantalla mientras la persona sigue hablando
    la frase siguiente sin overlay propio, que es justo la técnica de B-roll
    (beats_alineados[i]["index"] == i siempre, así que basta indexar hacia
    adelante).
    """
    duracion = t_fin - t_ini
    fin_deseado = t_ini + duracion * config.BROLL_PIP_DURACION_FACTOR
    for r_sig in beats_alineados[idx + 1:]:
        if not r_sig["matched"]:
            continue
        if r_sig["beat"][2] == "YO":
            continue
        fin_deseado = min(fin_deseado, r_sig["ini"] - config.BROLL_PIP_GAP_MIN_S)
        break
    return round(max(fin_deseado, t_fin), 3)


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
    """Extrae la plantilla de animación de 'qué se ve', soportando códigos H01-H08 y nombres directos."""
    if not texto_ve:
        return "tarjeta-cta"

    match_h = re.search(r"\b(H\d{2})\b", texto_ve)
    if match_h and clips_map:
        entry = clips_map.get(match_h.group(1))
        if entry:
            return entry[0]

    plantillas_validas = [
        "anim-apps", "tarjeta-cta", "comparativa", "anim-sol", "anim-bateria",
        "anim-moto", "anim-splash", "tarjeta-specs", "stickers", "banner-hook", "pip-producto"
    ]
    for p in plantillas_validas:
        if p in texto_ve:
            return p

    match = re.search(r"\b(tarjeta-[a-z]+|anim-[a-z]+)\b", texto_ve)
    if match:
        return match.group(1)

    return "tarjeta-cta"  # fallback común si el tipo es ANIM


def procesar_guion(numero_guion: int, json_cortado_path: Path, dir_trabajo: Path,
                   ruta_html: Path = None) -> dict:
    """Procesa el guion N, alinea con la transcripción y genera las 4 órdenes + reporte."""
    datos_html = cargar_datos_html(ruta_html)
    guion_dict = obtener_guion(numero_guion, datos_html)
    clips_map = datos_html.get("CLIPS", {})

    trans_data = json.loads(Path(json_cortado_path).read_text(encoding="utf-8"))
    palabras = trans_data.get("palabras", [])

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
            ordenes_animaciones.append({
                "nombre": nombre_anim,
                "ini": t_ini,
                "dur": dur,
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
                t_fin = extender_fin_evento(t_ini, t_fin, idx, beats_alineados)

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
                    "fin": extender_fin_evento(t_ini, t_fin, idx, beats_alineados),
                    "palabra": dice[:30],
                    "tag": slug,
                    "asset": f"broll-manual:{slug}",
                    "codigo": codigo,
                })

    # Guardar los 4 JSONs de órdenes
    ruta_sfx = dir_trabajo / "guion.sfx.json"
    ruta_anim = dir_trabajo / "guion.animaciones.json"
    ruta_eventos = dir_trabajo / "guion.eventos.json"
    ruta_broll = dir_trabajo / "guion.broll.json"
    ruta_reporte = dir_trabajo / "10_guion-alineado.md"

    ordenes_sfx = espaciar_sfx(ordenes_sfx)
    ruta_sfx.write_text(json.dumps({"sfx": ordenes_sfx}, ensure_ascii=False, indent=2), encoding="utf-8")
    ruta_anim.write_text(json.dumps({"animaciones": ordenes_animaciones}, ensure_ascii=False, indent=2), encoding="utf-8")
    ruta_eventos.write_text(json.dumps({"eventos": ordenes_eventos}, ensure_ascii=False, indent=2), encoding="utf-8")
    ruta_broll.write_text(json.dumps({"broll": ordenes_broll}, ensure_ascii=False, indent=2), encoding="utf-8")

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
          f"PIP ({len(ordenes_eventos)}), B-roll ({len(ordenes_broll)})")

    return {
        "sfx": ruta_sfx,
        "animaciones": ruta_anim,
        "eventos": ruta_eventos,
        "broll": ruta_broll,
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
