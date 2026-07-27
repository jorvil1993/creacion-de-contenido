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
import shutil
import subprocess
import sys
from pathlib import Path

import config

AQUI = Path(__file__).resolve().parent


def paso(descripcion, cmd):
    print(f"\n{'='*70}\n{descripcion}\n{'='*70}")
    resultado = subprocess.run([sys.executable, *cmd], cwd=str(AQUI))
    if resultado.returncode != 0:
        print(f"ERROR en: {descripcion}", file=sys.stderr)
        sys.exit(resultado.returncode)


def main():
    parser = argparse.ArgumentParser(description="Pipeline completo: crudo -> video publicable")
    parser.add_argument("entrada", type=str)
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
    parser.add_argument("--reaplicar", action="store_true",
                        help="Reutiliza la transcripción, el corte y el plan de retención de una "
                             "corrida existente (mismo --nombre): entra directo en overlays -> "
                             "render -> audio sin volver a transcribir ni cortar. Para iterar rápido "
                             "desde el editor visual sobre ajustes de SFX/posiciones/eventos.")
    args = parser.parse_args()

    ruta_entrada = Path(args.entrada).resolve()
    if not ruta_entrada.exists():
        print(f"ERROR: no existe {ruta_entrada}", file=sys.stderr)
        sys.exit(1)

    nombre = args.nombre or ruta_entrada.stem
    dir_trabajo = config.DIR_SALIDA / nombre
    dir_trabajo.mkdir(parents=True, exist_ok=True)

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
    else:
        paso("FASE 1a: Transcripción (WhisperX)", [
            "f1_transcribir.py", str(ruta_entrada), "--salida", str(transcripcion)
        ])

        paso("FASE 1b: Corte inteligente", [
            "f2_cortar.py", str(transcripcion), str(ruta_entrada), "--salida", str(video_cortado),
            *perfil,
        ])

        # El nombre 03_retencion.mp4 no se renderiza: --sin-render solo escribe el
        # plan JSON (03_retencion.plan.json); el render real ocurre en la fase de
        # composición de abajo, con overlays y subtítulos en la misma pasada.
        paso("FASE 3a: Análisis de retención (face tracking, punch-ins, regla de 5s)", [
            "f4_retencion.py", str(video_cortado), str(json_cortado),
            "--salida", str(dir_trabajo / "03_retencion.mp4"), "--sin-render", *perfil,
        ])

    # ---- MODO DIRIGIDO POR GUION (--guion N) ------------------------------
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
        if not args.hook and res_g.get("hook"):
            args.hook = res_g["hook"]
        if not args.musica and res_g.get("musica"):
            args.musica = res_g["musica"]

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
        "--final", *perfil,
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

    # Publicación: solo el final viaja a OneDrive (sección 3 del plan).
    config.DIR_PUBLICADOS.mkdir(parents=True, exist_ok=True)
    publicado = config.DIR_PUBLICADOS / f"{nombre}.mp4"
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
        print(f"Editor visual:           {dir_trabajo / '09_editor-visual.html'}")


if __name__ == "__main__":
    main()
