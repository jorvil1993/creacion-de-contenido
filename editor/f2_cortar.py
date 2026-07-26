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


def detectar_cortes_silencio(silencios: list) -> list:
    """Silencios > umbral -> se recorta el centro, dejando margen a cada lado."""
    umbral_s = PERFIL["silencio_umbral_ms"] / 1000
    margen_s = config.SILENCIO_MARGEN_MS / 1000
    cortes = []
    for s in silencios:
        duracion = s["duracion"]
        if duracion <= umbral_s:
            continue
        if duracion <= 2 * margen_s:
            continue  # muy corto para dejar margen en ambos lados, no se toca
        inicio_corte = s["inicio"] + margen_s
        fin_corte = s["fin"] - margen_s
        if fin_corte > inicio_corte:
            cortes.append({
                "inicio": round(inicio_corte, 3),
                "fin": round(fin_corte, 3),
                "razon": f"silencio de {duracion:.2f}s",
            })
    return cortes


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


def cortar_video_ffmpeg(ruta_entrada: Path, ruta_salida: Path, intervalos: list):
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
    partes_filtro.append(f"{concat_inputs}concat=n={n}:v=1:a=1[vout][aout]")
    filtro = ";".join(partes_filtro)

    cmd = [
        "ffmpeg", "-y", "-i", str(ruta_entrada),
        "-filter_complex", filtro,
        "-map", "[vout]", "-map", "[aout]",
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

    cortes = []
    cortes += detectar_cortes_silencio(silencios)
    cortes += detectar_cortes_muletillas(palabras, segmentos)
    cortes += detectar_tomas_repetidas(segmentos)

    print(f"Cortes detectados: {len(cortes)}")
    for c in cortes:
        print(f"  [{c['inicio']:.2f}s - {c['fin']:.2f}s] {c['razon']}")

    intervalos_conservados = calcular_intervalos_a_conservar(duracion_total, cortes)
    duracion_resultante = sum(iv["fin"] - iv["inicio"] for iv in intervalos_conservados)
    print(f"\nDuración original: {duracion_total:.1f}s -> resultante: {duracion_resultante:.1f}s")

    cortar_video_ffmpeg(ruta_video, ruta_salida, intervalos_conservados)

    palabras_recalculadas = recalcular_timestamps_palabras(palabras, intervalos_conservados)

    salida_json = ruta_salida.with_suffix(".json")
    salida_datos = copy.deepcopy(datos)
    salida_datos["palabras"] = palabras_recalculadas
    salida_datos.pop("segmentos", None)
    salida_datos.pop("silencios", None)
    salida_datos["cortes_aplicados"] = cortes
    salida_datos["intervalos_conservados_original"] = intervalos_conservados
    salida_datos["duracion_resultante_s"] = round(duracion_resultante, 2)
    salida_json.write_text(json.dumps(salida_datos, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nVideo cortado: {ruta_salida}")
    print(f"Transcripción recalculada: {salida_json}")

    if not (config.DURACION_MIN_S <= duracion_resultante <= config.DURACION_MAX_S):
        print(f"\nADVERTENCIA: duración resultante ({duracion_resultante:.1f}s) fuera del rango objetivo "
              f"({config.DURACION_MIN_S}-{config.DURACION_MAX_S}s). Puede necesitar calibrar umbrales o "
              f"guion más corto en la próxima grabación.")


if __name__ == "__main__":
    main()
