"""
Fase 5 — Overlays y producción visual.

Genera y compone: banner de hook (primeros 3s), tarjeta de cierre con CTA
(logo + WhatsApp), y stickers simples en los huecos que dejó marcados el
motor de la regla de 5s (f4_retencion.py).

Nota de alcance (ver BITACORA-A.md): el plan pide también inserto PiP de
producto, tarjeta de specs y comparativa lado a lado — todas necesitan
datos reales de `assets/productos/` (fotos) y del catálogo, que aún no
existen. Las funciones de render están escritas y listas para recibir
esos datos (`render_tarjeta_generica`), pero esta pasada no las inventa:
usa lo que sí es real esta noche (logo, WhatsApp, texto del guion).

Uso:
    python f6_overlays.py "video_audio.mp4" "video.plan.json" "video_transcripcion.json" [--salida salida.mp4]
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import config

ANCHO, ALTO = config.ANCHO, config.ALTO
NAVY = (10, 42, 62, 255)
CIAN = (79, 209, 217, 255)
BLANCO = (255, 255, 255, 255)

# Palabras clave -> tipo de sticker. Placeholder genérico (no depende del
# catálogo real de sesión B, que no se leyó por estar fuera de mi territorio
# esta noche). Reemplazar/ampliar en Fase 7 con el catálogo real.
PALABRAS_CLAVE_STICKER = {
    "envío": "bandera", "envíos": "bandera", "bolivia": "bandera", "nacional": "bandera",
    "whatsapp": "destello", "pedido": "destello", "garantía": "destello", "oferta": "destello",
}


def _fuente(nombre_archivo: str, tamano: int) -> ImageFont.FreeTypeFont:
    ruta = config.DIR_FUENTES / nombre_archivo
    return ImageFont.truetype(str(ruta), tamano)


def _texto_centrado(draw, centro_x, y, texto, fuente, color, letter_spacing=0):
    if letter_spacing:
        ancho_total = sum(draw.textlength(c, font=fuente) + letter_spacing for c in texto) - letter_spacing
        x = centro_x - ancho_total / 2
        for c in texto:
            draw.text((x, y), c, font=fuente, fill=color)
            x += draw.textlength(c, font=fuente) + letter_spacing
    else:
        bbox = draw.textbbox((0, 0), texto, font=fuente)
        w = bbox[2] - bbox[0]
        draw.text((centro_x - w / 2, y), texto, font=fuente, fill=color)


def _rounded_card(size, color, radio=32):
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radio, fill=color)
    return img, draw


def _envolver(draw, texto: str, fuente, ancho_max: float) -> list:
    """Parte el texto en líneas que quepan en ancho_max, midiendo de verdad.

    La versión anterior partía la lista de palabras por la mitad y asumía dos
    líneas: con textos largos se salía de la tarjeta y con textos cortos dejaba
    un hueco raro. Aquí se mide cada línea con la fuente real.
    """
    lineas, actual = [], []
    for palabra in texto.split():
        prueba = " ".join(actual + [palabra])
        if actual and draw.textlength(prueba, font=fuente) > ancho_max:
            lineas.append(" ".join(actual))
            actual = [palabra]
        else:
            actual.append(palabra)
    if actual:
        lineas.append(" ".join(actual))
    return lineas


def render_hook_banner(texto: str, ruta_salida: Path):
    """Banner de hook de los primeros segundos. Tarjeta navy, texto blanco,
    borde cian sutil.

    La tarjeta se dimensiona según el texto (no al revés): se envuelve midiendo
    con la fuente real y, si hiciera falta más de 3 líneas, se baja el tamaño de
    letra antes que recortar. Nunca se corta una frase para que entre.
    """
    w = 940
    margen_x, margen_y = 42, 34
    ancho_texto = w - margen_x * 2

    medidor = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    for tamano in (58, 52, 46, 40):
        fuente = _fuente("Poppins-ExtraBold.ttf", tamano)
        lineas = _envolver(medidor, texto, fuente, ancho_texto)
        if len(lineas) <= 3:
            break

    alto_linea = round(tamano * 1.22)
    h = margen_y * 2 + alto_linea * len(lineas)

    img, _ = _rounded_card((w, h), NAVY, radio=28)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([2, 2, w - 3, h - 3], radius=28, outline=CIAN, width=3)

    y = margen_y - round(tamano * 0.12)   # compensa el interlineado superior de la fuente
    for linea in lineas:
        _texto_centrado(draw, w / 2, y, linea, fuente, BLANCO)
        y += alto_linea

    lienzo = Image.new("RGBA", (ANCHO, h), (0, 0, 0, 0))
    lienzo.paste(img, ((ANCHO - w) // 2, 0), img)
    lienzo.save(ruta_salida)
    return (ANCHO - w) // 2, 220, w, h


VERDE_WA = (37, 211, 102, 255)


def _icono_whatsapp(tam: int = 108) -> Image.Image:
    """Ícono de WhatsApp dibujado: burbuja verde + auricular blanco.

    Se dibuja en vez de usar un PNG para no depender de un archivo externo y
    poder escalarlo sin pérdida.
    """
    img = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, tam - 1, tam - 1), fill=VERDE_WA)
    # colita de la burbuja
    d.polygon([(tam * 0.20, tam * 0.86), (tam * 0.40, tam * 0.72), (tam * 0.34, tam * 0.94)],
              fill=VERDE_WA)
    # auricular estilizado
    u = tam / 100.0
    d.rounded_rectangle((30 * u, 28 * u, 46 * u, 50 * u), radius=6 * u, fill=BLANCO)
    d.rounded_rectangle((54 * u, 50 * u, 70 * u, 72 * u), radius=6 * u, fill=BLANCO)
    d.line([(44 * u, 46 * u), (56 * u, 58 * u)], fill=BLANCO, width=int(9 * u))
    return img


def _texto_contorneado(draw, centro_x, y, texto, fuente, color, grosor=6):
    """Texto con contorno negro: legible sobre cualquier fondo, sin necesitar
    una caja opaca detrás. Mismo principio que los subtítulos (sección 5.3)."""
    bbox = draw.textbbox((0, 0), texto, font=fuente, stroke_width=grosor)
    w = bbox[2] - bbox[0]
    draw.text((centro_x - w / 2, y), texto, font=fuente, fill=color,
              stroke_width=grosor, stroke_fill=(0, 0, 0, 230))


def render_cta_cierre(ruta_salida: Path, eco: str = ""):
    """Cierre SIN caja de fondo: logo + ícono de WhatsApp + número + handle.

    La versión anterior era un rectángulo navy sólido con borde cian, que se
    veía pegado encima del video. Aquí se aplica el mismo criterio que a los
    subtítulos: contorno negro en vez de fondo opaco. El texto se lee igual
    sobre cualquier imagen y el video respira.

    `eco`: repetición corta del hook, para cerrar el loop (sección 4.5 del
    plan). Es el respaldo PIL de lo que hace `tarjeta-cta.html` de Hyperframes.
    """
    w, h = ANCHO, (560 if eco else 470)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    y = 12
    ruta_logo = config.DIR_ASSETS / "logo" / "deviceshop-icono-blanco-transparente.png"
    if ruta_logo.exists():
        logo = Image.open(ruta_logo).convert("RGBA")
        logo.thumbnail((132, 132))
        # sombra suave para despegar el logo del fondo
        sombra = Image.new("RGBA", logo.size, (0, 0, 0, 0))
        sombra.paste((0, 0, 0, 150), (0, 0), logo)
        img.paste(sombra, (int(w / 2 - logo.width / 2) + 3, y + 3), sombra)
        img.paste(logo, (int(w / 2 - logo.width / 2), y), logo)
        y += logo.height + 26

    f_titulo = _fuente("Poppins-ExtraBold.ttf", 62)
    f_num = _fuente("Poppins-ExtraBold.ttf", 58)
    f_handle = _fuente("Poppins-Bold.ttf", 40)

    _texto_contorneado(draw, w / 2, y, "¡Pide el tuyo ya!", f_titulo, BLANCO, grosor=7)
    y += 92

    # fila: ícono de WhatsApp + número, centrados como un bloque
    icono = _icono_whatsapp(104)
    texto_num = config.WHATSAPP_NUMERO
    ancho_num = draw.textbbox((0, 0), texto_num, font=f_num, stroke_width=7)[2]
    ancho_fila = icono.width + 22 + ancho_num
    x_fila = (w - ancho_fila) / 2
    img.paste(icono, (int(x_fila), int(y - 12)), icono)
    draw.text((x_fila + icono.width + 22, y), texto_num, font=f_num, fill=BLANCO,
              stroke_width=7, stroke_fill=(0, 0, 0, 230))
    y += 128

    _texto_contorneado(draw, w / 2, y, config.TIKTOK_HANDLE, f_handle, CIAN, grosor=5)

    if eco:
        # Cierre del loop: lo último que se lee es la frase con la que abrió el
        # video, así el rebobinado se siente continuo.
        y += 66
        f_eco = _fuente("Poppins-Bold.ttf", 36)
        for linea in _envolver(draw, eco, f_eco, w - 180):
            _texto_contorneado(draw, w / 2, y, linea, f_eco, CIAN, grosor=5)
            y += 46

    img.save(ruta_salida)
    # Arriba, igual que los insertos: en un talking-head sentado la franja
    # superior está vacía y la cabeza ocupa el centro. A media altura el logo
    # caía sobre la cara.
    return 0, int(ALTO * 0.13), w, h


def render_sticker_destello(ruta_salida: Path, tam=150):
    """Estrella simple (destello) en cian — sustituto liviano del emoji animado
    de la agencia hasta que exista un asset animado real."""
    img = Image.new("RGBA", (tam, tam), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy, r_ext, r_int = tam / 2, tam / 2, tam / 2 - 6, tam / 5
    puntos = []
    for i in range(8):
        ang = i * 3.14159 / 4
        r = r_ext if i % 2 == 0 else r_int
        puntos.append((cx + r * __import__("math").sin(ang), cy - r * __import__("math").cos(ang)))
    draw.polygon(puntos, fill=CIAN)
    img.save(ruta_salida)


def render_sticker_bandera(ruta_salida: Path, w=150, h=100):
    """Bandera de Bolivia simplificada (3 franjas) en tarjeta redondeada."""
    img, draw = _rounded_card((w, h), BLANCO, radio=16)
    franja = h // 3
    draw.rectangle([6, 6, w - 6, franja], fill=(213, 43, 30, 255))
    draw.rectangle([6, franja, w - 6, franja * 2], fill=(249, 227, 0, 255))
    draw.rectangle([6, franja * 2, w - 6, h - 6], fill=(0, 121, 52, 255))
    img.save(ruta_salida)


def render_pip_producto(ruta_foto: Path, ruta_salida: Path, ancho=520, alto=680,
                         centrar_en_lienzo: bool = True):
    """Inserto PiP de producto real (sección 5.1): esquinas redondeadas, borde
    blanco con acento cian sutil, contenido = foto real recortada al centro.

    centrar_en_lienzo=True guarda el PNG del ancho completo con la tarjeta
    centrada dentro (comportamiento histórico, para overlays centrados).
    =False guarda solo la tarjeta, para poder posicionarla libremente en X:
    si el PNG ocupa todo el ancho, cualquier desplazamiento horizontal se
    duplica y la tarjeta se sale del cuadro.
    """
    foto = Image.open(ruta_foto).convert("RGBA")
    w, h = foto.size
    aspecto_objetivo = ancho / alto
    if (w / h) > aspecto_objetivo:
        nuevo_w = int(h * aspecto_objetivo)
        x0 = (w - nuevo_w) // 2
        foto = foto.crop((x0, 0, x0 + nuevo_w, h))
    else:
        nuevo_h = int(w / aspecto_objetivo)
        y0 = (h - nuevo_h) // 2
        foto = foto.crop((0, y0, w, y0 + nuevo_h))
    foto = foto.resize((ancho, alto), Image.LANCZOS)

    radio = 36
    mascara = Image.new("L", (ancho, alto), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([0, 0, ancho - 1, alto - 1], radius=radio, fill=255)

    borde = 10
    w_tarjeta, h_tarjeta = ancho + borde * 2, alto + borde * 2
    marco = Image.new("RGBA", (w_tarjeta, h_tarjeta), (0, 0, 0, 0))
    draw_marco = ImageDraw.Draw(marco)
    draw_marco.rounded_rectangle([0, 0, w_tarjeta - 1, h_tarjeta - 1], radius=radio + borde, fill=BLANCO)
    draw_marco.rounded_rectangle([0, 0, w_tarjeta - 1, h_tarjeta - 1], radius=radio + borde, outline=CIAN, width=3)
    marco.paste(foto, (borde, borde), mascara)

    if not centrar_en_lienzo:
        marco.save(ruta_salida)
        return w_tarjeta, h_tarjeta

    lienzo = Image.new("RGBA", (ANCHO, h_tarjeta), (0, 0, 0, 0))
    lienzo.paste(marco, ((ANCHO - w_tarjeta) // 2, 0), marco)
    lienzo.save(ruta_salida)
    return (ANCHO - w_tarjeta) // 2, h_tarjeta


def _buscar_foto_producto_default() -> Path | None:
    """Busca una foto frontal usable en assets/productos/*/ (cualquier producto
    disponible). No asume un producto específico — se adapta a lo que exista."""
    dir_productos = config.DIR_ASSETS / "productos"
    if not dir_productos.exists():
        return None
    candidatos = sorted(dir_productos.glob("*/frontal*.jpg")) + sorted(dir_productos.glob("*/frontal*.png"))
    return candidatos[0] if candidatos else None


def render_tarjeta_generica(titulo: str, cuerpo: str, ruta_salida: Path, w=880, h=360):
    """Mecanismo genérico para specs/comparativa — listo para recibir datos reales
    del catálogo (Fase 7). Esta noche no se usa con datos inventados."""
    img, draw = _rounded_card((w, h), NAVY, radio=32)
    f_titulo = _fuente("Poppins-ExtraBold.ttf", 46)
    f_cuerpo = _fuente("Poppins-Bold.ttf", 32)
    _texto_centrado(draw, w / 2, 40, titulo, f_titulo, CIAN)
    y = 130
    for linea in cuerpo.split("\n"):
        _texto_centrado(draw, w / 2, y, linea, f_cuerpo, BLANCO)
        y += 50
    lienzo = Image.new("RGBA", (ANCHO, h), (0, 0, 0, 0))
    lienzo.paste(img, ((ANCHO - w) // 2, 0), img)
    lienzo.save(ruta_salida)
    return (ANCHO - w) // 2, 700, w, h


def _normalizar(t):
    return re.sub(r"[^\wáéíóúñü]", "", t.lower())


# ---------------------------------------------------------------------------
# Insertos disparados por lo que se dice (catálogo de assets)
# ---------------------------------------------------------------------------
def _cargar_catalogo() -> list:
    """Assets etiquetados por editor/catalogo_assets.py. Vacío si no existe."""
    ruta = config.DIR_CONTEXTO / "catalogo-assets.json"
    if not ruta.exists():
        return []
    try:
        return json.loads(ruta.read_text(encoding="utf-8")).get("assets", [])
    except Exception:
        return []


def _producto_dominante(palabras: list) -> str | None:
    """Qué producto es el protagonista del video, según cuánto se lo nombra.

    Sin esto, decir "pantalla" en un video del Paperwhite traía el protector de
    un Scribe: la etiqueta coincidía pero el producto no. El inserto tiene que
    ser del aparato del que se está hablando.
    """
    modelos = {"paperwhite": "#paperwhite", "colorsoft": "#colorsoft",
               "scribe": "#scribe", "kobo": "#kobo", "basic": "#basic"}
    conteo = {}
    for p in palabras:
        n = _normalizar(p["texto"])
        for clave, tag in modelos.items():
            if clave in n:
                conteo[tag] = conteo.get(tag, 0) + 1
    return max(conteo, key=conteo.get) if conteo else None


def _version_sin_fondo(asset: dict) -> Path | None:
    """Versión recortada del mismo producto, si `quitar_fondos.py` la generó.

    Un producto sin fondo se integra en el video; con su fondo original se ve
    como una calcomanía pegada encima. Se prefiere siempre la recortada.
    """
    dir_prod = config.DIR_ASSETS / "productos" / asset.get("producto", "")
    if not dir_prod.is_dir():
        return None
    for nombre in ("frontal.png", "vista2.png", "vista3.png"):
        cand = dir_prod / nombre
        if cand.exists():
            return cand
    return None


def _elegir_asset(tag: str, catalogo: list, ya_usados: set,
                   producto: str | None = None) -> dict | None:
    """Mejor asset para una etiqueta, sin repetir los ya usados en este video.

    Prioridad: coincidir con el producto del que trata el video (lo que más
    pesa), imagen sobre video, sin fondo > blanco > ambiente, y vertical antes
    que horizontal porque el lienzo es 9:16.
    """
    def puntaje(a):
        p = 0
        if producto and producto in a.get("tags", []):
            p += 100                       # el producto correcto manda sobre todo lo demás
        p += 40 if a["medio"] == "imagen" else 0
        p += {"transparente": 30, "blanco": 20, "ambiente": 10}.get(a["fondo"], 0)
        p += {"vertical": 15, "cuadrada": 10, "horizontal": 5}.get(a["orientacion"], 0)
        p += 15 if a["tipo"] == "producto" else 0
        return p

    # #no-usar-en-video marca las fotos de proveedor con marca de agua: sirven
    # para la web, pero en un video se vería la marca de otra empresa.
    candidatos = [a for a in catalogo
                  if tag in a.get("tags", [])
                  and a["id"] not in ya_usados
                  and "#no-usar-en-video" not in a.get("tags", [])]

    # Si el video trata de un modelo concreto, no mostrar accesorios ni fotos
    # de OTRO modelo: es peor enseñar el producto equivocado que no enseñar
    # nada. (Caso real: decir "pantalla" en un video del Paperwhite traía el
    # protector de un Scribe, porque el del Paperwhite tenía marca de agua.)
    if producto:
        modelos = {"#paperwhite", "#colorsoft", "#scribe", "#kobo", "#basic"}
        def es_de_otro_modelo(a):
            suyos = modelos & set(a.get("tags", []))
            return bool(suyos) and producto not in suyos
        filtrados = [a for a in candidatos if not es_de_otro_modelo(a)]
        if filtrados:
            candidatos = filtrados
        elif any(es_de_otro_modelo(a) for a in candidatos):
            return None                    # solo había de otros modelos: mejor omitir

    if not candidatos:
        return None
    return max(candidatos, key=puntaje)


def _posicion_inserto(w_tarjeta: int, h_tarjeta: int, track_rostro: list, t: float) -> tuple:
    """Coloca el inserto en la zona libre, esquivando el rostro.

    El dato ya existe: f4_retencion guarda `track_rostro` en el plan y hasta
    ahora se descartaba. El inserto iba siempre a `ALTO * 0.60` fijo, que en un
    talking-head sentado cae justo sobre la cara.

    Bandas del lienzo 9:16: 0-10% zona segura superior, ~20-45% el rostro,
    77% los subtítulos, 85-100% zona segura inferior de TikTok. La franja
    utilizable real es la que va de debajo del rostro hasta encima del texto.
    """
    # posición horizontal del rostro en el momento del inserto (0-1)
    cx = 0.5
    if track_rostro:
        cercanos = [p for p in track_rostro if abs(p["t"] - t) < 1.5]
        muestras = cercanos or track_rostro
        cx = sum(p["cx"] for p in muestras) / len(muestras)

    # Vertical: ARRIBA. En un talking-head sentado la cabeza ocupa la franja
    # media (~40-70% del alto) y toda la parte superior queda vacía. Intentar
    # meter el inserto entre el rostro y los subtítulos siempre termina rozando
    # la cara; arriba hay espacio de sobra y nunca hay conflicto (el banner de
    # hook solo vive los primeros segundos, antes del primer inserto).
    y = int(ALTO * config.INSERTO_Y_PCT)

    # Horizontal: al lado contrario del rostro, con margen
    margen = 40
    if cx <= 0.5:
        x = ANCHO - w_tarjeta - margen          # rostro a la izquierda -> inserto a la derecha
    else:
        x = margen
    return max(margen, min(x, ANCHO - w_tarjeta - margen)), y


def _frase_alrededor(palabras: list, t: float, ventana: float = 3.0) -> str:
    """Lo que se dice alrededor de un momento — alimenta el prompt de generación."""
    return " ".join(p["texto"] for p in palabras
                    if t - ventana <= p["inicio"] <= t + ventana)


def planificar_insertos_por_palabra(palabras: list, track_rostro: list, dir_tmp: Path,
                                     libre_fn, catalogo: list = None,
                                     generador=None, pendientes: list = None,
                                     tags_reservados: set = None) -> list:
    """Insertos visuales disparados por el guion, no por un tiempo arbitrario.

    Recorre la transcripción buscando palabras del vocabulario
    (config.PALABRAS_A_TAGS) y, cuando encuentra una, muestra un asset del
    catálogo etiquetado con ese tema.

    Orden de preferencia de la imagen:
      1. **Foto real del catálogo** — siempre gana. Flux no sabe cómo es un
         Kindle de verdad (verificado por la sesión B).
      2. **Imagen puesta a mano** en assets/generado/manual/ (ver
         contexto/prompts-externos.md).
      3. **Generada con Flux** en el momento (f9_generar) — solo para conceptos
         de ambiente que ninguna foto del catálogo cubre: sol, cama, café,
         noche, viaje...

    `tags_reservados` son las etiquetas que ya se llevó una animación
    (config.CONCEPTOS_PREFIEREN_ANIMACION). Para esas NO se busca foto: el
    catálogo tiene 30 assets etiquetados `#agua` porque son Kindle resistentes
    al agua, y por eso decir "agua" devolvía una foto de producto en vez del
    splash. Las etiquetas de esos 30 assets no se tocan — siguen valiendo para
    sus otros usos; lo único que cambia es que estas ya no disparan un inserto.
    """
    tags_reservados = tags_reservados or set()
    catalogo = _cargar_catalogo() if catalogo is None else catalogo

    producto = _producto_dominante(palabras)
    if producto:
        print(f"  producto dominante del video: {producto}")

    import f9_generar

    eventos, usados, ultimo_t = [], set(), -999.0
    for p in palabras:
        if len(eventos) >= config.INSERTOS_MAX:
            break
        tag = config.PALABRAS_A_TAGS.get(_normalizar(p["texto"]))
        if not tag:
            continue
        if tag in tags_reservados:
            continue                       # ese concepto ya lo cuenta una animación
        t0 = p["inicio"]
        if t0 - ultimo_t < config.INSERTO_SEPARACION_MIN_S:
            continue
        t1 = t0 + config.INSERTO_DURACION_S
        if not libre_fn(t0, t1):
            continue

        asset = _elegir_asset(tag, catalogo, usados, producto)
        origen = None
        if asset is not None and asset["medio"] == "imagen":
            ruta_img = _version_sin_fondo(asset) or (config.RAIZ_PROYECTO / asset["ruta"])
            origen = asset["id"]
            if not ruta_img.exists():
                continue
        elif generador is not None:
            # El catálogo no tiene nada para esta etiqueta: se genera.
            ruta_img = generador(tag, _frase_alrededor(palabras, t0))
            if ruta_img is None:
                if pendientes is not None and tag not in [t for t, _ in pendientes]:
                    pendientes.append((tag, _frase_alrededor(palabras, t0, 2.0)))
                continue
            origen = f"generado:{ruta_img.name}"
        else:
            continue

        ruta_png = dir_tmp / f"ov_inserto_{len(eventos)}.png"
        try:
            w_tarjeta, h_tarjeta = render_pip_producto(
                ruta_img, ruta_png, ancho=400, alto=520, centrar_en_lienzo=False)
        except Exception as e:
            print(f"AVISO: no se pudo renderizar {origen}: {e}")
            continue

        x, y = _posicion_inserto(w_tarjeta, h_tarjeta, track_rostro, t0)
        eventos.append({"tipo": "pip-producto", "archivo": ruta_png, "x": x, "y": y,
                        "ini": round(t0, 3), "fin": round(t1, 3),
                        "palabra": p["texto"], "tag": tag, "asset": origen})
        if asset is not None:
            usados.add(asset["id"])
        ultimo_t = t0

    return eventos


def _limite_primer_plano(intervalos_conservados: list) -> float:
    """Fin (en la línea de tiempo ya cortada) del primer tramo continuo de habla.

    f2_cortar.py puede dejar contiguos dos fragmentos que originalmente NO lo
    eran (p.ej. se cortó un silencio o una muletilla entre ellos). Sin este
    límite, el hook podía juntar "Si quieres leer más" + "año, pero te" — dos
    trozos de oraciones distintas que quedaron pegados por un corte, pero que
    nunca se dijeron seguidos. Cortar la recolección de palabras del hook en el
    primer corte evita mezclar fragmentos no contiguos."""
    if not intervalos_conservados:
        return float("inf")
    primero = intervalos_conservados[0]
    return primero["fin"] - primero["inicio"]


def _texto_hook_desde_transcripcion(palabras: list, intervalos_conservados: list) -> str:
    """Primera frase COMPLETA del video, no las primeras N palabras.

    Antes se cortaba con `primeras[:7]` y quedaban frases partidas a la mitad
    ("¿Quieres leer más este año, pero te" — faltaba "da pereza"). Es el peor
    lugar posible para ese error: son los 3 segundos que deciden la retención
    de todo el video.

    Ahora se recolecta hasta el signo de cierre (? ! .). Solo si la frase supera
    HOOK_MAX_PALABRAS se recorta, y en ese caso se retrocede hasta la última
    coma para no dejar un fragmento colgando.
    """
    # Se usa la ventana de tiempo sobre la línea de tiempo YA CORTADA, no el
    # límite del primer plano. En el video editado esas palabras se oyen
    # seguidas y los subtítulos ya las muestran así, de modo que el banner
    # puede mostrarlas igual. Limitar al primer plano dejaba el hook en
    # "¿Quieres leer más este año" y perdía el "pero te da pereza" que le da
    # sentido a la frase.
    candidatas = [p for p in palabras if p["inicio"] < config.HOOK_VENTANA_BUSQUEDA_S]
    if not candidatas:
        candidatas = palabras[:config.HOOK_MAX_PALABRAS]

    recogidas = []
    completa = False
    for p in candidatas:
        recogidas.append(p["texto"])
        if p["texto"].rstrip().endswith(("?", "!", ".")):
            completa = True
            break                                    # frase completa, listo
        if len(recogidas) >= config.HOOK_MAX_PALABRAS:
            break

    texto = " ".join(recogidas).strip()
    # Solo si se agotó el tope sin cerrar la frase se retrocede a la última
    # coma, para no dejar colgando un fragmento sin sentido.
    if not completa and "," in texto:
        texto = texto.rsplit(",", 1)[0]
    return texto.strip(" ,")


def _semilla_video(nombre_video: str) -> int:
    """Semilla determinista derivada del nombre del archivo de video.

    El plan exige render reproducible, así que NO se usa `random`: el mismo
    video da siempre exactamente el mismo resultado, pero dos videos distintos
    reciben variantes distintas de cada animación. Antes el splash y la batería
    salían idénticos en todos los videos.
    """
    return int(hashlib.sha1(nombre_video.encode("utf-8")).hexdigest()[:8], 16)


def _variante(semilla: int, nombre: str, n: int = 3) -> int:
    """Índice de variante estable para una animación concreta de este video."""
    mezcla = hashlib.sha1(f"{semilla}|{nombre}".encode("utf-8")).hexdigest()[:8]
    return int(mezcla, 16) % n


def _variante_aparicion(semilla: int, nombre: str, indice: int, n: int,
                        previas: list) -> int:
    """Variante para la aparición número `indice` de la misma animación.

    José pidió que decir "agua" y luego "tina" dé DOS splash, pero distintos:
    repetir la misma toma se lee como error de edición, y caer a una foto de
    producto es justo lo que no quiere. Así que la semilla incluye el índice de
    aparición, y además se fuerza que no repita ninguna variante ya usada en
    este video mientras queden libres.

    Sigue siendo determinista: todo sale de la semilla del nombre del video y
    de datos que ya son deterministas. Renderizar el mismo video dos veces da
    exactamente el mismo resultado — es lo que permite comparar renders.
    """
    base = _variante(semilla, f"{nombre}|{indice}", n)
    if base not in previas or len(previas) >= n:
        return base
    for k in range(1, n):
        candidata = (base + k) % n
        if candidata not in previas:
            return candidata
    return base


def _foto_dispositivo(producto: str | None, catalogo: list = None) -> Path | None:
    """Foto real recortada del aparato protagonista del video.

    La usa la animación de sol: enseña el Kindle de verdad, no un e-reader
    dibujado. Está documentado que Flux no sabe cómo es un Kindle real, así que
    para el producto siempre gana la foto — y desde la Fase 0 casi todos los
    productos tienen recorte con alfa en assets/productos/<producto>/.

    Orden: recorte del producto dominante > recorte de cualquier producto >
    None (la composición dibuja su silueta de respaldo).
    """
    catalogo = _cargar_catalogo() if catalogo is None else catalogo

    def puntaje(a):
        p = 0
        p += 60 if a.get("tipo") == "producto" else 0      # el aparato, no su funda
        p += {"vertical": 25, "cuadrada": 12, "horizontal": 5}.get(a.get("orientacion"), 0)
        p += {"blanco": 18, "transparente": 20, "ambiente": 4}.get(a.get("fondo"), 0)
        return p

    candidatos = [a for a in catalogo
                  if a.get("medio") == "imagen"
                  and "#no-usar-en-video" not in a.get("tags", [])
                  and (not producto or producto in a.get("tags", []))]
    for a in sorted(candidatos, key=puntaje, reverse=True):
        recorte = _version_sin_fondo(a)
        if recorte is not None and recorte.exists():
            return recorte
    return _buscar_foto_producto_default()


def _etiqueta_animacion(nombre: str, indice: int) -> str:
    """Texto de la animación. La repetición lleva el suyo: decir dos veces
    "resistente al agua" con tres segundos de diferencia se lee como un error
    de edición, no como énfasis."""
    if indice > 0:
        alterna = config.ANIMACION_ETIQUETAS_REPETICION.get(nombre)
        if alterna:
            return alterna
    return config.ANIMACION_ETIQUETAS.get(nombre, "")


def _construir_animacion(nombre: str, t0: float, var: int, dir_tmp: Path,
                          track_rostro: list, hf: bool, semilla: int,
                          foto_dispositivo: Path = None,
                          usar_video_sol: bool = False,
                          indice: int = 0) -> tuple:
    """Renderiza UNA animación y devuelve (ruta, x, y, motor).

    Compartido por el disparo automático y por la lista que arma el editor
    (--animaciones-manual), para que las dos vías produzcan exactamente el
    mismo clip y no puedan divergir.
    """
    import f7_animaciones
    import f8_hyperframes

    # Video real de sol: si José lo grabó, gana sobre cualquier animación
    # dibujada. No se cierra a una sola opción — si el archivo no existe se cae
    # a Hyperframes sin decir nada raro.
    if usar_video_sol and nombre == "sol":
        ruta_pip = config.DIR_ASSETS / "sol_video_pip.mov"
        if ruta_pip.exists():
            x, y = _posicion_inserto(420, 540, track_rostro or [], t0)
            return ruta_pip, x, y, "Video PiP"

    etiqueta = _etiqueta_animacion(nombre, indice)
    if hf:
        variables = {"variante": str(var), "etiqueta": etiqueta}
        if nombre != "moto":                          # la moto cruza a lo ancho
            variables["lado"] = _lado_libre(track_rostro or [], t0)
        if nombre == "sol" and foto_dispositivo is not None:
            ruta_rel = f8_hyperframes.preparar_imagen(foto_dispositivo)
            if ruta_rel:
                variables["imagen"] = ruta_rel
        ruta = f8_hyperframes.render(f"anim-{nombre}", variables)
        if ruta is not None:
            return ruta, 0, 0, "Hyperframes"

    # Respaldo PIL — también variado, y con nombre de archivo propio por
    # variante: con un nombre fijo la segunda aparición pisaba el MOV de la
    # primera y las dos terminaban apuntando al mismo clip.
    dur = config.ANIMACION_DURACION.get(nombre, 2.4)
    ruta = f7_animaciones.generar(nombre, dir_tmp, duracion=dur, semilla=semilla,
                                  variante=var, foto_dispositivo=foto_dispositivo,
                                  etiqueta=etiqueta)
    if ruta is None:
        return None, 0, 0, "PIL"
    # El tamaño real del lienzo, no 420x420 fijo: el sol es más ancho y con el
    # valor viejo se salía por el margen derecho.
    w_pil, h_pil = f7_animaciones.TAMANOS.get(nombre, (420, 420))
    x, y = ((0, int(ALTO * 0.10)) if nombre == "moto"
            else _posicion_inserto(w_pil, h_pil, track_rostro or [], t0))
    return ruta, x, y, "PIL"


def _lado_libre(track_rostro: list, t: float) -> str:
    """Dónde poner un overlay para no taparle la cara: al lado contrario."""
    if not track_rostro:
        return "derecha"
    cercanos = [p for p in track_rostro if abs(p["t"] - t) < 1.5] or track_rostro
    cx = sum(p["cx"] for p in cercanos) / len(cercanos)
    return "derecha" if cx <= 0.5 else "izquierda"


def _texto_eco_loop(texto_hook: str) -> str:
    """Versión corta del hook para cerrar el loop en la tarjeta de CTA.

    Se corta en la primera coma (que en un hook casi siempre separa la pregunta
    del complemento) y, si aun así es largo, se limita por palabras. Termina en
    '?' si el hook era una pregunta, para que se lea como la misma frase.
    """
    t = (texto_hook or "").strip()
    if not t:
        return ""
    pregunta = t.rstrip().endswith("?") or t.lstrip().startswith("¿")
    corto = t.split(",")[0].strip(" ,.")
    palabras = corto.split()
    if len(palabras) > config.LOOP_ECO_MAX_PALABRAS:
        corto = " ".join(palabras[:config.LOOP_ECO_MAX_PALABRAS])
    corto = corto.strip(" ,.")
    if pregunta and not corto.endswith("?"):
        corto += "?"
    return corto


def planificar_overlays(palabras: list, huecos: list, duracion_total: float, dir_tmp: Path,
                         intervalos_conservados: list = None, hook_manual: str = None,
                         track_rostro: list = None, generar: bool = True,
                         nombre_video: str = "video", sol_pip_video: bool = False,
                         eventos_manual: list = None,
                         animaciones_manual: list = None) -> list:
    import f8_hyperframes
    eventos = []
    hf = config.USAR_HYPERFRAMES and f8_hyperframes.disponible()
    semilla = _semilla_video(nombre_video)
    if not hf:
        print("  AVISO: Hyperframes no disponible — overlays con el renderizador PIL de respaldo.")

    # ---- HOOK -------------------------------------------------------------
    # hook_manual gana siempre: es la vía para usar contexto/banco-hooks.md,
    # que tiene 40 hooks curados a <=7 palabras. Lo derivado de la
    # transcripción es el respaldo automático.
    texto_hook = (hook_manual or "").strip() or _texto_hook_desde_transcripcion(
        palabras, intervalos_conservados)
    texto_hook = texto_hook or "Mira esto"
    fin_hook = min(config.HOOK_DURACION_S, duracion_total)

    clip_hook = f8_hyperframes.render("banner-hook", {"texto": texto_hook}) if hf else None
    if clip_hook:
        # Migrado a Hyperframes: la versión de PIL era una tarjeta navy opaca;
        # esta es texto blanco con sombra, que respeta mejor la proporción
        # 80% metraje / 20% marca de la sección 5.3 y se ve más limpio.
        import f7_animaciones
        eventos.append({"tipo": "hook", "archivo": clip_hook, "medio": "video",
                        "x": 0, "y": 0, "ini": 0.0, "fin": fin_hook,
                        # texto/miniatura: solo para que el editor visual (§3c)
                        # pueda mostrar y editar el hook sin volver a derivarlo
                        "texto": texto_hook,
                        "miniatura": str(f7_animaciones.miniatura(clip_hook) or "")})
    else:
        ruta_hook = dir_tmp / "ov_hook.png"
        x, y, w, h = render_hook_banner(texto_hook, ruta_hook)
        eventos.append({"tipo": "hook", "archivo": ruta_hook, "x": x, "y": y,
                        "ini": 0.0, "fin": fin_hook, "texto": texto_hook})

    # ---- CTA DE CIERRE (con el eco que cierra el loop) ---------------------
    ini_cta = max(duracion_total - 6.5, 3.5)
    eco = _texto_eco_loop(texto_hook) if config.LOOP_ACTIVO else ""
    clip_cta = f8_hyperframes.render("tarjeta-cta", {
        "mensaje": "¡Pide el tuyo ya!",
        "whatsapp": config.WHATSAPP_NUMERO,
        "handle": config.TIKTOK_HANDLE,
        "eco": eco,
    }) if hf else None
    if clip_cta:
        import f7_animaciones
        eventos.append({"tipo": "cta", "archivo": clip_cta, "medio": "video",
                        "x": 0, "y": 0, "ini": ini_cta, "fin": duracion_total,
                        "eco": eco, "miniatura": str(f7_animaciones.miniatura(clip_cta) or "")})
        if eco:
            print(f"  loop: el CTA cierra con el eco del hook -> \"{eco}\"")
    else:
        ruta_cta = dir_tmp / "ov_cta.png"
        x, y, w, h = render_cta_cierre(ruta_cta, eco=eco)
        eventos.append({"tipo": "cta", "archivo": ruta_cta, "x": x, "y": y,
                        "ini": ini_cta, "fin": duracion_total, "eco": eco})

    ventanas_ocupadas = [(0.0, fin_hook), (ini_cta, duracion_total)]

    def _libre(t0, t1):
        return all(t1 <= a or t0 >= b for a, b in ventanas_ocupadas)

    # ---- ANIMACIONES ------------------------------------------------------
    # Para conceptos que ninguna foto ilustra bien: "batería" traía la foto de
    # un cargador; ahora es una batería que se llena contando semanas.
    # Motor primario Hyperframes (GSAP); PIL queda de respaldo.
    import f7_animaciones

    # La animación de sol enseña el aparato REAL del video (§3a del plan v2)
    producto_anim = _producto_dominante(palabras)
    foto_dispositivo = _foto_dispositivo(producto_anim)

    # nombre -> variantes ya usadas en este video. Antes era un `set` de
    # nombres que vetaba la segunda aparición de cualquier animación: por eso
    # decir "agua" traía splash y decir "tina" tres segundos después caía a una
    # foto de producto. Ahora el límite es ANIMACION_MAX_POR_TIPO y la segunda
    # sale con otra variante.
    anim_hechas, t_animaciones = {}, []
    # Etiquetas que a partir de ahora NO deben traer una foto del catálogo:
    # para estos conceptos la animación gana (config.CONCEPTOS_PREFIEREN_ANIMACION).
    tags_reservados = set()

    plan_animaciones = animaciones_manual
    if plan_animaciones is None:
        plan_animaciones = []
        for p in palabras:
            nombre = config.ANIMACIONES_POR_PALABRA.get(_normalizar(p["texto"]))
            if not nombre:
                continue
            plan_animaciones.append({"nombre": nombre, "ini": p["inicio"],
                                     "palabra": p["texto"]})

    # Las etiquetas reservadas salen de la TRANSCRIPCIÓN, no de la lista de
    # animaciones que se van a colocar. Dos razones:
    #  - una animación que no cabe no debe dejar entrar la foto en su lugar;
    #  - si José quita una animación desde el editor, en su hueco no debe
    #    aparecer sola una foto de producto. Quitar algo tiene que dejar un
    #    hueco, no invocar otra cosa por detrás.
    for p in palabras:
        n = _normalizar(p["texto"])
        if n not in config.ANIMACIONES_POR_PALABRA:
            continue
        tag_palabra = config.PALABRAS_A_TAGS.get(n)
        if tag_palabra in config.CONCEPTOS_PREFIEREN_ANIMACION:
            tags_reservados.add(tag_palabra)

    # Dos pasadas. En la primera solo entra la PRIMERA aparición de cada
    # concepto; las repeticiones esperan a la segunda.
    # Sin esto el orden del guion decidía por nosotros: "La batería dura semanas,
    # literalmente semanas, y además es resistente al agua" colocaba la segunda
    # batería a los 16.0s, esa ventana tapaba "resistente" a los 17.7s y el agua
    # se quedaba sin animación. Medido, no supuesto. Una segunda mención nunca
    # debe quitarle el sitio a la primera de otro concepto.
    # En manual no hay reordenamiento: la lista de José se respeta como está.
    pasadas = (0, 1) if animaciones_manual is None else (1,)
    colocadas = set()

    for pasada in pasadas:
        for i, entrada in enumerate(plan_animaciones):
            if i in colocadas:
                continue
            nombre = entrada.get("nombre")
            if nombre not in config.ANIMACION_DURACION:
                print(f"AVISO: animación desconocida '{nombre}' — se omite.")
                colocadas.add(i)
                continue
            t0 = float(entrada["ini"])
            palabra = entrada.get("palabra", "")

            previas = anim_hechas.setdefault(nombre, [])
            if pasada == 0 and previas:
                continue                     # su turno es la segunda pasada
            # En modo manual los límites son AVISO, no bloqueo: José ya decidió.
            if len(previas) >= config.ANIMACION_MAX_POR_TIPO:
                if animaciones_manual is not None:
                    print(f"  AVISO: '{nombre}' repetida {len(previas) + 1} veces "
                          f"(el automático corta en {config.ANIMACION_MAX_POR_TIPO}) — se respeta.")
                else:
                    continue
            # Separación contra TODAS las ya colocadas, no solo contra la última:
            # con dos pasadas el orden de colocación ya no es el orden del tiempo.
            if any(abs(t0 - tp) < config.ANIMACION_SEPARACION_MIN_S for tp in t_animaciones):
                if animaciones_manual is None:
                    continue
                print(f"  AVISO: animación en {t0:.1f}s a menos de "
                      f"{config.ANIMACION_SEPARACION_MIN_S}s de otra — se respeta.")

            dur = float(entrada.get("dur") or config.ANIMACION_DURACION.get(nombre, 2.4))
            t1 = t0 + dur
            if t1 > ini_cta > t0:
                # El CTA le comería el gesto por la mitad. Se adelanta lo justo para
                # que quepa entero, sin invadir el overlay anterior: enseñar media
                # animación y cortarla se lee peor que empezarla medio segundo antes.
                # (Caso real: "sol" se dice a 29.0s y el CTA entra a 30.7s — la
                # animación de 2.6s se quedaba en 1.7s.)
                fin_previo = max([b for a, b in ventanas_ocupadas if b <= t0] or [0.0])
                adelanto = min(t1 - ini_cta, max(0.0, t0 - fin_previo))
                if adelanto > 0.05:
                    t0 -= adelanto
                    t1 = t0 + dur
                    print(f"  animación '{nombre}' adelantada {adelanto:.2f}s para que "
                          f"entre completa antes del CTA")
                t1 = min(t1, ini_cta)
            if not _libre(t0, t1):
                if animaciones_manual is None:
                    continue
                print(f"  AVISO: animación '{nombre}' en {t0:.1f}s se pisa con otro overlay — se respeta.")

            n_var = config.ANIMACION_VARIANTES.get(nombre, 3)
            var = entrada.get("variante")
            var = int(var) % n_var if var is not None else _variante_aparicion(
                semilla, nombre, len(previas), n_var, previas)

            # El video real de sol solo sirve para la PRIMERA aparición: repetirlo
            # daría dos veces la misma toma, que es lo que José no quiere.
            usar_video_sol = bool(entrada.get("video_sol", sol_pip_video)) and not previas

            ruta_anim, x, y, motor = _construir_animacion(
                nombre, t0, var, dir_tmp, track_rostro, hf, semilla,
                foto_dispositivo=foto_dispositivo, usar_video_sol=usar_video_sol,
                indice=len(previas))
            if ruta_anim is None:
                print(f"AVISO: no se pudo construir la animación '{nombre}' para {t0:.1f}s.")
                colocadas.add(i)
                continue

            eventos.append({"tipo": f"anim-{nombre}", "archivo": ruta_anim, "medio": "video",
                            "x": x, "y": y, "ini": round(t0, 3), "fin": round(t1, 3),
                            "palabra": palabra,
                            # metadatos para el editor visual (§3c): qué animación
                            # es, con qué variante salió y con qué motor
                            "anim": nombre, "variante": var, "motor": motor,
                            "miniatura": str(f7_animaciones.miniatura(ruta_anim) or "")})
            ventanas_ocupadas.append((t0, t1))
            previas.append(var)
            t_animaciones.append(t0)
            colocadas.add(i)
            origen = f"por '{palabra}'" if palabra else "manual"
            print(f"  animación '{nombre}' (variante {var}, aparición {len(previas)}) "
                  f"{origen} en {t0:.1f}s [{motor}]")

    if tags_reservados:
        print(f"  conceptos con animación (no traen foto de catálogo): "
              f"{', '.join(sorted(tags_reservados))}")

    # ---- FICHA TÉCNICA ----------------------------------------------------
    # Se arma con el producto que detecta el guion, así que dos videos de
    # modelos distintos generan tarjetas distintas — no un gráfico fijo.
    producto_video = _producto_dominante(palabras)
    if producto_video and hf:
        ficha = config.ESPECIFICACIONES.get(producto_video)
        momento = next((p["inicio"] for p in palabras
                        if _normalizar(p["texto"]) in config.PALABRAS_SPECS), None)
        if ficha and momento is not None:
            t1 = momento + f8_hyperframes.DURACIONES["tarjeta-specs"]
            if _libre(momento, t1):
                variables = {"producto": ficha["nombre"]}
                for i, (etq, val) in enumerate(ficha["specs"][:3], start=1):
                    variables[f"spec{i}_label"] = etq
                    variables[f"spec{i}_valor"] = val
                clip = f8_hyperframes.render("tarjeta-specs", variables)
                if clip:
                    # Las composiciones de Hyperframes ocupan el lienzo completo
                    # 1080x1920 y ya se posicionan dentro de la franja superior,
                    # así que se superponen en 0,0 sin calcular offsets.
                    eventos.append({"tipo": "specs", "archivo": clip, "medio": "video",
                                    "x": 0, "y": 0, "ini": round(momento, 3),
                                    "fin": round(t1, 3)})
                    ventanas_ocupadas.append((momento, t1))
                    print(f"  ficha técnica ({ficha['nombre']}) en {momento:.1f}s [Hyperframes]")

    # ---- COMPARATIVA ------------------------------------------------------
    # Solo cuando el guion nombra DOS modelos distintos: si el video habla de un
    # solo aparato, una tabla comparativa sería relleno sin información.
    if hf:
        ev_comp = _planificar_comparativa(palabras, _libre)
        if ev_comp:
            eventos.append(ev_comp)
            ventanas_ocupadas.append((ev_comp["ini"], ev_comp["fin"]))

    # Insertos disparados por el guion. Antes había UN PiP fijo al 40% del
    # video, en un momento arbitrario y en una posición fija que caía sobre la
    # cara. Ahora se muestran cuando José nombra el tema y se ubican esquivando
    # el rostro con el track que ya calcula f4_retencion.
    # Respaldo de generación en GPU. El servidor de ComfyUI arranca de forma
    # perezosa: si todas las imágenes están en caché (o no hace falta ninguna),
    # no se levanta nunca y no cuesta un segundo.
    if eventos_manual is not None:
        # El editor visual v2 (Fase 2 del plan) ya decidió qué assets mostrar
        # y dónde: se usa tal cual, sin correr el disparo automático ni tocar
        # ComfyUI/Flux. "Reemplaza la lista completa de eventos [de inserto]",
        # distinto de --posiciones-manual que solo mueve los que el
        # automático ya eligió.
        insertos = eventos_manual
    else:
        import f9_generar
        pendientes = []
        servidor = f9_generar.ServidorCompartido() if (generar and config.GENERAR_HABILITADO) else None
        try:
            gen_fn = None
            if servidor is not None and f9_generar.instalado():
                gen_fn = lambda tag, frase: f9_generar.generar_para_tag(tag, frase, servidor=servidor)
            insertos = planificar_insertos_por_palabra(
                palabras, track_rostro or [], dir_tmp, _libre,
                generador=gen_fn, pendientes=pendientes,
                tags_reservados=tags_reservados)
        finally:
            if servidor is not None:
                servidor.cerrar()

        if pendientes:
            # Conceptos que el guion nombró y nadie pudo ilustrar: quedan anotados
            # con su prompt listo para generarlos fuera (Google Flow / Nano Banana).
            f9_generar.escribir_prompts_externos(pendientes)
            print(f"  {len(pendientes)} concepto(s) sin imagen -> contexto/prompts-externos.md")

    for ev in insertos:
        eventos.append(ev)
        ventanas_ocupadas.append((ev["ini"], ev["fin"]))
        origen = "manual" if eventos_manual is not None else f"por '{ev.get('palabra','')}' ({ev.get('tag','')})"
        print(f"  inserto {origen} en {ev['ini']:.1f}s -> {ev.get('asset','?')}")

    if not insertos and eventos_manual is None:
        # Respaldo: si el catálogo no tiene nada aplicable, al menos mostrar
        # una foto de producto si existe en assets/productos/
        foto_producto = _buscar_foto_producto_default()
        if foto_producto is not None:
            ini_pip = duracion_total * 0.4
            fin_pip = min(ini_pip + 3.5, ini_cta - 0.5)
            if fin_pip > ini_pip and _libre(ini_pip, fin_pip):
                ruta_pip = dir_tmp / "ov_pip.png"
                w_t, h_t = render_pip_producto(foto_producto, ruta_pip, ancho=400, alto=520,
                                               centrar_en_lienzo=False)
                x, y = _posicion_inserto(w_t, h_t, track_rostro or [], ini_pip)
                eventos.append({"tipo": "pip-producto", "archivo": ruta_pip, "x": x, "y": y,
                                "ini": ini_pip, "fin": fin_pip})
                ventanas_ocupadas.append((ini_pip, fin_pip))
        else:
            print("AVISO: sin insertos por palabra clave y sin fotos en assets/productos/.")

    # ---- STICKERS ---------------------------------------------------------
    # Migrados a Hyperframes: los de PIL eran una estrella y un tricolor
    # estáticos. Los de la plantilla entran con rebote, pulsan y la bandera
    # ondea — que es lo que hacen los stickers de la agencia (sección 5.1).
    ruta_destello = dir_tmp / "ov_destello.png"
    ruta_bandera = dir_tmp / "ov_bandera.png"
    if not hf:
        render_sticker_destello(ruta_destello)
        render_sticker_bandera(ruta_bandera)

    posiciones_esquina = [(60, 260), (ANCHO - 210, 260), (60, 1000), (ANCHO - 210, 1000)]
    idx_pos = 0
    dur_sticker = f8_hyperframes.DURACIONES["stickers"] if hf else 1.5

    def _agregar_sticker(clave: str, t0: float, tipo: str):
        nonlocal idx_pos
        t1 = min(t0 + dur_sticker, duracion_total)
        if hf:
            # `stickers.html` acepta destello | envio | bandera
            clip = f8_hyperframes.render("stickers", {"tipo": clave})
            if clip:
                eventos.append({"tipo": tipo, "archivo": clip, "medio": "video",
                                "x": 0, "y": 0, "ini": round(t0, 3), "fin": round(t1, 3)})
                ventanas_ocupadas.append((t0, t1))
                return True
        archivo = ruta_destello if clave == "destello" else ruta_bandera
        if not archivo.exists():
            render_sticker_destello(ruta_destello)
            render_sticker_bandera(ruta_bandera)
        x, y = posiciones_esquina[idx_pos % len(posiciones_esquina)]
        idx_pos += 1
        eventos.append({"tipo": tipo, "archivo": archivo, "x": x, "y": y,
                        "ini": round(t0, 3), "fin": round(t1, 3)})
        ventanas_ocupadas.append((t0, t1))
        return True

    vistos = set()
    for p in palabras:
        clave = PALABRAS_CLAVE_STICKER.get(_normalizar(p["texto"]))
        if clave and p["inicio"] not in vistos and _libre(p["inicio"], p["inicio"] + dur_sticker):
            vistos.add(p["inicio"])
            _agregar_sticker(clave, p["inicio"], f"sticker-{clave}")

    for hueco in huecos:
        centro = (hueco["inicio"] + hueco["fin"]) / 2
        if not _libre(centro, centro + dur_sticker):
            continue
        # sin azar: alterna por el segundo en que cae, así el render es reproducible
        clave = "destello" if int(centro) % 2 == 0 else "bandera"
        _agregar_sticker(clave, centro, "sticker-hueco")

    return eventos


# ---------------------------------------------------------------------------
# Comparativa lado a lado (Hyperframes) — solo si el guion nombra 2 modelos
# ---------------------------------------------------------------------------
def _modelos_mencionados(palabras: list) -> list:
    """Modelos nombrados, en orden de aparición y sin repetir."""
    modelos = {"paperwhite": "#paperwhite", "colorsoft": "#colorsoft",
               "scribe": "#scribe", "kobo": "#kobo", "basic": "#basic"}
    vistos, orden = set(), []
    for p in palabras:
        n = _normalizar(p["texto"])
        for clave, tag in modelos.items():
            if clave in n and tag not in vistos:
                vistos.add(tag)
                orden.append({"tag": tag, "t": p["inicio"]})
    return orden


def _planificar_comparativa(palabras: list, libre_fn) -> dict | None:
    """Tabla A vs B cuando el video compara dos modelos.

    Se dispara con dos condiciones juntas: que aparezcan DOS modelos distintos y
    que existan specs de ambos en config.ESPECIFICACIONES. Si el video habla de
    un solo aparato no se muestra nada — una comparativa de relleno le quitaría
    sitio a un inserto que sí aporta.
    """
    import f8_hyperframes

    modelos = _modelos_mencionados(palabras)
    if len(modelos) < 2:
        return None
    a, b = modelos[0], modelos[1]
    ficha_a = config.ESPECIFICACIONES.get(a["tag"])
    ficha_b = config.ESPECIFICACIONES.get(b["tag"])
    if not (ficha_a and ficha_b):
        return None

    # Momento: cuando se nombra el segundo modelo, que es donde el espectador
    # necesita ver la diferencia.
    t0 = b["t"]
    dur = f8_hyperframes.DURACIONES["comparativa"]
    if not libre_fn(t0, t0 + dur):
        # se prueba justo después, por si el segundo modelo cae dentro del hook
        t0 = t0 + dur
        if not libre_fn(t0, t0 + dur):
            return None

    variables = {"modeloA": ficha_a["nombre"], "modeloB": ficha_b["nombre"]}
    for i, (_, val) in enumerate(ficha_a["specs"][:3], start=1):
        variables[f"specA{i}"] = val
    for i, (_, val) in enumerate(ficha_b["specs"][:3], start=1):
        variables[f"specB{i}"] = val

    clip = f8_hyperframes.render("comparativa", variables)
    if clip is None:
        return None
    print(f"  comparativa {ficha_a['nombre']} vs {ficha_b['nombre']} en {t0:.1f}s [Hyperframes]")
    return {"tipo": "comparativa", "archivo": clip, "medio": "video",
            "x": 0, "y": 0, "ini": round(t0, 3), "fin": round(t0 + dur, 3)}


def componer_overlays(ruta_video: Path, eventos: list, ruta_salida: Path, duracion_total: float):
    inputs = ["-i", str(ruta_video)]
    for ev in eventos:
        # Sin -loop 1 -t, ffmpeg lee el PNG como UN solo frame en PTS=0: el filtro
        # fade de abajo evaluaría su rampa de opacidad una sola vez en t=0 y esa
        # imagen (casi transparente) quedaría "congelada" así para todo el video
        # (overlay repite el último frame al llegar a EOF). Hay que darle duración
        # real para que el fade avance en el tiempo como corresponde.
        inputs += ["-loop", "1", "-framerate", str(config.FPS), "-t", f"{duracion_total:.3f}", "-i", str(ev["archivo"])]

    filtro_partes = []
    etiqueta_actual = "0:v"
    for i, ev in enumerate(eventos, start=1):
        salida_etiqueta = f"v{i}"
        dur_fade = 0.15
        filtro_partes.append(
            f"[{i}:v]format=rgba,fade=t=in:st={ev['ini']:.3f}:d={dur_fade}:alpha=1,"
            f"fade=t=out:st={ev['fin'] - dur_fade:.3f}:d={dur_fade}:alpha=1[ov{i}]"
        )
        filtro_partes.append(
            f"[{etiqueta_actual}][ov{i}]overlay={ev['x']}:{ev['y']}:"
            f"enable='between(t,{ev['ini']:.3f},{ev['fin']:.3f})'[{salida_etiqueta}]"
        )
        etiqueta_actual = salida_etiqueta

    filtro = ";".join(filtro_partes)
    cmd = [
        "ffmpeg", "-y", *inputs,
        "-filter_complex", filtro,
        "-map", f"[{etiqueta_actual}]", "-map", "0:a",
        *config.args_video(),
        "-c:a", "copy",
        str(ruta_salida),
    ]
    print(f"Componiendo {len(eventos)} overlays...")
    resultado = subprocess.run(cmd, capture_output=True, text=True)
    if resultado.returncode != 0:
        print(resultado.stderr[-4000:], file=sys.stderr)
        raise RuntimeError("ffmpeg falló al componer overlays")


def aplicar_posiciones_manual(eventos: list, ruta_json: Path) -> int:
    """Sobrescribe la posición de los insertos con la que eligió José a mano.

    La automática (esquivar el rostro, franja superior) funciona bien, pero hay
    encuadres donde él quiere el inserto en otro sitio. El JSON lo produce el
    editor visual (f10_editor_visual.py).

    El emparejamiento es por (tipo, instante), no por índice: si el guion cambia
    y aparece un inserto más, los ajustes viejos siguen cayendo donde deben en
    vez de desplazarse todos.
    """
    if not ruta_json.exists():
        print(f"AVISO: no existe {ruta_json} — se usan las posiciones automáticas.")
        return 0
    try:
        ajustes = json.loads(ruta_json.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"AVISO: {ruta_json} no es un JSON válido ({e}) — posiciones automáticas.")
        return 0
    if isinstance(ajustes, dict):
        ajustes = ajustes.get("posiciones", [])

    aplicados = 0
    for a in ajustes:
        candidatos = [ev for ev in eventos
                      if ev["tipo"] == a.get("tipo")
                      and abs(ev["ini"] - float(a.get("ini", -99))) < 0.4]
        if not candidatos:
            print(f"AVISO: sin overlay '{a.get('tipo')}' cerca de {a.get('ini')}s — ajuste ignorado.")
            continue
        ev = candidatos[0]
        ev["x"], ev["y"] = int(a["x"]), int(a["y"])
        aplicados += 1
        print(f"  posición manual: {ev['tipo']} en {ev['ini']:.1f}s -> x={ev['x']} y={ev['y']}")
    return aplicados


def cargar_eventos_manual(ruta_json: Path, dir_tmp: Path, catalogo: list = None) -> list | None:
    """Lista completa de insertos `pip-producto` armada a mano en el editor
    visual (Fase 2 del plan v2): sustituir, añadir y quitar sin correr el
    disparo automático. Cada entrada trae {ini, fin, x, y, asset_id} (o
    "archivo" si ya tiene un PNG renderizado — p.ej. uno que el editor no
    tocó). Si trae asset_id, se busca en el catálogo y se renderiza con
    render_pip_producto(); el resultado se cachea por asset_id para no
    volver a renderizar en cada --reaplicar.

    None si el archivo no existe o no es válido (respaldo: automático).
    """
    if not ruta_json.exists():
        print(f"AVISO: no existe {ruta_json} — se usa el disparo automático de insertos.")
        return None
    try:
        datos = json.loads(ruta_json.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"AVISO: {ruta_json} no es un JSON válido ({e}) — disparo automático.")
        return None
    if isinstance(datos, dict):
        datos = datos.get("eventos", [])

    catalogo = _cargar_catalogo() if catalogo is None else catalogo
    por_id = {a["id"]: a for a in catalogo}

    eventos = []
    for i, ev in enumerate(datos):
        asset_id = ev.get("asset_id")
        archivo = ev.get("archivo")
        if asset_id:
            asset = por_id.get(asset_id)
            if asset is None:
                print(f"AVISO: asset_id '{asset_id}' no está en el catálogo — evento manual #{i} omitido.")
                continue
            ruta_img = _version_sin_fondo(asset) or (config.RAIZ_PROYECTO / asset["ruta"])
            if not ruta_img.exists():
                print(f"AVISO: no existe el archivo de '{asset_id}' — evento manual #{i} omitido.")
                continue
            nombre_cache = re.sub(r"[^\w-]", "_", asset_id)
            ruta_png = dir_tmp / f"manual_{nombre_cache}.png"
            if not ruta_png.exists():
                render_pip_producto(ruta_img, ruta_png, ancho=400, alto=520, centrar_en_lienzo=False)
        elif archivo and Path(archivo).exists():
            ruta_png = Path(archivo)
        else:
            print(f"AVISO: evento manual #{i} sin 'asset_id' ni 'archivo' válido — omitido.")
            continue

        try:
            ini, fin = float(ev["ini"]), float(ev["fin"])
        except (KeyError, TypeError, ValueError):
            print(f"AVISO: evento manual #{i} sin ini/fin válidos — omitido.")
            continue

        eventos.append({
            "tipo": ev.get("tipo", "pip-producto"), "archivo": ruta_png,
            "x": int(ev.get("x", 0)), "y": int(ev.get("y", 0)),
            "ini": round(ini, 3), "fin": round(fin, 3),
            "palabra": ev.get("palabra", ""), "tag": ev.get("tag", ""),
            "asset": asset_id or ev.get("asset", "manual"),
        })
    return eventos


def cargar_animaciones_manual(ruta_json: Path) -> list | None:
    """Lista completa de animaciones armada en el editor visual (§3c del plan).

    Es a las animaciones lo que `--eventos-manual` es a los insertos: reemplaza
    el disparo por palabra entero, así que sirve para **quitar** una animación
    (no ponerla en la lista), **moverla** (otro `ini`) y **añadirla** en un
    segundo cualquiera eligiendo del inventario (`f8_hyperframes.inventario_animaciones()`).

    Cada entrada: {"nombre": "sol", "ini": 28.9} y, opcionales, "dur",
    "variante" (para fijar una toma concreta en vez de la determinista) y
    "video_sol" (usar assets/sol_video_pip.mov en vez de la animación HTML).
    Una lista vacía es una orden válida: "este video no lleva animaciones".

    None si el archivo no existe o no es válido — entonces manda el automático.
    """
    if not ruta_json.exists():
        print(f"AVISO: no existe {ruta_json} — se usa el disparo automático de animaciones.")
        return None
    try:
        datos = json.loads(ruta_json.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"AVISO: {ruta_json} no es un JSON válido ({e}) — disparo automático.")
        return None
    if isinstance(datos, dict):
        datos = datos.get("animaciones", [])
    if not isinstance(datos, list):
        print(f"AVISO: {ruta_json} no contiene una lista — disparo automático.")
        return None

    limpias = []
    for i, a in enumerate(datos):
        nombre = a.get("nombre") or str(a.get("tipo", "")).replace("anim-", "")
        try:
            ini = float(a["ini"])
        except (KeyError, TypeError, ValueError):
            print(f"AVISO: animación manual #{i} sin 'ini' válido — omitida.")
            continue
        limpias.append({k: v for k, v in {
            "nombre": nombre, "ini": ini, "dur": a.get("dur"),
            "variante": a.get("variante"), "video_sol": a.get("video_sol"),
            "palabra": a.get("palabra", ""),
        }.items() if v is not None})
    limpias.sort(key=lambda a: a["ini"])
    print(f"Animaciones manuales cargadas desde {ruta_json}: {len(limpias)} "
          f"(se ignora el disparo por palabra)")
    return limpias


def _duracion_video(ruta: Path) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration",
           "-of", "default=noprint_wrappers=1:nokey=1", str(ruta)]
    salida = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(salida.stdout.strip())


def main():
    parser = argparse.ArgumentParser(description="Overlays: hook, CTA, stickers")
    parser.add_argument("video", type=str)
    parser.add_argument("plan_retencion", type=str)
    parser.add_argument("transcripcion", type=str)
    parser.add_argument("--salida", type=str, default=None)
    parser.add_argument("--solo-planificar", type=str, default=None, metavar="EVENTOS_JSON",
                        help="No compone video: genera los PNG y escribe la lista de eventos en este JSON, "
                             "para que f4_retencion los componga dentro de su propia codificación")
    parser.add_argument("--hook", type=str, default=None, metavar="TEXTO",
                        help="Texto del banner de hook. Si se omite, se usa la primera frase completa "
                             "del video. Para hooks curados ver contexto/banco-hooks.md (40 opciones).")
    parser.add_argument("--sin-generar", action="store_true",
                        help="No usar ComfyUI/Flux como respaldo cuando el catálogo no tenga imagen "
                             "para un concepto (la primera generación cuesta ~40s de arranque)")
    parser.add_argument("--posiciones-manual", type=str, default=None, metavar="JSON",
                        help="Posiciones de insertos elegidas a mano (las exporta el editor "
                             "visual, f10_editor_visual.py). Reemplazan a las automáticas.")
    parser.add_argument("--eventos-manual", type=str, default=None, metavar="JSON",
                        help="Lista completa de insertos pip-producto armada en el editor visual "
                             "(Fase 2): sustituye QUÉ asset se muestra, no solo dónde. Distinto de "
                             "--posiciones-manual.")
    parser.add_argument("--nombre-video", type=str, default=None,
                        help="Nombre del video: de aquí sale la semilla determinista que elige la "
                             "variante de cada animación. Mismo nombre = mismo resultado siempre.")
    parser.add_argument("--animaciones-manual", type=str, default=None, metavar="JSON",
                        help="Lista completa de animaciones armada en el editor visual "
                             "(Fase 3c): quita, mueve y añade animaciones. Reemplaza el "
                             "disparo por palabra.")
    parser.add_argument("--sol-pip-video", action="store_true",
                        help="Usar el video de sol en vez de la animación HTML")
    args = parser.parse_args()

    ruta_video = Path(args.video)
    plan = json.loads(Path(args.plan_retencion).read_text(encoding="utf-8"))
    datos_transcripcion = json.loads(Path(args.transcripcion).read_text(encoding="utf-8"))
    palabras = datos_transcripcion["palabras"]

    ruta_salida = Path(args.salida) if args.salida else ruta_video.with_name(ruta_video.stem + "_overlays.mp4")
    dir_tmp = (Path(args.solo_planificar).parent if args.solo_planificar else ruta_salida.parent) / "_tmp_overlays"
    dir_tmp.mkdir(exist_ok=True)

    duracion = _duracion_video(ruta_video)
    intervalos_conservados = datos_transcripcion.get("intervalos_conservados_original", [])

    eventos_manual = None
    if args.eventos_manual:
        eventos_manual = cargar_eventos_manual(Path(args.eventos_manual), dir_tmp)

    animaciones_manual = None
    if args.animaciones_manual:
        animaciones_manual = cargar_animaciones_manual(Path(args.animaciones_manual))

    eventos = planificar_overlays(palabras, plan.get("huecos_regla_5s", []), duracion, dir_tmp,
                                   intervalos_conservados=intervalos_conservados,
                                   hook_manual=args.hook,
                                   track_rostro=plan.get("track_rostro", []),
                                   generar=not args.sin_generar,
                                   nombre_video=args.nombre_video or ruta_video.stem,
                                   sol_pip_video=args.sol_pip_video,
                                   eventos_manual=eventos_manual,
                                   animaciones_manual=animaciones_manual)

    if args.posiciones_manual:
        aplicar_posiciones_manual(eventos, Path(args.posiciones_manual))

    print(f"Overlays planificados: {len(eventos)}")
    for ev in eventos:
        print(f"  [{ev['ini']:.1f}s-{ev['fin']:.1f}s] {ev['tipo']}")

    if args.solo_planificar:
        eventos_serializables = [{**ev, "archivo": str(ev["archivo"])} for ev in eventos]
        Path(args.solo_planificar).write_text(
            json.dumps(eventos_serializables, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nEventos de overlay guardados: {args.solo_planificar}")
    else:
        componer_overlays(ruta_video, eventos, ruta_salida, duracion)
        print(f"\nVideo con overlays: {ruta_salida}")

    if not any(ev["tipo"] == "pip-producto" for ev in eventos):
        print("\nNOTA: no se incluyó inserto PiP de producto — no se encontró ninguna foto en "
              "assets/productos/*/frontal*.jpg, o no hubo una ventana libre para insertarlo. "
              "Specs y comparativa tampoco se generan todavía (necesitan datos del catálogo real, "
              "ver render_tarjeta_generica()).")


if __name__ == "__main__":
    main()
