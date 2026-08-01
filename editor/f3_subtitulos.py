"""
Fase 2 — Subtítulos .ass estilo agencia (karaoke palabra por palabra).

Toma el JSON de palabras (ya con timestamps recalculados por f2_cortar.py)
y genera un archivo .ass listo para quemar con ffmpeg.

Uso:
    python f3_subtitulos.py "video_cortado.json" [--salida subs.ass]
    ffmpeg -i video_cortado.mp4 -vf "ass=subs.ass" -c:a copy video_final.mp4
"""
import argparse
import json
import re
from pathlib import Path

import config

CABECERA_ASS = """[Script Info]
Title: Subtitulos DeviceShop
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: {ancho}
PlayResY: {alto}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{fuente},{tamano},{color_primario},{color_resaltado},{color_contorno},{backcolour},-1,0,0,0,100,100,0,0,{borderstyle},{outline_w},{shadow},2,60,60,{margen_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _tiempo_ass(segundos: float) -> str:
    cs = round(segundos * 100)
    h, resto = divmod(cs, 360000)
    m, resto = divmod(resto, 6000)
    s, cs = divmod(resto, 100)
    return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"


def _limpiar_para_oracion(texto: str, es_primera_palabra_video: bool) -> str:
    """Capitalización tipo oración (NO mayúsculas) — firma visual de la agencia.

    WhisperX ya transcribe con capitalización de oración correcta (mayúscula solo
    tras punto/interrogación/exclamación y en nombres propios) — no hay que tocar
    nada, salvo asegurar que la primera palabra de todo el video empiece en
    mayúscula. Forzar mayúscula al inicio de cada BLOQUE visual (2-4 palabras)
    está mal: la mayoría de los bloques empiezan a mitad de oración."""
    texto = texto.strip()
    if not texto:
        return texto
    if es_primera_palabra_video and texto[0].islower():
        return texto[0].upper() + texto[1:]
    return texto


def agrupar_en_bloques(palabras: list, minimo: int = None, maximo: int = None) -> list:
    """Agrupa palabras en bloques de `minimo`-`maximo`, respetando pausas como límite natural.

    Sin argumentos, es el bloque corto de siempre (config.SUB_PALABRAS_POR_BLOQUE_*).
    `minimo=maximo=1` da un bloque por palabra sin caso especial: la condición
    `len(bloque_actual) >= maximo` ya cierra en cada palabra.
    """
    bloques = []
    bloque_actual = []
    maximo = maximo if maximo is not None else config.SUB_PALABRAS_POR_BLOQUE_MAX
    minimo = minimo if minimo is not None else config.SUB_PALABRAS_POR_BLOQUE_MIN

    for i, p in enumerate(palabras):
        bloque_actual.append(p)
        es_ultima = i == len(palabras) - 1
        pausa_siguiente = (palabras[i + 1]["inicio"] - p["fin"]) if not es_ultima else 999

        debe_cerrar = (
            len(bloque_actual) >= maximo
            or es_ultima
            or (len(bloque_actual) >= minimo and pausa_siguiente > 0.35)
            or re.search(r"[.!?]$", p["texto"])
        )
        if debe_cerrar:
            bloques.append(bloque_actual)
            bloque_actual = []

    if bloque_actual:
        bloques.append(bloque_actual)
    return bloques


# Cuántas palabras entran en un bloque según la agrupación del estilo (config.SUB_ESTILOS).
AGRUPACION_BOUNDS = {
    "palabra": (1, 1),
    "bloque_corto": (config.SUB_PALABRAS_POR_BLOQUE_MIN, config.SUB_PALABRAS_POR_BLOQUE_MAX),
    "bloque_largo": (3, 6),
}


def _texto_palabra(p: dict, correcciones: dict, indice_de: dict, primera_palabra_global,
                    mayusculas: bool = False) -> str:
    texto_crudo = correcciones.get(str(indice_de[id(p)]), p["texto"])
    texto = _limpiar_para_oracion(texto_crudo, es_primera_palabra_video=(p is primera_palabra_global))
    return texto.upper() if mayusculas else texto


def _palabra_clave(bloque: list) -> int:
    """Índice, dentro del bloque, de la palabra de más impacto para "Palabra clave fija".

    Heurística simple de v1 (sin NLP): la palabra más larga: en textos de venta
    hablados suele ser el sustantivo o el número que importa ("Colorsoft",
    "insomnio", "150 gramos"), no una muletilla corta. Empate → la primera.
    """
    return max(range(len(bloque)), key=lambda i: (len(bloque[i]["texto"]), -i))


def generar_ass(palabras: list, tamano_px: int = None, correcciones: dict = None,
                 estilo: str = None) -> str:
    """`correcciones` (Bloque 5, parte B): {indice_global_de_la_palabra: texto_corregido}.

    Cambia SOLO lo que se ve en el subtítulo — nunca `p["texto"]` ni los
    tiempos. Es a propósito: `palabras` es la MISMA lista que f13_guion.py usa
    para alinear el guion contra la transcripción (`test_align.py`), y
    Whisper suele escribir mal nombres de producto o precios ("Colorsoft",
    "Kindle", los Bs). Corregir la ortografía ahí serviría para lo que se ve,
    pero cambiaría también contra qué se compara cada beat del guion — dos
    problemas distintos que no conviene resolver con el mismo dato.

    `estilo` (Bloque 5b): clave de config.SUB_ESTILOS. Sin esto, "karaoke" —
    el de siempre, byte a byte igual a antes de que existieran los estilos.
    """
    correcciones = correcciones or {}
    preset = config.SUB_ESTILOS[estilo or config.SUB_ESTILO_DEFECTO]

    cabecera = CABECERA_ASS.format(
        ancho=config.ANCHO,
        alto=config.ALTO,
        fuente=config.SUB_FUENTE,
        tamano=tamano_px or config.SUB_TAMANO_PX,
        color_primario=preset.get("color_primario") or config.SUB_COLOR_TEXTO,
        color_resaltado=config.SUB_COLOR_RESALTADO,
        color_contorno=preset.get("outline_color") or config.SUB_COLOR_CONTORNO,
        backcolour=preset.get("backcolour") or "&H00000000",
        borderstyle=preset.get("borderstyle", 1),
        outline_w=preset.get("outline_w", 3),
        shadow=preset.get("shadow", 0),
        margen_v=int((1 - config.SUB_POSICION_ALTURA_PCT) * config.ALTO) - 40,
    )

    # Índice GLOBAL de cada palabra (posición en la transcripción completa,
    # no dentro de su bloque). Es la clave estable que usa el editor
    # para identificar "la palabra número 14", igual antes y después de
    # agruparlas en bloques.
    indice_de = {id(p): i for i, p in enumerate(palabras)}

    minimo, maximo = AGRUPACION_BOUNDS[preset["agrupacion"]]
    bloques = agrupar_en_bloques(palabras, minimo=minimo, maximo=maximo)
    lineas = []
    primera_palabra_global = palabras[0] if palabras else None
    mayusculas = preset.get("mayusculas", False)

    for bloque in bloques:
        inicio_bloque = bloque[0]["inicio"]
        fin_bloque = bloque[-1]["fin"]

        if preset["resaltado"] in ("dinamico", "subrayado", "foco"):
            # Un evento por cada palabra activa dentro del bloque: "dinamico"
            # (karaoke) la resalta cambiando de color; "subrayado" la subraya
            # con \u1 nativo de ASS (no hace falta medir el ancho de la
            # palabra, al revés de dibujar una caja a mano debajo); "foco"
            # además la agranda con \fscx/\fscy — hay que devolverla a 100%
            # en el cierre, si no el escalado se le queda pegado al resto de
            # la línea (los tags de override valen desde ahí en adelante).
            for idx_activa, palabra_activa in enumerate(bloque):
                inicio_evento = palabra_activa["inicio"]
                fin_evento = bloque[idx_activa + 1]["inicio"] if idx_activa + 1 < len(bloque) else fin_bloque

                partes_texto = []
                for j, p in enumerate(bloque):
                    texto = _texto_palabra(p, correcciones, indice_de, primera_palabra_global,
                                            mayusculas=mayusculas)
                    if j == idx_activa and preset["resaltado"] == "dinamico":
                        partes_texto.append(f"{{\\c{config.SUB_COLOR_RESALTADO}}}{texto}{{\\c{config.SUB_COLOR_TEXTO}}}")
                    elif j == idx_activa and preset["resaltado"] == "subrayado":
                        partes_texto.append(f"{{\\u1\\c{config.SUB_COLOR_RESALTADO}}}{texto}{{\\u0\\c{config.SUB_COLOR_TEXTO}}}")
                    elif j == idx_activa:
                        partes_texto.append(
                            f"{{\\c{config.SUB_COLOR_FOCO}\\fscx145\\fscy145}}{texto}{{\\c{config.SUB_COLOR_TEXTO}\\fscx100\\fscy100}}")
                    else:
                        partes_texto.append(texto)
                texto_linea = " ".join(partes_texto)

                lineas.append(
                    f"Dialogue: 0,{_tiempo_ass(inicio_evento)},{_tiempo_ass(fin_evento)},Default,,0,0,0,,{texto_linea}"
                )
        else:
            # Un solo evento para todo el bloque: nada de resaltado temporal.
            idx_clave = _palabra_clave(bloque) if preset["resaltado"] == "estatico" else -1
            partes_texto = []
            for j, p in enumerate(bloque):
                texto = _texto_palabra(p, correcciones, indice_de, primera_palabra_global,
                                        mayusculas=mayusculas)
                if j == idx_clave:
                    partes_texto.append(f"{{\\c{config.SUB_COLOR_KEYWORD}}}{texto}{{\\c{config.SUB_COLOR_TEXTO}}}")
                else:
                    partes_texto.append(texto)
            texto_linea = " ".join(partes_texto)
            if preset["animacion"] == "pop":
                texto_linea = "{\\fscx55\\fscy55\\t(0,120,\\fscx100\\fscy100)}" + texto_linea
            elif preset["animacion"] == "glow":
                texto_linea = "{\\blur2}" + texto_linea
            elif preset["animacion"] == "shake":
                texto_linea = "{\\t(0,60,\\frz-3)\\t(60,120,\\frz3)\\t(120,180,\\frz-1)\\t(180,240,\\frz0)}" + texto_linea

            lineas.append(
                f"Dialogue: 0,{_tiempo_ass(inicio_bloque)},{_tiempo_ass(fin_bloque)},Default,,0,0,0,,{texto_linea}"
            )

    return cabecera + "\n".join(lineas) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Genera subtitulos .ass karaoke estilo agencia")
    parser.add_argument("transcripcion", type=str)
    parser.add_argument("--salida", type=str, default=None)
    parser.add_argument("--tamano", type=int, default=None, metavar="PX",
                        help="Tamaño del subtítulo en píxeles (Bloque 5). Sin esto, config.SUB_TAMANO_PX")
    parser.add_argument("--correcciones", type=str, default=None, metavar="JSON",
                        help="{'correcciones': {'14': 'Colorsoft'}} — corrige SOLO lo que se ve, "
                             "no toca los tiempos ni la alineación del guion")
    parser.add_argument("--estilo", type=str, default=None, choices=list(config.SUB_ESTILOS),
                        help="Estilo visual del subtítulo (Bloque 5b), elegido en el editor visual. "
                             "Sin esto, config.SUB_ESTILO_DEFECTO ('karaoke', el de siempre)")
    args = parser.parse_args()

    ruta_transcripcion = Path(args.transcripcion)
    datos = json.loads(ruta_transcripcion.read_text(encoding="utf-8"))
    palabras = datos["palabras"]

    correcciones = {}
    if args.correcciones and Path(args.correcciones).exists():
        datos_correcciones = json.loads(Path(args.correcciones).read_text(encoding="utf-8"))
        correcciones = datos_correcciones.get("correcciones", datos_correcciones)

    ruta_salida = Path(args.salida) if args.salida else ruta_transcripcion.with_suffix(".ass")
    contenido = generar_ass(palabras, tamano_px=args.tamano, correcciones=correcciones, estilo=args.estilo)
    ruta_salida.write_text(contenido, encoding="utf-8-sig")
    estilo_id = args.estilo or config.SUB_ESTILO_DEFECTO
    minimo, maximo = AGRUPACION_BOUNDS[config.SUB_ESTILOS[estilo_id]["agrupacion"]]
    n_bloques = len(agrupar_en_bloques(palabras, minimo=minimo, maximo=maximo))
    print(f"Subtitulos ASS generados: {ruta_salida}")
    print(f"  estilo '{estilo_id}' · {n_bloques} bloques de {minimo}-{maximo} palabras"
          + (f" · {len(correcciones)} palabra(s) corregida(s)" if correcciones else ""))


if __name__ == "__main__":
    main()
