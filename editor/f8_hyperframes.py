"""
Puente con Hyperframes: renderiza las plantillas de `plantillas/` como clips
MOV con canal alfa, listos para componer sobre el video.

Por qué existe: las animaciones dibujadas con PIL (`f7_animaciones.py`) son
funcionales pero pobres — sin tipografía real, sin easing de GSAP, sin sombras
ni gradientes. Las plantillas de Hyperframes sí tienen todo eso.

Clave para que los videos NO salgan todos iguales: cada render recibe
**variables tomadas del guion del video** (producto, specs, textos), así que
dos videos distintos producen clips distintos. El caché es por contenido: si
las variables cambian, se vuelve a renderizar; si son idénticas, se reutiliza.

Formato: **MOV (ProRes 4444)**, no webm. La sesión B verificó a nivel de píxel
que el alfa de VP9 no sobrevivía al decodificarlo con este ffmpeg, y el de
ProRes sí (ver plantillas/README.md).

Uso:
    python f8_hyperframes.py --lista
    python f8_hyperframes.py --plantilla tarjeta-specs --vars '{"producto":"Kindle Paperwhite"}'
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import config

DIR_PLANTILLAS = config.RAIZ_PROYECTO / "plantillas"
DIR_CACHE = config.RAIZ_AI_VIDEO / "cache_hyperframes"

# Plantilla -> variables que acepta (ver plantillas/README.md)
PLANTILLAS = {
    "banner-hook":    ["texto"],
    "pip-producto":   ["imagen", "etiqueta"],
    "tarjeta-specs":  ["producto", "spec1_label", "spec1_valor",
                       "spec2_label", "spec2_valor", "spec3_label", "spec3_valor"],
    "comparativa":    ["modeloA", "specA1", "specA2", "specA3",
                       "modeloB", "specB1", "specB2", "specB3"],
    "stickers":       ["tipo"],
    "tarjeta-cta":    ["mensaje", "whatsapp", "handle", "eco"],
    # Animaciones — sustituyen a las de PIL (f7_animaciones.py), que se ven
    # pobres al lado de estas: sin easing, sin tipografía, sin sombras.
    # `variante` da la variación determinista por video (semilla del nombre de
    # archivo), `lado` esquiva el rostro con el track que ya calcula f4.
    "anim-bateria":   ["variante", "lado", "etiqueta"],
    "anim-splash":    ["variante", "lado", "etiqueta"],
    "anim-moto":      ["variante", "etiqueta"],
    "anim-sol":       ["variante", "lado", "etiqueta"],
}

# Duración de cada composición, tomada del `data-duration` de su HTML. El
# pipeline la necesita para saber cuánto dura el clip sin abrir el archivo.
DURACIONES = {
    "banner-hook": 3.2,
    "pip-producto": 4.0,
    "tarjeta-specs": 4.5,
    "comparativa": 5.0,
    "stickers": 2.5,
    "tarjeta-cta": 6.5,
    "anim-bateria": 2.4,
    "anim-splash": 2.2,
    "anim-moto": 2.6,
    "anim-sol": 2.4,
}


def disponible() -> bool:
    """¿Se puede renderizar? Necesita el proyecto y npx en el PATH."""
    return (DIR_PLANTILLAS / "package.json").exists() and shutil.which("npx") is not None


def _huella_plantilla(plantilla: str) -> str:
    """Hash del HTML de la composición + la hoja de estilos compartida.

    Sin esto el caché era una trampa: la clave solo miraba las variables, así
    que al editar el HTML de una plantilla el pipeline seguía reutilizando el
    MOV viejo y el cambio "no se veía". Pasó de verdad al mover la tarjeta de
    specs a la franja superior: se re-renderizó en 0.0s y salió igual que antes.
    """
    h = hashlib.sha1()
    for ruta in (DIR_PLANTILLAS / "compositions" / f"{plantilla}.html",
                 DIR_PLANTILLAS / "compositions" / "_shared.css"):
        if ruta.exists():
            h.update(ruta.read_bytes())
    return h.hexdigest()[:8]


def _clave(plantilla: str, variables: dict) -> str:
    """Huella del contenido: mismas variables y mismo HTML -> mismo clip."""
    crudo = (plantilla + "|" + json.dumps(variables, sort_keys=True, ensure_ascii=False)
             + "|" + _huella_plantilla(plantilla))
    return hashlib.sha1(crudo.encode("utf-8")).hexdigest()[:16]


def render(plantilla: str, variables: dict = None, timeout: int = 300) -> Path | None:
    """Renderiza una plantilla a MOV con alfa. Devuelve la ruta o None si falla."""
    if plantilla not in PLANTILLAS:
        print(f"AVISO: plantilla desconocida '{plantilla}'", file=sys.stderr)
        return None
    if not disponible():
        print("AVISO: Hyperframes no disponible (falta plantillas/package.json o npx)",
              file=sys.stderr)
        return None

    variables = {k: v for k, v in (variables or {}).items() if v not in (None, "")}
    DIR_CACHE.mkdir(parents=True, exist_ok=True)
    destino = DIR_CACHE / f"{plantilla}_{_clave(plantilla, variables)}.mov"
    if destino.exists() and destino.stat().st_size > 1024:
        return destino                                  # ya renderizado con estas variables

    cmd = ["npx", "hyperframes", "render",
           "-c", f"compositions/{plantilla}.html",
           "--format", "mov", "-q", "high",
           "-o", str(destino)]
    if variables:
        cmd += ["--variables", json.dumps(variables, ensure_ascii=False)]

    try:
        r = subprocess.run(cmd, cwd=str(DIR_PLANTILLAS), capture_output=True,
                           text=True, timeout=timeout, shell=True)
    except subprocess.TimeoutExpired:
        print(f"AVISO: render de '{plantilla}' excedió {timeout}s", file=sys.stderr)
        return None

    if r.returncode != 0 or not destino.exists():
        cola = (r.stderr or r.stdout or "")[-1200:]
        print(f"AVISO: falló el render de '{plantilla}':\n{cola}", file=sys.stderr)
        return None
    return destino


def limpiar_cache():
    if DIR_CACHE.exists():
        shutil.rmtree(DIR_CACHE)
        print(f"Caché borrado: {DIR_CACHE}")


def main():
    ap = argparse.ArgumentParser(description="Renderiza plantillas de Hyperframes")
    ap.add_argument("--lista", action="store_true")
    ap.add_argument("--plantilla", type=str, default=None)
    ap.add_argument("--vars", type=str, default=None, help="JSON con las variables")
    ap.add_argument("--limpiar-cache", action="store_true")
    args = ap.parse_args()

    if args.limpiar_cache:
        limpiar_cache()
        return
    if args.lista or not args.plantilla:
        print(f"Hyperframes disponible: {disponible()}")
        print(f"Proyecto: {DIR_PLANTILLAS}")
        print(f"Caché:    {DIR_CACHE}\n")
        for p, v in PLANTILLAS.items():
            print(f"  {p:<16} variables: {', '.join(v)}")
        return

    variables = json.loads(args.vars) if args.vars else {}
    ruta = render(args.plantilla, variables)
    print(f"-> {ruta}" if ruta else "-> falló")


if __name__ == "__main__":
    main()
