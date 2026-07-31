"""
Fase 16 — Dar una corrida por terminada y liberar el disco.

Una corrida deja ~225 MB en `C:\\ai-video\\salida\\<nombre>\\`, de los cuales el
entregable son 29 MB (el `07_FINAL.mp4`, que además ya está copiado en
`salida/` de OneDrive). El resto son pasos intermedios que solo hacen falta
MIENTRAS se está editando: el compuesto sin audio, los `.mov` de los PiP ya
quemados dentro del video, las previsualizaciones, el proxy del reproductor.

Este módulo los borra, pero **solo cuando el video ya está publicado**. Es la
guarda que hace que el botón sea seguro: si el `.mp4` no aparece en
`config.DIR_PUBLICADOS`, no se borra nada y se dice por qué. Perder los
intermedios cuesta un re-render; perder el único archivo que existía no se
arregla.

Los archivos de TEXTO no se tocan (los `ajustes.*.json`, la transcripción, la
hoja de sonido, el reporte del guion). Pesan unos 50 KB entre todos —o sea,
nada— y son el registro de qué se decidió en ese video: con qué hook, qué
B-rolls, qué sonidos. Borrarlos no libera disco y sí borra el historial.

Uso:
    python editor/f16_limpiar.py --ver                 # qué se liberaría, sin tocar nada
    python editor/f16_limpiar.py Guion-7               # limpia esa corrida
    python editor/f16_limpiar.py --todas               # las que ya estén publicadas
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config

# Lo que se borra: pasos intermedios y cachés. Todo esto se regenera con un
# re-render, y ninguno es el entregable.
ARCHIVOS_PESADOS = (
    "06_video.mp4",        # compuesto sin la mezcla de audio (fase 3)
    "06_preview.mp4",      # lo mismo, a media resolución
    "07_PREVIEW.mp4",      # previsualización, nunca se publica
    "00_tomas.mp4",        # unión de varias tomas antes de cortar
    "03_retencion.mp4",    # intermedios de versiones viejas del pipeline
    "04_audio.mp4",
    "05_overlays.mp4",
    "09_editor-visual.html",   # el editor v1 autocontenido, sustituido por f11
)

CARPETAS_PESADAS = (
    "_tmp_guion",      # los .mov de los PiP, ya compuestos dentro del video
    "_tmp_overlays",
    "_editor",         # proxy del reproductor: se regenera al abrir el editor
)

# El corte crudo. Es lo que hace que `--reaplicar` cueste segundos en vez de
# un minuto largo, así que NO entra en la limpieza normal: solo con --a-fondo.
CORTE_CRUDO = "02_cortado.mp4"

# El entregable. Solo se borra si de verdad está publicado, y solo con
# --a-fondo: sin él el editor cae al corte crudo y enseña el video SIN
# subtítulos, sin B-rolls y sin encuadre, que es peor de lo que suena.
VIDEO_FINAL = "07_FINAL.mp4"


def publicados_de(nombre: str) -> list:
    """Los .mp4 que esta corrida dejó en `salida/` de OneDrive.

    `editor._ruta_versionada` publica como `<nombre>.mp4` y, si ya existía,
    `<nombre>_v2.mp4`, `_v3.mp4`… Hay que mirarlos todos: una corrida
    re-renderizada varias veces solo tiene el último con sufijo.
    """
    dir_pub = config.DIR_PUBLICADOS
    if not dir_pub.is_dir():
        return []
    salida = []
    for p in sorted(dir_pub.glob(f"{nombre}*.mp4")):
        resto = p.stem[len(nombre):]
        if resto == "" or (resto.startswith("_v") and resto[2:].isdigit()):
            salida.append(p)
    return salida


def _tamano(p: Path) -> int:
    try:
        if p.is_file():
            return p.stat().st_size
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    except OSError:
        return 0


def calcular(dir_trabajo, a_fondo: bool = False) -> dict:
    """Qué se borraría y cuánto pesa. NO toca nada."""
    dir_trabajo = Path(dir_trabajo)
    nombre = dir_trabajo.name
    pub = publicados_de(nombre)

    objetivos = []
    for n in ARCHIVOS_PESADOS:
        p = dir_trabajo / n
        if p.is_file():
            objetivos.append(p)
    for n in CARPETAS_PESADAS:
        p = dir_trabajo / n
        if p.is_dir():
            objetivos.append(p)
    if a_fondo:
        for n in (VIDEO_FINAL, CORTE_CRUDO):
            p = dir_trabajo / n
            if p.is_file():
                objetivos.append(p)

    return {
        "nombre": nombre,
        "existe": dir_trabajo.is_dir(),
        "publicado": [str(p) for p in pub],
        "esta_publicado": bool(pub),
        "objetivos": [{"ruta": str(p), "nombre": p.name, "bytes": _tamano(p),
                       "carpeta": p.is_dir()} for p in objetivos],
        "bytes": sum(_tamano(p) for p in objetivos),
        "a_fondo": a_fondo,
    }


def limpiar(dir_trabajo, a_fondo: bool = False, forzar: bool = False) -> dict:
    """Borra los intermedios. Sin `forzar`, exige que el video esté publicado.

    Esa condición es la razón de ser del módulo: mientras el video solo exista
    dentro de la carpeta de trabajo, esa carpeta NO es basura.
    """
    plan = calcular(dir_trabajo, a_fondo=a_fondo)
    if not plan["existe"]:
        return {**plan, "ok": False, "motivo": "esa corrida no existe", "liberado": 0}
    if not plan["esta_publicado"] and not forzar:
        return {**plan, "ok": False, "liberado": 0,
                "motivo": ("todavía no hay ningún video de esta corrida en salida/ de "
                           "OneDrive. Renderizá el final antes de limpiar: si se borran "
                           "los intermedios ahora, no queda ningún archivo del video.")}

    liberado = 0
    borrados, fallos = [], []
    for obj in plan["objetivos"]:
        p = Path(obj["ruta"])
        try:
            if obj["carpeta"]:
                shutil.rmtree(p)
            else:
                p.unlink()
            liberado += obj["bytes"]
            borrados.append(obj["nombre"])
        except OSError as e:
            # Lo más probable: el editor abierto tiene el mp4 bloqueado. Se
            # sigue con el resto en vez de abortar a medias.
            fallos.append(f"{obj['nombre']}: {e}")

    return {**plan, "ok": True, "liberado": liberado,
            "borrados": borrados, "fallos": fallos}


def _mb(n: int) -> str:
    return f"{n / (1024 * 1024):.1f} MB"


def main():
    ap = argparse.ArgumentParser(
        description="Libera el disco de una corrida ya publicada")
    ap.add_argument("nombre", nargs="?", help="corrida a limpiar")
    ap.add_argument("--todas", action="store_true",
                    help="todas las corridas que ya estén publicadas")
    ap.add_argument("--ver", action="store_true",
                    help="solo enseña qué se liberaría, sin borrar nada")
    ap.add_argument("--a-fondo", action="store_true",
                    help="ademas borra 07_FINAL.mp4 y 02_cortado.mp4: se pierde la "
                         "previa del render en el editor y --reaplicar")
    ap.add_argument("--forzar", action="store_true",
                    help="limpia aunque el video no esté publicado (peligroso)")
    args = ap.parse_args()

    if args.nombre:
        dirs = [config.DIR_SALIDA / args.nombre]
    elif args.todas or args.ver:
        # Mirar no borra nada, así que `--ver` a secas ya vale para todas. Para
        # BORRAR sí hay que decir explícitamente qué: un `--todas` de más no
        # puede salir de escribir un comando a medias.
        dirs = sorted(d for d in config.DIR_SALIDA.iterdir() if d.is_dir())
    else:
        ap.error("hay que decir un nombre de corrida o --todas "
                 "(o --ver, que enseña todas sin tocar nada)")

    total = 0
    for d in dirs:
        if args.ver:
            plan = calcular(d, a_fondo=args.a_fondo)
            if not plan["objetivos"]:
                continue
            estado = "publicado" if plan["esta_publicado"] else "SIN PUBLICAR (no se tocaría)"
            print(f"\n{d.name}  [{estado}]  liberaría {_mb(plan['bytes'])}")
            for o in plan["objetivos"]:
                print(f"    {_mb(o['bytes']):>10}  {o['nombre']}{'/' if o['carpeta'] else ''}")
            if plan["esta_publicado"]:
                total += plan["bytes"]
        else:
            r = limpiar(d, a_fondo=args.a_fondo, forzar=args.forzar)
            if not r["ok"]:
                print(f"{d.name}: {r['motivo']}")
                continue
            total += r["liberado"]
            print(f"{d.name}: {_mb(r['liberado'])} liberados ({len(r['borrados'])} elementos)")
            for f in r["fallos"]:
                print(f"    no se pudo borrar {f}")

    print(f"\n{'Se liberarían' if args.ver else 'Liberados'}: {_mb(total)}")
    if args.ver:
        print("Nada se ha tocado. Quitá --ver para hacerlo de verdad.")


if __name__ == "__main__":
    main()
