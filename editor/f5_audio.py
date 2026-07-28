"""
Fase 4 — Audio.

Mezcla la voz de José (dominante) con música de fondo (ducking automático
por sidechain) y SFX en punch-ins/hook, y normaliza todo al final.

Usa los assets reales entregados por la sesión B en assets/musica/ y
assets/sfx/ (ver los README.md de esas carpetas). Si algún archivo
esperado no existe, la mezcla continúa sin esa capa y lo deja anotado en
consola — nunca debe ser motivo de que el pipeline se detenga.

Uso:
    python f5_audio.py "video_retencion.mp4" "video_retencion.plan.json" [--salida salida.mp4] [--sin-musica]
"""
import argparse
import json
import math
import subprocess
import sys
from pathlib import Path

import config


def _log(msg):
    print(msg, flush=True)


def _duracion_video(ruta: Path) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(ruta)]
    salida = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(salida.stdout.strip())


def _ruta_sfx(nombre_archivo: str) -> Path | None:
    ruta = config.DIR_ASSETS / "sfx" / nombre_archivo
    return ruta if ruta.exists() else None


def _niveles_sfx() -> dict:
    """Pico real de cada SFX en dB, medido una vez y cacheado.

    Los archivos del pack vienen con niveles descontrolados entre sí: medido el
    2026-07-26 hay 20 dB de diferencia entre `notificacion_1` (-38.5 dB medio) y
    `impacto_hit` (-18.7 dB). Aplicarles el mismo multiplicador `volume=` es
    inútil — justamente `pop.mp3`, el de aparición de producto, es de los más
    silenciosos del pack. Por eso subir los volúmenes de 0.30 a 0.65 no cambió
    nada medible: el problema no era el multiplicador, era el material.

    Con esto cada sonido se lleva primero a un pico común y recién después se
    le aplica el volumen artístico de config.SFX_POR_EVENTO.
    """
    dir_sfx = config.DIR_ASSETS / "sfx"
    cache = dir_sfx / "_niveles.json"
    datos = {}
    if cache.exists():
        try:
            datos = json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            datos = {}

    faltantes = [p for p in dir_sfx.glob("*.mp3") if p.name not in datos]
    for p in faltantes:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(p), "-af", "volumedetect",
                            "-f", "null", "-"], capture_output=True, text=True)
        pico = None
        for linea in (r.stderr or "").splitlines():
            if "max_volume:" in linea:
                try:
                    pico = float(linea.split("max_volume:")[1].replace("dB", "").strip())
                except ValueError:
                    pass
        datos[p.name] = pico if pico is not None else 0.0

    if faltantes:
        try:
            cache.write_text(json.dumps(datos, indent=2), encoding="utf-8")
        except Exception:
            pass
    return datos


def _alineacion_sfx() -> dict:
    """Dónde golpea cada sonido dentro de su propio archivo.

    No todos los efectos golpean en el primer frame. Medido sobre el pack
    (assets/sfx/_alineacion.json, campo `punto`):

    - `impacto_hit.mp3` golpea a los 0.00s  -> golpe
    - `whoosh_swoosh.mp3` llega a su cresta a los 0.49s -> swell
    - `riser_1.mp3` revienta a los 2.38s    -> build

    Colocar los tres con `adelay` al segundo del evento visual solo acierta con
    el primero: el whoosh sube DESPUÉS del corte y el riser revienta dos segundos
    y medio tarde, que es lo mismo que no ponerlo. Por eso el archivo se coloca
    en `t - punto`, para que sea el GOLPE el que caiga sobre el evento.

    Si el JSON no está, todo vale 0.0 y el comportamiento es el de antes.
    """
    ruta = config.DIR_ASSETS / "sfx" / "_alineacion.json"
    if not ruta.exists():
        return {}
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except Exception:
        _log("AVISO: no se pudo leer _alineacion.json — los SFX se colocan por el inicio del archivo.")
        return {}


def _ruta_musica(nombre_archivo: str) -> Path | None:
    """Pista de assets/musica/ por nombre exacto o por prefijo.

    El prefijo existe porque los guiones del panel nombran la pista corta
    ("entra 02-lofi a -20 dB") y el archivo real es `02-lofi-brillante.mp3`.
    Sin esto, `--guion N` pasaba `02-lofi`, no resolvía, y el video salía
    SIN música con solo un aviso en el log.
    """
    dir_musica = config.DIR_ASSETS / "musica"
    ruta = dir_musica / nombre_archivo
    if ruta.exists():
        return ruta
    if not dir_musica.is_dir():
        return None
    candidatos = sorted(p for p in dir_musica.glob(f"{nombre_archivo}*")
                        if p.suffix.lower() in (".mp3", ".wav", ".m4a", ".ogg"))
    return candidatos[0] if candidatos else None


def clave_ancla(ev: dict, vistas: dict = None) -> str:
    """Identidad estable de un evento visual, para que su sonido lo siga.

    La regla editorial del pipeline es "el sonido acompaña un evento visual"
    (config.py:285). Hasta v1 esa regla solo valía al GENERAR: si después José
    arrastraba un PiP en el editor, su `pop` se quedaba en el segundo viejo y la
    regla se rompía en silencio. El ancla la mantiene también al editar.

    No se usa el tiempo como identidad — es justo lo que cambia al mover algo.
    Se usa qué es: el asset del PiP, el nombre y la variante de la animación, o
    el tipo cuando es único (hook, cta, specs). `vistas` lleva la cuenta de
    repeticiones para distinguir dos eventos por lo demás idénticos.
    """
    tipo = ev.get("tipo", "")
    if tipo.startswith("anim-"):
        base = f"{tipo}|v{ev.get('variante', '')}"
    elif tipo == "pip-producto":
        base = f"pip|{ev.get('asset') or ev.get('asset_id') or ''}"
    else:
        base = tipo
    if vistas is None:
        return base
    n = vistas.get(base, 0)
    vistas[base] = n + 1
    return f"{base}#{n}"


def reanclar_sfx(eventos_sfx: list, eventos_overlay: list) -> int:
    """Devuelve cada SFX anclado al segundo donde HOY está su evento visual.

    Se llama al cargar una lista manual: si José movió un PiP en el editor, su
    `pop` se mueve con él sin que tenga que arrastrar las dos cosas. Si borró el
    evento visual, el sonido se queda donde estaba y se avisa — borrarle el
    sonido por su cuenta sería decidir por él.
    """
    if not eventos_overlay:
        return 0
    vistas = {}
    posiciones = {clave_ancla(ev, vistas): float(ev["ini"]) for ev in eventos_overlay}

    movidos = 0
    for ev in eventos_sfx:
        ancla = ev.get("ancla")
        if not ancla:
            continue
        if ancla not in posiciones:
            _log(f"AVISO: el sonido de {ev['t']:.2f}s estaba anclado a '{ancla}', que ya no "
                 f"existe — se queda donde está.")
            continue
        nuevo = round(posiciones[ancla] + float(ev.get("desfase", 0.0)), 3)
        if abs(nuevo - float(ev["t"])) > 0.01:
            _log(f"  sonido reanclado: {ev['t']:.2f}s -> {nuevo:.2f}s (sigue a '{ancla}')")
            ev["t"] = nuevo
            movidos += 1
    if movidos:
        eventos_sfx.sort(key=lambda e: e["t"])
    return movidos


def avisos_sfx(eventos: list, duracion: float = None) -> list:
    """Problemas que el automático no resuelve solo y que José debe poder VER.

    No bloquean nada: el criterio del plan v2 es que lo automático es un primer
    borrador, no un veredicto. El editor los pinta en amarillo y él decide.
    """
    avisos = []
    ordenados = sorted(eventos, key=lambda e: e["t"])

    for a, b in zip(ordenados, ordenados[1:]):
        hueco = b["t"] - a["t"]
        if hueco < config.SFX_SEPARACION_MIN_S:
            avisos.append({
                "tipo": "separacion", "t": b["t"],
                "texto": f"{b['archivo']} cae a {hueco:.2f}s del anterior "
                         f"(mínimo recomendado {config.SFX_SEPARACION_MIN_S}s)",
            })

    # Tres veces el mismo sonido seguido se oye como un tic del editor, no como
    # una intención. Es el mismo problema de "uso sin discreción" que motivó
    # rediseñar los SFX por evento visual.
    seguidos, anterior = 0, None
    for e in ordenados:
        seguidos = seguidos + 1 if e["archivo"] == anterior else 1
        anterior = e["archivo"]
        if seguidos >= 3:
            avisos.append({
                "tipo": "repeticion", "t": e["t"],
                "texto": f"{e['archivo']} suena {seguidos} veces seguidas",
            })

    # Densidad global (bloque 3 del plan de mejoras): 12-15 SFX en 35s suena a
    # tic de editor, no a intención. El umbral es el mismo preset "normal" que
    # usa el tope automático, así el aviso y el tope hablan de lo mismo.
    if duracion:
        resumen = resumen_densidad(eventos, duracion)
        if resumen["cada_s"] is not None and resumen["cada_s"] < config.SFX_DENSIDAD_PRESETS["normal"]:
            avisos.append({
                "tipo": "densidad", "t": 0.0,
                "texto": f"{resumen['n']} efectos en {resumen['duracion']:.1f}s "
                         f"(uno cada {resumen['cada_s']:.1f}s) — más denso que lo recomendado "
                         f"(uno cada {config.SFX_DENSIDAD_PRESETS['normal']}s)",
            })
    return avisos


def resumen_densidad(eventos: list, duracion: float) -> dict:
    """Cuántos SFX hay y cada cuánto caen, para el contador del editor y la hoja
    de sonido. `cada_s` es None sin eventos, para no dividir por cero."""
    n = len(eventos)
    return {"n": n, "duracion": round(duracion, 2),
            "cada_s": round(duracion / n, 2) if n else None}


# Prioridad para el TOPE GLOBAL de densidad (`aplicar_tope_densidad`), distinta
# de la que usa `construir_eventos_sfx` para resolver colisiones ENTRE TIPOS al
# generar. Se indexa por la `razon` final del evento, que en los automáticos
# coincide con el tipo (hook/corte/punch-in/pip-producto/sticker/cta) y en los
# del guion es "guion_N" o "hook_fisico" (ver f13_guion.py).
PRIORIDAD_SFX_POR_RAZON = {
    "hook": 100, "hook_fisico": 100,
    "pip-producto": 90, "sticker": 90, "cta": 90,
    "corte": 50,
    "punch-in": 10,
}
# Un SFX colocado a mano en el panel del guion ("guion_N") es una decisión
# editorial explícita, no ruido automático — por eso pesa más que un corte o
# un punch-in genérico, aunque menos que un overlay o el hook.
PRIORIDAD_SFX_DEFECTO = 80


def aplicar_tope_densidad(eventos: list, separacion_s: float) -> list:
    """Cupo global de SFX: como máximo uno cada `separacion_s`, sin importar el
    tipo. Se aplica DESPUÉS de resolver colisiones por tipo/evento — hoy solo
    los punch-ins tenían un tope (`config.SFX_MAX_PUNCH_INS`); esto lo extiende
    a la lista completa, respetando prioridad (gana el más importante, no el
    primero en el tiempo).
    """
    def prioridad(ev):
        return PRIORIDAD_SFX_POR_RAZON.get(ev.get("razon", ""), PRIORIDAD_SFX_DEFECTO)

    ordenados = sorted(eventos, key=lambda e: (-prioridad(e), e["t"]))
    aceptados = []
    for ev in ordenados:
        if any(abs(ev["t"] - a["t"]) < separacion_s for a in aceptados):
            continue
        aceptados.append(ev)
    aceptados.sort(key=lambda e: e["t"])
    return aceptados


def construir_eventos_sfx(plan_retencion: dict, eventos_overlay: list = None) -> list:
    """SFX atados a EVENTOS VISUALES, no a picos de volumen de la voz.

    Antes: un whoosh idéntico en cada pico de energía RMS, o sea cada vez que
    José levantaba la voz. Criterio mecánico — correlaciona con el volumen del
    habla, no con que pase algo en pantalla. Resultado percibido: "uso sin
    discreción, donde quiera".

    Ahora se recolectan los eventos que el espectador VE (hook, aparición de
    overlays, cortes entre planos, punch-ins fuertes), se resuelven colisiones
    por prioridad y se asigna un sonido distinto según el tipo, rotando entre
    variantes.
    """
    candidatos = [{"t": 0.0, "tipo": "hook", "prioridad": 100, "ancla": "hook#0"}]

    # Overlays que aparecen en pantalla (PiP de producto, CTA, animaciones)
    vistas = {}
    for ev in (eventos_overlay or []):
        tipo = ev.get("tipo", "")
        ancla = clave_ancla(ev, vistas)                 # se cuenta también el hook
        if tipo == "hook":
            continue                                   # ya está arriba, en t=0
        clave = tipo if tipo in config.SFX_POR_EVENTO else "sticker"
        candidatos.append({"t": float(ev["ini"]), "tipo": clave, "prioridad": 90,
                           "ancla": ancla})

    # Cortes entre planos: cambio visual real (jump cut)
    for plano in plan_retencion.get("planos", [])[1:]:
        candidatos.append({"t": float(plano["inicio"]), "tipo": "corte", "prioridad": 50})

    # Punch-ins: SOLO los picos más fuertes, no todos
    picos = sorted(plan_retencion.get("picos_energia", []),
                   key=lambda p: p.get("energia", 0), reverse=True)
    for pico in picos[:config.SFX_MAX_PUNCH_INS]:
        candidatos.append({"t": float(pico["t"]), "tipo": "punch-in", "prioridad": 10})

    # Colisiones: gana el de mayor prioridad; se descarta lo que caiga muy cerca
    candidatos.sort(key=lambda c: (-c["prioridad"], c["t"]))
    aceptados = []
    for c in candidatos:
        if any(abs(c["t"] - a["t"]) < config.SFX_SEPARACION_MIN_S for a in aceptados):
            continue
        aceptados.append(c)
    aceptados.sort(key=lambda c: c["t"])

    # Asignar archivo concreto rotando entre las variantes de cada tipo
    usados_por_tipo = {}
    eventos = []
    for c in aceptados:
        cfg = config.SFX_POR_EVENTO[c["tipo"]]
        i = usados_por_tipo.get(c["tipo"], 0)
        usados_por_tipo[c["tipo"]] = i + 1
        evento = {
            "t": round(c["t"], 3),
            "archivo": cfg["archivos"][i % len(cfg["archivos"])],
            "volumen": cfg["volumen"],
            "razon": c["tipo"],
        }
        if c.get("ancla"):
            # De qué evento visual cuelga este sonido, y con cuánto desfase.
            # Es lo que permite que al mover el PiP en el editor su `pop` lo siga.
            evento["ancla"] = c["ancla"]
            evento["desfase"] = 0.0
        eventos.append(evento)
    return eventos


def escribir_hoja_sonido(eventos: list, palabras: list, ruta: Path, duracion: float):
    """Hoja de sonido para revisar y ajustar a mano.

    Muestra la transcripción con tiempos, dónde cayó cada SFX y con qué frase
    coincide, más el vocabulario disponible. Sirve para corregir por chat:
    "el pop de 14.9s muévelo a 15.4" o "en el segundo 22 mete un impacto".
    """
    disponibles = sorted(
        {a for cfg in config.SFX_POR_EVENTO.values() for a in cfg["archivos"]}
    )
    dir_sfx = config.DIR_ASSETS / "sfx"
    todos = sorted(p.name for p in dir_sfx.glob("*.mp3")) if dir_sfx.exists() else []
    sin_usar = [a for a in todos if a not in disponibles]

    resumen = resumen_densidad(eventos, duracion)
    cada_s = f" · uno cada {resumen['cada_s']:.1f}s" if resumen["cada_s"] is not None else ""
    L = [
        "# Hoja de sonido",
        "",
        f"Video de {duracion:.1f}s · {len(eventos)} efectos colocados{cada_s}.",
        "",
        "Para ajustar: dile al agente qué cambiar (mover, quitar, agregar o cambiar",
        "el sonido de un momento). Los cambios se guardan en un JSON y se vuelven a",
        "aplicar con `--sfx-manual`, sin tener que reeditar nada a mano.",
        "",
        "## Efectos colocados",
        "",
        "`sigue a` es el evento visual del que cuelga el sonido: si ese overlay se",
        "mueve en el editor, el sonido se mueve con él.",
        "",
        "| t | evento | sonido | vol | sigue a | qué se dice ahí |",
        "|---|---|---|---|---|---|",
    ]

    for ev in eventos:
        t = ev["t"]
        cerca = [p["texto"] for p in palabras if t - 0.9 <= p["inicio"] <= t + 1.4]
        frase = " ".join(cerca)[:52] or "—"
        ancla = f"`{ev['ancla']}`" if ev.get("ancla") else "—"
        L.append(f"| {t:.2f}s | {ev['razon']} | `{ev['archivo']}` | {ev['volumen']} | "
                 f"{ancla} | {frase} |")

    avisos = avisos_sfx(eventos, duracion)
    if avisos:
        L += [
            "",
            "## Avisos (no bloquean nada — decide José)",
            "",
        ]
        for a in avisos:
            L.append(f"- **{a['t']:.2f}s** · {a['texto']}")

    L += [
        "",
        "## Transcripción con tiempos",
        "",
        "Marcado con 🔊 el segundo donde cae un efecto.",
        "",
    ]

    tiempos_sfx = [e["t"] for e in eventos]
    linea, inicio_linea = [], 0.0
    for p in palabras:
        if not linea:
            inicio_linea = p["inicio"]
        linea.append(p["texto"])
        if len(linea) >= 9:
            marca = "🔊" if any(inicio_linea <= t <= p["fin"] for t in tiempos_sfx) else "  "
            L.append(f"- `{inicio_linea:6.2f}s` {marca} {' '.join(linea)}")
            linea = []
    if linea:
        marca = "🔊" if any(inicio_linea <= t for t in tiempos_sfx) else "  "
        L.append(f"- `{inicio_linea:6.2f}s` {marca} {' '.join(linea)}")

    L += [
        "",
        "## Vocabulario de sonidos",
        "",
        "### En uso",
        "",
        "| sonido | se usa para |",
        "|---|---|",
    ]
    for tipo, cfg in config.SFX_POR_EVENTO.items():
        L.append(f"| {', '.join(f'`{a}`' for a in cfg['archivos'])} | {tipo} (vol {cfg['volumen']}) |")

    if sin_usar:
        # Agrupado por categoría: en un pack de 141 sonidos, una lista corrida de
        # 98 nombres no sirve para elegir nada.
        alineacion = _alineacion_sfx()
        por_categoria = {}
        for a in sin_usar:
            cat = alineacion.get(a, {}).get("categoria", "otros")
            por_categoria.setdefault(cat, []).append(a)
        L += ["", "### Disponibles sin usar", "",
              "Para meter uno, agrégalo a la lista de ajustes manuales de abajo.", ""]
        for cat in sorted(por_categoria):
            L.append(f"**{cat}** ({len(por_categoria[cat])}): "
                     + ", ".join(f"`{a}`" for a in sorted(por_categoria[cat])))
            L.append("")

    L += [
        "",
        "## Formato para ajustes manuales",
        "",
        "```json",
        "[",
        '  {"t": 14.87, "archivo": "pop.mp3", "volumen": 0.95, "razon": "producto",',
        '   "ancla": "pip|kindle-pw-jade#0", "desfase": 0.0},',
        '  {"t": 22.10, "archivo": "impacto_hit.mp3", "volumen": 0.9, "razon": "enfasis"}',
        "]",
        "```",
        "",
        "Guardarlo y correr `f5_audio.py ... --sfx-manual ese_archivo.json`.",
        "Reemplaza la lista automática por completo.",
        "",
        "`ancla` es opcional. Si está, el `t` se recalcula solo a partir de dónde esté",
        "hoy ese evento visual (`desfase` es cuánto se adelanta o atrasa respecto a él).",
        "Un sonido sin `ancla` se queda exactamente en su `t`.",
        "",
        "`t` es el segundo en que el sonido GOLPEA, no en el que empieza a sonar. Un",
        "riser con `t: 12.0` arranca solo unos segundos antes y revienta en el 12.0,",
        "que es donde tiene que estar el reveal. Cuánto se adelanta cada archivo está",
        "medido en `assets/sfx/_alineacion.json`.",
    ]
    ruta.write_text("\n".join(L), encoding="utf-8")


def mezclar_audio(ruta_video: Path, eventos_sfx: list, ruta_salida: Path,
                  usar_musica: bool = True, musica_archivo: str = None,
                  musica_volumen: float = None, musica_inicio_s: float = None):
    duracion = _duracion_video(ruta_video)
    musica_archivo = musica_archivo or config.MUSICA_ARCHIVO_DEFAULT
    vol_musica = config.MUSICA_VOLUMEN if musica_volumen is None else float(musica_volumen)
    inicio_musica = 0.0 if musica_inicio_s is None else max(0.0, float(musica_inicio_s))

    inputs = ["-i", str(ruta_video)]
    ruta_musica = _ruta_musica(musica_archivo) if usar_musica else None
    if usar_musica and ruta_musica is None:
        _log(f"AVISO: no se encontró {musica_archivo} en assets/musica/ — se sigue sin música de fondo.")

    idx_siguiente = 1
    idx_musica = None
    if ruta_musica is not None:
        idx_musica = idx_siguiente
        inputs += ["-stream_loop", "-1", "-i", str(ruta_musica)]
        idx_siguiente += 1

    niveles = _niveles_sfx()
    alineacion = _alineacion_sfx()
    eventos_validos = []
    for ev in eventos_sfx:
        ruta = _ruta_sfx(ev["archivo"])
        if ruta is None:
            _log(f"AVISO: no se encontró SFX {ev['archivo']} (evento '{ev['razon']}' en t={ev['t']:.2f}s) — se omite.")
            continue
        inputs += ["-i", str(ruta)]
        # normalización al pico objetivo + volumen artístico, todo en dB
        pico = niveles.get(ev["archivo"], 0.0)
        vol = ev.get("volumen", config.SFX_VOLUMEN)
        ganancia_db = (config.SFX_PICO_OBJETIVO_DB - pico) + 20 * math.log10(max(vol, 0.001))
        punto = float(alineacion.get(ev["archivo"], {}).get("punto", 0.0))
        eventos_validos.append({**ev, "idx": idx_siguiente, "ganancia_db": ganancia_db,
                                "punto": punto})
        idx_siguiente += 1

    filtro_partes = []
    labels_mezcla = []

    filtro_partes.append(
        f"[0:a]aformat=sample_rates={config.AUDIO_SAMPLE_RATE}:channel_layouts=stereo[voz]"
    )
    labels_mezcla.append("[voz]")

    if idx_musica is not None:
        filtro_partes.append(
            f"[{idx_musica}:a]atrim=start={inicio_musica:.2f}:end={inicio_musica + duracion:.2f},asetpts=PTS-STARTPTS,"
            f"aformat=sample_rates={config.AUDIO_SAMPLE_RATE}:channel_layouts=stereo,volume={vol_musica:.2f}[mus_raw]"
        )
        filtro_partes.append(
            "[mus_raw][voz]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=300[mus_duck]"
        )
        labels_mezcla.append("[mus_duck]")

    for i, ev in enumerate(eventos_validos):
        # El evento visual cae en ev["t"]; lo que tiene que coincidir con él es el
        # GOLPE del sonido, que está `punto` segundos dentro del archivo. Así que
        # el archivo arranca antes. Si no cabe (un riser de 2.4s anclado al
        # segundo 1), se recorta por delante lo que no entra y el golpe sigue
        # cayendo donde debe.
        punto = ev["punto"]
        corte = max(0.0, punto - ev["t"])
        ms = round(max(0.0, ev["t"] - punto) * 1000)
        ventana = (punto - corte) + config.SFX_DURACION_MAX_S
        label = f"sfx{i}"
        filtro_partes.append(
            # 1) llevar el archivo a un pico común (compensa los 20 dB de
            #    dispersión del pack), 2) recortar largo con desvanecido para que
            #    un stinger de 8s no se solape con lo que viene, 3) recién
            #    entonces aplicar el volumen artístico del tipo de evento.
            f"[{ev['idx']}:a]aformat=sample_rates={config.AUDIO_SAMPLE_RATE}:channel_layouts=stereo,"
            f"volume={ev['ganancia_db']:.2f}dB,"
            f"atrim=start={corte:.3f}:end={corte + ventana:.3f},asetpts=PTS-STARTPTS,"
            f"afade=t=out:st={max(0.05, ventana - 0.25):.2f}:d=0.25,"
            f"adelay={ms}:all=1[{label}]"
        )
        labels_mezcla.append(f"[{label}]")

    n = len(labels_mezcla)
    entrada_mezcla = "".join(labels_mezcla)
    filtro_partes.append(
        f"{entrada_mezcla}amix=inputs={n}:duration=first:dropout_transition=0:normalize=0[premix]"
    )
    filtro_partes.append(
        f"[premix]loudnorm=I={config.LOUDNORM_TARGET_LUFS}:TP={config.LOUDNORM_PEAK_DB}:LRA=11[audio_final]"
    )

    filtro = ";".join(filtro_partes)

    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filtro,
        "-map", "0:v", "-map", "[audio_final]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k", "-ar", str(config.AUDIO_SAMPLE_RATE),
        "-shortest",
        str(ruta_salida),
    ]
    _log(f"Mezclando audio: voz + {'música ducked' if idx_musica else 'sin música'} + {len(eventos_validos)} SFX...")
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    if resultado.returncode != 0:
        _log(resultado.stderr[-4000:])
        raise RuntimeError("ffmpeg falló al mezclar audio")


def main():
    parser = argparse.ArgumentParser(description="Mezcla voz + música (ducking) + SFX, normaliza")
    parser.add_argument("video", type=str)
    parser.add_argument("plan_retencion", type=str, help=".plan.json generado por f4_retencion.py (picos de energía)")
    parser.add_argument("--salida", type=str, default=None)
    parser.add_argument("--sin-musica", action="store_true")
    parser.add_argument("--musica", type=str, default=None, help="Nombre de archivo en assets/musica/")
    parser.add_argument("--musica-volumen", type=float, default=None, help="Volumen de la música (0.0 a 1.5)")
    parser.add_argument("--musica-inicio", type=float, default=None, help="Segundo de inicio dentro de la pista de música")
    parser.add_argument("--overlays", type=str, default=None, metavar="EVENTOS_JSON",
                        help="Eventos de overlay de f6_overlays.py --solo-planificar. Sin esto los SFX "
                             "solo pueden atarse a cortes y punch-ins, no a la aparición de overlays.")
    parser.add_argument("--transcripcion", type=str, default=None,
                        help="JSON de f2_cortar.py — necesario para la hoja de sonido")
    parser.add_argument("--hoja-sonido", type=str, default=None, metavar="MD",
                        help="Escribe una hoja de sonido revisable (transcripción + SFX + vocabulario)")
    parser.add_argument("--sfx-manual", type=str, default=None, metavar="JSON",
                        help="Lista de SFX escrita a mano; reemplaza la automática por completo")
    args = parser.parse_args()

    ruta_video = Path(args.video)
    plan = json.loads(Path(args.plan_retencion).read_text(encoding="utf-8"))
    ruta_salida = Path(args.salida) if args.salida else ruta_video.with_name(ruta_video.stem + "_audio.mp4")

    eventos_overlay = []
    if args.overlays and Path(args.overlays).exists():
        eventos_overlay = json.loads(Path(args.overlays).read_text(encoding="utf-8"))

    if args.sfx_manual and Path(args.sfx_manual).exists():
        datos_sfx = json.loads(Path(args.sfx_manual).read_text(encoding="utf-8"))
        eventos = datos_sfx.get("sfx", datos_sfx) if isinstance(datos_sfx, dict) else datos_sfx
        for e in eventos:
            e.setdefault("volumen", config.SFX_VOLUMEN)
            e.setdefault("razon", "manual")
            # `_ruta_sfx` tolera una ruta absoluta (pathlib la deja pasar tal
            # cual), pero los niveles medidos y los puntos de golpe se indexan
            # por NOMBRE de archivo. f13_guion escribe rutas absolutas, así que
            # sus SFX se saltaban en silencio la normalización de volumen y la
            # alineación al golpe. Con el nombre pelado los dos aciertan.
            e["archivo"] = Path(str(e["archivo"])).name
        eventos.sort(key=lambda e: e["t"])
        _log(f"SFX manuales cargados desde {args.sfx_manual} (se ignora la lista automática)")
        # El sonido sigue a su evento visual: si el PiP se movió desde la Fase 2,
        # su `pop` se mueve con él sin que José tenga que arrastrar las dos cosas.
        reanclar_sfx(eventos, eventos_overlay)
    else:
        # Sin --sfx-manual (video improvisado sin --guion): el tope global se
        # aplica ACÁ, porque construir_eventos_sfx() por sí sola solo resuelve
        # colisiones DENTRO de cada tipo (bloque 3 del plan de mejoras). Los
        # SFX que sí vienen de --sfx-manual (guion.sfx.json) ya llegan topados
        # desde f13_guion.py — no se vuelven a topar acá para no deshacer un
        # ajuste que José ya guardó a mano en el editor (ajustes.sfx.json).
        eventos = construir_eventos_sfx(plan, eventos_overlay)
        eventos = aplicar_tope_densidad(eventos, config.SFX_DENSIDAD_PRESETS["normal"])

    duracion_video = _duracion_video(ruta_video)
    if args.hoja_sonido and args.transcripcion and Path(args.transcripcion).exists():
        palabras = json.loads(Path(args.transcripcion).read_text(encoding="utf-8"))["palabras"]
        escribir_hoja_sonido(eventos, palabras, Path(args.hoja_sonido), duracion_video)
        _log(f"Hoja de sonido: {args.hoja_sonido}")
    conteo = {}
    for e in eventos:
        conteo[e["razon"]] = conteo.get(e["razon"], 0) + 1
    detalle = ", ".join(f"{v} {k}" for k, v in sorted(conteo.items()))
    _log(f"Eventos SFX planificados: {len(eventos)} ({detalle})")
    for e in eventos:
        ancla = f"  -> sigue a {e['ancla']}" if e.get("ancla") else ""
        _log(f"  {e['t']:6.2f}s  {e['razon']:<13} {e['archivo']}{ancla}")

    for aviso in avisos_sfx(eventos, duracion_video):
        _log(f"  AVISO [{aviso['tipo']}] {aviso['t']:.2f}s: {aviso['texto']}")

    mezclar_audio(ruta_video, eventos, ruta_salida, usar_musica=not args.sin_musica,
                  musica_archivo=args.musica, musica_volumen=args.musica_volumen,
                  musica_inicio_s=args.musica_inicio)
    _log(f"\nAudio mezclado: {ruta_salida}")


if __name__ == "__main__":
    main()
