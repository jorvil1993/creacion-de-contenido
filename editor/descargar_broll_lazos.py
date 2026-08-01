"""
Descarga el B-roll vertical de Lazos desde Pixabay.

Por qué metraje real y no generado: los mejores planos de estos guiones son
personas en situaciones cotidianas, y ese es justo el encuadre que un modelo
local de video NO da limpio — se parece a un vídeo narrado y el modelo le
quema subtítulos falsos encima (medido en `contexto/PROMPT-ARREGLAR-BROLL-LTX.md`).
Un banco de stock no tiene ese problema, es instantáneo y sale gratis.

Licencia: Pixabay Content License — uso comercial libre, sin atribución
obligatoria. Es la misma con la que se armó la librería de música
(`assets/musica/LIBRERIA-RECOMENDADA.md`), así que el criterio ya estaba
sentado en el proyecto. Se guarda igualmente la URL de origen de cada clip en
el catálogo, para poder comprobar la licencia de cualquiera más adelante.

Se baja la variante `_medium` (1440x2560): la salida es 1080x1920, así que
sobra resolución para reencuadrar o acercarse sin perder nitidez. La `_large`
(2160x3840) pesa el doble y no aporta nada a esta salida.

Uso:
    python editor/descargar_broll_lazos.py            # todos los que falten
    python editor/descargar_broll_lazos.py --solo L17 # uno concreto
    python editor/descargar_broll_lazos.py --listar   # qué hay y qué falta
"""
import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# La consola de Windows es cp1252 y cualquier símbolo fuera de esa tabla
# (una flecha, un tic) tumba el script con UnicodeEncodeError en medio de una
# descarga larga. Mismo motivo por el que test_regresion.py hace esto.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import config

DIR_BROLL = config.DIR_ASSETS / "marcas" / "lazos" / "broll"
RUTA_CATALOGO = DIR_BROLL / "catalogo.json"
DIR_CONTACTOS = DIR_BROLL / "_contactos"
RUTA_CANDIDATOS = DIR_CONTACTOS / "candidatos.json"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

# Pausa entre peticiones. No es paranoia: es un banco gratuito y bajar 24 clips
# a toda velocidad es la forma de que corten el acceso a todo el mundo.
PAUSA_S = 2.5

# Los 24 conceptos del panel de Lazos -> qué buscar. Las búsquedas van en
# INGLÉS porque el catálogo de Pixabay está etiquetado en inglés; buscar en
# español devuelve una fracción de los resultados.
#
# `alt` es una segunda búsqueda para cuando la primera no da nada vertical.
CONCEPTOS = {
    "L01": {"desc": "Techo de un cuarto a oscuras desde la cama",
            "q": "dark bedroom night", "px": "woman lying in bed at night", "alt": "insomnia night bed"},
    "L02": {"desc": "Mano dejando el celular en la cama",
            "q": "hand phone bed night", "px": "hand holding phone in bed", "alt": "smartphone dark hand"},
    "L03": {"desc": "Persona sola entre gente",
            "q": "sad woman window", "px": "sad woman looking out window", "alt": "lonely man thinking"},
    "L04": {"desc": "Pantalla de contactos sin abrir",
            "q": "texting message phone", "px": "person scrolling phone screen", "alt": "using smartphone night"},
    "L05": {"desc": "Habitación vacía con luz de tarde",
            "q": "empty room window light", "px": "empty room sunlight window", "alt": "sunlight interior floor"},
    "L06": {"desc": "Objeto de logro cubierto de polvo",
            "q": "old objects dust", "px": "dusty old objects shelf", "alt": "forgotten box memories"},
    "L07": {"desc": "Espejo, ensayar una sonrisa",
            "q": "woman mirror reflection", "px": "woman looking at mirror", "alt": "man looking mirror"},
    "L08": {"desc": "Manos secándose la cara",
            "q": "washing face water", "px": "washing face in sink", "alt": "hands face towel"},
    "L09": {"desc": "Escritorio con libros y café",
            "q": "notebook pen desk", "px": "notebook and books on desk", "alt": "books stack table"},
    "L10": {"desc": "Zapatillas sin usar junto a la puerta",
            "q": "sneakers floor", "px": "sneakers on floor", "alt": "sport shoes gym"},
    "L11": {"desc": "Pulgar deslizando sin parar",
            "q": "finger scrolling screen", "px": "finger scrolling smartphone", "alt": "phone addiction hand"},
    "L12": {"desc": "Auriculares en el bus, mirada perdida",
            "q": "headphones window travel", "px": "headphones looking out bus window", "alt": "bus window city"},
    "L13": {"desc": "Silla vacía en una mesa puesta",
            "q": "empty chair table", "px": "empty chair by window", "alt": "empty dining table"},
    "L14": {"desc": "Ropa colgada que ya nadie usa",
            "q": "clothes hanging wardrobe", "px": "clothes hanging in closet", "alt": "closet clothes"},
    "L15": {"desc": "Cruce de calles de noche",
            "q": "night city street walking", "px": "walking alone city street night", "alt": "rain street lights night"},
    "L16": {"desc": "Mano sobre el picaporte",
            "q": "hand door handle", "px": "hand on door handle", "alt": "opening door light"},
    "L17": {"desc": "Mano hundiéndose bajo el agua",
            "q": "hand underwater", "px": "hand underwater reaching", "alt": "underwater reaching light"},
    "L18": {"desc": "Dos manos que se agarran",
            "q": "helping hand", "px": "two hands holding each other", "alt": "two hands holding together"},
    "L19": {"desc": "Primera luz por la ventana",
            "q": "sunlight window curtain", "px": "sunlight through window morning", "alt": "morning light room"},
    "L20": {"desc": "Manos abiertas recibiendo luz",
            "q": "praying hands light", "px": "open hands praying", "alt": "open hands sunlight"},
    "L21": {"desc": "Círculo de personas",
            "q": "people holding hands group", "px": "group of people holding hands", "alt": "friends together support"},
    "L22": {"desc": "Sillas en círculo, sala vacía",
            "q": "empty chairs hall", "px": "empty chairs in a room", "alt": "church empty pews"},
    "L23": {"desc": "Vela encendida en penumbra",
            "q": "candle flame dark", "px": "candle flame in the dark", "alt": "candle light prayer"},
    "L24": {"desc": "Camino al amanecer",
            "q": "forest path sunrise", "px": "path through forest at sunrise", "alt": "walking path nature morning"},
}


# Solo con User-Agent la búsqueda devuelve 403: el filtro mira también estas
# cabeceras, que cualquier navegador manda y urllib no. Con las cinco pasa.
CABECERAS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}


def _pedir(url: str, binario: bool = False, timeout: int = 60, cabeceras: dict = None):
    req = urllib.request.Request(url, headers=cabeceras or CABECERAS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        datos = r.read()
    return datos if binario else datos.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------
# Pexels — la fuente buena para material humano
# --------------------------------------------------------------------------
# Pixabay sirve para naturaleza, ambientes y objetos, pero para "una persona
# sintiendo algo concreto" no tiene fondo: «hand underwater» devolvió acuarios
# y medusas, y «ropa colgada» un conejo con gafas. En Pexels esa misma búsqueda
# da 8.000 resultados de gente real filmada. Se usa su API oficial, no el HTML.

RUTA_KEY = Path(r"C:\ai-video\secretos\pexels.key")


def _key_pexels() -> str:
    """La clave de Pexels, de la variable de entorno o del archivo local.

    Vive FUERA del repositorio a propósito: es una credencial, y este proyecto
    está en OneDrive y en git. `.gitignore` cubre además `*.key` y `secretos/`
    por si alguna copia acaba dentro.
    """
    import os
    k = os.environ.get("PEXELS_API_KEY", "").strip()
    if k:
        return k
    if RUTA_KEY.exists():
        return RUTA_KEY.read_text(encoding="utf-8").strip()
    return ""


def buscar_pexels(consulta: str, n: int = 8) -> list:
    """Candidatos verticales de Pexels. Devuelve dicts con lo necesario."""
    key = _key_pexels()
    if not key:
        print("    falta la clave de Pexels (PEXELS_API_KEY o "
              f"{RUTA_KEY})")
        return []
    url = ("https://api.pexels.com/videos/search?query="
           + urllib.parse.quote(consulta)
           + f"&orientation=portrait&per_page={n}&size=medium")
    # El User-Agent hace falta aunque la petición lleve clave: sin él urllib
    # manda `Python-urllib/3.12` y la API responde 403, mientras que la misma
    # llamada con curl pasa. Se pierde media hora buscándolo en la clave.
    try:
        datos = json.loads(_pedir(url, timeout=30,
                                  cabeceras={"Authorization": key, "User-Agent": UA}))
    except Exception as e:
        print(f"    no se pudo buscar «{consulta}» en Pexels: {e}")
        return []

    salida = []
    for v in datos.get("videos", []):
        # De todos los archivos del clip, el más pequeño que llegue a 1080 de
        # ancho: la salida es 1080x1920 y bajarse un 4K de 80 MB para escalarlo
        # a la mitad es tirar disco y tiempo.
        aptos = [f for f in v.get("video_files", [])
                 if (f.get("width") or 0) >= config.ANCHO
                 and (f.get("height") or 0) > (f.get("width") or 0)]
        if not aptos:
            continue
        mejor = min(aptos, key=lambda f: f["width"])
        salida.append({
            "id": v["id"],
            "pagina": v.get("url", ""),
            "thumb": v.get("image", ""),
            "video": mejor["link"],
            "ancho": mejor["width"], "alto": mejor["height"],
            "duracion": v.get("duration", 0),
            "autor": (v.get("user") or {}).get("name", ""),
        })
    return salida


def buscar(consulta: str) -> list:
    """Candidatos verticales para una búsqueda, del más relevante al menos.

    Se lee la página pública de resultados y se sacan los identificadores. La
    URL del CDN se reconstruye a partir del `_tiny` que la página ya expone:
    misma ruta, otra variante.

    Devuelve la base del CDN, que sirve tanto para la miniatura (`_tiny.jpg`,
    unos 30 KB) como para el vídeo (`_medium.mp4`, decenas de MB). Esa
    diferencia es la que permite MIRAR antes de bajar: una búsqueda floja
    devuelve un cisne donde pedías un trofeo con polvo, y con vídeo directo eso
    cuesta 30 MB por error.
    """
    url = ("https://pixabay.com/videos/search/"
           + urllib.parse.quote(consulta)
           + "/?orientation=vertical")
    try:
        html = _pedir(url, timeout=30)
    except Exception as e:
        print(f"    no se pudo buscar «{consulta}»: {e}")
        return []

    vistos, salida = set(), []
    for m in re.finditer(r'https://cdn\.pixabay\.com/video/([\d/]+)/([\w-]+)_tiny\.(?:mp4|jpg)', html):
        base = f"https://cdn.pixabay.com/video/{m.group(1)}/{m.group(2)}"
        if base in vistos:
            continue
        vistos.add(base)
        salida.append(base)
    return salida


def hoja_pexels(cid: str, info: dict, n: int = 8) -> dict:
    """Hoja de contactos con candidatos de Pexels."""
    from PIL import Image, ImageDraw

    DIR_CONTACTOS.mkdir(parents=True, exist_ok=True)
    cands = []
    for consulta in (info.get("px") or info["q"], info.get("alt")):
        if not consulta:
            continue
        cands += buscar_pexels(consulta, n)
        time.sleep(1.0)
        if len(cands) >= n:
            break
    vistos, unicos = set(), []
    for c in cands:
        if c["id"] not in vistos:
            vistos.add(c["id"])
            unicos.append(c)
    unicos = unicos[:n]
    if not unicos:
        print(f"  {cid}  sin candidatos en Pexels")
        return {}

    ANCHO_M, ALTO_M = 200, 356
    hoja = Image.new("RGB", (ANCHO_M * len(unicos), ALTO_M + 26), (16, 22, 32))
    d = ImageDraw.Draw(hoja)
    for i, c in enumerate(unicos):
        x = i * ANCHO_M
        try:
            crudo = _pedir(c["thumb"], binario=True, timeout=45)
            tmp = DIR_CONTACTOS / f"_{cid}_{i}.jpg"
            tmp.write_bytes(crudo)
            im = Image.open(tmp).convert("RGB")
            im.thumbnail((ANCHO_M - 4, ALTO_M - 4))
            hoja.paste(im, (x + 2, 24))
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        d.text((x + 6, 6), f"{cid}#{i}", fill=(255, 210, 80))
        time.sleep(0.25)
    destino = DIR_CONTACTOS / f"{cid}.png"
    hoja.save(destino)
    print(f"  {cid}  {len(unicos)} candidatos -> {destino.name}")
    return {"fuente": "pexels", "candidatos": unicos}


def bajar_pexels(cid: str, cand: dict, info: dict, catalogo: dict) -> bool:
    """Baja un candidato de Pexels ya elegido."""
    destino = DIR_BROLL / f"{cid}.mp4"
    try:
        crudo = _pedir(cand["video"], binario=True, timeout=300)
    except Exception as e:
        print(f"  {cid}  fallo al bajar: {e}")
        return False
    destino.write_bytes(crudo)
    w, h = _dimensiones(destino)
    if w < config.ANCHO or h <= w:
        destino.unlink(missing_ok=True)
        print(f"  {cid}  descartado: {w}x{h}")
        return False
    catalogo[cid] = {
        "archivo": destino.name,
        "descripcion": info["desc"],
        "origen": cand.get("pagina", ""),
        "autor": cand.get("autor", ""),
        "ancho": w, "alto": h,
        "duracion": _duracion(destino),
        "mb": round(len(crudo) / 1e6, 1),
        "licencia": "Pexels License — uso comercial libre, sin atribución obligatoria",
    }
    print(f"  {cid}  {w}x{h}  {catalogo[cid]['duracion']}s  {catalogo[cid]['mb']} MB")
    time.sleep(1.0)
    return True


def hoja_de_contactos(cid: str, info: dict, n: int = 8) -> dict:
    """Baja las miniaturas de los candidatos y las monta en una sola imagen.

    Es el paso que faltaba en el primer intento: sin mirar, el script se
    quedaba con el primer clip vertical que tuviera resolución suficiente,
    y "dust shelf old" devolvía un cisne. Mirar cuesta 30 KB por candidato.
    """
    from PIL import Image, ImageDraw

    DIR_CONTACTOS.mkdir(parents=True, exist_ok=True)
    candidatos = []
    for consulta in (info["q"], info.get("alt")):
        if not consulta:
            continue
        candidatos += [(b, consulta) for b in buscar(consulta)]
        time.sleep(PAUSA_S)
        if len(candidatos) >= n:
            break
    # dedup conservando el orden
    unicos, vistos = [], set()
    for b, q in candidatos:
        if b not in vistos:
            vistos.add(b)
            unicos.append((b, q))
    unicos = unicos[:n]
    if not unicos:
        print(f"  {cid}  sin candidatos")
        return {}

    minis = []
    for base, _q in unicos:
        try:
            crudo = _pedir(base + "_tiny.jpg", binario=True, timeout=45)
        except Exception:
            minis.append(None)
            continue
        tmp = DIR_CONTACTOS / f"_{cid}_{len(minis)}.jpg"
        tmp.write_bytes(crudo)
        minis.append(tmp)
        time.sleep(0.4)

    ANCHO_M, ALTO_M = 200, 356
    hoja = Image.new("RGB", (ANCHO_M * len(minis), ALTO_M + 26), (16, 22, 32))
    d = ImageDraw.Draw(hoja)
    for i, m in enumerate(minis):
        x = i * ANCHO_M
        if m and m.exists():
            try:
                im = Image.open(m).convert("RGB")
                im.thumbnail((ANCHO_M - 4, ALTO_M - 4))
                hoja.paste(im, (x + 2, 24))
            except Exception:
                pass
            m.unlink(missing_ok=True)
        d.text((x + 6, 6), f"{cid}#{i}", fill=(255, 210, 80))
    destino = DIR_CONTACTOS / f"{cid}.png"
    hoja.save(destino)
    print(f"  {cid}  {len(minis)} candidatos -> {destino.name}")
    return {"candidatos": [b for b, _ in unicos],
            "consultas": [q for _, q in unicos]}


def _dimensiones(ruta: Path) -> tuple:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", str(ruta)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        w, h = r.stdout.strip().split(",")[:2]
        return int(w), int(h)
    except Exception:
        return (0, 0)


def _duracion(ruta: Path) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(ruta)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
        return round(float(r.stdout.strip()), 2)
    except Exception:
        return 0.0


def _bajar_en_alta(cid: str, base: str, info: dict, catalogo: dict) -> bool:
    """Baja un candidato ya elegido, en la mejor variante que llegue a 1080."""
    destino = DIR_BROLL / f"{cid}.mp4"
    for variante in ("_medium.mp4", "_large.mp4"):
        try:
            crudo = _pedir(base + variante, binario=True, timeout=240)
        except Exception:
            continue
        destino.write_bytes(crudo)
        w, h = _dimensiones(destino)
        if w >= config.ANCHO and h > w:
            vid = base.rstrip("/").split("/")[-1].split("-")[-1]
            catalogo[cid] = {
                "archivo": destino.name,
                "descripcion": info["desc"],
                "origen": f"https://pixabay.com/videos/id-{vid}/",
                "cdn": base + variante,
                "ancho": w, "alto": h,
                "duracion": _duracion(destino),
                "mb": round(len(crudo) / 1e6, 1),
                "licencia": "Pixabay Content License — uso comercial libre, sin atribución",
            }
            print(f"  {cid}  {w}x{h}  {catalogo[cid]['duracion']}s  "
                  f"{catalogo[cid]['mb']} MB")
            time.sleep(PAUSA_S)
            return True
        time.sleep(PAUSA_S)
    destino.unlink(missing_ok=True)
    print(f"  {cid}  ninguna variante llega a {config.ANCHO} de ancho")
    return False


def descargar_uno(cid: str, info: dict, catalogo: dict) -> bool:
    destino = DIR_BROLL / f"{cid}.mp4"
    if destino.exists() and catalogo.get(cid):
        print(f"  {cid}  ya está ({destino.name})")
        return True

    for consulta in (info["q"], info.get("alt")):
        if not consulta:
            continue
        print(f"  {cid}  buscando «{consulta}»…")
        candidatos = buscar(consulta)
        time.sleep(PAUSA_S)
        if not candidatos:
            continue

        for base in candidatos[:6]:
            # `_medium` no significa lo mismo en todos los clips: en unos es
            # 1440x2560 y en otros 720x1280, que es MENOS que la salida de
            # 1080x1920 y se vería blando. Se prueba medium y, si se queda
            # corto, large; si ninguno llega, este candidato no sirve.
            datos, url, w, h = None, None, 0, 0
            for variante in ("_medium.mp4", "_large.mp4"):
                try:
                    crudo = _pedir(base + variante, binario=True, timeout=240)
                except urllib.error.HTTPError:
                    continue
                except Exception as e:
                    print(f"       fallo al bajar: {e}")
                    continue
                destino.write_bytes(crudo)
                w, h = _dimensiones(destino)
                if w >= config.ANCHO:
                    datos, url = crudo, base + variante
                    break
                time.sleep(PAUSA_S)
            if datos is None:
                destino.unlink(missing_ok=True)
                if w:
                    print(f"       (descartado: {w}x{h}, por debajo de "
                          f"{config.ANCHO}x{config.ALTO})")
                time.sleep(PAUSA_S)
                continue
            # Vertical de verdad. La página filtra por orientación pero algún
            # clip cuadrado se cuela, y un 1:1 estirado a 9:16 se nota.
            if h <= w:
                destino.unlink(missing_ok=True)
                time.sleep(PAUSA_S)
                continue
            vid = base.rstrip("/").split("/")[-1].split("-")[-1]
            catalogo[cid] = {
                "archivo": destino.name,
                "descripcion": info["desc"],
                "busqueda": consulta,
                "origen": f"https://pixabay.com/videos/id-{vid}/",
                "cdn": url,
                "ancho": w, "alto": h,
                "duracion": _duracion(destino),
                "mb": round(len(datos) / 1e6, 1),
                "licencia": "Pixabay Content License — uso comercial libre, sin atribución",
            }
            print(f"       ✓ {w}x{h}  {catalogo[cid]['duracion']}s  "
                  f"{catalogo[cid]['mb']} MB")
            time.sleep(PAUSA_S)
            return True
        time.sleep(PAUSA_S)

    print(f"       ✗ sin resultado vertical para {cid}")
    return False


def main():
    ap = argparse.ArgumentParser(description="Descarga el B-roll vertical de Lazos")
    ap.add_argument("--solo", type=str, default=None, help="Un concepto (L17)")
    ap.add_argument("--listar", action="store_true", help="Qué hay y qué falta")
    ap.add_argument("--contactos", action="store_true",
                    help="Baja SOLO las miniaturas y monta una hoja por concepto, "
                         "para mirar antes de gastar ancho de banda")
    ap.add_argument("--pixabay", action="store_true",
                    help="Usar Pixabay en vez de Pexels (peor para material humano)")
    ap.add_argument("--elegir", type=str, default=None, metavar="L03=2,L05=0",
                    help="Baja en alta el candidato elegido de cada concepto, "
                         "usando los números de la hoja de contactos")
    args = ap.parse_args()

    if args.contactos:
        objetivo = {args.solo: CONCEPTOS[args.solo]} if args.solo else CONCEPTOS
        cand = {}
        if RUTA_CANDIDATOS.exists():
            try:
                cand = json.loads(RUTA_CANDIDATOS.read_text(encoding="utf-8"))
            except Exception:
                cand = {}
        print(f"Hojas de contactos en {DIR_CONTACTOS}\n")
        for cid, info in objetivo.items():
            try:
                r = (hoja_pexels(cid, info) if not args.pixabay
                     else hoja_de_contactos(cid, info))
                if r:
                    cand[cid] = r
            except KeyboardInterrupt:
                break
            DIR_CONTACTOS.mkdir(parents=True, exist_ok=True)
            RUTA_CANDIDATOS.write_text(json.dumps(cand, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
        print(f"\nListo. Mirá las hojas y después:  --elegir L01=0,L03=2,…")
        return 0

    if args.elegir:
        if not RUTA_CANDIDATOS.exists():
            print("ERROR: primero hay que correr --contactos")
            return 1
        cand = json.loads(RUTA_CANDIDATOS.read_text(encoding="utf-8"))
        catalogo = {}
        if RUTA_CATALOGO.exists():
            try:
                catalogo = json.loads(RUTA_CATALOGO.read_text(encoding="utf-8"))
            except Exception:
                catalogo = {}
        DIR_BROLL.mkdir(parents=True, exist_ok=True)
        for par in args.elegir.split(","):
            par = par.strip()
            if not par or "=" not in par:
                continue
            cid, idx = par.split("=", 1)
            cid = cid.strip().upper()
            if cid not in cand:
                print(f"  {cid}: sin candidatos (¿corriste --contactos?)")
                continue
            try:
                elegido = cand[cid]["candidatos"][int(idx)]
            except (ValueError, IndexError):
                print(f"  {cid}: el candidato {idx} no existe")
                continue
            # Pexels guarda un dict con las URLs ya resueltas; Pixabay, la base
            # del CDN como texto. Se distingue por el tipo, no por una bandera.
            if isinstance(elegido, dict):
                ok = bajar_pexels(cid, elegido, CONCEPTOS[cid], catalogo)
            else:
                ok = _bajar_en_alta(cid, elegido, CONCEPTOS[cid], catalogo)
            if ok:
                RUTA_CATALOGO.write_text(json.dumps(catalogo, ensure_ascii=False, indent=2),
                                         encoding="utf-8")
        total = sum(c.get("mb", 0) for c in catalogo.values())
        print(f"\n{len(catalogo)} clips en el catálogo · {total:.0f} MB")
        return 0

    DIR_BROLL.mkdir(parents=True, exist_ok=True)
    catalogo = {}
    if RUTA_CATALOGO.exists():
        try:
            catalogo = json.loads(RUTA_CATALOGO.read_text(encoding="utf-8"))
        except Exception:
            catalogo = {}

    if args.listar:
        print(f"{'id':<5} {'estado':<9} {'medidas':<12} {'seg':>6}  descripción")
        for cid, info in CONCEPTOS.items():
            c = catalogo.get(cid)
            if c:
                print(f"{cid:<5} {'ok':<9} {c['ancho']}x{c['alto']:<7} "
                      f"{c['duracion']:>6}  {info['desc']}")
            else:
                print(f"{cid:<5} {'FALTA':<9} {'—':<12} {'—':>6}  {info['desc']}")
        hay = sum(1 for c in CONCEPTOS if c in catalogo)
        print(f"\n{hay}/{len(CONCEPTOS)} descargados")
        return 0

    objetivo = {args.solo: CONCEPTOS[args.solo]} if args.solo else CONCEPTOS
    if args.solo and args.solo not in CONCEPTOS:
        print(f"ERROR: {args.solo} no existe. Opciones: {', '.join(CONCEPTOS)}")
        return 1

    print(f"Descargando B-roll de Lazos a {DIR_BROLL}")
    print(f"{len(objetivo)} concepto(s), pausa de {PAUSA_S}s entre peticiones\n")
    ok = 0
    for cid, info in objetivo.items():
        try:
            if descargar_uno(cid, info, catalogo):
                ok += 1
        except KeyboardInterrupt:
            print("\ninterrumpido — lo descargado hasta aquí queda guardado")
            break
        RUTA_CATALOGO.write_text(json.dumps(catalogo, ensure_ascii=False, indent=2),
                                 encoding="utf-8")

    RUTA_CATALOGO.write_text(json.dumps(catalogo, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    total_mb = sum(c.get("mb", 0) for c in catalogo.values())
    print(f"\n{ok}/{len(objetivo)} descargados · {total_mb:.0f} MB en total")
    print(f"Catálogo: {RUTA_CATALOGO}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
