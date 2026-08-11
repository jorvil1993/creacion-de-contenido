"""Carrusel EDITORIAL — el segundo sistema visual de los artes.

Por que existe (2026-08-05): Jose armo un carrusel con Claude en la web y le
rindio mas que los suyos con fotos. Ese carrusel no era "IA generando fotos":
era diseño — fondo claro de papel, tipografia enorme, un acento de color, una
idea por slide, y la foto real apareciendo UNA sola vez como prueba. Esto
reproduce ese sistema con los tokens de DeviceShop.

Es PARALELO a a1_marca.py, no lo reemplaza:

  a1_marca.py         navy, foto de fondo a sangre, pie con logo + WhatsApp
  a13_editorial.py    papel claro, tipografia grande, numeracion, hairlines

La gracia de tener los dos es poder alternar: si Jose publica uno por dia, un
dia sale en un sistema y al otro dia en el otro, y el feed no se ve monotono
aunque hable del mismo producto.

Cuesta CERO cuota de IA: el contenido lo escribe Claude Code y esto solo lo
maqueta. Son ~1.3s por slide (Chrome headless a 2x, igual que a1_marca).

    from artes import a13_editorial as ed
    ed.render_carrusel([...], Path(r"C:\\ai-video\\artes\\mi-sesion"))
"""
from __future__ import annotations

import html as _html
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
PLANTILLA = RAIZ / "artes" / "plantillas" / "carrusel-editorial.html"
FUENTES = RAIZ / "assets" / "fuentes"
LOGO = (
    RAIZ / "contexto" / "LOGOS IVAN" / "drive-download-20260702T141516Z-3-001"
    / "deviceshop color.png"
)
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

FORMATOS = {
    "cuadrado": (1080, 1080),
    "retrato": (1080, 1350),   # 4:5, el que prioriza el feed de Meta (ver a1_marca)
    "vertical": (1080, 1920),
}
ESCALA = 2

# Paleta del sistema. El acento NO es el turquesa de marca tal cual (#00C7CA):
# sobre papel claro ese tono no tiene contraste suficiente para texto chico
# (el kicker y los numeros se lavan). Se usa el mismo tono bajado en luz, que
# sigue leyendose como el turquesa de la casa. El fondo de la slide de cierre
# si va en el turquesa pleno, porque ahi el texto encima es navy.
FONDO = "#F2F1EE"
TINTA = "#101C26"
GRIS = "#5B6770"
ACENTO = "#00898C"
TURQUESA = "#00C7CA"
LINEA = "rgba(16,28,38,.22)"


def preparar_foto(origen: Path, destino: Path, formato: str = "cuadrado",
                  recorte_top: float = 0.0, encuadre_y: float = 0.42) -> Path:
    """Deja una foto lista para el molde 'foto': corta la franja de arriba y
    encuadra al lienzo sin deformar.

    `encuadre_y` es que parte del sobrante vertical se descarta por arriba: 0
    deja el borde superior, 1 el inferior. Sube a ~.75 cuando el producto cae
    en el tercio bajo de la foto, porque ahi es donde el molde 'foto' pone el
    titular blanco y el texto termina encima de una pantalla clara. Subir el
    encuadre corre el aparato al centro y le deja al texto una zona oscura.

    `recorte_top` es la fraccion del alto que se corta desde arriba, y va A
    MANO. Existe `a2_recorte.preparar_fondo()`, que intenta detectar sola la
    franja de texto en ingles que Amazon quema arriba, pero su heuristica pide
    una banda clara y uniforme: en las fotos del Scribe el texto esta sobre
    beige y madera, no la detecta y la deja pasar (probado el 2026-08-05, en la
    primera slide salio "Just 5.4mm and 400g with 11 glare-free display" a toda
    pantalla). Mejor pedir el numero explicito que confiar en que la detecte.
    """
    ancho_obj, alto_obj = FORMATOS[formato]
    with Image.open(origen) as im:
        im = im.convert("RGB")
        if recorte_top > 0:
            im = im.crop((0, int(im.height * recorte_top), im.width, im.height))
        escala = max(ancho_obj / im.width, alto_obj / im.height)
        im = im.resize((max(1, round(im.width * escala)),
                        max(1, round(im.height * escala))), Image.LANCZOS)
        x = (im.width - ancho_obj) // 2
        y = int((im.height - alto_obj) * encuadre_y)
        destino.parent.mkdir(parents=True, exist_ok=True)
        im.crop((x, y, x + ancho_obj, y + alto_obj)).save(
            destino, quality=95, subsampling=0)
    return destino


@dataclass
class Slide:
    """Una slide del carrusel editorial.

    `tipo` elige el molde y define que campos se usan:

      portada   titular + bajada + "Desliza"
      texto     titular + bajada (la version sobria de portada, para el medio)
      golpe     SOLO titular, al doble de cuerpo. Sin regla y sin nada mas.
      lista     titular + items: list[str]  -> filas 01 / 02 / 03
      grilla    titular + items: list[tuple[dato, descripcion]] -> 2x2
      antes     titular + items: [(antes, ahora)]  -> dos columnas
      foto      foto + titular + bajada, texto blanco sobre la imagen a sangre
      cierre    titular + bajada + contacto, sobre turquesa pleno

    `invertida` da vuelta la slide (turquesa pleno con tinta navy, igual que el
    cierre). Sirve para marcar UNA slide del medio -- la del giro -- y que el
    carrusel no sea seis veces el mismo papel claro.
    """

    tipo: str
    kicker: str = ""
    titular: str = ""
    bajada: str = ""
    items: list = field(default_factory=list)
    foto: Path | None = None
    contacto: list[tuple[str, str]] = field(default_factory=list)
    invertida: bool = False


def _uri(p: Path) -> str:
    return p.resolve().as_uri()


def _dado_vuelta(slide: Slide) -> bool:
    """Turquesa pleno con tinta navy: siempre el cierre, y cualquier slide que
    lo pida a mano con invertida=True."""
    return slide.tipo == "cierre" or slide.invertida


def _esc(t: str) -> str:
    """Escapa el texto pero deja pasar <span class='acento'>, que es la unica
    marca que se usa a mano en los titulares (misma convencion que el resto
    del panel)."""
    marcador_a, marcador_b = "\x00A\x00", "\x00B\x00"
    t = t.replace("<span class='acento'>", marcador_a).replace(
        '<span class="acento">', marcador_a).replace("</span>", marcador_b)
    t = _html.escape(t)
    return t.replace(marcador_a, "<span class='acento'>").replace(marcador_b, "</span>")


def _barra(slide: Slide, i: int, n: int) -> str:
    kicker = _esc(slide.kicker) if slide.kicker else "&nbsp;"
    return (f'<div class="barra"><span class="kicker">{kicker}</span>'
            f'<span class="pag">{i:02d} / {n:02d}</span></div>')


def _titulo(slide: Slide) -> str:
    return f"<h1>{_esc(slide.titular)}</h1>" if slide.titular else ""


def _bajada(slide: Slide) -> str:
    return f'<div class="bajada">{_esc(slide.bajada)}</div>' if slide.bajada else ""


def _cuerpo(slide: Slide, i: int, n: int) -> str:
    """Arma el HTML del centro segun el tipo. Cada rama es un molde."""
    if slide.tipo == "foto":
        if not slide.foto or not slide.foto.exists():
            raise RuntimeError(f"slide {i}: el molde 'foto' necesita una imagen que exista")
        return (
            f'<div class="foto"><img src="{_uri(slide.foto)}" alt=""></div>'
            '<div class="foto-velo"></div>'
            f'<div class="lienzo sobre-foto">{_barra(slide, i, n)}'
            '<div class="centro" style="justify-content:flex-end">'
            f'{_titulo(slide)}<div class="regla"></div>{_bajada(slide)}'
            '</div></div>'
        )

    if slide.tipo == "lista":
        filas = "".join(
            f'<div class="item"><span class="n">{k:02d}</span>'
            f'<span class="t">{_esc(str(t))}</span></div>'
            for k, t in enumerate(slide.items, 1)
        )
        centro = (f'{_titulo(slide)}<div class="regla"></div>'
                  f'<div class="lista">{filas}</div>')

    elif slide.tipo == "grilla":
        celdas = "".join(
            f'<div class="celda"><span class="dato">{_esc(str(d))}</span>'
            f'<span class="des">{_esc(str(t))}</span></div>'
            for d, t in slide.items
        )
        centro = f'{_titulo(slide)}<div class="grilla">{celdas}</div>'

    elif slide.tipo == "antes":
        antes, ahora = slide.items[0]
        centro = (
            f'{_titulo(slide)}<div class="regla"></div>'
            '<div class="dos">'
            f'<div class="col"><span class="rot">Antes</span>'
            f'<span class="t">{_esc(antes)}</span></div>'
            f'<div class="col ahora"><span class="rot">Ahora</span>'
            f'<span class="t">{_esc(ahora)}</span></div>'
            '</div>'
        )

    elif slide.tipo == "golpe":
        # Sin regla y sin nada debajo: la slide es la frase. Si lleva bajada es
        # de una linea, para rematar.
        centro = f'{_titulo(slide)}{_bajada(slide)}'

    elif slide.tipo == "cierre":
        filas = "".join(
            f'<div class="fila"><span class="rot">{_esc(r)}</span>'
            f'<span class="val">{_esc(v)}</span></div>'
            for r, v in slide.contacto
        )
        centro = (f'{_titulo(slide)}<div class="regla"></div>{_bajada(slide)}'
                  f'<div class="contacto">{filas}</div>')

    else:  # portada | texto
        centro = f'{_titulo(slide)}<div class="regla"></div>{_bajada(slide)}'

    # La portada abre con la marca; el cierre la lleva arriba sobre el acento;
    # las del medio la llevan chica al pie, presente sin gritar.
    if slide.tipo == "cierre":
        encabezado = (f'<img class="logo-top" src="{_uri(LOGO)}" alt="DeviceShop">'
                      f'<span class="pag">{i:02d} / {n:02d}</span>')
        arriba = f'<div class="barra">{encabezado}</div>'
        pie = ""
    else:
        arriba = _barra(slide, i, n)
        pie = ('<div class="marca-pie">'
               + ('<span class="desliza">Desliza &rarr;</span>' if slide.tipo == "portada"
                  else "<span></span>")
               + f'<img src="{_uri(LOGO)}" alt="DeviceShop"></div>')

    return f'<div class="lienzo">{arriba}<div class="centro">{centro}</div>{pie}</div>'


def _medidas(ancho: int, alto: int, slide: Slide) -> dict:
    """Todo se deriva del ancho, como en a1_marca: un solo numero manda y el
    sistema se reacomoda solo al pasar de cuadrado a vertical.

    Los cuerpos subieron ~30% el 2026-08-06. El primer carrusel (Scribe) tenia
    el titular perfecto y todo lo demas ilegible: en el feed una slide cuadrada
    se ve a ~390px de ancho, o sea a poco mas de un TERCIO del tamaño en que uno
    la revisa en la PC. Un cuerpo de 0.0265 del ancho son 28px sobre 1080, que
    en el feed quedan en 10px reales: nadie lee eso sin abrir la imagen, y el
    que no abre no lee la lista ni la grilla, que es donde esta el argumento.
    Referencia para no volver atras: el cuerpo NO debe bajar de 0.033 del ancho
    (~36px sobre 1080, ~13px en el feed). El aire para pagarlo salio del vacio
    inferior, que sobraba en las seis slides.
    """
    b = ancho
    # La portada y el cierre van con el titular mas grande: son las dos que
    # tienen que frenar el dedo y cerrar. Las del medio comparten cuadro con
    # una lista o una grilla y necesitan menos cuerpo.
    tit = 0.083 if slide.tipo in ("portada", "cierre") else 0.058
    if slide.tipo == "foto":
        tit = 0.062
    # El 'golpe' va casi al doble que una slide normal: es la unica cosa en el
    # cuadro, tiene que leerse entera de un vistazo en el feed sin abrir nada.
    if slide.tipo == "golpe":
        tit = 0.112
    return {
        "__W__": str(ancho), "__H__": str(alto),
        "__F__": _uri(FUENTES),
        "__FONDO__": FONDO, "__TINTA__": TINTA, "__GRIS__": GRIS,
        "__ACENTO__": TURQUESA if _dado_vuelta(slide) else ACENTO,
        "__LINEA__": LINEA,
        "__MARGEN__": f"{b * 0.068:.0f}",
        "__KICKER__": f"{b * 0.0225:.1f}",
        "__TIT__": f"{b * tit:.1f}",
        "__BAJADA__": f"{b * 0.0355:.1f}",
        "__AIRE__": f"{b * 0.06:.0f}",
        "__REGLA_MT__": f"{b * 0.038:.0f}",
        "__REGLA_MB__": f"{b * 0.034:.0f}",
        "__LISTA_MT__": f"{b * 0.030:.0f}",
        "__ITEM_GAP__": f"{b * 0.030:.0f}",
        "__ITEM_PY__": f"{b * 0.025:.0f}",
        "__ITEM_N__": f"{b * 0.030:.1f}",
        "__ITEM_NW__": f"{b * 0.052:.0f}",
        "__ITEM_F__": f"{b * 0.0345:.1f}",
        "__CELDA_P__": f"{b * 0.030:.0f}",
        "__CELDA_H__": f"{b * 0.190:.0f}",
        "__CELDA_GAP__": f"{b * 0.014:.0f}",
        "__CELDA_F__": f"{b * 0.0295:.1f}",
        # El dato de la grilla NO sube con el resto: a 0.056 un dato de dos
        # palabras ("Lapiz incluido") parte en dos renglones y descuadra la fila
        # contra la celda de al lado. Ya se leia bien -- el problema de tamaño
        # estaba en la descripcion gris de abajo, no aca.
        "__DATO__": f"{b * 0.052:.1f}",
        "__COL_MB__": f"{b * 0.018:.0f}",
        "__CONTACTO__": f"{b * 0.044:.1f}",
        "__CONTACTO_W__": f"{b * 0.175:.0f}",
        "__LOGO_H__": f"{b * 0.052:.0f}",
        "__LOGO_PIE__": f"{b * 0.034:.0f}",
        "__CLASE_BODY__": " ".join(
            (["golpe"] if slide.tipo == "golpe" else [])
            + (["cierre"] if _dado_vuelta(slide) else [])
        ),
    }


def render_slide(slide: Slide, salida: Path, i: int = 1, n: int = 1,
                 formato: str = "cuadrado") -> Path:
    ancho, alto = FORMATOS[formato]
    w, h = ancho * ESCALA, alto * ESCALA

    reemplazos = _medidas(w, h, slide)
    reemplazos["__CUERPO__"] = _cuerpo(slide, i, n)

    pagina_html = PLANTILLA.read_text(encoding="utf-8")
    for k, v in reemplazos.items():
        pagina_html = pagina_html.replace(k, v)

    with tempfile.TemporaryDirectory() as tmp:
        pagina = Path(tmp) / "slide.html"
        pagina.write_text(pagina_html, encoding="utf-8")
        crudo = Path(tmp) / "crudo.png"
        subprocess.run(
            [str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars",
             "--force-device-scale-factor=1",
             f"--window-size={w},{h}", f"--screenshot={crudo}", _uri(pagina)],
            check=True, capture_output=True,
        )
        salida.parent.mkdir(parents=True, exist_ok=True)
        # Se rinde al doble y se baja con LANCZOS: mismo motivo que a1_marca --
        # a 1:1 el antialiasing del texto es pobre.
        with Image.open(crudo) as im:
            im.convert("RGB").resize((ancho, alto), Image.LANCZOS).save(
                salida, quality=95, subsampling=0)
    return salida


def render_carrusel(slides: list[Slide], carpeta: Path, prefijo: str = "slide",
                    formato: str = "cuadrado") -> list[Path]:
    n = len(slides)
    return [render_slide(s, carpeta / f"{prefijo}-{i}.jpg", i, n, formato)
            for i, s in enumerate(slides, 1)]
