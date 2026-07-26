"""
Catálogo de assets visuales — la matriz que conecta "lo que José dice" con
"qué imagen o video mostrar".

Escanea `contexto/fotos y videos/` (la biblioteca real de la web, que NO se
toca ni se reorganiza) y genera:

  - contexto/catalogo-assets.json  -> lo que consume el pipeline
  - contexto/catalogo-assets.md    -> matriz legible para revisar y etiquetar a mano

Lo que se infiere solo: producto, tipo, orientación, tipo de fondo, dimensiones.
Lo que se etiqueta a mano: las etiquetas de CONTEXTO (#agua #cama #noche #regalo…),
que son las que deciden cuándo entra cada imagen en el video. El escáner respeta
lo que ya escribiste: si vuelves a correrlo, no pisa las etiquetas manuales.

Uso:
    python catalogo_assets.py                # escanea y actualiza el catálogo
    python catalogo_assets.py --solo-nuevos  # lista lo que falta etiquetar
"""
import argparse
import json
import subprocess
from pathlib import Path

from PIL import Image

import config

DIR_BIBLIOTECA = config.DIR_CONTEXTO / "fotos y videos"
RUTA_JSON = config.DIR_CONTEXTO / "catalogo-assets.json"
RUTA_MD = config.DIR_CONTEXTO / "catalogo-assets.md"

EXT_IMAGEN = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
EXT_VIDEO = {".mp4", ".mov", ".webm"}

# Carpeta de primer nivel -> tipo de asset
TIPO_POR_CARPETA = {
    "fotos-dispósitivos": "producto",
    "fotos-dispositivos": "producto",
    "fotos-fundas": "funda",
    "fotos fundas": "funda",
    "fotos-accesorios": "accesorio",
    "pagina amazon": "captura-web",
    "pagina kobo": "captura-web",
    "RESEÑAS": "resena",
    "videos": "video",
}

# Usos sugeridos por tipo. El pipeline los lee para saber dónde encaja cada asset.
USOS_POR_TIPO = {
    "producto": ["pip", "hero"],
    "funda": ["pip", "detalle"],
    "accesorio": ["pip", "detalle"],
    "captura-web": ["prueba-social"],
    "resena": ["prueba-social"],
    "video": ["broll"],
    "caja": ["pip", "confianza"],
}


def _sin_acentos(t: str) -> str:
    tabla = str.maketrans("áéíóúÁÉÍÓÚñÑ", "aeiouAEIOUnN")
    return t.translate(tabla)


def _slug(t: str) -> str:
    t = _sin_acentos(t.lower().strip())
    return "-".join(p for p in t.replace("_", "-").replace(" ", "-").split("-") if p)


def _detectar_fondo(ruta: Path) -> str:
    """transparente | blanco | ambiente

    'blanco' = foto de catálogo recortada sobre fondo liso (sirve para PiP tras
    pasarle rembg). 'ambiente' = foto en contexto real (sirve tal cual como
    inserto o fondo).
    """
    try:
        with Image.open(ruta) as im:
            if im.mode in ("RGBA", "LA") and im.getchannel("A").getextrema()[0] < 250:
                return "transparente"
            im = im.convert("RGB")
            w, h = im.size
            muestras = [
                im.getpixel((2, 2)), im.getpixel((w - 3, 2)),
                im.getpixel((2, h - 3)), im.getpixel((w - 3, h - 3)),
                im.getpixel((w // 2, 2)), im.getpixel((w // 2, h - 3)),
            ]
            if all(min(p) > 235 for p in muestras):
                return "blanco"
            return "ambiente"
    except Exception:
        return "desconocido"


def _dimensiones_video(ruta: Path):
    cmd = ["ffprobe", "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=width,height:format=duration",
           "-of", "json", str(ruta)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, check=True)
        d = json.loads(r.stdout)
        s = d["streams"][0]
        return s["width"], s["height"], round(float(d["format"]["duration"]), 1)
    except Exception:
        return None, None, None


def _orientacion(w, h) -> str:
    if not w or not h:
        return "desconocida"
    if h > w * 1.2:
        return "vertical"
    if w > h * 1.2:
        return "horizontal"
    return "cuadrada"


def escanear() -> list:
    assets = []
    if not DIR_BIBLIOTECA.exists():
        print(f"AVISO: no existe {DIR_BIBLIOTECA}")
        return assets

    for ruta in sorted(DIR_BIBLIOTECA.rglob("*")):
        if not ruta.is_file():
            continue
        ext = ruta.suffix.lower()
        if ext not in EXT_IMAGEN and ext not in EXT_VIDEO:
            continue

        partes = ruta.relative_to(DIR_BIBLIOTECA).parts
        carpeta_raiz = partes[0]
        tipo = TIPO_POR_CARPETA.get(carpeta_raiz, "otro")

        # "videos/en cajas/basic" -> caja; el subnivel manda sobre el genérico
        ruta_txt = _sin_acentos(str(ruta).lower())
        if "en cajas" in ruta_txt or "caja" in ruta_txt:
            tipo = "caja"

        # El producto suele ser la carpeta de segundo nivel
        producto = _slug(partes[1]) if len(partes) > 2 else _slug(carpeta_raiz)
        # El color, cuando existe, es el tercer nivel (estructura de fotos-fundas)
        color = _slug(partes[2]) if len(partes) > 3 else None

        if ext in EXT_VIDEO:
            w, h, dur = _dimensiones_video(ruta)
            fondo = "ambiente"
        else:
            try:
                with Image.open(ruta) as im:
                    w, h = im.size
            except Exception:
                w = h = None
            dur = None
            fondo = _detectar_fondo(ruta)

        assets.append({
            "id": _slug(str(ruta.relative_to(DIR_BIBLIOTECA).with_suffix(""))),
            "ruta": str(ruta.relative_to(config.RAIZ_PROYECTO)).replace("\\", "/"),
            "producto": producto,
            "color": color,
            "tipo": tipo,
            "medio": "video" if ext in EXT_VIDEO else "imagen",
            "orientacion": _orientacion(w, h),
            "dimensiones": [w, h] if w else None,
            "duracion_s": dur,
            "fondo": fondo,
            "usos": USOS_POR_TIPO.get(tipo, []),
            "origen": "propio",
            "tags": [],          # <- se llenan a mano; el escáner nunca las pisa
            "revisado": False,
        })
    return assets


# Reglas de etiquetado automático. Se infiere de la ruta y del tipo detectado.
# Son un punto de partida para corregir a mano, no la verdad final: el escáner
# no puede saber si una foto se tomó en una piscina o si el fondo es una cama.
# (subcadena en la ruta, etiquetas, tipos a los que aplica o None = todos)
#
# La distinción por tipo importa: una FUNDA de Paperwhite no es resistente al
# agua — lo es el dispositivo. Sin este filtro, buscar "resistente al agua"
# habría traído la foto de una funda.
REGLAS_TAGS = [
    ("paperwhite",  ["#paperwhite"],                       None),
    ("paperwhite",  ["#agua"],                             {"producto", "video", "caja"}),
    ("colorsoft",   ["#colorsoft", "#color"],              None),
    ("scribe",      ["#scribe"],                           None),
    ("scribe",      ["#escribir", "#stylus"],              {"producto", "video", "caja"}),
    ("kids",        ["#ninos", "#regalo"],                 None),
    ("basic",       ["#basic", "#economico"],              None),
    ("kobo",        ["#kobo"],                             None),
    ("libra",       ["#botones"],                          {"producto", "video", "caja"}),
    ("clara",       ["#compacto"],                         {"producto", "video", "caja"}),
    ("stylus",      ["#stylus", "#escribir"],              None),
    ("protector",   ["#protector", "#pantalla"],           None),
    ("brazo",       ["#soporte", "#mano"],                 None),
    ("cargador",    ["#carga", "#bateria"],                None),
    ("pasa pagina", ["#pasapaginas", "#lectura"],          None),
    ("varios model", ["#comparativa"],                     None),
    ("outlet",      ["#outlet", "#honestidad"],            None),
    ("bolsita",     ["#viaje", "#transporte"],             None),
    ("transparente", ["#transparente"],                    None),
    # El LEEME de fotos-fundas avisa que varias fotos de proveedor traen marca
    # de agua. Sirven para la web pero NO para video: se vería la marca de otro.
    ("watermark",   ["#marca-de-agua", "#no-usar-en-video"], None),
    ("marca de agua", ["#marca-de-agua", "#no-usar-en-video"], None),
]

# Etiquetas que descalifican un asset para aparecer en video
TAGS_EXCLUIDOS_VIDEO = {"#no-usar-en-video"}

TAGS_POR_TIPO = {
    "caja":        ["#caja", "#sellado", "#confianza"],
    "video":       ["#broll"],
    "captura-web": ["#specs", "#prueba-social"],
    "resena":      ["#resena", "#prueba-social"],
    "funda":       ["#funda", "#proteccion"],
    "accesorio":   ["#accesorio"],
    "producto":    ["#producto"],
}


def sugerir_tags(a: dict) -> list:
    """Etiquetas inferidas de la ruta, el tipo y las propiedades detectadas."""
    ruta = _sin_acentos(a["ruta"].lower())
    tags = list(TAGS_POR_TIPO.get(a["tipo"], []))

    for clave, etiquetas, tipos in REGLAS_TAGS:
        if clave in ruta and (tipos is None or a["tipo"] in tipos):
            tags += etiquetas

    if a["color"]:
        tags.append(f"#color-{a['color']}")

    # Propiedades técnicas útiles para decidir dónde encaja el asset
    if a["fondo"] == "blanco":
        tags.append("#catalogo")        # candidato a rembg para PiP
    elif a["fondo"] == "transparente":
        tags.append("#sin-fondo")       # listo para PiP tal cual
    elif a["fondo"] == "ambiente":
        tags.append("#ambiente")        # sirve como escena, no solo como producto

    if a["orientacion"] == "vertical":
        tags.append("#vertical")        # puede ir a pantalla completa sin relleno

    # dedup conservando orden
    vistos, salida = set(), []
    for t in tags:
        if t not in vistos:
            vistos.add(t)
            salida.append(t)
    return salida


def fusionar(nuevos: list, previos: list) -> list:
    """Conserva el trabajo manual (tags, usos editados, revisado) al reescanear."""
    por_id = {a["id"]: a for a in previos}
    fusionados = []
    for a in nuevos:
        viejo = por_id.get(a["id"])
        if viejo:
            a["tags"] = viejo.get("tags", [])
            a["revisado"] = viejo.get("revisado", False)
            if viejo.get("usos"):
                a["usos"] = viejo["usos"]
            if viejo.get("origen"):
                a["origen"] = viejo["origen"]
        fusionados.append(a)
    return fusionados


def escribir_markdown(assets: list):
    por_producto = {}
    for a in assets:
        por_producto.setdefault(a["producto"], []).append(a)

    sin_tags = [a for a in assets if not a["tags"]]

    lineas = [
        "# Matriz de assets visuales — DeviceShop",
        "",
        "Generado por `editor/catalogo_assets.py`. **No editar a mano este archivo**:",
        "las etiquetas se editan en `catalogo-assets.json` (campo `tags`) y se vuelve",
        "a generar. El escáner respeta lo que ya etiquetaste.",
        "",
        "## Cómo etiquetar",
        "",
        "Las etiquetas de contexto son lo que decide **cuándo** entra cada imagen en el",
        "video. Cuando José dice una palabra que coincide con una etiqueta, el pipeline",
        "puede mostrar ese asset. Ejemplos de vocabulario sugerido:",
        "",
        "| Etiqueta | Cuándo entra |",
        "|---|---|",
        "| `#agua` `#piscina` `#tina` | \"resistente al agua\", \"en la piscina\" |",
        "| `#sol` `#exterior` | \"bajo el sol\", \"sin reflejos\" |",
        "| `#cama` `#noche` `#oscuridad` | \"antes de dormir\", \"luz regulable\" |",
        "| `#mano` `#tamano` `#bolsillo` | \"liviano\", \"cabe en el bolsillo\" |",
        "| `#caja` `#sellado` | \"nuevo y sellado\", \"en su caja\" |",
        "| `#regalo` | \"el regalo perfecto\" |",
        "| `#pantalla` `#lectura` | \"pantalla como papel\", \"e-ink\" |",
        "| `#envio` `#bolivia` | \"hacemos envíos\" |",
        "| `#comparativa` | \"contra tu celular\", \"cuál te conviene\" |",
        "",
        "## Resumen",
        "",
        f"- **{len(assets)}** assets indexados",
        f"- **{sum(1 for a in assets if a['medio'] == 'video')}** videos (B-roll potencial)",
        f"- **{sum(1 for a in assets if a['fondo'] == 'blanco')}** con fondo blanco (candidatas a rembg para PiP)",
        f"- **{sum(1 for a in assets if a['fondo'] == 'transparente')}** ya con transparencia",
        f"- **{len(sin_tags)}** sin etiquetar todavía",
        "",
    ]

    for producto in sorted(por_producto):
        grupo = por_producto[producto]
        lineas += [f"## {producto}", "",
                   "| archivo | tipo | color | orient. | fondo | tags |",
                   "|---|---|---|---|---|---|"]
        for a in sorted(grupo, key=lambda x: x["ruta"]):
            nombre = Path(a["ruta"]).name
            tags = " ".join(a["tags"]) if a["tags"] else "—"
            lineas.append(
                f"| `{nombre}` | {a['tipo']} | {a['color'] or '—'} | "
                f"{a['orientacion']} | {a['fondo']} | {tags} |"
            )
        lineas.append("")

    RUTA_MD.write_text("\n".join(lineas), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Indexa la biblioteca de fotos y videos")
    ap.add_argument("--solo-nuevos", action="store_true",
                    help="Solo listar los assets que aún no tienen etiquetas")
    ap.add_argument("--sugerir-tags", action="store_true",
                    help="Rellena las etiquetas vacías con las inferidas de la ruta y el tipo. "
                         "No pisa las que ya estén escritas ni las marcadas como revisadas.")
    args = ap.parse_args()

    previos = []
    if RUTA_JSON.exists():
        previos = json.loads(RUTA_JSON.read_text(encoding="utf-8")).get("assets", [])

    assets = fusionar(escanear(), previos)

    if args.sugerir_tags:
        rellenados = 0
        for a in assets:
            if not a["tags"] and not a["revisado"]:
                a["tags"] = sugerir_tags(a)
                rellenados += 1
        print(f"Etiquetas sugeridas para {rellenados} assets "
              f"(no se tocaron los que ya tenían o estaban revisados).")

    if args.solo_nuevos:
        faltan = [a for a in assets if not a["tags"]]
        print(f"{len(faltan)} assets sin etiquetar:")
        for a in faltan[:40]:
            print(f"  {a['producto']:<32} {Path(a['ruta']).name}")
        if len(faltan) > 40:
            print(f"  ... y {len(faltan) - 40} más")
        return

    RUTA_JSON.write_text(
        json.dumps({"version": 1, "assets": assets}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    escribir_markdown(assets)

    print(f"Assets indexados: {len(assets)}")
    print(f"  videos:            {sum(1 for a in assets if a['medio'] == 'video')}")
    print(f"  fondo blanco:      {sum(1 for a in assets if a['fondo'] == 'blanco')} (candidatos a rembg)")
    print(f"  con transparencia: {sum(1 for a in assets if a['fondo'] == 'transparente')}")
    print(f"  sin etiquetar:     {sum(1 for a in assets if not a['tags'])}")
    print(f"\n  {RUTA_JSON}")
    print(f"  {RUTA_MD}")


if __name__ == "__main__":
    main()
