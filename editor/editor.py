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

AQUI = Path(__file__).resolve().parent


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


def _duracion(ruta: Path) -> float:
    salida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(ruta)],
        capture_output=True, text=True, check=True).stdout.strip()
    return float(salida)


def unir_tomas(rutas: list, destino: Path) -> tuple:
    """Une varias grabaciones en un solo archivo y devuelve (ruta, empalmes).

    Para cuando José graba el mismo guion en DOS PLANOS REALES — uno abierto y
    uno cerrado, como pide la columna "Tomas" del panel ("Plano cerrado, acercá
    la cámara. Cambio de distancia real, no zoom digital"). El pipeline entero
    trabaja sobre un archivo, así que se unen antes de transcribir y se anotan
    los segundos donde empalman: esos son los ÚNICOS cambios de plano de verdad
    del video, y f4_retencion los usa para reiniciar ahí la rampa de zoom (y solo
    ahí — un corte de silencio no es un cambio de plano).

    Primero se intenta el demuxer `concat` con `-c copy`: son tomas de la misma
    cámara con los mismos ajustes, así que copiar es instantáneo y no añade una
    generación de compresión. Si ffmpeg se queja (parámetros distintos entre
    archivos), se recodifica con el filtro concat, que sí normaliza.
    """
    empalmes, acumulado = [], 0.0
    for r in rutas[:-1]:
        acumulado += _duracion(r)
        empalmes.append(round(acumulado, 3))

    lista = destino.with_suffix(".txt")
    lista.write_text(
        "".join(f"file '{Path(r).as_posix()}'\n" for r in rutas), encoding="utf-8")
    cmd_copia = ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                 "-i", str(lista), "-c", "copy", str(destino)]
    if subprocess.run(cmd_copia, capture_output=True).returncode != 0:
        print("  (las tomas no son copiables tal cual — se recodifican para unirlas)")
        entradas, partes = [], []
        for i, r in enumerate(rutas):
            entradas += ["-i", str(r)]
            partes.append(f"[{i}:v][{i}:a]")
        filtro = f"{''.join(partes)}concat=n={len(rutas)}:v=1:a=1[v][a]"
        cmd_recod = ["ffmpeg", "-y", "-loglevel", "error", *entradas,
                     "-filter_complex", filtro, "-map", "[v]", "-map", "[a]",
                     *config.args_video(), "-c:a", "aac", "-b:a", "192k", str(destino)]
        r = subprocess.run(cmd_recod, capture_output=True, text=True)
        if r.returncode != 0:
            print(r.stderr[-2000:], file=sys.stderr)
            sys.exit("ERROR: no se pudieron unir las tomas")
    lista.unlink(missing_ok=True)

    print(f"  {len(rutas)} tomas unidas en {destino.name}; "
          f"empalmes en {', '.join(f'{t:.2f}s' for t in empalmes)}")
    return destino, empalmes


def main():
    parser = argparse.ArgumentParser(description="Pipeline completo: crudo -> video publicable")
    parser.add_argument("entrada", type=str, nargs="+",
                        help="Grabación cruda. Se pueden pasar VARIOS archivos en el orden en "
                             "que van: cada uno es un plano real (abierto, cerrado…) y el "
                             "pipeline los une antes de transcribir, marcando los empalmes "
                             "como los únicos cambios de plano del video")
    parser.add_argument("--nombre", type=str, default=None, help="Nombre base para los archivos de salida")
    parser.add_argument("--sin-musica", action="store_true", help="Omitir música de fondo en la Fase 4")
    parser.add_argument("--guion", type=int, default=None, metavar="N",
                        help="Número de guion (de PANEL-PRODUCCION.html) a ejecutar. Incursiona el "
                             "modo dirigido por guion: extrae hook, SFX, animaciones, PIP y B-roll "
                             "alineándolos con la transcripción.")
    parser.add_argument("--musica", type=str, default=None, help="Nombre de archivo de música en assets/musica/")
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
    parser.add_argument("--encuadre-manual", type=str, default=None, metavar="JSON",
                        help="Punch-ins y tramos de plano cerrado elegidos a mano en el editor "
                             "visual (Fase 3d). Manda sobre lo que saque del guion y sobre los "
                             "picos de energía del audio")
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
    parser.add_argument("--abrir-editor", action="store_true",
                        help="Al terminar, abrir el editor visual v2 (f11_servidor) con esta "
                             "corrida ya cargada, en vez de tener que lanzarlo aparte. Es el "
                             "editor de verdad: B-roll, animaciones, encuadre y re-renderizar. "
                             "Queda ocupando la terminal hasta que se cierre con Ctrl+C")
    parser.add_argument("--reaplicar", action="store_true",
                        help="Reutiliza la transcripción, el corte y el plan de retención de una "
                             "corrida existente (mismo --nombre): entra directo en overlays -> "
                             "render -> audio sin volver a transcribir ni cortar. Para iterar rápido "
                             "desde el editor visual sobre ajustes de SFX/posiciones/eventos.")
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
        "sin_musica": bool(args.sin_musica),
        "sol_pip_video": bool(args.sol_pip_video),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    tomas_json = dir_trabajo / "00_tomas.json"
    if len(rutas_entrada) > 1:
        print(f"\n{'='*70}\nFASE 0: Unir {len(rutas_entrada)} planos reales\n{'='*70}")
        ruta_entrada, empalmes = unir_tomas(rutas_entrada, dir_trabajo / "00_tomas.mp4")
        tomas_json.write_text(json.dumps(empalmes), encoding="utf-8")
    else:
        ruta_entrada = rutas_entrada[0]
        tomas_json.unlink(missing_ok=True)   # una sola toma: sin empalmes que marcar

    transcripcion = dir_trabajo / "01_transcripcion.json"
    video_cortado = dir_trabajo / "02_cortado.mp4"
    plan_retencion = dir_trabajo / "03_retencion.plan.json"
    subtitulos_ass = dir_trabajo / "04_subtitulos.ass"
    eventos_overlays = dir_trabajo / "05_overlays.eventos.json"
    video_compuesto = dir_trabajo / "06_video.mp4"
    video_final = dir_trabajo / "07_FINAL.mp4"

    json_cortado = video_cortado.with_suffix(".json")

    # El presentador cambia las muletillas y los umbrales: José y su esposa no
    # hablan igual (sección 2 del plan).
    perfil = ["--presentador", args.presentador] if args.presentador else []

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
    else:
        # El hook físico (entrar al cuadro, sentarse) es silencio puro, así que
        # el corte de silencios se lo llevaba entero. Cuánto conservar sale del
        # campo `hooksegs` del guion en PANEL-PRODUCCION.html, y hay que leerlo
        # ANTES de cortar — por eso este parseo suelto en vez de esperar a
        # f13_guion, que necesita la transcripción ya recortada.
        cortar_extra = []
        if args.guion is not None:
            import f13_guion
            params = f13_guion.leer_parametros_guion(args.guion)
            if params["hooksegs"] > 0:
                cortar_extra += ["--conservar-inicio", str(params["hooksegs"])]
                print(f"\nGuion {args.guion} ({params['tipo_hook']}): se conservarán "
                      f"{params['hooksegs']}s de hook físico al inicio.")
            if params["cierresegs"] > 0:
                cortar_extra += ["--conservar-fin", str(params["cierresegs"])]
                print(f"Guion {args.guion}: se conservarán {params['cierresegs']}s de "
                      f"cierre físico al final.")
        if tomas_json.exists():
            cortar_extra += ["--tomas", str(tomas_json)]

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

    if not args.reaplicar:
        # El nombre 03_retencion.mp4 no se renderiza: --sin-render solo escribe el
        # plan JSON (03_retencion.plan.json); el render real ocurre en la fase de
        # composición de abajo, con overlays y subtítulos en la misma pasada.
        paso("FASE 3a: Análisis de retención (face tracking, punch-ins, regla de 5s)", [
            "f4_retencion.py", str(video_cortado), str(json_cortado),
            "--salida", str(dir_trabajo / "03_retencion.mp4"), "--sin-render",
            *perfil, *encuadre_guion,
        ])

    paso("FASE 2: Subtítulos ASS", [
        "f3_subtitulos.py", str(json_cortado), "--salida", str(subtitulos_ass)
    ])

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
    ])

    cmd_audio = ["f5_audio.py", str(video_compuesto), str(plan_retencion), "--salida", str(video_final),
                 "--overlays", str(eventos_overlays),
                 "--transcripcion", str(json_cortado),
                 "--hoja-sonido", str(dir_trabajo / "08_hoja-sonido.md")]
    if args.sin_musica:
        cmd_audio.append("--sin-musica")
    if args.musica:
        cmd_audio += ["--musica", args.musica]
    if args.sfx_manual:
        cmd_audio += ["--sfx-manual", args.sfx_manual]
    paso("FASE 4: Audio (música + ducking + SFX + loudnorm; el video se copia sin recomprimir)", cmd_audio)

    # Publicación: solo el final viaja a OneDrive con versión incremental si ya existe.
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

    print(f"\nVideo final (trabajo):   {video_final}")
    print(f"Video final (OneDrive):  {publicado}")
    if not args.sin_editor_visual:
        # Se aclara que este es el HTML suelto (v1: solo sonidos y posiciones).
        # Sin la aclaración parecía ser "el editor" a secas, y el que sirve para
        # trabajar —B-roll, animaciones, encuadre, re-renderizar— es el v2.
        print(f"Editor v1 (HTML suelto): {dir_trabajo / '09_editor-visual.html'}")

    if args.abrir_editor:
        print(f"\n{'='*70}\nEditor visual v2 — Ctrl+C para cerrarlo\n{'='*70}")
        subprocess.run([sys.executable, "f11_servidor.py", str(dir_trabajo)], cwd=str(AQUI))
    else:
        print(f"\nPara retocarlo:          python editor/abrir_editor.py {nombre}")
        print("                         (o «Abrir Editor DeviceShop.bat», que abre la última)")


if __name__ == "__main__":
    main()
