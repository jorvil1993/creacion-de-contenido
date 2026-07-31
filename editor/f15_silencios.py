"""
Editor de silencios — ver y deshacer lo que recortó f2_cortar.py.

f2_cortar recorta silencios, muletillas y tomas repetidas sin dejar rastro
visible: el video sale ya cortado y no hay forma de saber qué se fue ni de
recuperarlo. Este módulo hace visible ese corte y permite deshacerlo tramo a
tramo.

## Por qué restaurar obliga a re-cortar desde la grabación original

El metraje de un tramo recortado NO ESTÁ en 02_cortado.mp4: ffmpeg lo descartó
al concatenar los intervalos conservados. Medido sobre Guion-7: la grabación
dura 39.914s y el cortado 24.834s. Los 7.6s de silencio inicial no están en
ninguna parte de ese archivo, así que no hay ningún ajuste de coordenadas que
los pueda traer de vuelta. Restaurar = volver a cortar la grabación original
con una lista de cortes distinta. No hay atajo.

Lo que sí se evita es re-transcribir: 01_transcripcion.json conserva las
palabras, los segmentos y los silencios de la grabación ENTERA, y nada de eso
cambia al mover un corte. WhisperX (large-v3, la parte cara del pipeline) no
vuelve a correr. Se rehace el corte (ffmpeg, segundos) y lo que depende de él.

## Cómo sobreviven los ajustes ya hechos

Los ajustes.*.json guardan segundos de la línea de tiempo CORTADA, que es justo
la que cambia. Se remapean componiendo dos funciones de f2_cortar:

    tiempo_viejo --mapear_a_original(intervalos_viejos)--> grabación original
                 --mapear_a_nueva_linea(intervalos_nuevos)--> tiempo_nuevo

La grabación original es el único sistema de coordenadas que no se mueve. La
ida y vuelta es exacta (verificado sobre Guion-7 con paso de 10 ms: error
máximo 0.000 ms).

Los eventos con duración conservan su DURACIÓN, no su instante final: un B-roll
de 1.85s sigue durando 1.85s aunque en medio se haya restaurado un silencio de
7.6s. Estirarlo hasta el nuevo final sería convertir un inserto en un plano
fijo de nueve segundos. Cuando eso pasa —cuando el evento cruzaba el tramo
restaurado— se emite un AVISO en vez de decidir en silencio: el editor lo pinta
y José revisa ese evento a mano.
"""
import json
import sys
from pathlib import Path

import config
import f2_cortar

# Un ajuste que cruza un tramo restaurado cambia de duración al remapearse. Por
# debajo de esto es redondeo (los intervalos van a milésimas y ffmpeg cuadra al
# fotograma); por encima, el evento de verdad abarcaba metraje que antes no
# existía y hay que avisar.
UMBRAL_AVISO_S = 0.05

# Qué remapear de cada archivo de ajustes: (clave de la lista, campo de inicio,
# campo de fin). Clave None = el JSON es la lista directa. Campo de fin None =
# el evento es un instante, no un tramo.
#
# Deliberadamente FUERA de esta tabla:
#   - ajustes.musica.json  -> su `inicio_s` es un desplazamiento DENTRO de la
#     pista de música, no un segundo del video. Remapearlo cambiaría por qué
#     compás entra la canción cada vez que se toca un silencio.
#   - ajustes.hook.json, ajustes.subtitulos.json -> texto y tamaño, sin tiempos.
CAMPOS_TIEMPO = {
    "ajustes.eventos.json": [("eventos", "ini", "fin")],
    "ajustes.broll.json": [("broll", "ini", "fin")],
    "ajustes.hookcta.json": [("hook_cta", "ini", "fin")],
    "ajustes.sfx.json": [(None, "t", None)],
    "ajustes.animaciones.json": [("animaciones", "ini", None)],
    "ajustes.encuadre.json": [("punch_ins", "t", None),
                              ("planos_cerrados", "ini", "fin")],
    "ajustes.sesion.json": [(None, "t", None)],
}

NOMBRE_AJUSTES = "ajustes.silencios.json"


# --------------------------------------------------------------------------
# Identidad de un tramo
# --------------------------------------------------------------------------

def tipo_de_corte(razon: str) -> str:
    """Clasifica un corte por su razón, para agrupar y para el identificador."""
    r = (razon or "").lower()
    if r.startswith("silencio"):
        return "silencio"
    if r.startswith("muletilla"):
        return "muletilla"
    if r.startswith("conector"):
        return "conector"
    if r.startswith("toma repetida"):
        return "toma-repetida"
    return "otro"


def id_de_corte(corte: dict) -> str:
    """Identificador estable de un tramo, a prueba de re-cortes.

    Cuelga del SILENCIO de origen (`limite_inicio`), no del corte que se
    calculó a partir de él, y en coordenadas de la grabación original.

    La diferencia importa y costó una prueba de punta a punta descubrirla: el
    corte del silencio inicial depende de `hooksegs` del panel. Con hooksegs=0
    va de 0.15s a 7.75s; con hooksegs=3 va de 0.00s a 4.90s. Colgando el id del
    corte, cambiar ese campo en el panel dejaba el ajuste guardado apuntando a
    un tramo inexistente y el silencio restaurado volvía a cortarse EN
    SILENCIO. El silencio de origen, en cambio, empieza en 0.000s pase lo que
    pase: sale de la transcripción, que no depende de ningún parámetro.

    Para las muletillas y las tomas repetidas no hay silencio de origen y el
    tramo ES la palabra o la frase, que ya es estable por sí misma.
    """
    base = corte.get("limite_inicio")
    if base is None:
        base = corte.get("inicio_detectado", corte["inicio"])
    return f"{tipo_de_corte(corte.get('razon', ''))}-{base:.3f}"


# --------------------------------------------------------------------------
# Estado guardado
# --------------------------------------------------------------------------

def _leer_json(ruta: Path):
    """Lee un JSON tolerando el BOM que ponen las herramientas de Windows.

    `utf-8` a secas revienta con un archivo que empieza por BOM, y el BOM lo
    pone cualquier cosa: el Bloc de notas, `Out-File` de PowerShell, medio
    Windows. Se descubrió porque un `ajustes.silencios.json` con BOM se leía
    como vacío y el re-corte se saltaba EN SILENCIO: el render salía, con la
    duración de siempre, y la elección de José desaparecía sin un solo mensaje.
    `utf-8-sig` se come el BOM si está y se comporta como `utf-8` si no.

    Devuelve None si el archivo es ilegible de verdad, para que quien llame
    pueda distinguir "no hay nada elegido" de "hay algo y no se pudo leer" —
    dos situaciones que exigen respuestas distintas.
    """
    try:
        return json.loads(ruta.read_text(encoding="utf-8-sig"))
    except Exception as e:
        print(f"AVISO: no se pudo leer {ruta.name}: {e}", file=sys.stderr)
        return None


def leer_ajustes(dir_trabajo) -> dict:
    """El estado del editor de silencios. Ausente = todo automático."""
    f = Path(dir_trabajo) / NOMBRE_AJUSTES
    if not f.exists():
        return {"cortes": {}}
    datos = _leer_json(f)
    if not isinstance(datos, dict):
        return {"cortes": {}}
    datos.setdefault("cortes", {})
    return datos


def hay_cambios(dir_trabajo) -> bool:
    """¿El estado guardado pide algo distinto del corte automático?"""
    for estado in leer_ajustes(dir_trabajo).get("cortes", {}).values():
        if not isinstance(estado, dict):
            continue
        if estado.get("activo") is False:
            return True
        if estado.get("inicio") is not None or estado.get("fin") is not None:
            return True
    return False


def aplicar_seleccion(cortes: list, ruta_ajustes) -> tuple:
    """Filtra y ajusta la lista de cortes detectados según lo elegido a mano.

    Devuelve (cortes_a_aplicar, cortes_descartados). Un tramo desactivado sale
    de la lista: el silencio vuelve al video. Un tramo con límites propios se
    corta más corto, dejando más aire a los lados.
    """
    ruta = Path(ruta_ajustes)
    if not ruta.exists():
        return list(cortes), []
    datos = _leer_json(ruta)
    if datos is None:
        # Se pidió un archivo de selección y no se pudo leer. Cortar como
        # siempre es lo seguro, pero callarlo no: el video saldría con la
        # duración de antes y nadie sabría por qué se ignoró lo elegido.
        print(f"AVISO: se ignora {ruta.name} y se corta como siempre. "
              f"Revisá ese archivo: lo elegido en el editor NO se ha aplicado.",
              file=sys.stderr)
        return list(cortes), []
    estados = (datos or {}).get("cortes", {}) or {}

    aplicar, descartados = [], []
    for corte in cortes:
        estado = estados.get(id_de_corte(corte))
        if not isinstance(estado, dict):
            aplicar.append(corte)
            continue
        if estado.get("activo") is False:
            descartados.append(corte)
            continue
        nuevo = dict(corte)
        # Los límites que puede pedir el editor no pueden pasarse del tramo que
        # el detector encontró: recortar MÁS de lo automático es cortar habla,
        # y este bloque existe para lo contrario.
        tope_ini = corte.get("limite_inicio", corte["inicio"])
        tope_fin = corte.get("limite_fin", corte["fin"])
        if estado.get("inicio") is not None:
            nuevo["inicio"] = round(max(tope_ini, float(estado["inicio"])), 3)
        if estado.get("fin") is not None:
            nuevo["fin"] = round(min(tope_fin, float(estado["fin"])), 3)
        if nuevo["fin"] - nuevo["inicio"] <= 0.01:
            descartados.append(corte)   # lo encogieron hasta desaparecer
            continue
        aplicar.append(nuevo)
    return aplicar, descartados


# --------------------------------------------------------------------------
# Catálogo de tramos
# --------------------------------------------------------------------------

def _parametros_corte(dir_trabajo) -> dict:
    """Con qué se cortó esta corrida. Las corridas viejas no lo guardan."""
    f = Path(dir_trabajo) / "02_cortado.json"
    if not f.exists():
        return {}
    datos = _leer_json(f)
    return (datos or {}).get("corte_parametros", {}) or {}


def catalogo(dir_trabajo) -> dict:
    """Todos los tramos que el corte automático detecta, con su estado actual.

    Se recalcula desde 01_transcripcion.json en vez de leerse de
    02_cortado.json, y esa es la diferencia que hace que el bloque funcione más
    de una vez: `cortes_aplicados` solo contiene los que se aplicaron, así que
    al restaurar uno desaparecería de la lista y no habría forma de volver a
    cortarlo. La transcripción, en cambio, no cambia nunca.
    """
    dir_trabajo = Path(dir_trabajo)
    f_transcripcion = dir_trabajo / "01_transcripcion.json"
    f_cortado = dir_trabajo / "02_cortado.json"
    if not f_transcripcion.exists() or not f_cortado.exists():
        return {"disponible": False, "motivo": "faltan 01_transcripcion.json o 02_cortado.json",
                "tramos": [], "fuente": None, "fuente_existe": False}

    datos_t = _leer_json(f_transcripcion) or {}
    datos_c = _leer_json(f_cortado) or {}
    params = datos_c.get("corte_parametros", {}) or {}

    fuente = params.get("fuente_corte") or datos_t.get("fuente")
    ruta_fuente = Path(fuente) if fuente else None
    fuente_existe = bool(ruta_fuente and ruta_fuente.exists())

    intervalos = datos_c.get("intervalos_conservados_original", [])
    duracion_original = params.get("duracion_original_s")
    if not duracion_original:
        # Corrida anterior a `corte_parametros`: el final del último intervalo
        # conservado es el mejor límite conocido de la grabación.
        duracion_original = intervalos[-1]["fin"] if intervalos else 0.0

    # El perfil manda en el umbral de silencio y en las muletillas. Fijarlo
    # antes de detectar: con el perfil equivocado el catálogo mostraría tramos
    # que no son los que se cortaron. Una clave desconocida (una corrida vieja
    # que guardó el nombre para mostrar en vez de la clave) cae al perfil por
    # defecto: enseñar el catálogo aproximado es mejor que dejar el panel roto.
    try:
        f2_cortar.PERFIL = config.perfil(params.get("presentador"))
    except ValueError:
        f2_cortar.PERFIL = config.perfil()
    detectados, _, _ = f2_cortar.detectar_todos_los_cortes(
        datos_t, float(duracion_original),
        float(params.get("conservar_inicio_s") or 0.0),
        float(params.get("conservar_fin_s") or 0.0))

    estados = leer_ajustes(dir_trabajo).get("cortes", {})
    aplicados = datos_c.get("cortes_aplicados", [])

    tramos = []
    for corte in sorted(detectados, key=lambda c: c["inicio"]):
        cid = id_de_corte(corte)
        estado = estados.get(cid) if isinstance(estados.get(cid), dict) else {}
        activo = estado.get("activo") is not False
        ini = corte["inicio"] if estado.get("inicio") is None else float(estado["inicio"])
        fin = corte["fin"] if estado.get("fin") is None else float(estado["fin"])
        tipo = tipo_de_corte(corte.get("razon", ""))
        tramos.append({
            "id": cid,
            "tipo": tipo,
            "razon": corte.get("razon", ""),
            "activo": activo,
            # Coordenadas de la GRABACIÓN ORIGINAL: es lo que no se mueve.
            "inicio": round(ini, 3),
            "fin": round(fin, 3),
            "duracion": round(fin - ini, 3),
            "inicio_detectado": round(corte["inicio"], 3),
            "fin_detectado": round(corte["fin"], 3),
            # Hasta dónde pueden llegar los tiradores: el silencio entero.
            # Solo los silencios se pueden estrechar; una muletilla o una toma
            # repetida se corta o no se corta, no tiene sentido cortar media.
            "limite_inicio": round(corte.get("limite_inicio", corte["inicio"]), 3),
            "limite_fin": round(corte.get("limite_fin", corte["fin"]), 3),
            "ajustable": tipo == "silencio",
            # Dónde cae la costura en el video que se está viendo ahora mismo.
            # Solo tiene sentido para un tramo que está cortado: si está
            # restaurado, el tramo se ve entero y no hay costura.
            "t_en_video": f2_cortar.mapear_a_nueva_linea(corte["inicio"], intervalos)
            if intervalos else 0.0,
            "estaba_aplicado": any(abs(a["inicio"] - corte["inicio"]) < 0.02
                                   for a in aplicados),
        })

    return {
        "disponible": True,
        "tramos": tramos,
        "fuente": str(ruta_fuente) if ruta_fuente else None,
        "fuente_existe": fuente_existe,
        "duracion_original_s": round(float(duracion_original), 3),
        "duracion_actual_s": datos_c.get("duracion_resultante_s"),
        "parametros": params,
        # Los tramos que de verdad sobrevivieron en el 02_cortado.mp4 que se
        # está viendo. NO es lo mismo que "los tramos no activos del catálogo":
        # al destildar un silencio en el panel, el catálogo cambia al instante
        # pero el video en pantalla sigue siendo el de antes hasta re-renderizar.
        # La aguja tiene que mapear con lo que el archivo tiene, no con lo que
        # se acaba de pedir, o señalaría un punto de la grabación que no se
        # corresponde con el fotograma que se está viendo.
        "intervalos_conservados": intervalos,
    }


def datos_silencios(dir_trabajo) -> dict:
    """Lo que consume el editor visual por /datos."""
    cat = catalogo(dir_trabajo)
    if not cat.get("disponible"):
        return cat

    activos = [t for t in cat["tramos"] if t["activo"]]
    restaurados = [t for t in cat["tramos"] if not t["activo"]]
    cat["resumen"] = {
        "total": len(cat["tramos"]),
        "cortados": len(activos),
        "restaurados": len(restaurados),
        "segundos_cortados": round(sum(t["duracion"] for t in activos), 2),
        "segundos_restaurados": round(sum(t["duracion"] for t in restaurados), 2),
    }
    cat["pendiente_de_render"] = hay_cambios(dir_trabajo) and not _corte_al_dia(dir_trabajo)
    cat["umbral_aviso_s"] = UMBRAL_AVISO_S
    # Los avisos del último re-corte. El remapeo ocurre durante el render, con
    # el editor cerrado: si no viajaran por aquí, el único rastro de que un
    # evento cambió de duración sería una línea en una consola que ya se cerró.
    cat["avisos_remapeo"] = leer_avisos(dir_trabajo)

    # Elecciones guardadas que ya no corresponden a ningún tramo del catálogo.
    # Pasa si cambian los parámetros del corte (otro `hooksegs` en el panel,
    # otro presentador) o si se re-transcribe la grabación. Sin este aviso, la
    # elección simplemente dejaría de aplicarse y nadie sabría por qué el
    # silencio que había devuelto al video volvió a desaparecer.
    ids = {t["id"] for t in cat["tramos"]}
    cat["huerfanos"] = sorted(set(leer_ajustes(dir_trabajo).get("cortes", {})) - ids)
    return cat


def _corte_al_dia(dir_trabajo) -> bool:
    """¿El 02_cortado.mp4 en disco ya refleja lo elegido en el editor?"""
    dir_trabajo = Path(dir_trabajo)
    f = dir_trabajo / "02_cortado.json"
    if not f.exists():
        return False
    try:
        aplicados = (_leer_json(f) or {}).get("cortes_aplicados", [])
    except Exception:
        return False
    esperados = [t for t in catalogo(dir_trabajo)["tramos"] if t["activo"]]
    if len(aplicados) != len(esperados):
        return False
    por_inicio = sorted(round(a["inicio"], 2) for a in aplicados)
    esperado_inicio = sorted(round(t["inicio"], 2) for t in esperados)
    return por_inicio == esperado_inicio


# --------------------------------------------------------------------------
# Remapeo de los ajustes ya hechos
# --------------------------------------------------------------------------

def remapear_tiempo(t: float, intervalos_viejos: list, intervalos_nuevos: list) -> float:
    """Un segundo de la línea de tiempo vieja a la nueva, vía la grabación."""
    return f2_cortar.mapear_a_nueva_linea(
        f2_cortar.mapear_a_original(t, intervalos_viejos), intervalos_nuevos)


def remapear_ajustes(dir_trabajo, intervalos_viejos: list, intervalos_nuevos: list,
                     escribir: bool = True) -> dict:
    """Lleva todos los ajustes.*.json de la línea vieja a la nueva.

    Devuelve {"cambiados": [...], "avisos": [...]}. Los avisos son los casos que
    NO se pueden remapear con certeza: eventos que cruzaban un tramo restaurado
    y que, de respetarse su instante final, pasarían a durar varios segundos de
    más. Se conserva la duración y se avisa; el editor los pinta para que José
    los revise en vez de que el cambio pase inadvertido.
    """
    dir_trabajo = Path(dir_trabajo)
    dur_nueva = sum(iv["fin"] - iv["inicio"] for iv in intervalos_nuevos)
    cambiados, avisos = [], []

    for nombre, listas in CAMPOS_TIEMPO.items():
        f = dir_trabajo / nombre
        if not f.exists():
            continue
        try:
            datos = _leer_json(f)
        except Exception:
            avisos.append({"archivo": nombre, "tipo": "ilegible",
                           "detalle": "no se pudo leer; se deja como está"})
            continue

        tocado = False
        for clave, campo_ini, campo_fin in listas:
            if clave is None:
                items = datos if isinstance(datos, list) else [datos]
            else:
                items = datos.get(clave) if isinstance(datos, dict) else None
                if not isinstance(items, list):
                    continue

            for item in items:
                if not isinstance(item, dict) or item.get(campo_ini) is None:
                    continue
                viejo_ini = float(item[campo_ini])
                nuevo_ini = remapear_tiempo(viejo_ini, intervalos_viejos, intervalos_nuevos)

                if campo_fin and item.get(campo_fin) is not None:
                    viejo_fin = float(item[campo_fin])
                    duracion = viejo_fin - viejo_ini
                    directo = remapear_tiempo(viejo_fin, intervalos_viejos, intervalos_nuevos)
                    nuevo_fin = round(nuevo_ini + duracion, 3)
                    if abs(directo - nuevo_fin) > UMBRAL_AVISO_S:
                        avisos.append({
                            "archivo": nombre, "lista": clave, "tipo": "cruza-tramo",
                            "ini_viejo": round(viejo_ini, 3), "fin_viejo": round(viejo_fin, 3),
                            "ini_nuevo": nuevo_ini, "fin_nuevo": nuevo_fin,
                            "fin_si_se_estirara": directo,
                            "etiqueta": (item.get("tipo") or item.get("nombre")
                                         or item.get("asset") or item.get("razon") or ""),
                            "detalle": (f"abarcaba un tramo que cambió: se conserva su "
                                        f"duración de {duracion:.2f}s en vez de estirarlo "
                                        f"hasta {directo:.2f}s"),
                        })
                    if nuevo_fin > dur_nueva:
                        avisos.append({
                            "archivo": nombre, "lista": clave, "tipo": "fuera-de-rango",
                            "ini_nuevo": nuevo_ini, "fin_nuevo": nuevo_fin,
                            "etiqueta": (item.get("tipo") or item.get("nombre")
                                         or item.get("asset") or ""),
                            "detalle": (f"termina en {nuevo_fin:.2f}s, más allá del final "
                                        f"del video ({dur_nueva:.2f}s); se acorta"),
                        })
                        nuevo_fin = round(dur_nueva, 3)
                    if item[campo_fin] != nuevo_fin:
                        item[campo_fin] = nuevo_fin
                        tocado = True

                if item[campo_ini] != nuevo_ini:
                    item[campo_ini] = nuevo_ini
                    tocado = True

        if tocado:
            cambiados.append(nombre)
            if escribir:
                # Copia de respaldo antes de pisar: un remapeo mal calculado con
                # los ajustes ya sobrescritos no se podría deshacer, y son horas
                # de trabajo manual de José.
                respaldo = f.with_suffix(f.suffix + ".previo")
                respaldo.write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
                tmp = f.with_suffix(f.suffix + ".tmp")
                tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=2),
                               encoding="utf-8")
                tmp.replace(f)

    return {"cambiados": cambiados, "avisos": avisos}


def guardar_avisos(dir_trabajo, avisos: list) -> Path:
    """Deja los avisos del último remapeo para que el editor los enseñe.

    El remapeo ocurre durante el render, con el editor cerrado o en otra
    pestaña; sin dejarlos escritos, los avisos se los llevaría la consola y
    nadie se enteraría de que un evento cambió de duración.
    """
    f = Path(dir_trabajo) / "ajustes.silencios.avisos.json"
    f.write_text(json.dumps({"avisos": avisos}, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    return f


def leer_avisos(dir_trabajo) -> list:
    f = Path(dir_trabajo) / "ajustes.silencios.avisos.json"
    if not f.exists():
        return []
    try:
        return (_leer_json(f) or {}).get("avisos", [])
    except Exception:
        return []
