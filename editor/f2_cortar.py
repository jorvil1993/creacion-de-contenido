"""
Fase 1b — Corte inteligente.

Toma el JSON de f1_transcribir.py y decide qué recortar:
  1. Silencios largos (> SILENCIO_UMBRAL_MS), dejando margen a cada lado.
  2. Muletillas (lista calibrable en config.py).
  3. Tomas repetidas (similitud difusa entre frases cercanas) — se queda con la última.

Luego corta el video con ffmpeg (filter_complex trim+concat, sin reencode
intermedio a disco) y RECALCULA los timestamps de las palabras sobre la
nueva línea de tiempo. Esta recalculación es la parte más delicada: si se
desincroniza, subtítulos y overlays quedan corridos.

Uso:
    python f2_cortar.py "video.transcripcion.json" "video.mp4" [--salida salida.mp4]
"""
import argparse
import copy
import difflib
import json
import re
import subprocess
import sys
from pathlib import Path

import config


def _normalizar(texto: str) -> str:
    texto = texto.lower().strip()
    texto = re.sub(r"[^\wáéíóúñü\s]", "", texto)
    return texto.strip()


# Perfil del presentador activo. Se fija en main() con --presentador; por
# defecto es el de José, que es el único calibrado con grabación real.
# Antes estas listas eran globales de config y no había forma de que la esposa
# de José tuviera las suyas (sección 2 del plan pide soportar 2 presentadores).
PERFIL = config.perfil()


def _es_muletilla(palabra_texto: str) -> bool:
    return _normalizar(palabra_texto) in PERFIL["muletillas"]


def _es_conector_ambiguo(palabra_texto: str) -> bool:
    return _normalizar(palabra_texto) in PERFIL["conectores_ambiguos"]


def detectar_cortes_silencio(silencios: list, conservar_inicio_s: float = 0.0,
                              conservar_fin_s: float = 0.0,
                              duracion_total: float = None) -> tuple:
    """Silencios > umbral -> se recorta el centro, dejando margen a cada lado.

    `conservar_inicio_s` protege el HOOK FÍSICO: los segundos de silencio que
    quedan JUSTO ANTES de la primera palabra no se cortan. Es el gesto de entrar
    al cuadro y sentarse, que sin esto desaparecía — en la grabación del guion 7
    había 7.9s de silencio inicial y el corte dejaba 0.15s: el video arrancaba
    con José ya hablando.

    Se protege el FINAL de ese silencio, no el principio: lo que hay que salvar
    es la entrada, no los segundos de silla vacía de antes, que se siguen
    cortando igual que siempre.

    `conservar_fin_s` es lo mismo en la otra punta: protege los segundos de
    silencio que quedan JUSTO DESPUÉS de la última palabra (levantarte, bajar
    el aparato). Ahí se protege el INICIO de ese silencio, no el final: lo que
    hay que salvar es la salida, no los segundos de silla vacía de después, que
    se siguen cortando igual que siempre. Necesita `duracion_total` para saber
    cuál es el silencio final (el que termina pegado al fin del archivo).

    Devuelve (cortes, hook_conservado_s, cierre_conservado_s). f13_guion usa el
    segundo para saber que hay una ventana de hook donde colocar sus sonidos.
    """
    umbral_s = PERFIL["silencio_umbral_ms"] / 1000
    margen_s = config.SILENCIO_MARGEN_MS / 1000
    cortes = []

    # El silencio inicial es el que arranca pegado al segundo 0; solo ese es el
    # hook. Un silencio a mitad del video no lleva protección por más largo que
    # sea. (f1_transcribir emite los silencios ordenados y el primero, si existe,
    # empieza en 0.0.)
    inicio_protegido = None
    if conservar_inicio_s > 0 and silencios and silencios[0]["inicio"] <= 0.05:
        inicio_protegido = silencios[0]

    # Simétrico: el silencio final es el que termina pegado a la duración total
    # del archivo. Solo ese es el cierre; una pausa larga a mitad del video no
    # lleva protección por más que se acerque al final.
    fin_protegido = None
    if (conservar_fin_s > 0 and silencios and duracion_total is not None
            and abs(silencios[-1]["fin"] - duracion_total) <= 0.05):
        fin_protegido = silencios[-1]

    conservado_inicio = 0.0
    conservado_fin = 0.0
    for s in silencios:
        duracion = s["duracion"]
        if duracion <= umbral_s:
            continue
        if duracion <= 2 * margen_s:
            continue  # muy corto para dejar margen en ambos lados, no se toca

        if s is inicio_protegido:
            # Se corta desde el arranque del archivo hasta dejar exactamente
            # `conservar_inicio_s` de aire antes de la primera palabra. Si el
            # silencio es más corto que eso, no se corta nada.
            inicio_corte = 0.0
            fin_corte = s["fin"] - conservar_inicio_s
            conservado_inicio = min(conservar_inicio_s, duracion)
            if fin_corte <= inicio_corte:
                print(f"  hook físico: el silencio inicial dura {duracion:.2f}s y se pidieron "
                      f"{conservar_inicio_s:.2f}s — se conserva entero, sin corte.")
                continue
            razon = (f"silencio inicial de {duracion:.2f}s "
                     f"(se conservan {conservado_inicio:.2f}s de hook físico)")
        elif s is fin_protegido:
            # Se corta desde `conservar_fin_s` después de la última palabra
            # hasta el final del archivo. Si el silencio es más corto que eso,
            # no se corta nada.
            inicio_corte = s["inicio"] + conservar_fin_s
            fin_corte = s["fin"]
            conservado_fin = min(conservar_fin_s, duracion)
            if fin_corte <= inicio_corte:
                print(f"  cierre físico: el silencio final dura {duracion:.2f}s y se pidieron "
                      f"{conservar_fin_s:.2f}s — se conserva entero, sin corte.")
                continue
            razon = (f"silencio final de {duracion:.2f}s "
                     f"(se conservan {conservado_fin:.2f}s de cierre físico)")
        else:
            inicio_corte = s["inicio"] + margen_s
            fin_corte = s["fin"] - margen_s
            razon = f"silencio de {duracion:.2f}s"

        if fin_corte > inicio_corte:
            cortes.append({
                "inicio": round(inicio_corte, 3),
                "fin": round(fin_corte, 3),
                "razon": razon,
                # El silencio ENTERO del que sale este corte. El editor de
                # silencios lo usa como tope de sus tiradores: se puede cortar
                # menos (dejar más aire) hasta devolver el silencio completo,
                # pero nunca más, porque a partir de ahí ya se estaría cortando
                # habla y este bloque existe para lo contrario.
                "limite_inicio": round(s["inicio"], 3),
                "limite_fin": round(s["fin"], 3),
            })
    return cortes, round(conservado_inicio, 3), round(conservado_fin, 3)


def detectar_cortes_muletillas(palabras: list, segmentos: list) -> list:
    """Marca palabras-muletilla para remover, salvo que sean la primera/última de su frase."""
    cortes = []
    # localizar primera/última palabra por segmento comparando tiempos
    primeras = {round(seg["inicio"], 3) for seg in segmentos}
    ultimas = {round(seg["fin"], 3) for seg in segmentos}

    for i, p in enumerate(palabras):
        texto = p["texto"]
        es_borde = round(p["inicio"], 3) in primeras or round(p["fin"], 3) in ultimas
        if es_borde:
            continue  # nunca cortar primera/última palabra de una frase

        if _es_muletilla(texto):
            cortes.append({"inicio": p["inicio"], "fin": p["fin"], "razon": f"muletilla '{texto}'"})
            continue

        if _es_conector_ambiguo(texto):
            # solo se corta si está aislado: pausa notable antes Y después
            pausa_antes = p["inicio"] - palabras[i - 1]["fin"] if i > 0 else 999
            pausa_despues = palabras[i + 1]["inicio"] - p["fin"] if i < len(palabras) - 1 else 999
            if pausa_antes > 0.3 and pausa_despues > 0.3:
                cortes.append({"inicio": p["inicio"], "fin": p["fin"], "razon": f"conector aislado '{texto}'"})

    return cortes


def detectar_tomas_repetidas(segmentos: list) -> list:
    """Compara frases cercanas por similitud difusa; si coinciden, corta la más antigua."""
    cortes = []
    ventana_s = config.TOMA_REPETIDA_VENTANA_S
    umbral = config.TOMA_REPETIDA_SIMILITUD_MIN

    for i in range(len(segmentos)):
        texto_i = _normalizar(segmentos[i]["texto"])
        if len(texto_i) < 4:
            continue
        for j in range(i + 1, len(segmentos)):
            if segmentos[j]["inicio"] - segmentos[i]["fin"] > ventana_s:
                break
            texto_j = _normalizar(segmentos[j]["texto"])
            if len(texto_j) < 4:
                continue
            ratio = difflib.SequenceMatcher(None, texto_i, texto_j).ratio()
            if ratio >= umbral:
                # se quedan con la última (j): cortar la i (más antigua)
                cortes.append({
                    "inicio": segmentos[i]["inicio"],
                    "fin": segmentos[i]["fin"],
                    "razon": f"toma repetida (similitud {ratio:.2f} con frase en {segmentos[j]['inicio']:.1f}s): '{segmentos[i]['texto'][:40]}'",
                })
                break  # ya se decidió remover i, no seguir comparándola

    return cortes


def _fusionar_intervalos(intervalos: list) -> list:
    if not intervalos:
        return []
    ordenados = sorted(intervalos, key=lambda x: x["inicio"])
    fusionados = [dict(ordenados[0])]
    for actual in ordenados[1:]:
        anterior = fusionados[-1]
        if actual["inicio"] <= anterior["fin"]:
            anterior["fin"] = max(anterior["fin"], actual["fin"])
            anterior.setdefault("razones", [anterior.get("razon", "")]).append(actual.get("razon", ""))
        else:
            fusionados.append(dict(actual))
    return fusionados


def calcular_intervalos_a_conservar(duracion_total: float, cortes: list) -> list:
    cortes = _fusionar_intervalos(cortes)
    conservar = []
    cursor = 0.0
    for c in cortes:
        if c["inicio"] > cursor:
            conservar.append({"inicio": round(cursor, 3), "fin": round(c["inicio"], 3)})
        cursor = max(cursor, c["fin"])
    if duracion_total - cursor > 0.01:
        conservar.append({"inicio": round(cursor, 3), "fin": round(duracion_total, 3)})
    return [c for c in conservar if c["fin"] - c["inicio"] > 0.01]


def recalcular_timestamps_palabras(palabras: list, intervalos_conservados: list) -> list:
    """Mapea timestamps originales -> nueva línea de tiempo concatenada.
    Descarta palabras que caen fuera de todos los intervalos conservados."""
    nuevas_palabras = []
    offset_nuevo = 0.0
    for intervalo in intervalos_conservados:
        s, e = intervalo["inicio"], intervalo["fin"]
        for p in palabras:
            # una palabra se conserva solo si cae COMPLETAMENTE dentro del intervalo
            if p["inicio"] >= s - 1e-6 and p["fin"] <= e + 1e-6:
                nueva = dict(p)
                nueva["inicio"] = round(offset_nuevo + (p["inicio"] - s), 3)
                nueva["fin"] = round(offset_nuevo + (p["fin"] - s), 3)
                nuevas_palabras.append(nueva)
        offset_nuevo += (e - s)
    nuevas_palabras.sort(key=lambda x: x["inicio"])
    return nuevas_palabras


def mapear_a_nueva_linea(t: float, intervalos_conservados: list) -> float:
    """Un instante de la grabación original -> su posición tras el corte.

    Es la misma aritmética que `recalcular_timestamps_palabras`, pero para un
    tiempo suelto en vez de una palabra. La usan los límites entre tomas reales
    (cuando se graban dos planos y se unen antes de transcribir): si no se
    remapearan, el render creería que el cambio de plano sigue en el segundo del
    archivo crudo y el zoom se reiniciaría en el sitio equivocado.

    Un instante que cayó DENTRO de un tramo cortado se pega al corte, que es
    donde de verdad quedó en el video resultante.
    """
    offset = 0.0
    for iv in intervalos_conservados:
        if t < iv["inicio"]:
            return round(offset, 3)          # cayó en un tramo cortado
        if t <= iv["fin"]:
            return round(offset + (t - iv["inicio"]), 3)
        offset += iv["fin"] - iv["inicio"]
    return round(offset, 3)


def mapear_a_original(t: float, intervalos_conservados: list) -> float:
    """Inversa exacta de `mapear_a_nueva_linea`: del video cortado al original.

    La necesita el editor de silencios: para llevar un ajuste (un SFX, un
    B-roll) de la línea de tiempo vieja a la nueva hay que pasar por la
    grabación original, que es el único sistema de coordenadas que NO cambia
    cuando se restaura un tramo. Componer `mapear_a_original` con los
    intervalos viejos y `mapear_a_nueva_linea` con los nuevos da el remapeo
    completo, y es exacto: verificado sobre Guion-7 con paso de 10 ms, error
    máximo 0.000 ms.

    Ambigüedad en los empalmes: un instante que cae JUSTO en la costura entre
    dos intervalos conservados corresponde a dos puntos del original (el fin de
    uno y el principio del siguiente). Se devuelve el FIN del intervalo que
    termina, no el inicio del que empieza, porque un ajuste colocado en esa
    costura se hizo mirando el fotograma que ya estaba en pantalla.
    """
    offset = 0.0
    for iv in intervalos_conservados:
        largo = iv["fin"] - iv["inicio"]
        if t <= offset + largo + 1e-9:
            return round(iv["inicio"] + (t - offset), 3)
        offset += largo
    return round(intervalos_conservados[-1]["fin"], 3) if intervalos_conservados else 0.0


def detectar_todos_los_cortes(datos_transcripcion: dict, duracion_total: float,
                              conservar_inicio: float = 0.0,
                              conservar_fin: float = 0.0) -> tuple:
    """Los tres detectores de una sola llamada, sobre la transcripción SIN cortar.

    Se extrajo de `main()` para que el editor de silencios pueda recalcular el
    catálogo de cortes candidatos sin volver a transcribir ni cortar nada. Es
    determinista: la misma transcripción y el mismo perfil dan siempre la misma
    lista, así que los identificadores que el editor construye a partir de ella
    sobreviven a cualquier número de re-cortes.

    Devuelve (cortes, hook_conservado_s, cierre_conservado_s).
    """
    palabras = datos_transcripcion.get("palabras", [])
    segmentos = datos_transcripcion.get("segmentos", [])
    silencios = datos_transcripcion.get("silencios", [])

    cortes, hook_s, cierre_s = detectar_cortes_silencio(
        silencios, conservar_inicio, conservar_fin, duracion_total)
    cortes = list(cortes)
    cortes += detectar_cortes_muletillas(palabras, segmentos)
    cortes += detectar_tomas_repetidas(segmentos)
    return cortes, hook_s, cierre_s


def boundaries_de_cortes(intervalos: list) -> list:
    """Instantes de corte en la línea de tiempo YA concatenada.

    Cada empalme entre dos tramos conservados es un salto de plano visible. El
    tiempo de ese empalme en el video resultante es la suma de las duraciones de
    todos los tramos anteriores. El último tramo no genera empalme (es el final).
    Estos son los puntos donde f2b_transiciones dibuja la transición, y los que
    el editor visual enseña para quitar o ajustar.
    """
    limites = []
    acum = 0.0
    for iv in intervalos[:-1]:
        acum += iv["fin"] - iv["inicio"]
        limites.append(round(acum, 3))
    return limites


def _resolucion_video(ruta: Path) -> tuple:
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
           "stream=width,height", "-of", "csv=p=0:s=x", str(ruta)]
    salida = subprocess.run(cmd, capture_output=True, text=True, check=True)
    w, h = salida.stdout.strip().split("x")
    return int(w), int(h)


def cortar_video_ffmpeg(ruta_entrada: Path, ruta_salida: Path, intervalos: list,
                        transicion: str = "ninguna", intensidad_trans: float = 1.0,
                        boundaries: list = None, specs: list = None):
    n = len(intervalos)
    if n == 0:
        raise ValueError("No quedaron intervalos para conservar — revisar umbrales de corte")

    partes_filtro = []
    labels_v = []
    labels_a = []
    for i, iv in enumerate(intervalos):
        partes_filtro.append(
            f"[0:v]trim=start={iv['inicio']}:end={iv['fin']},setpts=PTS-STARTPTS[v{i}]"
        )
        partes_filtro.append(
            f"[0:a]atrim=start={iv['inicio']}:end={iv['fin']},asetpts=PTS-STARTPTS[a{i}]"
        )
        labels_v.append(f"[v{i}]")
        labels_a.append(f"[a{i}]")

    concat_inputs = "".join(l1 + l2 for l1, l2 in zip(labels_v, labels_a))
    # El video concatenado sale por [vc]; si hay transición, se le encadenan los
    # filtros ventaneados en los empalmes y el resultado sale por [vout]. Los
    # filtros NO cambian la duración (ver f2b_transiciones), así que el mapeo de
    # tiempos de aguas abajo no se entera.
    partes_filtro.append(f"{concat_inputs}concat=n={n}:v=1:a=1[vc][aout]")
    map_v = "[vc]"
    if boundaries is None:
        boundaries = boundaries_de_cortes(intervalos)
    filtro_trans = ""
    if specs:
        # Formato por empalme: cada corte con su propia transición e intensidad.
        import f2b_transiciones
        try:
            w_src, h_src = _resolucion_video(ruta_entrada)
        except Exception:
            w_src, h_src = config.ANCHO, config.ALTO
        filtro_trans = f2b_transiciones.construir_filtro_multi(specs, w_src, h_src, config.FPS)
        if filtro_trans:
            n = len({s["tipo"] for s in specs if s.get("tipo", "ninguna") != "ninguna"})
            print(f"Transiciones por empalme: {len(specs)} corte(s) con transición "
                  f"({n} tipo(s) distinto(s))")
    elif transicion and transicion != "ninguna" and boundaries:
        # Formato global (bandera CLI): una sola transición para todos los empalmes.
        import f2b_transiciones
        try:
            w_src, h_src = _resolucion_video(ruta_entrada)
        except Exception:
            w_src, h_src = config.ANCHO, config.ALTO
        filtro_trans = f2b_transiciones.construir_filtro(
            transicion, boundaries, w_src, h_src, intensidad_trans, config.FPS)
        if filtro_trans:
            print(f"Transición entre cortes: '{transicion}' (intensidad {intensidad_trans:.1f}) "
                  f"en {len(boundaries)} empalme(s)")
    if filtro_trans:
        partes_filtro.append(f"[vc]{filtro_trans}[vout]")
        map_v = "[vout]"
    filtro = ";".join(partes_filtro)

    cmd = [
        "ffmpeg", "-y", "-i", str(ruta_entrada),
        "-filter_complex", filtro,
        "-map", map_v, "-map", "[aout]",
        *config.args_video(),
        "-c:a", "aac", "-b:a", "192k",
        str(ruta_salida),
    ]
    print("Ejecutando ffmpeg (esto puede tardar)...")
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    if resultado.returncode != 0:
        print(resultado.stderr[-4000:], file=sys.stderr)
        raise RuntimeError("ffmpeg falló al cortar el video")


def _duracion_video(ruta: Path) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(ruta)]
    salida = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(salida.stdout.strip())


def main():
    parser = argparse.ArgumentParser(description="Corta silencios, muletillas y tomas repetidas")
    parser.add_argument("transcripcion", type=str)
    parser.add_argument("video", type=str)
    parser.add_argument("--salida", type=str, default=None)
    parser.add_argument("--presentador", type=str, default=None,
                        choices=sorted(config.PRESENTADORES),
                        help="Perfil de corte a usar (muletillas y umbral de silencio propios)")
    parser.add_argument("--conservar-inicio", type=float, default=None, metavar="SEGS",
                        help="Segundos de silencio a conservar justo antes de la primera "
                             "palabra: el hook físico (entrar al cuadro, sentarse). Con "
                             "--guion N el valor sale del campo `hooksegs` del panel")
    parser.add_argument("--conservar-fin", type=float, default=None, metavar="SEGS",
                        help="Segundos de silencio a conservar justo después de la última "
                             "palabra: el cierre físico (levantarte, bajar el aparato). Con "
                             "--guion N el valor sale del campo `cierresegs` del panel")
    parser.add_argument("--silencios", type=str, default=None, metavar="JSON",
                        help="ajustes.silencios.json del editor visual: qué tramos "
                             "detectados NO hay que cortar (silencios restaurados a "
                             "mano) y con qué límites. Sin esto se cortan todos los "
                             "detectados, que es el comportamiento de siempre")
    parser.add_argument("--tomas", type=str, default=None, metavar="JSON",
                        help="Lista de segundos donde empieza cada toma real, en la línea de "
                             "tiempo del archivo de entrada (la escribe editor.py al unir "
                             "varias grabaciones). Se remapean al video ya cortado")
    parser.add_argument("--transicion", type=str, default="ninguna",
                        help="Transición a dibujar en los empalmes entre cortes "
                             "(flash-blanco, glitch, zoom-punch, ...). 'ninguna' = corte "
                             "seco de siempre. Ver f2b_transiciones.TRANSICIONES")
    parser.add_argument("--intensidad-transicion", type=float, default=1.0, metavar="K",
                        help="Fuerza de la transición: 0.5 suave, 1.0 normal, 1.5 agresiva")
    parser.add_argument("--transiciones-json", type=str, default=None, metavar="JSON",
                        help="ajustes.transiciones.json del editor visual: tipo, intensidad "
                             "y qué empalmes quitar. Manda sobre --transicion/--intensidad")
    args = parser.parse_args()

    global PERFIL
    PERFIL = config.perfil(args.presentador)
    if not PERFIL["calibrado"]:
        print(f"AVISO: el perfil '{PERFIL['nombre']}' todavía no está calibrado con "
              "grabación real — revisa el corte antes de publicar.")

    ruta_transcripcion = Path(args.transcripcion)
    ruta_video = Path(args.video)
    ruta_salida = Path(args.salida) if args.salida else ruta_video.with_name(ruta_video.stem + "_cortado.mp4")

    datos = json.loads(ruta_transcripcion.read_text(encoding="utf-8"))
    palabras = datos["palabras"]
    segmentos = datos.get("segmentos", [])
    silencios = datos.get("silencios", [])

    duracion_total = _duracion_video(ruta_video)

    conservar_inicio = (args.conservar_inicio if args.conservar_inicio is not None
                        else config.HOOK_CONSERVAR_INICIO_S)
    if conservar_inicio > 0:
        print(f"Hook físico: se conservan {conservar_inicio:.2f}s de silencio antes de la "
              f"primera palabra.")

    conservar_fin = (args.conservar_fin if args.conservar_fin is not None
                     else config.HOOK_CONSERVAR_FIN_S)
    if conservar_fin > 0:
        print(f"Cierre físico: se conservan {conservar_fin:.2f}s de silencio después de la "
              f"última palabra.")

    cortes, hook_conservado_s, cierre_conservado_s = detectar_todos_los_cortes(
        datos, duracion_total, conservar_inicio, conservar_fin)

    # El editor de silencios puede desactivar cortes: si hay una selección
    # guardada, manda ella. La detección de arriba se ejecuta igual porque es la
    # que produce el catálogo completo de tramos que el editor deja elegir.
    if args.silencios:
        import f15_silencios
        cortes, descartados = f15_silencios.aplicar_seleccion(
            cortes, Path(args.silencios))
        if descartados:
            print(f"\nEditor de silencios: {len(descartados)} tramo(s) NO se cortan "
                  f"(restaurados a mano):")
            for c in descartados:
                print(f"  [{c['inicio']:.2f}s - {c['fin']:.2f}s] {c['razon']}")

    print(f"Cortes detectados: {len(cortes)}")
    for c in cortes:
        print(f"  [{c['inicio']:.2f}s - {c['fin']:.2f}s] {c['razon']}")

    intervalos_conservados = calcular_intervalos_a_conservar(duracion_total, cortes)
    duracion_resultante = sum(iv["fin"] - iv["inicio"] for iv in intervalos_conservados)
    print(f"\nDuración original: {duracion_total:.1f}s -> resultante: {duracion_resultante:.1f}s")

    # Transiciones entre cortes. El editor visual, si lo tocó José, manda por
    # encima de las banderas: puede cambiar el tipo, la intensidad y quitar
    # empalmes sueltos. Los empalmes se cuentan por índice sobre la lista
    # completa `todos_los_empalmes`, que es determinista dada la selección de
    # cortes — así el editor y el render hablan del mismo empalme.
    transicion = args.transicion
    intensidad_transicion = args.intensidad_transicion
    todos_los_empalmes = boundaries_de_cortes(intervalos_conservados)
    empalmes_activos = list(todos_los_empalmes)
    specs = None
    marcas_guardadas = None          # lista [{t,tipo,intensidad}] para reescribir en el JSON
    transiciones_por_empalme = {}    # {idx: {tipo, intensidad}} (formato viejo por empalme)
    dur_cortada = duracion_resultante
    if args.transiciones_json and Path(args.transiciones_json).exists():
        cfg = json.loads(Path(args.transiciones_json).read_text(encoding="utf-8"))
        if "marcas" in cfg:
            # Formato LIBRE: transiciones en cualquier segundo de la línea de
            # tiempo cortada, puestas a mano en el editor (una tira con aguja).
            # Es el que sirve para un video ya unido, donde el corte visual no
            # cae en ningún empalme que el pipeline detecte.
            specs = []
            marcas_guardadas = []
            for m in (cfg.get("marcas") or []):
                tipo = m.get("tipo", "ninguna")
                if tipo in (None, "", "ninguna"):
                    continue
                t = float(m.get("t", -1))
                if not (0 <= t <= dur_cortada):
                    continue
                intens = float(m.get("intensidad", 1.0))
                specs.append({"t": round(t, 3), "tipo": tipo, "intensidad": intens})
                marcas_guardadas.append({"t": round(t, 3), "tipo": tipo,
                                         "intensidad": round(intens, 2)})
        elif "empalmes" in cfg:
            # Formato por empalme detectado: cada corte con su propia transición.
            specs = []
            for idx, ecfg in (cfg.get("empalmes") or {}).items():
                i = int(idx)
                if not (0 <= i < len(todos_los_empalmes)):
                    continue
                tipo = ecfg.get("tipo", "ninguna")
                if tipo in (None, "", "ninguna"):
                    continue
                intens = float(ecfg.get("intensidad", 1.0))
                specs.append({"t": todos_los_empalmes[i], "tipo": tipo, "intensidad": intens})
                transiciones_por_empalme[i] = {"tipo": tipo, "intensidad": round(intens, 2)}
        else:
            # Formato VIEJO/global: un tipo para todos, con empalmes quitados.
            transicion = cfg.get("transicion", transicion)
            intensidad_transicion = float(cfg.get("intensidad", intensidad_transicion))
            quitados = set(cfg.get("empalmes_quitados", []))
            empalmes_activos = [t for i, t in enumerate(todos_los_empalmes) if i not in quitados]

    cortar_video_ffmpeg(ruta_video, ruta_salida, intervalos_conservados,
                        transicion=transicion, intensidad_trans=intensidad_transicion,
                        boundaries=empalmes_activos, specs=specs)

    palabras_recalculadas = recalcular_timestamps_palabras(palabras, intervalos_conservados)

    salida_json = ruta_salida.with_suffix(".json")
    salida_datos = copy.deepcopy(datos)
    salida_datos["palabras"] = palabras_recalculadas
    salida_datos.pop("segmentos", None)
    salida_datos.pop("silencios", None)
    salida_datos["cortes_aplicados"] = cortes
    salida_datos["intervalos_conservados_original"] = intervalos_conservados
    salida_datos["duracion_resultante_s"] = round(duracion_resultante, 2)
    # Con qué se detectaron los cortes y sobre qué archivo. El editor de
    # silencios reconstruye el catálogo de tramos llamando otra vez a los
    # detectores, y sin estos tres datos tendría que adivinar los parámetros:
    # con otro `conservar_inicio` el primer tramo sale distinto y el editor
    # enseñaría un corte que no es el que se aplicó.
    salida_datos["corte_parametros"] = {
        "conservar_inicio_s": round(conservar_inicio, 3),
        "conservar_fin_s": round(conservar_fin, 3),
        # La CLAVE del perfil ("jose"/"esposa"), no su nombre para mostrar:
        # config.perfil() solo entiende la clave, y guardar "José" hacía que el
        # editor de silencios reventara al reconstruir el catálogo.
        "presentador": args.presentador,
        "duracion_original_s": round(duracion_total, 3),
        "fuente_corte": str(ruta_video),
    }
    # Ventana de hook físico en la NUEVA línea de tiempo: va de 0 a este valor y
    # no tiene ni una palabra. f13_guion la usa para colocar ahí los sonidos del
    # primer beat, que por definición no puede alinear contra la transcripción
    # (no se dice nada mientras se entra al cuadro).
    salida_datos["hook_conservado_s"] = hook_conservado_s
    salida_datos["cierre_conservado_s"] = cierre_conservado_s

    # Empalmes entre cortes (línea de tiempo YA cortada) y la transición aplicada.
    # El editor visual los lee para dibujar un marcador en cada uno y dejar
    # quitarlo o cambiar el estilo/intensidad.
    salida_datos["empalmes_s"] = todos_los_empalmes
    if marcas_guardadas is not None:
        salida_datos["transicion"] = {"marcas": marcas_guardadas}
    elif specs is not None:
        salida_datos["transicion"] = {"empalmes": {str(i): c for i, c in
                                                   transiciones_por_empalme.items()}}
    else:
        salida_datos["transicion"] = {
            "tipo": transicion,
            "intensidad": round(intensidad_transicion, 2),
            "empalmes_quitados": sorted(set(range(len(todos_los_empalmes))) -
                                        {todos_los_empalmes.index(t) for t in empalmes_activos})
                                  if len(empalmes_activos) != len(todos_los_empalmes) else [],
        }

    if args.tomas:
        tomas_orig = json.loads(Path(args.tomas).read_text(encoding="utf-8"))
        tomas_nuevas = sorted({mapear_a_nueva_linea(float(t), intervalos_conservados)
                               for t in tomas_orig})
        salida_datos["tomas_s"] = tomas_nuevas
        print(f"\nTomas reales remapeadas al video cortado: "
              f"{', '.join(f'{t:.2f}s' for t in tomas_nuevas)}")
    salida_json.write_text(json.dumps(salida_datos, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nVideo cortado: {ruta_salida}")
    print(f"Transcripción recalculada: {salida_json}")

    if not (config.DURACION_MIN_S <= duracion_resultante <= config.DURACION_MAX_S):
        print(f"\nADVERTENCIA: duración resultante ({duracion_resultante:.1f}s) fuera del rango objetivo "
              f"({config.DURACION_MIN_S}-{config.DURACION_MAX_S}s). Puede necesitar calibrar umbrales o "
              f"guion más corto en la próxima grabación.")


if __name__ == "__main__":
    main()
