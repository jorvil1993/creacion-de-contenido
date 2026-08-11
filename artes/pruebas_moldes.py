"""PROTOTIPOS de los moldes que faltan. NO esta conectado al panel todavia.

Existe para poder VER como quedaria cada molde antes de decidir si se implementa
de verdad (que implica plantilla propia, campos nuevos en `a1_marca.Arte` y su
bloque en el panel). Cada funcion de aca es un arte real renderizado con el mismo
motor de siempre — Chrome headless a 2x y bajado con LANCZOS — asi que lo que se
ve es lo que saldria.

    C:\\ai-video\\venv312\\Scripts\\python.exe artes/pruebas_moldes.py

Los cuatro moldes salen de los formatos estaticos que mas convierten en Meta y
que hoy el panel NO sabe hacer:

  chat        testimonio / conversacion real de WhatsApp (el objetivo de la
              cuenta es MESSAGES: la creatividad que parece un chat convierte)
  precio      oferta apilada — precio + que incluye + reversion de riesgo
  comparativa tabla de filas tablet vs e-reader (la objecion #1 del negocio)
  ciudad      el mismo arte nombrando la ciudad (el mejor CTR historico lo hace)

**Todo el contenido sale de documentos propios, nada inventado:**
`deviceshop/DOCUMENTOS MD DE LA EMPRESA/` -- objeciones-respuestas.md (la
objecion #1 y la #3), analisis-chats-ventas-jun-jul-2026.md (la frase que cierra
en La Paz/Cochabamba y el caso de postventa), precios-y-margenes.md (Bs 2.390,
que es REFERENCIAL: ese doc avisa que los precios cambian seguido).
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from artes.a1_marca import (  # noqa: E402
    CHROME, FORMATOS, FUENTES, LOGO_NAVY, NAVY, TURQUESA, Arte, render,
)

SALIDA = Path(r"C:\ai-video\artes\_pruebas-moldes")
RECORTE = Path(r"C:\ai-video\artes\2026-08-03-test-kindle-paperwhite\recorte.png")
ESCALA = 2
FORMATO = "retrato"          # 4:5, el que Meta prioriza en el feed

# Verde de burbuja saliente de WhatsApp. Se usa el real y no el turquesa de la
# casa a proposito: la gracia del molde es que se lea como una captura de chat
# de verdad. La marca entra por el pie, no por las burbujas.
WA_FONDO, WA_MIA, WA_SUYA = "#ECE5DD", "#D9FDD3", "#FFFFFF"


def _uri(p: Path) -> str:
    return p.resolve().as_uri()


def _pie(base: float, alto: float) -> str:
    """El pie fijo de los 36 artes: logo abajo-izquierda, WhatsApp abajo-derecha."""
    return f"""
  <div class="logo-caja"><img src="__LOGO__" alt="Device Shop BO"></div>
  <div class="cta">
    <div class="fila"><svg viewBox="0 0 24 24" fill="#011A2E"><path d="M12.04 2C6.58 2 2.13 6.45 2.13 11.91c0 1.75.46 3.45 1.32 4.95L2 22l5.25-1.38a9.9 9.9 0 0 0 4.79 1.22h.01c5.46 0 9.91-4.45 9.91-9.91 0-2.65-1.03-5.14-2.9-7.01A9.82 9.82 0 0 0 12.04 2zm0 18.15h-.01a8.2 8.2 0 0 1-4.19-1.15l-.3-.18-3.12.82.83-3.04-.2-.31a8.22 8.22 0 0 1-1.26-4.38c0-4.54 3.7-8.23 8.25-8.23 2.2 0 4.27.86 5.83 2.42a8.18 8.18 0 0 1 2.41 5.82c0 4.54-3.7 8.23-8.24 8.23zm4.52-6.16c-.25-.12-1.47-.72-1.69-.81-.23-.08-.39-.12-.56.13-.16.24-.64.8-.78.97-.14.16-.29.18-.54.06-.25-.12-1.05-.39-1.99-1.23-.74-.66-1.23-1.47-1.38-1.72-.14-.25-.01-.38.11-.5.11-.11.25-.29.37-.43.13-.15.17-.25.25-.41.08-.17.04-.31-.02-.43-.06-.12-.56-1.34-.76-1.84-.2-.48-.4-.42-.56-.43h-.48c-.16 0-.43.06-.65.31-.22.25-.85.83-.85 2.03s.87 2.35.99 2.51c.12.16 1.71 2.61 4.15 3.66.58.25 1.03.4 1.39.51.58.19 1.11.16 1.53.1.47-.07 1.47-.6 1.67-1.18.21-.58.21-1.07.15-1.18-.06-.11-.22-.17-.47-.29z"/></svg>
      <span class="txt">CONTÁCTANOS</span></div>
    <div class="fila oscura"><span class="num">692-14437</span></div>
  </div>"""


def _base_css(w: float, h: float, base: float, pie: float, fondo: str) -> str:
    return f"""
  @font-face {{ font-family:'Poppins'; src:url('{_uri(FUENTES)}/Poppins-ExtraBold.ttf'); font-weight:800; }}
  @font-face {{ font-family:'Poppins'; src:url('{_uri(FUENTES)}/Poppins-Bold.ttf');      font-weight:700; }}
  @font-face {{ font-family:'Poppins'; src:url('{_uri(FUENTES)}/Poppins-Regular.ttf');   font-weight:400; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html,body {{ width:{w}px; height:{h}px; overflow:hidden; }}
  .lienzo {{ position:relative; width:{w}px; height:{h}px; font-family:'Poppins',sans-serif;
             overflow:hidden; background:{fondo}; --pie:{pie}px; }}
  .kicker {{ font-weight:800; font-size:{base*0.026:.1f}px; letter-spacing:.14em;
             text-transform:uppercase; color:{TURQUESA}; }}
  .titular {{ font-weight:800; font-size:{base*0.066:.1f}px; line-height:.99;
              letter-spacing:-.015em; text-transform:uppercase; color:#fff; }}
  .titular .acento {{ color:{TURQUESA}; }}
  .logo-caja {{ position:absolute; left:0; bottom:0; height:var(--pie); background:{TURQUESA};
                border-top-right-radius:{base*0.055:.0f}px; padding:0 {base*0.032:.0f}px 0 3%;
                display:flex; align-items:center; }}
  .logo-caja img {{ height:{base*0.098:.0f}px; display:block; }}
  .cta {{ position:absolute; right:4.2%; bottom:0; height:var(--pie); display:flex;
          flex-direction:column; justify-content:center; gap:{base*0.011:.0f}px; }}
  .cta .fila {{ background:{TURQUESA}; border-radius:999px; padding:{base*0.014:.0f}px {base*0.030:.0f}px;
                display:flex; align-items:center; justify-content:center; gap:.5em; }}
  .cta .fila.oscura {{ background:{NAVY}; }}
  .cta .fila svg {{ width:{base*0.032:.0f}px; height:{base*0.032:.0f}px; flex:none; }}
  .cta .txt {{ font-weight:700; font-size:{base*0.026:.1f}px; color:{NAVY}; letter-spacing:.02em; }}
  .cta .num {{ font-weight:800; font-size:{base*0.038:.1f}px; color:#fff; }}
"""


def _render_html(cuerpo_css: str, cuerpo_html: str, destino: Path) -> Path:
    """Rinde a 2x y baja con LANCZOS, igual que a1_marca.render()."""
    ancho, alto = FORMATOS[FORMATO]
    w, h = ancho * ESCALA, alto * ESCALA
    base, pie = w, h * 0.15
    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        logo = tmpd / "logo.png"
        Image.open(LOGO_NAVY).save(logo)
        html = (f"<!doctype html><meta charset='utf-8'><style>"
                f"{cuerpo_css}</style><div class='lienzo'>{cuerpo_html}"
                f"{_pie(base, h)}</div>").replace("__LOGO__", _uri(logo))
        pagina = tmpd / "arte.html"
        pagina.write_text(html, encoding="utf-8")
        crudo = tmpd / "crudo.png"
        subprocess.run(
            [str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars",
             f"--window-size={w},{h}", f"--screenshot={crudo}",
             "--default-background-color=00000000", _uri(pagina)],
            check=True, capture_output=True,
        )
        destino.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(crudo) as im:
            im.convert("RGB").resize((ancho, alto), Image.LANCZOS).save(
                destino, quality=94)
    return destino


# --------------------------------------------------------------------------
# Molde 1 — chat / testimonio
# --------------------------------------------------------------------------
# La objecion #1 REAL de junio-julio fue "¿tienen tienda fisica?" (7 veces) y la
# respuesta que cierra esta textual en analisis-chats-ventas: "Hacemos entregas a
# domicilio sin costo adicional y paga cuando le entregan".
CHAT = [
    ("suya", "Hola, buenas tardes 🙌 ¿tienen tienda física?"),
    ("mia",  "Hola! Somos 100% a domicilio. Hacemos entregas sin costo "
             "adicional y <b>paga cuando le entregan</b> 🛵"),
    ("suya", "Ah perfecto. ¿Y si lo quiero hoy?"),
    ("mia",  "En Santa Cruz se lo entregamos <b>hoy mismo</b>. Nuevo, en caja "
             "sellada y con garantía de 1 mes ✅"),
]


def molde_chat() -> Path:
    ancho, alto = FORMATOS[FORMATO]
    w, h = ancho * ESCALA, alto * ESCALA
    base, pie = w, h * 0.15
    css = _base_css(w, h, base, pie, f"linear-gradient(160deg,#03243c,#01466b 60%,#016b7d)") + f"""
  .cab {{ position:absolute; left:5.5%; right:5.5%; top:5%; }}
  .cab .titular {{ margin-top:{base*0.012:.0f}px; }}
  .chat {{ position:absolute; left:5.5%; right:5.5%; top:23%;
           bottom:calc(var(--pie) + {base*0.035:.0f}px);
           background:{WA_FONDO}; border-radius:{base*0.028:.0f}px;
           padding:{base*0.030:.0f}px; display:flex; flex-direction:column;
           justify-content:center; gap:{base*0.020:.0f}px;
           box-shadow:0 {base*0.012:.0f}px {base*0.040:.0f}px rgba(0,0,0,.35); }}
  .b {{ max-width:80%; padding:{base*0.019:.0f}px {base*0.024:.0f}px;
        border-radius:{base*0.020:.0f}px; font-size:{base*0.0285:.1f}px;
        line-height:1.32; color:#111b21; font-weight:400;
        box-shadow:0 1px 2px rgba(0,0,0,.16); position:relative; }}
  .b b {{ font-weight:700; }}
  .b.suya {{ background:{WA_SUYA}; align-self:flex-start; border-top-left-radius:{base*0.006:.0f}px; }}
  .b.mia  {{ background:{WA_MIA};  align-self:flex-end;   border-top-right-radius:{base*0.006:.0f}px; }}
  .b .hora {{ display:block; text-align:right; font-size:{base*0.017:.1f}px;
              color:#667781; margin-top:{base*0.004:.0f}px; }}
"""
    burbujas = "".join(
        f'<div class="b {q}">{t}<span class="hora">'
        f'{"14:0" + str(i * 2) if i < 5 else "14:1"}</span></div>'
        for i, (q, t) in enumerate(CHAT)
    )
    cuerpo = f"""
  <div class="cab">
    <div class="kicker">Conversación real · Santa Cruz</div>
    <div class="titular">«¿TIENEN<br>TIENDA <span class="acento">FÍSICA</span>?»</div>
  </div>
  <div class="chat">{burbujas}</div>"""
    return _render_html(css, cuerpo, SALIDA / "1-chat.jpg")


# --------------------------------------------------------------------------
# Molde 2 — oferta con precio
# --------------------------------------------------------------------------
# Bs 2.390 es el precio REFERENCIAL de precios-y-margenes.md, que avisa que los
# precios cambian seguido. Si esto se implementa, el precio tiene que venir de un
# campo del panel que Jose escribe cada vez, nunca de una constante en el codigo.
INCLUYE = [
    "Nuevo y en caja sellada",
    "Garantía de 1 mes",
    "Entrega inmediata — stock propio",
    "Envíos a todo el país · QR contra entrega",
]


def molde_precio() -> Path:
    ancho, alto = FORMATOS[FORMATO]
    w, h = ancho * ESCALA, alto * ESCALA
    base, pie = w, h * 0.15
    tic = ('<svg viewBox="0 0 24 24" fill="none" stroke="#011A2E" stroke-width="3.4" '
           'stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>')
    css = _base_css(w, h, base, pie, "linear-gradient(160deg,#03243c,#01466b 60%,#016b7d)") + f"""
  .cab {{ position:absolute; left:5.5%; top:5%; max-width:62%; }}
  .cab .titular {{ margin-top:{base*0.010:.0f}px; font-size:{base*0.058:.1f}px; }}
  .prod-img {{ position:absolute; right:-6%; top:30%; height:44%; }}
  .prod-img img {{ height:100%; width:auto; display:block;
                   filter:drop-shadow(0 {base*0.014:.0f}px {base*0.030:.0f}px rgba(0,0,0,.45)); }}
  .precio {{ position:absolute; left:5.5%; top:26%; }}
  .precio .desde {{ font-weight:700; font-size:{base*0.024:.1f}px; color:#fff; opacity:.8;
                    letter-spacing:.06em; text-transform:uppercase; }}
  .precio .num {{ font-weight:800; font-size:{base*0.115:.1f}px; color:{TURQUESA};
                  line-height:.92; letter-spacing:-.02em; }}
  .precio .num small {{ font-size:{base*0.045:.1f}px; }}
  .incluye {{ position:absolute; left:5.5%; right:5.5%;
              bottom:calc(var(--pie) + {base*0.030:.0f}px);
              background:rgba(1,26,46,.72); border:1px solid rgba(255,255,255,.16);
              border-radius:{base*0.024:.0f}px; padding:{base*0.026:.0f}px {base*0.028:.0f}px;
              display:flex; flex-direction:column; gap:{base*0.016:.0f}px; }}
  .incluye .it {{ display:flex; align-items:center; gap:{base*0.014:.0f}px;
                  color:#fff; font-weight:700; font-size:{base*0.026:.1f}px; }}
  .incluye .tic {{ width:{base*0.030:.0f}px; height:{base*0.030:.0f}px; flex:none;
                   border-radius:50%; background:{TURQUESA}; display:flex;
                   align-items:center; justify-content:center; }}
  .incluye .tic svg {{ width:62%; height:62%; }}
"""
    items = "".join(
        f'<div class="it"><span class="tic">{tic}</span>{t}</div>' for t in INCLUYE)
    cuerpo = f"""
  <div class="cab">
    <div class="kicker">Entrega inmediata</div>
    <div class="titular">KINDLE<br>PAPERWHITE <span class="acento">16GB</span></div>
  </div>
  <div class="precio">
    <div class="desde">Precio</div>
    <div class="num"><small>Bs</small> 2.390</div>
  </div>
  <div class="prod-img"><img src="{_uri(RECORTE)}" alt=""></div>
  <div class="incluye">{items}</div>"""
    return _render_html(css, cuerpo, SALIDA / "2-precio.jpg")


# --------------------------------------------------------------------------
# Molde 3 — comparativa en filas
# --------------------------------------------------------------------------
# Las cuatro filas son las "ideas fuerza" textuales de la OBJECION #1 en
# objeciones-respuestas.md. No hay ninguna afirmacion nueva.
FILAS = [
    ("A pleno sol",     "Brilla, se vuelve espejo", "Se lee como papel"),
    ("Notificaciones",  "WhatsApp, redes, todo",    "Solo para leer"),
    ("Batería",         "Horas",                    "Semanas"),
    ("Para tus ojos",   "Te tira luz a la cara",    "Refleja la luz del ambiente"),
]


def molde_comparativa() -> Path:
    ancho, alto = FORMATOS[FORMATO]
    w, h = ancho * ESCALA, alto * ESCALA
    base, pie = w, h * 0.15
    css = _base_css(w, h, base, pie, "linear-gradient(160deg,#03243c,#01466b 60%,#016b7d)") + f"""
  .cab {{ position:absolute; left:5.5%; right:5.5%; top:4.5%; }}
  .cab .titular {{ margin-top:{base*0.010:.0f}px; font-size:{base*0.062:.1f}px; }}
  .tabla {{ position:absolute; left:5.5%; right:5.5%; top:22%;
            bottom:calc(var(--pie) + {base*0.030:.0f}px);
            display:flex; flex-direction:column; justify-content:space-between; }}
  .fila {{ display:grid; grid-template-columns:1fr 1fr; gap:{base*0.014:.0f}px;
           align-items:stretch; }}
  .et {{ grid-column:1 / -1; font-weight:800; font-size:{base*0.023:.1f}px;
         color:#fff; opacity:.62; letter-spacing:.10em; text-transform:uppercase;
         margin-bottom:{base*0.008:.0f}px; }}
  .cel {{ border-radius:{base*0.020:.0f}px; padding:{base*0.020:.0f}px {base*0.022:.0f}px;
          font-weight:700; font-size:{base*0.026:.1f}px; line-height:1.24;
          display:flex; align-items:center; }}
  .cel.mal  {{ background:rgba(213,43,30,.16); border:1px solid rgba(255,120,110,.42); color:#ffd9d5; }}
  .cel.bien {{ background:rgba(0,199,202,.16); border:1px solid rgba(0,199,202,.55); color:#eafcfd; }}
  .cabeza {{ display:grid; grid-template-columns:1fr 1fr; gap:{base*0.014:.0f}px; }}
  .chip {{ border-radius:999px; text-align:center; font-weight:800;
           font-size:{base*0.030:.1f}px; padding:{base*0.014:.0f}px 0; letter-spacing:.04em; }}
  .chip.t {{ background:#D52B1E; color:#fff; }}
  .chip.k {{ background:{TURQUESA}; color:{NAVY}; }}
"""
    filas = "".join(
        f'<div class="fila"><div class="et">{et}</div>'
        f'<div class="cel mal">{mal}</div><div class="cel bien">{bien}</div></div>'
        for et, mal, bien in FILAS
    )
    cuerpo = f"""
  <div class="cab">
    <div class="kicker">La pregunta que más nos hacen</div>
    <div class="titular">«CON MI TABLET<br>LEO <span class="acento">IGUAL</span>»</div>
  </div>
  <div class="tabla">
    <div class="cabeza"><div class="chip t">TABLET</div><div class="chip k">E-READER</div></div>
    {filas}
  </div>"""
    return _render_html(css, cuerpo, SALIDA / "3-comparativa.jpg")


# --------------------------------------------------------------------------
# Molde 4 — el mismo arte, con la ciudad en el titular
# --------------------------------------------------------------------------
# No necesita plantilla nueva: es el motor de siempre con otro titular. Se rinde
# para poder VER que el titular de dos lineas aguanta el nombre de la ciudad.
CIUDADES = ["SANTA CRUZ", "COCHABAMBA", "LA PAZ"]


def molde_ciudad() -> list[Path]:
    salidas = []
    for ciudad in CIUDADES:
        arte = Arte(
            titular=f'{ciudad}:<br>TU PRÓXIMO LIBRO<br>LLEGA <span class="acento">HOY</span>',
            producto="Kindle Paperwhite 16GB",
            escena="navy",
            recorte=RECORTE,
            recorte_alto=44, recorte_y=59, recorte_x=50,
            formato=FORMATO,
            sello="moto",
        )
        slug = ciudad.lower().replace(" ", "-")
        salidas.append(render(arte, SALIDA / f"4-ciudad-{slug}.jpg"))
    return salidas


def main() -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    if not RECORTE.exists():
        print(f"falta el recorte de prueba: {RECORTE}")
        return
    for f in (molde_chat, molde_precio, molde_comparativa):
        print("ok", f().name)
    for p in molde_ciudad():
        print("ok", p.name)
    print(f"\ntodo en {SALIDA}")


if __name__ == "__main__":
    main()
