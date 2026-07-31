"""
Orquestador del pipeline completo: grabación cruda -> video publicable.

Fases 1-5 del plan (transcripción, corte, subtítulos, retención, audio, overlays).
Fase 6 (generación GPU) no está implementada aún — es de baja prioridad según
el propio plan (sección 7, Fase 6: "posponerse indefinidamente" si el
presupuesto visual se cubre con PiP + overlays).

Estructura (optimizada 2026-07-26 — ver contexto/AUDITORIA-OPTIMIZACION.md):
el video solo se codifica DOS veces (antes eran cuatro). El análisis de
retención, los subtítulos y los overlays se preparan primero como datos
(JSON/.ass/PNG), y luego f4_retencion compone todo — zoom, overlays y
subtítulos — dentro de una única codificación NVENC. La mezcla de audio
(f5) copia el video sin recomprimirlo.

Orden de composición (importante): los subtítulos van en la capa visual más
alta — dentro del filtro de f4, el `ass=` se aplica DESPUÉS de los overlays,
así ningún overlay (hook, CTA, sticker) tapa el texto.

Los intermedios se escriben en C:\\ai-video\\salida\\<nombre>\\ (fuera de
OneDrive, regla de la sección 3 del plan); solo el video final se copia a
la carpeta salida/ del proyecto en OneDrive.

Uso:
    python editor.py "entrada/video_crudo.mp4"
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import config
import f0_preparar

AQUI = Path(__file__).resolve().parent

# `unir_tomas` y `_duracion` viven ahora en f0_preparar.py. Se re-exportan con
# el nombre de siempre para no romper a nadie que los importe desde aquí: la
# pantalla de preparación tiene que unir con la MISMA función que el pipeline,
# y dos copias de la misma lógica es exactamente cómo la previa acabaría
# mostrando algo distinto de lo que sale del render.
unir_tomas = f0_preparar.unir_tomas
_duracion = f0_preparar.duracion


def _ruta_versionada(dir_destino: Path, nombre_base: str) -> Path:
    """Si `nombre.mp4` ya existe en dir_destino, genera `nombre_v2.mp4`, `nombre_v3.mp4`, etc.
    para evitar sobreescribir versiones anteriores."""
    cand = dir_destino / f"{nombre_base}.mp4"
    if not cand.exists():
        return cand
    v = 2
    while True:
        cand_v = dir_destino / f"{nombre_base}_v{v}.mp4"
        if not cand_v.exists():
            return cand_v
        v += 1


def paso(descripcion, cmd):
    print(f"\n{'='*70}\n{descripcion}\n{'='*70}")
    resultado = subprocess.run([sys.executable, *cmd], cwd=str(AQUI))
    if resultado.returncode != 0:
        print(f"ERROR en: {descripcion}", file=sys.stderr)
        sys.exit(resultado.returncode)


def _clips_de_entrada(rutas_entrada: list, desde: float, hasta: float) -> list:
    """Decide qué recorte se aplica a cada archivo de entrada.

    Tres orígenes, en este orden de prioridad:

      1. `--desde` / `--hasta` en la línea de comandos. Es el camino de agente:
         un recorte simple, sin abrir ninguna pantalla. Solo vale con UN archivo
         de entrada — con varios no habría forma de saber a cuál se refiere.
      2. El `.preparado.json` que dejó la pantalla de preparación junto al
         archivo de entrada. Es lo que hace que volver a correr el mismo
         material se acuerde de los recortes y del orden de los clips.
      3. Nada: los archivos enteros, tal como se pasaron. El comportamiento de
         siempre.

    El .preparado.json solo aporta su LISTA de clips cuando en la línea de
    comandos vino un único archivo. Si se pasaron varios a mano, mandan los de
    la línea de comandos: si no, pedir dos archivos y recibir tres (porque el
    .preparado.json guardaba tres) sería imposible de entender.
    """
    if desde is not None or hasta is not None:
        if len(rutas_entrada) > 1:
            sys.exit("ERROR: --desde/--hasta solo valen con UN archivo de entrada. "
                     "Para recortar varios clips usá la pantalla de preparación "
                     "(«Preparar grabación.bat»).")
        print(f"\nRecorte pedido por línea de comandos: "
              f"{desde or 0.0:.2f}s -> {'fin' if hasta is None else f'{hasta:.2f}s'}")
        return [{"ruta": rutas_entrada[0], "desde": desde or 0.0, "hasta": hasta}]

    if len(rutas_entrada) == 1:
        prep = f0_preparar.leer_preparado(rutas_entrada[0])
        if prep:
            clips = prep["clips"]
            print(f"\nPreparación guardada ({f0_preparar.ruta_preparado(rutas_entrada[0]).name}): "
                  f"{len(clips)} clip(s), {prep.get('total_s', '?')}s en total.")
            for c in clips:
                print(f"  {Path(c['ruta']).name}: {c['desde']:.2f}s -> {c['hasta']:.2f}s")
            print("  (para ignorarla, borrá ese archivo o pasá --desde/--hasta)")
            return clips
    elif f0_preparar.leer_preparado(rutas_entrada[0]):
        print("\nAVISO: hay un .preparado.json para este material, pero se pasaron "
              "varios archivos a mano — mandan los de la línea de comandos.")

    return [{"ruta": r, "desde": 0.0, "hasta": None} for r in rutas_entrada]


def main():
    parser = argparse.ArgumentParser(description="Pipeline completo: crudo -> video publicable")
    parser.add_argument("entrada", type=str, nargs="+",
                        help="Grabación cruda. Se pueden pasar VARIOS archivos en el orden en "
                             "que van: cada uno es un plano real (abierto, cerrado…) y el "
                             "pipeline los une antes de transcribir, marcando los empalmes "
                             "como los únicos cambios de plano del video")
    parser.add_argument("--nombre", type=str, default=None, help="Nombre base para los archivos de salida")
    parser.add_argument("--desde", type=float, default=None, metavar="SEGS",
                        help="Recortar la grabación desde este segundo. El recorte se aplica "
                             "ANTES de transcribir, así que el resto del pipeline ni se entera. "
                             "Solo con UN archivo de entrada; para varios clips está la pantalla "
                             "de preparación («Preparar grabación.bat»)")
    parser.add_argument("--hasta", type=float, default=None, metavar="SEGS",
                        help="Recortar la grabación hasta este segundo (por defecto, el final)")
    parser.add_argument("--sin-musica", action="store_true", help="Omitir música de fondo en la Fase 4")
    parser.add_argument("--guion", type=int, default=None, metavar="N",
                        help="Número de guion (de PANEL-PRODUCCION.html) a ejecutar. Incursiona el "
                             "modo dirigido por guion: extrae hook, SFX, animaciones, PIP y B-roll "
                             "alineándolos con la transcripción.")
    parser.add_argument("--musica", type=str, default=None, help="Nombre de archivo de música en assets/musica/")
    parser.add_argument("--musica-volumen", type=float, default=None, help="Volumen de la música de fondo (0.0 a 1.5)")
    parser.add_argument("--musica-inicio", type=float, default=None, help="Segundo de inicio dentro de la pista de música")
    parser.add_argument("--broll-manual", type=str, default=None, metavar="JSON",
                        help="Lista completa de B-rolls a pantalla completa")
    parser.add_argument("--hook", type=str, default=None, metavar="TEXTO",
                        help="Texto del banner de hook (los primeros segundos). Si se omite se usa la "
                             "primera frase completa del video. Hooks curados en contexto/banco-hooks.md")
    parser.add_argument("--presentador", type=str, default=None,
                        choices=sorted(config.PRESENTADORES),
                        help="Quién habla en el video. Cambia muletillas, umbral de silencio y "
                             "calibración de punch-ins (por defecto: jose)")
    parser.add_argument("--sin-generar", action="store_true",
                        help="No usar ComfyUI/Flux cuando el catálogo no tenga imagen para un "
                             "concepto. La primera generación cuesta ~40s de arranque; después va "
                             "por caché y es gratis")
    parser.add_argument("--sfx-manual", type=str, default=None, metavar="JSON",
                        help="Lista de efectos de sonido hecha a mano (o exportada por el editor "
                             "visual). Reemplaza la automática por completo")
    parser.add_argument("--posiciones-manual", type=str, default=None, metavar="JSON",
                        help="Posiciones de los insertos elegidas a mano en el editor visual")
    parser.add_argument("--eventos-manual", type=str, default=None, metavar="JSON",
                        help="Lista completa de insertos pip-producto armada en el editor visual "
                             "(Fase 2): sustituye/añade/quita qué asset se muestra, no solo dónde")
    parser.add_argument("--animaciones-manual", type=str, default=None, metavar="JSON",
                        help="Lista completa de animaciones armada en el editor visual "
                             "(Fase 3c): quita, mueve y añade animaciones. Reemplaza el "
                             "disparo por palabra de config.ANIMACIONES_POR_PALABRA")
    parser.add_argument("--hook-cta-manual", type=str, default=None, metavar="JSON",
                        help="Tiempos del hook y del CTA movidos a mano en el editor visual. "
                             "Mandan sobre los automáticos")
    parser.add_argument("--encuadre-manual", type=str, default=None, metavar="JSON",
                        help="Punch-ins y tramos de plano cerrado elegidos a mano en el editor "
                             "visual (Fase 3d). Manda sobre lo que saque del guion y sobre los "
                             "picos de energía del audio")
    parser.add_argument("--sub-tamano", type=int, default=None, metavar="PX",
                        help="Tamaño del subtítulo en píxeles, elegido en el editor visual "
                             "(Bloque 5). Sin esto, config.SUB_TAMANO_PX")
    parser.add_argument("--sub-correcciones", type=str, default=None, metavar="JSON",
                        help="Correcciones de texto de palabras mal transcritas (Whisper), hechas "
                             "en el editor visual. Solo cambia lo que se VE en el subtítulo — los "
                             "tiempos y la alineación guion↔transcripción siguen intactos")
    parser.add_argument("--sol-pip-video", action="store_true",
                        help="Usar el video de sol (sol_video_pip.mov) como PiP en vez de la animación HTML")
    parser.add_argument("--video-ambiente", action="store_true",
                        help="Generar los insertos de ambiente como CLIP de video con LTX 2.3 en vez "
                             "de foto fija (f12_video_gen). APAGADO por defecto: cada clip son "
                             "minutos de GPU y conviene tener >18 GB de RAM libres. Si un concepto "
                             "falla, cae solo a la imagen fija de Flux")
    parser.add_argument("--sin-video-ambiente", action="store_true",
                        help="Forzar insertos de ambiente como foto fija aunque config.LTX_HABILITADO "
                             "esté en True")
    parser.add_argument("--sin-editor-visual", action="store_true",
                        help="No generar el editor visual HTML al terminar")
    parser.add_argument("--preview", action="store_true",
                        help="Render de prueba: misma composición exacta pero a media resolución "
                             "y sin publicar. Sale en 07_PREVIEW.mp4 y NO toca 07_FINAL.mp4 ni "
                             "copia nada a OneDrive. Para comprobar un ajuste antes de gastar el "
                             "render bueno")
    parser.add_argument("--sin-abrir-editor", action="store_true",
                        help="No abrir el editor visual al terminar. Para corridas desatendidas "
                             "(un agente, una tanda nocturna): el editor es un servidor y se "
                             "queda ocupando la terminal hasta que se cierre con Ctrl+C")
    parser.add_argument("--reaplicar", action="store_true",
                        help="Reutiliza la transcripción, el corte y el plan de retención de una "
                             "corrida existente (mismo --nombre): entra directo en overlays -> "
                             "render -> audio sin volver a transcribir ni cortar. Para iterar rápido "
                             "desde el editor visual sobre ajustes de SFX/posiciones/eventos.")
    parser.add_argument("--silencios", type=str, default=None, metavar="JSON",
                        help="ajustes.silencios.json del editor visual: qué tramos "
                             "recortados hay que devolver al video. Con --reaplicar "
                             "rehace SOLO el corte y el plan de retención (la "
                             "transcripción se reutiliza) y remapea los ajustes ya "
                             "hechos a la nueva línea de tiempo")
    args = parser.parse_args()

    rutas_entrada = [Path(e).resolve() for e in args.entrada]
    faltan = [r for r in rutas_entrada if not r.exists()]
    if faltan:
        for r in faltan:
            print(f"ERROR: no existe {r}", file=sys.stderr)
        sys.exit(1)

    nombre = args.nombre or rutas_entrada[0].stem
    dir_trabajo = config.DIR_SALIDA / nombre
    dir_trabajo.mkdir(parents=True, exist_ok=True)

    # Constancia de con qué se lanzó la corrida, para que el editor visual pueda
    # re-renderizar en las MISMAS condiciones. Sin esto, f11_servidor llamaba a
    # editor.py sin --guion y el re-render re-derivaba del automático todo lo
    # que el guion había aportado: la hoja de sonido, las animaciones, la pista
    # de música y el perfil del presentador.
    (dir_trabajo / "00_corrida.json").write_text(json.dumps({
        "guion": args.guion,
        "presentador": args.presentador,
        "musica": args.musica,
        "musica_volumen": args.musica_volumen,
        "musica_inicio": args.musica_inicio,
        "sin_musica": bool(args.sin_musica),
        "sol_pip_video": bool(args.sol_pip_video),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    # FASE 0 — recortar y unir. Ocurre ANTES de transcribir, y eso es lo que la
    # hace segura: a partir de aquí el pipeline entero mira un solo archivo y
    # ninguna coordenada de tiempo de aguas abajo (palabras, SFX, overlays,
    # encuadre, ajustes.*.json) sabe que hubo un recorte. Los empalmes que
    # devuelve `preparar_entrada` ya están medidos sobre los clips RECORTADOS,
    # que es lo que después remapea f2_cortar con `mapear_a_nueva_linea`.
    #
    # Con --reaplicar no se hace nada de esto: esa bandera reusa el 01/02/03 de
    # la corrida anterior, así que ni f1 ni f2 llegan a mirar `ruta_entrada`.
    # Recortar igual sería recodificar la grabación entera en cada
    # re-renderizado del editor visual, que es el camino que más se usa.
    tomas_json = dir_trabajo / "00_tomas.json"
    ruta_entrada = rutas_entrada[0]
    if not args.reaplicar:
        clips = _clips_de_entrada(rutas_entrada, args.desde, args.hasta)
        hay_trabajo = len(clips) > 1 or any(
            c.get("desde") or c.get("hasta") is not None for c in clips)
        if hay_trabajo:
            print(f"\n{'='*70}\nFASE 0: Preparar la entrada ({len(clips)} clip(s))\n{'='*70}")
        ruta_entrada, empalmes = f0_preparar.preparar_entrada(
            clips, dir_trabajo / "00_tomas.mp4")
        if empalmes:
            tomas_json.write_text(json.dumps(empalmes), encoding="utf-8")
        else:
            tomas_json.unlink(missing_ok=True)   # una sola toma: sin empalmes que marcar

    transcripcion = dir_trabajo / "01_transcripcion.json"
    video_cortado = dir_trabajo / "02_cortado.mp4"
    plan_retencion = dir_trabajo / "03_retencion.plan.json"
    subtitulos_ass = dir_trabajo / "04_subtitulos.ass"
    eventos_overlays = dir_trabajo / "05_overlays.eventos.json"
    # El preview escribe en sus propios archivos: si compartiera nombre con el
    # render bueno, una prueba a media resolución dejaría el 07_FINAL.mp4 en
    # baja y no habría forma de notarlo hasta subirlo.
    video_compuesto = dir_trabajo / ("06_preview.mp4" if args.preview else "06_video.mp4")
    video_final = dir_trabajo / ("07_PREVIEW.mp4" if args.preview else "07_FINAL.mp4")

    json_cortado = video_cortado.with_suffix(".json")

    # El presentador cambia las muletillas y los umbrales: José y su esposa no
    # hablan igual (sección 2 del plan).
    perfil = ["--presentador", args.presentador] if args.presentador else []

    # El hook físico (entrar al cuadro, sentarse) es silencio puro, así que el
    # corte de silencios se lo llevaba entero. Cuánto conservar sale del campo
    # `hooksegs` del guion en PANEL-PRODUCCION.html, y hay que leerlo ANTES de
    # cortar — por eso este parseo suelto en vez de esperar a f13_guion, que
    # necesita la transcripción ya recortada.
    def _extra_de_corte():
        extra = []
        if args.guion is not None:
            import f13_guion
            params = f13_guion.leer_parametros_guion(args.guion)
            if params["hooksegs"] > 0:
                extra += ["--conservar-inicio", str(params["hooksegs"])]
                print(f"\nGuion {args.guion} ({params['tipo_hook']}): se conservarán "
                      f"{params['hooksegs']}s de hook físico al inicio.")
            if params["cierresegs"] > 0:
                extra += ["--conservar-fin", str(params["cierresegs"])]
                print(f"Guion {args.guion}: se conservarán {params['cierresegs']}s de "
                      f"cierre físico al final.")
        if tomas_json.exists():
            extra += ["--tomas", str(tomas_json)]
        return extra

    # Un re-corte invalida el plan de retención: se calculó sobre el video
    # anterior y sus segundos apuntan a otro sitio.
    recorte_rehecho = False

    if args.reaplicar:
        # Reusa 01/02/03 de una corrida anterior con el mismo --nombre: evita
        # los 41s de transcripción + corte + análisis de retención en cada
        # iteración desde el editor visual (sección Fase 0 del plan v2).
        faltantes = [p for p in (transcripcion, video_cortado, json_cortado, plan_retencion)
                     if not p.exists()]
        if faltantes:
            print(f"ERROR: --reaplicar necesita una corrida previa completa en {dir_trabajo}.\n"
                  "Faltan:", file=sys.stderr)
            for p in faltantes:
                print(f"  {p}", file=sys.stderr)
            print("Corré primero sin --reaplicar para generarlos.", file=sys.stderr)
            sys.exit(1)
        print(f"\n--reaplicar: reutilizando transcripción, corte y plan de retención de {dir_trabajo}")
        if args.guion is not None:
            # Trampa fácil de pisar: `hooksegs`/`cierresegs` los aplica
            # f2_cortar, que con --reaplicar no se vuelve a ejecutar. Sin este
            # aviso, cambiar el valor en el panel y volver a correr parece "no
            # hacer nada".
            print("  OJO: `hooksegs`/`cierresegs` se aplican al cortar. Si los cambiaste en "
                  "el panel, corré SIN --reaplicar para que tenga efecto.")

        # --- Silencios restaurados a mano desde el editor visual -------------
        # Único caso en que --reaplicar SÍ vuelve a cortar. Lo caro es la
        # transcripción (WhisperX large-v3), y esa no depende de dónde estén los
        # cortes: 01_transcripcion.json cubre la grabación entera y sigue siendo
        # válido. Se rehace el corte (ffmpeg, segundos) y el análisis de
        # retención, que sí mira el video cortado.
        import f15_silencios
        if args.silencios and f15_silencios.hay_cambios(dir_trabajo):
            datos_previos = json.loads(json_cortado.read_text(encoding="utf-8"))
            intervalos_viejos = datos_previos.get("intervalos_conservados_original", [])
            fuente_corte = ((datos_previos.get("corte_parametros") or {}).get("fuente_corte")
                            or json.loads(transcripcion.read_text(encoding="utf-8")).get("fuente"))
            fuente_corte = Path(fuente_corte) if fuente_corte else None

            if not fuente_corte or not fuente_corte.exists():
                # Sin la grabación original no hay de dónde sacar el metraje: el
                # tramo restaurado no está en 02_cortado.mp4. Mejor seguir con el
                # corte que ya hay que renderizar algo silenciosamente distinto.
                print(f"\nAVISO: no se puede rehacer el corte — falta la grabación original "
                      f"({fuente_corte}).\n  Se renderiza con el corte actual y los silencios "
                      f"restaurados NO se aplican.", file=sys.stderr)
            else:
                paso("FASE 1b-bis: Re-corte con los silencios restaurados", [
                    "f2_cortar.py", str(transcripcion), str(fuente_corte),
                    "--salida", str(video_cortado),
                    *perfil, *_extra_de_corte(), "--silencios", args.silencios,
                ])
                datos_nuevos = json.loads(json_cortado.read_text(encoding="utf-8"))
                intervalos_nuevos = datos_nuevos.get("intervalos_conservados_original", [])

                print("\nRemapeando los ajustes ya hechos a la nueva línea de tiempo...")
                res = f15_silencios.remapear_ajustes(
                    dir_trabajo, intervalos_viejos, intervalos_nuevos)
                for nombre_aj in res["cambiados"]:
                    print(f"  remapeado: {nombre_aj}")
                f15_silencios.guardar_avisos(dir_trabajo, res["avisos"])
                for aviso in res["avisos"]:
                    print(f"  AVISO [{aviso['archivo']}] {aviso.get('etiqueta','')}: "
                          f"{aviso['detalle']}")
                if res["avisos"]:
                    print(f"  -> {len(res['avisos'])} aviso(s). El editor los enseña al "
                          f"volver a abrirlo: hay que revisarlos a mano.")
                recorte_rehecho = True
    else:
        cortar_extra = _extra_de_corte()

        paso("FASE 1a: Transcripción (WhisperX)", [
            "f1_transcribir.py", str(ruta_entrada), "--salida", str(transcripcion)
        ])

        paso("FASE 1b: Corte inteligente", [
            "f2_cortar.py", str(transcripcion), str(ruta_entrada), "--salida", str(video_cortado),
            *perfil, *cortar_extra,
        ])

    # ---- MODO DIRIGIDO POR GUION (--guion N) ------------------------------
    # Va ANTES del análisis de retención: de aquí sale guion.encuadre.json, que
    # es lo que le dice a f4 dónde acercarse. Necesita 02_cortado.json, así que
    # este es el primer punto del pipeline en que puede correr.
    encuadre_guion = []
    if args.guion is not None:
        import f13_guion
        res_g = f13_guion.procesar_guion(args.guion, json_cortado, dir_trabajo)
        if not args.sfx_manual and res_g["sfx"].exists():
            args.sfx_manual = str(res_g["sfx"])
        if not args.animaciones_manual and res_g["animaciones"].exists():
            args.animaciones_manual = str(res_g["animaciones"])
        if not args.eventos_manual and res_g["eventos"].exists():
            args.eventos_manual = str(res_g["eventos"])
        if not args.broll_manual and res_g["broll"].exists():
            args.broll_manual = str(res_g["broll"])
        if res_g.get("encuadre") and res_g["encuadre"].exists():
            encuadre_guion = ["--encuadre", str(res_g["encuadre"])]
        if not args.hook and res_g.get("hook"):
            args.hook = res_g["hook"]
        if not args.musica and res_g.get("musica"):
            args.musica = res_g["musica"]

    # El encuadre hecho a mano gana sobre el que sale del guion: si José movió
    # un acercamiento en el editor es porque el automático no le convenció.
    # Funciona con o sin --guion.
    if args.encuadre_manual:
        encuadre_guion = ["--encuadre", args.encuadre_manual]
        print(f"\nEncuadre manual: {args.encuadre_manual}")

    if not args.reaplicar or recorte_rehecho:
        # El nombre 03_retencion.mp4 no se renderiza: --sin-render solo escribe el
        # plan JSON (03_retencion.plan.json); el render real ocurre en la fase de
        # composición de abajo, con overlays y subtítulos en la misma pasada.
        #
        # `recorte_rehecho` obliga a repetirlo aunque sea --reaplicar: el plan
        # guarda el track del rostro y la curva de acercamientos indexados por
        # segundo del video CORTADO, así que tras mover un corte apuntan al
        # fotograma equivocado. Reusarlo era el fallo silencioso de este bloque:
        # el render sale, pero el zoom se cierra medio segundo tarde.
        paso("FASE 3a: Análisis de retención (face tracking, punch-ins, regla de 5s)", [
            "f4_retencion.py", str(video_cortado), str(json_cortado),
            "--salida", str(dir_trabajo / "03_retencion.mp4"), "--sin-render",
            *perfil, *encuadre_guion,
        ])

    cmd_subs = ["f3_subtitulos.py", str(json_cortado), "--salida", str(subtitulos_ass)]
    if args.sub_tamano:
        cmd_subs += ["--tamano", str(args.sub_tamano)]
    if args.sub_correcciones:
        cmd_subs += ["--correcciones", args.sub_correcciones]
    paso("FASE 2: Subtítulos ASS", cmd_subs)

    cmd_overlays = [
        "f6_overlays.py", str(video_cortado), str(plan_retencion), str(json_cortado),
        "--solo-planificar", str(eventos_overlays),
        # la semilla de las variantes de animación sale del nombre del video, no
        # del archivo temporal: así el resultado es reproducible entre corridas
        "--nombre-video", nombre,
    ]
    if args.hook:
        cmd_overlays += ["--hook", args.hook]
    if args.sin_generar:
        cmd_overlays.append("--sin-generar")
    if args.posiciones_manual:
        cmd_overlays += ["--posiciones-manual", args.posiciones_manual]
    if args.eventos_manual:
        cmd_overlays += ["--eventos-manual", args.eventos_manual]
    if args.broll_manual:
        cmd_overlays += ["--broll-manual", args.broll_manual]
    if args.animaciones_manual:
        cmd_overlays += ["--animaciones-manual", args.animaciones_manual]
    if args.hook_cta_manual:
        cmd_overlays += ["--hook-cta-manual", args.hook_cta_manual]
    if args.sol_pip_video:
        cmd_overlays.append("--sol-pip-video")
    if args.video_ambiente:
        cmd_overlays.append("--video-ambiente")
    if args.sin_video_ambiente:
        cmd_overlays.append("--sin-video-ambiente")
    paso("FASE 5a+6: Overlays y generación (hook, ficha, animaciones, insertos, CTA)", cmd_overlays)

    paso("FASE 3b+5b+2b: Render único (zoom + overlays + subtítulos + loop, una sola codificación)", [
        "f4_retencion.py", str(video_cortado), str(json_cortado),
        "--salida", str(video_compuesto),
        "--solo-render", str(plan_retencion),
        "--overlays", str(eventos_overlays),
        "--subs", str(subtitulos_ass),
        # También aquí: con --reaplicar el plan de retención es el de la corrida
        # anterior y puede no traer los planos cerrados. Pasando el encuadre
        # recién calculado, iterar sobre el guion no obliga a re-analizar.
        "--final", *perfil, *encuadre_guion,
        *(["--escala", str(config.PREVIEW_ESCALA)] if args.preview else []),
    ])

    cmd_audio = ["f5_audio.py", str(video_compuesto), str(plan_retencion), "--salida", str(video_final),
                 "--overlays", str(eventos_overlays),
                 "--transcripcion", str(json_cortado),
                 "--hoja-sonido", str(dir_trabajo / "08_hoja-sonido.md")]
    if args.sin_musica:
        cmd_audio.append("--sin-musica")
    if args.musica:
        cmd_audio += ["--musica", args.musica]
    if args.musica_volumen is not None:
        cmd_audio += ["--musica-volumen", str(args.musica_volumen)]
    if args.musica_inicio is not None:
        cmd_audio += ["--musica-inicio", str(args.musica_inicio)]
    if args.sfx_manual:
        cmd_audio += ["--sfx-manual", args.sfx_manual]
    paso("FASE 4: Audio (música + ducking + SFX + loudnorm; el video se copia sin recomprimir)", cmd_audio)

    # Publicación: solo el final viaja a OneDrive con versión incremental si ya
    # existe. Un preview no se publica nunca — es de prueba y está en baja.
    publicado = None
    if not args.preview:
        config.DIR_PUBLICADOS.mkdir(parents=True, exist_ok=True)
        publicado = _ruta_versionada(config.DIR_PUBLICADOS, nombre)
        shutil.copy2(video_final, publicado)

    # Editor visual: se genera siempre al final para que José pueda retocar los
    # sonidos y las posiciones de los insertos arrastrando, en vez de leyendo
    # una tabla de tiempos en markdown.
    if not args.sin_editor_visual:
        paso("EXTRA: Editor visual (sonidos + posiciones de insertos)", [
            "f10_editor_visual.py", str(dir_trabajo)
        ])

    if args.preview:
        print(f"\nPREVIEW (media resolución, sin publicar): {video_final}")
        print("Cuando esté bien, corré lo mismo SIN --preview para el archivo de subir.")
    else:
        print(f"\nVideo final (trabajo):   {video_final}")
        print(f"Video final (OneDrive):  {publicado}")
    if not args.sin_editor_visual:
        # Se aclara que este es el HTML suelto (v1: solo sonidos y posiciones).
        # Sin la aclaración parecía ser "el editor" a secas, y el que sirve para
        # trabajar —B-roll, animaciones, encuadre, re-renderizar— es el v2.
        print(f"Editor v1 (HTML suelto): {dir_trabajo / '09_editor-visual.html'}")

    # El editor se abre SOLO: terminar un video y quedarte sin saber que el
    # siguiente paso existe era la forma mas facil de publicar el automatico sin
    # retocarlo. Un preview no lo abre — se pidio para comprobar algo desde el
    # editor, que ya esta abierto.
    if args.sin_abrir_editor or args.preview:
        print(f"\nPara retocarlo:          python editor/abrir_editor.py {nombre}")
        print("                         (o «Abrir Editor DeviceShop.bat», que abre la última)")
    else:
        print(f"\n{'='*70}\nEditor visual — Ctrl+C para cerrarlo\n{'='*70}")
        subprocess.run([sys.executable, "f11_servidor.py", str(dir_trabajo)], cwd=str(AQUI))


if __name__ == "__main__":
    main()
