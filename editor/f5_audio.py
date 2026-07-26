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


def _ruta_musica(nombre_archivo: str) -> Path | None:
    ruta = config.DIR_ASSETS / "musica" / nombre_archivo
    return ruta if ruta.exists() else None


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
    candidatos = [{"t": 0.0, "tipo": "hook", "prioridad": 100}]

    # Overlays que aparecen en pantalla (PiP de producto, CTA, stickers)
    for ev in (eventos_overlay or []):
        tipo = ev.get("tipo", "")
        if tipo == "hook":
            continue                                   # ya está arriba, en t=0
        clave = tipo if tipo in config.SFX_POR_EVENTO else "sticker"
        candidatos.append({"t": float(ev["ini"]), "tipo": clave, "prioridad": 90})

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
        eventos.append({
            "t": round(c["t"], 3),
            "archivo": cfg["archivos"][i % len(cfg["archivos"])],
            "volumen": cfg["volumen"],
            "razon": c["tipo"],
        })
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

    L = [
        "# Hoja de sonido",
        "",
        f"Video de {duracion:.1f}s · {len(eventos)} efectos colocados.",
        "",
        "Para ajustar: dile al agente qué cambiar (mover, quitar, agregar o cambiar",
        "el sonido de un momento). Los cambios se guardan en un JSON y se vuelven a",
        "aplicar con `--sfx-manual`, sin tener que reeditar nada a mano.",
        "",
        "## Efectos colocados",
        "",
        "| t | evento | sonido | vol | qué se dice ahí |",
        "|---|---|---|---|---|",
    ]

    for ev in eventos:
        t = ev["t"]
        cerca = [p["texto"] for p in palabras if t - 0.9 <= p["inicio"] <= t + 1.4]
        frase = " ".join(cerca)[:52] or "—"
        L.append(f"| {t:.2f}s | {ev['razon']} | `{ev['archivo']}` | {ev['volumen']} | {frase} |")

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
        L += ["", "### Disponibles sin usar", "",
              ", ".join(f"`{a}`" for a in sin_usar), ""]

    L += [
        "",
        "## Formato para ajustes manuales",
        "",
        "```json",
        "[",
        '  {"t": 14.87, "archivo": "pop.mp3", "volumen": 0.95, "razon": "producto"},',
        '  {"t": 22.10, "archivo": "impacto_hit.mp3", "volumen": 0.9, "razon": "enfasis"}',
        "]",
        "```",
        "",
        "Guardarlo y correr `f5_audio.py ... --sfx-manual ese_archivo.json`.",
        "Reemplaza la lista automática por completo.",
    ]
    ruta.write_text("\n".join(L), encoding="utf-8")


def mezclar_audio(ruta_video: Path, eventos_sfx: list, ruta_salida: Path,
                   usar_musica: bool = True, musica_archivo: str = None):
    duracion = _duracion_video(ruta_video)
    musica_archivo = musica_archivo or config.MUSICA_ARCHIVO_DEFAULT

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
        eventos_validos.append({**ev, "idx": idx_siguiente, "ganancia_db": ganancia_db})
        idx_siguiente += 1

    filtro_partes = []
    labels_mezcla = []

    filtro_partes.append(
        f"[0:a]aformat=sample_rates={config.AUDIO_SAMPLE_RATE}:channel_layouts=stereo[voz]"
    )
    labels_mezcla.append("[voz]")

    if idx_musica is not None:
        filtro_partes.append(
            f"[{idx_musica}:a]atrim=0:{duracion},asetpts=PTS-STARTPTS,"
            f"aformat=sample_rates={config.AUDIO_SAMPLE_RATE}:channel_layouts=stereo,volume={config.MUSICA_VOLUMEN}[mus_raw]"
        )
        filtro_partes.append(
            "[mus_raw][voz]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=300[mus_duck]"
        )
        labels_mezcla.append("[mus_duck]")

    for i, ev in enumerate(eventos_validos):
        ms = round(ev["t"] * 1000)
        label = f"sfx{i}"
        filtro_partes.append(
            # 1) llevar el archivo a un pico común (compensa los 20 dB de
            #    dispersión del pack), 2) recortar largo con desvanecido para que
            #    un stinger de 8s no se solape con lo que viene, 3) recién
            #    entonces aplicar el volumen artístico del tipo de evento.
            f"[{ev['idx']}:a]aformat=sample_rates={config.AUDIO_SAMPLE_RATE}:channel_layouts=stereo,"
            f"volume={ev['ganancia_db']:.2f}dB,"
            f"atrim=0:{config.SFX_DURACION_MAX_S},asetpts=PTS-STARTPTS,"
            f"afade=t=out:st={max(0.05, config.SFX_DURACION_MAX_S - 0.25):.2f}:d=0.25,"
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
        eventos = json.loads(Path(args.sfx_manual).read_text(encoding="utf-8"))
        for e in eventos:
            e.setdefault("volumen", config.SFX_VOLUMEN)
            e.setdefault("razon", "manual")
        eventos.sort(key=lambda e: e["t"])
        _log(f"SFX manuales cargados desde {args.sfx_manual} (se ignora la lista automática)")
    else:
        eventos = construir_eventos_sfx(plan, eventos_overlay)

    if args.hoja_sonido and args.transcripcion and Path(args.transcripcion).exists():
        palabras = json.loads(Path(args.transcripcion).read_text(encoding="utf-8"))["palabras"]
        escribir_hoja_sonido(eventos, palabras, Path(args.hoja_sonido), _duracion_video(ruta_video))
        _log(f"Hoja de sonido: {args.hoja_sonido}")
    conteo = {}
    for e in eventos:
        conteo[e["razon"]] = conteo.get(e["razon"], 0) + 1
    detalle = ", ".join(f"{v} {k}" for k, v in sorted(conteo.items()))
    _log(f"Eventos SFX planificados: {len(eventos)} ({detalle})")
    for e in eventos:
        _log(f"  {e['t']:6.2f}s  {e['razon']:<13} {e['archivo']}")

    mezclar_audio(ruta_video, eventos, ruta_salida, usar_musica=not args.sin_musica, musica_archivo=args.musica)
    _log(f"\nAudio mezclado: {ruta_salida}")


if __name__ == "__main__":
    main()
