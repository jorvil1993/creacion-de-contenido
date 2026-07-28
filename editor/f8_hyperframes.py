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
    # `imagen` es la foto REAL recortada del producto del video: la animación de
    # sol enseña el aparato de verdad con la pantalla legible, no un e-reader
    # dibujado (§3a del plan v2).
    "anim-sol":       ["variante", "lado", "etiqueta", "imagen"],
    "anim-apps":      ["variante"],
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
    "anim-sol": 2.6,
    "anim-apps": 3.0,
}


def plantilla_de(nombre: str) -> str:
    """Nombre de animación -> nombre de la plantilla.

    Conviven dos vocabularios y hasta ahora solo se contemplaba uno. El disparo
    por palabra usa nombres cortos ("bateria", "sol") y su plantilla es
    "anim-<nombre>". Pero el guion del panel nombra la plantilla ENTERA por su
    código: H08 es "anim-apps", H07 es "stickers", H01 es "tarjeta-specs".

    Anteponiendo "anim-" a ciegas se pedía "anim-anim-apps", que no existe:
    render() devolvía None, el respaldo PIL tampoco tiene esa animación y el
    beat ANIM del guion desaparecía sin error visible. Es exactamente lo que
    pasó en la corrida `Guion-7` del 2026-07-27: `guion.animaciones.json` pedía
    anim-apps en 2.0s y en `05_overlays.eventos.json` no había ni rastro.
    """
    return nombre if nombre in PLANTILLAS else f"anim-{nombre}"


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


def preparar_imagen(ruta: Path) -> str | None:
    """Deja una imagen del proyecto al alcance de las composiciones y devuelve
    su ruta **root-relativa**, que es la única que Hyperframes resuelve bien.

    Por qué hace falta: el renderer resuelve cada composición contra la raíz del
    proyecto de plantillas (`plantillas/`), no contra el proyecto del editor.
    Los recortes viven en `<proyecto>/assets/productos/...`, fuera de ese árbol,
    así que un `<img src>` apuntando ahí carga en blanco al renderizar (la misma
    trampa que ya está documentada en plantillas/README.md para `../`).

    El nombre lleva un hash del CONTENIDO, no de la ruta: si José vuelve a
    recortar la foto, cambia el nombre, cambia la clave del caché y el clip se
    vuelve a renderizar. Con el nombre a secas el pipeline habría seguido
    reutilizando el MOV viejo — es exactamente la trampa del caché que ya se
    pagó una vez con `_huella_plantilla`.
    """
    if ruta is None:
        return None
    ruta = Path(ruta)
    if not ruta.exists():
        print(f"AVISO: no existe la imagen {ruta} — la composición usará su respaldo dibujado.",
              file=sys.stderr)
        return None

    huella = hashlib.sha1(ruta.read_bytes()).hexdigest()[:8]
    nombre = f"{ruta.stem}_{huella}{ruta.suffix.lower()}"
    destino = DIR_PLANTILLAS / "assets" / "_pipeline" / nombre
    destino.parent.mkdir(parents=True, exist_ok=True)
    if not destino.exists():
        shutil.copyfile(ruta, destino)
    return f"assets/_pipeline/{nombre}"


def inventario_animaciones() -> list:
    """Animaciones que el editor visual puede ofrecer para añadir a mano.

    El editor no crea animaciones nuevas (§6 del plan): elige entre las que
    existen. Esta es la lista, con lo que la interfaz necesita para pintarla.
    """
    import f7_animaciones

    hf = disponible()
    inv = []
    for nombre in sorted(config.ANIMACION_DURACION):
        plantilla = plantilla_de(nombre)
        tiene_html = (DIR_PLANTILLAS / "compositions" / f"{plantilla}.html").exists()
        inv.append({
            "nombre": nombre,
            "tipo": plantilla,
            "etiqueta": config.ANIMACION_ETIQUETAS.get(nombre, nombre),
            "duracion": config.ANIMACION_DURACION.get(nombre, DURACIONES.get(plantilla, 2.4)),
            "variantes": config.ANIMACION_VARIANTES.get(nombre, 3),
            "motor": "Hyperframes" if (hf and tiene_html) else "PIL",
            # Ningún navegador reproduce ProRes 4444: en el editor esto se ve
            # como bloque con su primer fotograma, no en movimiento (§3c).
            "reproducible_en_navegador": False,
            "palabras": sorted({p for p, n in config.ANIMACIONES_POR_PALABRA.items() if n == nombre}),
            "respaldo_pil": nombre in f7_animaciones.GENERADORES,
        })
    return inv


def render(plantilla: str, variables: dict = None, timeout: int = 300) -> Path | None:
    """Renderiza una plantilla a MOV con alfa. Devuelve la ruta o None si falla."""
    if plantilla not in PLANTILLAS:
        print(f"AVISO: plantilla desconocida '{plantilla}'", file=sys.stderr)
        return None
    if not disponible():
        print("AVISO: Hyperframes no disponible (falta plantillas/package.json o npx)",
              file=sys.stderr)
        return None

    # Solo las variables que la plantilla declara. Sin este filtro, una llamada
    # genérica (por ejemplo la de las animaciones del guion, que siempre manda
    # `variante`/`lado`/`etiqueta`) metía claves que la composición ignora pero
    # que SÍ entran en la clave del caché: dos peticiones equivalentes se
    # renderizaban dos veces y quedaban dos MOV idénticos en disco.
    aceptadas = set(PLANTILLAS[plantilla])
    variables = {k: v for k, v in (variables or {}).items()
                 if k in aceptadas and v not in (None, "")}
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
