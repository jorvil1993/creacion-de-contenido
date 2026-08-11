"""Capa de marca: compone texto, logo y CTA sobre una escena y lo rinde a PNG/JPG.

El texto NO se dibuja con PIL ni se le pide a un modelo de imagen: se maqueta en
HTML/CSS y lo rinde Chrome headless. Es la unica forma de que la tipografia salga
como en un arte de agencia (kerning, mayusculas, sombras) y de que el mismo bloque
se reacomode solo al pasar de cuadrado a vertical.

Se rinde al doble y se baja con LANCZOS: el texto queda con bordes limpios en vez
del antialiasing pobre de un render 1:1.
"""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from artes import a5_sellos, a7_iconos

RAIZ = Path(__file__).resolve().parent.parent
FUENTES = RAIZ / "assets" / "fuentes"
LOGO_NAVY = (
    RAIZ / "contexto" / "LOGOS IVAN" / "drive-download-20260702T141516Z-3-001"
    / "deviceshop color.png"
)
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

# Medido pixel a pixel sobre los 36 artes reales. voz-de-marca.md trae otros
# valores (#0A2A3E / #4FD1D9) pero fueron a ojo: mandan estos.
TURQUESA = "#00C7CA"
NAVY = "#011A2E"

# "retrato" (4:5) es el formato que Meta prioriza en el feed desde 2026, y ademas
# sobrevive mejor a la grilla del perfil de Instagram, que desde enero de 2026
# recorta TODA miniatura a 3:4 (al cuadrado le come los costados). Se agrego
# despues de los otros dos a proposito: el default sigue siendo cuadrado para no
# cambiar solo lo que ya se venia publicando.
FORMATOS = {
    "cuadrado": (1080, 1080),
    "retrato": (1080, 1350),
    "vertical": (1080, 1920),
}

# Lo que la grilla de Instagram deja ver de cada formato: recorta al centro en
# 3:4. En 4:5 se pierde una franja arriba y otra abajo; en cuadrado se pierden
# los costados. `caja_segura()` devuelve ese rectangulo para dibujar la guia.
GRILLA_IG = 3 / 4  # ancho / alto


def caja_segura(formato: str) -> tuple[int, int, int, int]:
    """(x, y, ancho, alto) de lo que sobrevive al recorte 3:4 de la grilla de IG."""
    ancho, alto = FORMATOS[formato]
    if ancho / alto > GRILLA_IG:      # mas ancho que 3:4 -> se cortan los lados
        w = round(alto * GRILLA_IG)
        return ((ancho - w) // 2, 0, w, alto)
    h = round(ancho / GRILLA_IG)      # mas alto que 3:4 -> se corta arriba y abajo
    return (0, (alto - h) // 2, ancho, h)

# 2x es donde el texto deja de ganar nitidez visible y el intermedio todavia
# cabe comodo en memoria.
ESCALA = 2

# Escenas de estudio, sin IA ni foto. Jose ya publico artes asi (el verde de
# "CLARIDAD QUE ENGANCHA", el lila de "COMODIDAD CONTROL").
ESCENAS = {
    "navy":   ("linear-gradient(160deg,#03243c 0%,#01466b 55%,#016b7d 100%)", "rgba(0,199,202,.30)"),
    "calida": ("linear-gradient(160deg,#2b1d12 0%,#6b4426 55%,#c98a4b 100%)", "rgba(255,190,120,.28)"),
    "clara":  ("linear-gradient(160deg,#eef6f8 0%,#cfe9ee 55%,#a9dbe3 100%)", "rgba(255,255,255,.55)"),
    "verde":  ("linear-gradient(160deg,#0e3a2c 0%,#1c6b4f 55%,#3fa07a 100%)", "rgba(120,255,200,.22)"),
    "lila":   ("linear-gradient(160deg,#2a1740 0%,#5b3286 55%,#9b6fc4 100%)", "rgba(200,150,255,.26)"),
    "coral":  ("linear-gradient(160deg,#3d1420 0%,#8c2f44 55%,#d9756e 100%)", "rgba(255,160,150,.26)"),
}

# En fondo claro el texto blanco desaparece: el titular y la bajada pasan a navy.
ESCENAS_CLARAS = {"clara"}


@dataclass
class Arte:
    """Un arte. Los tamanos de letra se derivan del lienzo, no se fijan a mano."""

    titular: str  # admite <span class="acento"> para la palabra en turquesa
    producto: str
    bajada: str = ""
    escena: str = "navy"          # clave de ESCENAS, o None si se usa foto
    foto_fondo: Path | None = None  # foto de escena a sangre (pisa a `escena`)
    recorte: Path | None = None     # producto con alfa, se compone encima
    recorte_alto: float = 40.0      # % del alto del lienzo que ocupa el producto
    recorte_y: float = 60.0         # % del alto, centro del producto
    recorte_x: float = 50.0         # % del ancho, centro del producto
    formato: str = "cuadrado"
    sello: str = ""              # clave de a5_sellos: anios | moto | manos | ""
    # Jose la mando apagar por defecto (2026-08-01): el CTA se le metia dentro
    # y ademas satura. Queda opcional para el arte que la pida.
    confianza: list[str] = field(default_factory=list)
    # (dato, texto, x%, y%) — el arquetipo de callouts flotantes.
    callouts: list[tuple[str, str, float, float]] = field(default_factory=list)
    # (icono, titulo, descripcion) — el arquetipo de lista de fichas.
    fichas: list[tuple[str, str, str]] = field(default_factory=list)
    fichas_vidrio: bool = False   # el difuminado que pidio Jose, opcional
    # (dolor, solucion) — el modo que pidio Jose: conectar con lo que el
    # cliente quiere resolver, no listar caracteristicas.
    dolores: list[tuple[str, str]] = field(default_factory=list)
    # (img_dolor, etiqueta_dolor, img_solucion, etiqueta_solucion)
    split: tuple[Path, str, Path, str] | None = None
    # Para el carrusel de TikTok (2026-08-04): las slides que no son la ultima
    # no llevan CTA de WhatsApp (solo la ultima cierra con eso), y el pie
    # entero (logo + CTA, comparten alto y base) se dibuja mas chico para que
    # las fotos respiren. Default = comportamiento de siempre en TODO lo
    # demas -- ningun arte existente cambia si no pasa estos dos campos.
    pie_whatsapp: bool = True
    pie_escala: float = 1.0
    # Moldes de solo texto del carrusel de diseño (2026-08-05). En el arte de
    # siempre el bloque de texto va arriba porque abajo esta el producto; en una
    # slide sin foto eso deja un hueco enorme al pie. `texto_centro` lo centra
    # en el alto util (descontando el pie) y `titular_escala` agranda el titular
    # -- un numero solo o una frase corta necesitan mucho mas cuerpo que un
    # titular normal. Los dos con default = el arte de siempre, sin cambios.
    texto_centro: bool = False
    titular_escala: float = 1.0
    # --- moldes de 2026-08-10 ---------------------------------------------
    # Los tres formatos estaticos que mas convierten en Meta y que el panel no
    # sabia hacer. Todos con default vacio: ningun arte existente cambia.
    #
    # Linea chica en mayusculas encima del titular ("CONVERSACIÓN REAL · SANTA
    # CRUZ"). Sirve en cualquier molde, no solo en los nuevos.
    kicker: str = ""
    # (quien, texto) con quien in {"suya", "mia"} — la captura de WhatsApp.
    # `texto` admite <b>. El objetivo de la cuenta es MESSAGES: la creatividad
    # que parece un chat es la que mejor convierte en click-to-WhatsApp.
    chat: list[tuple[str, str]] = field(default_factory=list)
    # Oferta apilada. `precio` se escribe entero ("2.390") porque los precios
    # cambian seguido y el numero lo pone Jose cada vez, nunca el codigo.
    precio: str = ""
    moneda: str = "Bs"
    precio_rotulo: str = "Precio"
    incluye: list[str] = field(default_factory=list)
    # (criterio, lo malo, lo bueno) — la tabla de comparacion. Distinto de
    # `split`, que son dos fotos; esto es texto en filas.
    filas: list[tuple[str, str, str]] = field(default_factory=list)
    filas_titulos: tuple[str, str] = ("TABLET", "E-READER")
    # Donde arranca el bloque del molde, en % del alto. Depende de cuantas
    # lineas tenga el titular, por eso es un campo y no una constante.
    bloque_top: float = 23.0


def _uri(p: Path) -> str:
    return p.resolve().as_uri()


def render(arte: Arte, salida: Path) -> Path:
    ancho, alto = FORMATOS[arte.formato]
    w, h = ancho * ESCALA, alto * ESCALA
    base = w  # todas las medidas se derivan del ancho: un solo numero manda

    plantilla = (RAIZ / "artes" / "plantillas" / "hook-escena.html").read_text(
        encoding="utf-8"
    )

    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        # Se copia el logo a un temporal solo para tener una ruta file:// estable.
        logo = tmpd / "logo.png"
        Image.open(LOGO_NAVY).save(logo)

        if arte.foto_fondo:
            capa_fondo = (
                f'<div class="escena-foto"><img src="{_uri(arte.foto_fondo)}" alt="">'
                '</div><div class="velo"></div>'
            )
            grad, halo = "", ""
        else:
            grad, halo = ESCENAS[arte.escena]
            capa_fondo = '<div class="escena"><div class="halo"></div></div>'

        claro = (not arte.foto_fondo) and arte.escena in ESCENAS_CLARAS

        capa_prod = ""
        if arte.recorte:
            capa_prod = (
                f'<div class="producto-img"><img src="{_uri(arte.recorte)}" alt="">'
                "</div>"
            )

        callouts_html = "".join(
            f'<div class="callout" style="left:{x}%;top:{y}%">'
            f'<span class="dato">{dato}</span>{texto}</div>'
            for dato, texto, x, y in arte.callouts
        )

        fichas_html = ""
        if arte.fichas:
            filas = "".join(
                f'<div class="ficha"><span class="ico">{a7_iconos.html(ic)}</span>'
                f'<span class="txt"><span class="tit">{tit}</span>'
                f'<span class="des">{des}</span></span></div>'
                for ic, tit, des in arte.fichas
            )
            clase = "fichas vidrio" if arte.fichas_vidrio else "fichas"
            fichas_html = f'<div class="{clase}">{filas}</div>'

        dolores_html = ""
        if arte.dolores:
            equis = ('<svg viewBox="0 0 24 24" fill="none" stroke="#fff" '
                     'stroke-width="3.6" stroke-linecap="round">'
                     '<path d="M6 6l12 12M18 6L6 18"/></svg>')
            tick = ('<svg viewBox="0 0 24 24" fill="none" stroke="#011A2E" '
                    'stroke-width="3.6" stroke-linecap="round" '
                    'stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>')
            filas = "".join(
                f'<div class="dolor">'
                f'<span class="mal"><span class="marca">{equis}</span>'
                f'<span class="t">{mal}</span></span>'
                f'<span class="bien"><span class="marca">{tick}</span>'
                f'<span class="t">{bien}</span></span></div>'
                for mal, bien in arte.dolores
            )
            cl = "dolores vidrio" if arte.fichas_vidrio else "dolores"
            dolores_html = f'<div class="{cl}">{filas}</div>'

        split_html = ""
        if arte.split:
            im1, et1, im2, et2 = arte.split
            split_html = (
                '<div class="split">'
                f'<div class="mitad mal"><img src="{_uri(im1)}" alt="">'
                f'<span class="chip">{et1}</span></div>'
                '<div class="sep"></div>'
                f'<div class="mitad sano"><img src="{_uri(im2)}" alt="">'
                f'<span class="chip">{et2}</span></div></div>'
            )

        tic_svg = ('<svg viewBox="0 0 24 24" fill="none" stroke="#011A2E" '
                   'stroke-width="3.4" stroke-linecap="round" '
                   'stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>')

        kicker_html = (f'<div class="kicker">{arte.kicker}</div>'
                       if arte.kicker else "")

        chat_html = ""
        if arte.chat:
            # Las horas son decorativas y correlativas: sin ellas la burbuja no
            # se lee como WhatsApp, y poner la hora real del render seria peor
            # (el arte se publica otro dia).
            burbujas = "".join(
                f'<div class="b {quien}">{texto}'
                f'<span class="hora">14:{i * 2:02d}</span></div>'
                for i, (quien, texto) in enumerate(arte.chat)
            )
            chat_html = f'<div class="bloque chat">{burbujas}</div>'

        precio_html = ""
        if arte.precio:
            precio_html = (
                '<div class="precio">'
                f'<div class="rotulo">{arte.precio_rotulo}</div>'
                f'<div class="num"><small>{arte.moneda}</small> {arte.precio}</div>'
                "</div>"
            )

        incluye_html = ""
        if arte.incluye:
            items = "".join(
                f'<div class="it"><span class="tic">{tic_svg}</span>{t}</div>'
                for t in arte.incluye
            )
            incluye_html = f'<div class="incluye">{items}</div>'

        filas_html = ""
        if arte.filas:
            cuerpo = "".join(
                f'<div class="fila"><div class="et">{et}</div>'
                f'<div class="cel mal">{mal}</div>'
                f'<div class="cel bien">{bien}</div></div>'
                for et, mal, bien in arte.filas
            )
            t_mal, t_bien = arte.filas_titulos
            filas_html = (
                '<div class="bloque tabla">'
                f'<div class="cabeza"><div class="chip mal">{t_mal}</div>'
                f'<div class="chip bien">{t_bien}</div></div>'
                f"{cuerpo}</div>"
            )

        interior = a5_sellos.html(arte.sello)
        sello_html = f'<div class="sello">{interior}</div>' if interior else ""

        cta_html = "" if not arte.pie_whatsapp else (
            '<div class="cta">'
            '<div class="fila">'
            '<svg viewBox="0 0 24 24" fill="#011A2E"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2 22l5.25-1.38a9.9 9.9 0 0 0 4.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2zm0 18.15h-.01a8.2 8.2 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.22 8.22 0 0 1-1.26-4.38c0-4.54 3.7-8.23 8.25-8.23 2.2 0 4.27.86 5.83 2.42a8.18 8.18 0 0 1 2.41 5.82c0 4.54-3.7 8.23-8.24 8.23zm4.52-6.16c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.13-.16.24-.64.8-.78.97-.14.16-.29.18-.54.06-.25-.12-1.05-.39-1.99-1.23-.74-.66-1.23-1.47-1.38-1.72-.14-.25-.01-.38.11-.5.11-.11.25-.29.37-.43.13-.15.17-.25.25-.41.08-.17.04-.31-.02-.43-.06-.12-.56-1.34-.76-1.84-.2-.48-.4-.42-.56-.43h-.48c-.16 0-.43.06-.65.31-.22.25-.85.83-.85 2.03s.87 2.35.99 2.51c.12.16 1.71 2.61 4.15 3.66.58.25 1.03.4 1.39.51.58.19 1.11.16 1.53.1.47-.07 1.47-.6 1.67-1.18.21-.58.21-1.07.15-1.18-.06-.11-.22-.17-.47-.29z"/></svg>'
            '<span class="txt">CONTÁCTANOS</span>'
            '</div>'
            '<div class="fila oscura"><span class="num">692-14437</span></div>'
            '</div>'
        )

        tic = (
            '<span class="tic"><svg viewBox="0 0 24 24" fill="none" stroke="#011A2E" '
            'stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M20 6 9 17l-5-5"/></svg></span>'
        )
        confianza_html = (
            '<div class="confianza">'
            + "".join(f"<span>{tic}{t}</span>" for t in arte.confianza)
            + "</div>"
        ) if arte.confianza else ""

        reemplazos = {
            "__F__": _uri(FUENTES),
            "__W__": str(w),
            "__H__": str(h),
            "__CAPA_FONDO__": capa_fondo,
            "__CAPA_PRODUCTO__": capa_prod,
            "__CALLOUTS__": callouts_html,
            "__FICHAS__": fichas_html,
            "__DOLORES__": dolores_html,
            "__SPLIT__": split_html,
            "__ESCENA__": grad,
            "__HALO__": halo,
            "__HALO_Y__": f"{arte.recorte_y:.1f}",
            "__PROD_H__": f"{arte.recorte_alto:.1f}",
            "__PROD_X__": f"{arte.recorte_x:.1f}",
            "__PROD_Y__": f"{arte.recorte_y:.1f}",
            "__LOGO__": _uri(logo),
            "__TITULAR__": arte.titular,
            "__PRODUCTO__": arte.producto,
            "__BAJADA__": arte.bajada,
            "__SELLO__": sello_html,
            "__CTA__": cta_html,
            # --- moldes chat / precio / comparativa (2026-08-10) ---
            "__KICKER__": kicker_html,
            "__CHAT__": chat_html,
            "__PRECIO__": precio_html,
            "__INCLUYE__": incluye_html,
            "__FILAS__": filas_html,
            "__BLOQUE_TOP__": f"{arte.bloque_top:.1f}",
            "__BLO_GAP__": f"{base * 0.030:.0f}",
            "__KICK_F__": f"{base * 0.026:.1f}",
            "__KICK_MB__": f"{base * 0.012:.0f}",
            "__CH_RAD__": f"{base * 0.028:.0f}",
            "__CH_PAD__": f"{base * 0.030:.0f}",
            "__CH_GAP__": f"{base * 0.020:.0f}",
            "__CH_S__": f"{base * 0.012:.0f}",
            "__CH_S2__": f"{base * 0.040:.0f}",
            "__CH_BPY__": f"{base * 0.019:.0f}",
            "__CH_BPX__": f"{base * 0.024:.0f}",
            "__CH_BRAD__": f"{base * 0.020:.0f}",
            "__CH_PICO__": f"{base * 0.006:.0f}",
            "__CH_F__": f"{base * 0.0285:.1f}",
            "__CH_HF__": f"{base * 0.017:.1f}",
            "__CH_HMT__": f"{base * 0.004:.0f}",
            "__PR_RF__": f"{base * 0.024:.1f}",
            "__PR_NF__": f"{base * 0.115:.1f}",
            "__PR_MF__": f"{base * 0.045:.1f}",
            "__IN_RAD__": f"{base * 0.024:.0f}",
            "__IN_PY__": f"{base * 0.026:.0f}",
            "__IN_PX__": f"{base * 0.028:.0f}",
            "__IN_GAP__": f"{base * 0.016:.0f}",
            "__IN_ICOGAP__": f"{base * 0.014:.0f}",
            "__IN_F__": f"{base * 0.026:.1f}",
            "__IN_ICO__": f"{base * 0.030:.0f}",
            "__TB_GAP__": f"{base * 0.014:.0f}",
            "__TB_CF__": f"{base * 0.030:.1f}",
            "__TB_CP__": f"{base * 0.014:.0f}",
            "__TB_EF__": f"{base * 0.023:.1f}",
            "__TB_EMB__": f"{base * 0.008:.0f}",
            "__TB_RAD__": f"{base * 0.020:.0f}",
            "__TB_PY__": f"{base * 0.020:.0f}",
            "__TB_PX__": f"{base * 0.022:.0f}",
            "__TB_F__": f"{base * 0.026:.1f}",
            "__CONFIANZA__": confianza_html,
            # El sello vive arriba a la derecha; sin este margen el titular se
            # le mete debajo y la ultima palabra queda ilegible.
            "__TXT_MAX__": "74" if arte.sello else "100",
            "__FI_MT__": f"{base * 0.026:.0f}",
            "__SELLO_PX__": f"{base * a5_sellos.ancho(arte.sello) / 100:.0f}",
            "__TXT_COLOR__": NAVY if claro else "#ffffff",
            "__TIT_SOMBRA__": ("none" if claro
                               else "0 2px 18px rgba(0,0,0,.35)"),
            # En chat, comparativa y precio el bloque de abajo es el que manda.
            # El divisor y el nombre del producto solo le roban alto — y en
            # precio ademas chocaban: el bloque del precio arranca en
            # bloque_top% del lienzo y se montaba encima de la bajada.
            "__TEXTO_CLASE__": (
                ("texto centro" if arte.texto_centro else "texto")
                + (" compacto" if (arte.chat or arte.filas or arte.precio) else "")
            ),
            # El pie tapa la parte de abajo, asi que el centro real del hueco
            # libre esta mas arriba que el 50% del lienzo.
            "__TEXTO_Y__": f"{50 - 15 * arte.pie_escala / 2:.1f}",
            # tipografia
            "__TIT__": f"{base * 0.072 * arte.titular_escala:.1f}",
            "__SUB__": f"{base * 0.0335:.1f}",
            "__SELLO_N__": f"{base * 0.036:.1f}",
            # Agrandado 2026-08-04 (0.0135->0.018): la etiqueta salia muy chica
            # frente al icono -- Jose lo marco como "sellos muy pequeños".
            "__SELLO_L__": f"{base * 0.018:.1f}",
            "__CONF_F__": f"{base * 0.0225:.1f}",
            "__CTA_F__": f"{base * 0.026 * arte.pie_escala:.1f}",
            "__NUM_F__": f"{base * 0.038 * arte.pie_escala:.1f}",
            # geometria
            "__TIC__": f"{base * 0.032:.1f}",
            # El pie (logo + CTA de dos filas) mide ~16% del alto. La barra va
            # encima de eso, no sobre eso. `pie_escala` (default 1.0, no
            # cambia nada existente) achica el pie completo a proposito para
            # el carrusel de TikTok -- todo lo que compone el pie escala junto
            # para que logo y CTA sigan compartiendo alto y base.
            "__PIE__": f"{alto * ESCALA * 0.15 * arte.pie_escala:.0f}",
            "__CONF_GAP__": f"{base * 0.018:.0f}",
            "__CONF_P__": f"{base * 0.019:.1f}",
            "__RAD__": f"{base * 0.055 * arte.pie_escala:.1f}",
            "__LOGO_PR__": f"{base * 0.032 * arte.pie_escala:.1f}",
            "__LOGO_H__": f"{base * 0.098 * arte.pie_escala:.1f}",
            "__CTA_B__": f"{base * 0.030:.1f}",
            "__CTA_G__": f"{base * 0.011 * arte.pie_escala:.1f}",
            "__CTA_P__": f"{base * 0.014 * arte.pie_escala:.1f}",
            "__CTA_PX__": f"{base * 0.030 * arte.pie_escala:.1f}",
            "__WA__": f"{base * 0.032 * arte.pie_escala:.1f}",
            "__DO_W__": "48",
            "__SP_TOP__": "27", "__SP_BOT__": "17",
            "__SP_SEP__": f"{base * 0.006:.0f}",
            "__SP_CHIPB__": f"{base * 0.022:.0f}",
            "__SP_CHIPY__": f"{base * 0.010:.0f}",
            "__SP_CHIPX__": f"{base * 0.022:.0f}",
            "__SP_CHIPF__": f"{base * 0.0235:.1f}",
            "__DO_GAP__": f"{base * 0.008:.0f}",
            "__DO_ICOGAP__": f"{base * 0.011:.0f}",
            "__DO_ICO__": f"{base * 0.026:.0f}",
            "__DO_F__": f"{base * 0.0195:.1f}",
            "__FI_W__": "44",
            "__FI_GAP__": f"{base * 0.017:.0f}",
            "__FI_PAD__": f"{base * 0.024:.0f}",
            "__FI_ICOGAP__": f"{base * 0.016:.0f}",
            "__FI_ICO__": f"{base * 0.042:.0f}",
            "__FI_TIT__": f"{base * 0.0215:.1f}",
            "__FI_DES__": f"{base * 0.0165:.1f}",
            "__FI_COLOR__": (TURQUESA if not claro else NAVY),
            "__FI_LINEA__": ("rgba(255,255,255,.20)" if not claro
                             else "rgba(1,26,46,.15)"),
            "__CO_F__": f"{base * 0.0215:.1f}",
            "__CO_RAD__": f"{base * 0.018:.0f}",
            "__CO_PY__": f"{base * 0.016:.0f}",
            "__CO_PX__": f"{base * 0.020:.0f}",
            "__BLUR__": f"{base * 0.006:.0f}",
            "__CO_S__": f"{base * 0.004:.0f}",
            "__CO_S2__": f"{base * 0.010:.0f}",
            "__SOMBRA__": f"{base * 0.012:.0f}",
            "__SOMBRA2__": f"{base * 0.022:.0f}",
        }
        html = plantilla
        for k, v in reemplazos.items():
            html = html.replace(k, v)

        pagina = tmpd / "arte.html"
        pagina.write_text(html, encoding="utf-8")
        crudo = tmpd / "crudo.png"

        subprocess.run(
            [
                str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars",
                "--force-device-scale-factor=1",
                f"--window-size={w},{h}", f"--screenshot={crudo}", _uri(pagina),
            ],
            check=True, capture_output=True,
        )

        salida.parent.mkdir(parents=True, exist_ok=True)
        img = Image.open(crudo).convert("RGB")
        if img.size != (ancho, alto):
            img = img.resize((ancho, alto), Image.LANCZOS)
        # subsampling=0: sin esto el JPEG deshace los bordes del turquesa sobre
        # navy, que es donde mas se nota la compresion en estos artes.
        img.save(salida, quality=95, subsampling=0)

    return salida
