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

FORMATOS = {"cuadrado": (1080, 1080), "vertical": (1080, 1920)}

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

        interior = a5_sellos.html(arte.sello)
        sello_html = f'<div class="sello">{interior}</div>' if interior else ""

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
            "__CONFIANZA__": confianza_html,
            # El sello vive arriba a la derecha; sin este margen el titular se
            # le mete debajo y la ultima palabra queda ilegible.
            "__TXT_MAX__": "74" if arte.sello else "100",
            "__FI_MT__": f"{base * 0.026:.0f}",
            "__SELLO_PX__": f"{base * a5_sellos.ancho(arte.sello) / 100:.0f}",
            "__TXT_COLOR__": NAVY if claro else "#ffffff",
            "__TIT_SOMBRA__": ("none" if claro
                               else "0 2px 18px rgba(0,0,0,.35)"),
            # tipografia
            "__TIT__": f"{base * 0.072:.1f}",
            "__SUB__": f"{base * 0.0335:.1f}",
            "__SELLO_N__": f"{base * 0.034:.1f}",
            "__SELLO_L__": f"{base * 0.0135:.1f}",
            "__CONF_F__": f"{base * 0.0225:.1f}",
            "__CTA_F__": f"{base * 0.026:.1f}",
            "__NUM_F__": f"{base * 0.038:.1f}",
            # geometria
            "__TIC__": f"{base * 0.032:.1f}",
            # El pie (logo + CTA de dos filas) mide ~16% del alto. La barra va
            # encima de eso, no sobre eso.
            "__PIE__": f"{alto * ESCALA * 0.15:.0f}",
            "__CONF_GAP__": f"{base * 0.018:.0f}",
            "__CONF_P__": f"{base * 0.019:.1f}",
            "__RAD__": f"{base * 0.055:.1f}",
            "__LOGO_PR__": f"{base * 0.032:.1f}",
            "__LOGO_H__": f"{base * 0.098:.1f}",
            "__CTA_B__": f"{base * 0.030:.1f}",
            "__CTA_G__": f"{base * 0.011:.1f}",
            "__CTA_P__": f"{base * 0.014:.1f}",
            "__CTA_PX__": f"{base * 0.030:.1f}",
            "__WA__": f"{base * 0.032:.1f}",
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
