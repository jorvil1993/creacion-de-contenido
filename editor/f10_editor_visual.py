"""
Editor visual — sonidos y posiciones de los insertos, en una línea de tiempo.

José pidió (MEJORAS-PENDIENTES punto 8) poder colocar los efectos de sonido por
timestamp en una interfaz visual en vez de en una hoja de markdown, y además
poder mover a mano los PiP cuando el encuadre lo pida.

La mitad del contrato ya existía: `f5_audio.py --hoja-sonido` genera los datos y
`--sfx-manual` acepta el JSON de vuelta. Este módulo produce la interfaz que
falta, y agrega el mismo mecanismo para las posiciones
(`f6_overlays.py --posiciones-manual`).

Genera **un solo archivo HTML autocontenido**: los MP3 de los efectos y los
fotogramas del video van embebidos en base64, porque un artifact no puede
cargar archivos externos. Se abre con doble clic, no necesita servidor.

Uso:
    python f10_editor_visual.py "C:\\ai-video\\salida\\<nombre>"
    python f10_editor_visual.py "C:\\ai-video\\salida\\<nombre>" --salida editor.html
"""
import argparse
import base64
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

import config


def _b64(ruta: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(ruta.read_bytes()).decode("ascii")


def _duracion(ruta: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(ruta)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def _resolucion(ruta: Path) -> tuple[int, int]:
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height",
                        "-of", "csv=s=x:p=0", str(ruta)],
                       capture_output=True, text=True, check=True)
    w, h = r.stdout.strip().split("x")
    return int(w), int(h)


def muestras_encuadre(dir_trabajo: Path, duracion: float) -> list:
    """Un [t, cx, cy, zoom] por frame, con la MISMA función que usa el render
    real (f4_retencion.encuadre_en_t) — el preview del editor no aproxima el
    encuadre, lo replica exacto (sección 1.5 del plan v2)."""
    plan = json.loads((dir_trabajo / "03_retencion.plan.json").read_text(encoding="utf-8"))
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import f4_retencion as f4

    track_rostro = plan["track_rostro"]
    planos = plan["planos"]
    picos = plan["picos_energia"]
    tiempos_track = np.array([p["t"] for p in track_rostro]) if track_rostro else np.array([0.0])
    cx_track = np.array([p["cx"] for p in track_rostro]) if track_rostro else np.array([0.5])
    cy_track = np.array([p["cy"] for p in track_rostro]) if track_rostro else np.array([0.4])

    hacer_loop = config.LOOP_ACTIVO and duracion > config.LOOP_DURACION_S * 3
    t_loop = cx_ini = cy_ini = zoom_ini = None
    if hacer_loop:
        cx_ini, cy_ini, zoom_ini = f4.encuadre_en_t(0.0, tiempos_track, cx_track, cy_track, planos, picos)
        t_loop = duracion - config.LOOP_DURACION_S

    fps = config.FPS
    n = int(duracion * fps) + 2
    muestras = []
    for idx in range(n):
        t = idx / fps
        cx, cy, zoom = f4.encuadre_en_t(t, tiempos_track, cx_track, cy_track, planos, picos,
                                         hacer_loop, t_loop, cx_ini, cy_ini, zoom_ini)
        muestras.append([round(t, 3), round(cx, 4), round(cy, 4), round(zoom, 4)])
    return muestras


def _miniatura(video: Path, t: float, ancho: int = 270) -> str | None:
    """Fotograma del video en el segundo t, como JPEG embebible.

    Sin esto habría que colocar los insertos a ciegas: con el frame real de
    fondo se ve exactamente qué se está tapando.
    """
    with tempfile.TemporaryDirectory() as tmp:
        salida = Path(tmp) / "f.jpg"
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t:.3f}",
                            "-i", str(video), "-frames:v", "1",
                            "-vf", f"scale={ancho}:-1", "-q:v", "6", str(salida)],
                           capture_output=True)
        if r.returncode != 0 or not salida.exists():
            return None
        return _b64(salida, "image/jpeg")


def generar_proxy(video: Path, dir_trabajo: Path) -> Path:
    """Copia liviana (540x960, faststart) de `video` para que arrastrar la
    línea de tiempo del editor sea instantáneo — `02_cortado.mp4` pesa 75 MB.
    El render final SIEMPRE usa el original; esto es solo para scrubbing en
    el navegador (sección 3 del plan v2)."""
    dir_proxy = dir_trabajo / "_editor"
    dir_proxy.mkdir(parents=True, exist_ok=True)
    proxy = dir_proxy / "proxy.mp4"
    if proxy.exists() and proxy.stat().st_mtime >= video.stat().st_mtime:
        return proxy
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-i", str(video),
        "-vf", f"scale={config.ANCHO // 2}:{config.ALTO // 2}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart", str(proxy),
    ], check=True, capture_output=True)
    return proxy


def miniatura_catalogo(asset: dict, dir_cache: Path | None = None, ancho: int = 200) -> Path | None:
    """Miniatura cacheada de un asset del catálogo (grid de PiP, Fase 2).
    Nunca sirve el original al navegador: hay fotos de 4000x3000. Se
    invalida por mtime del archivo original, no por conteo ni por tiempo."""
    dir_cache = dir_cache or (config.DIR_EDITOR_CACHE / "thumbs")
    dir_cache.mkdir(parents=True, exist_ok=True)
    nombre = asset["id"].replace("\\", "__").replace("/", "__") + ".jpg"
    destino = dir_cache / nombre
    origen = config.RAIZ_PROYECTO / asset["ruta"]
    if not origen.exists():
        return None
    if destino.exists() and destino.stat().st_mtime >= origen.stat().st_mtime:
        return destino

    if asset["medio"] == "video":
        r = subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-ss", "0.5", "-i", str(origen),
            "-frames:v", "1", "-vf", f"scale={ancho}:-1", "-q:v", "6", str(destino),
        ], capture_output=True)
        if r.returncode != 0 or not destino.exists():
            return None
    else:
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None  # fotos propias de 4000x3000+, no hay riesgo que mitigar
        with Image.open(origen) as im:
            im = im.convert("RGB")
            im.thumbnail((ancho, ancho * 2))
            im.save(destino, "JPEG", quality=85)
    return destino


def recolectar(dir_trabajo: Path) -> dict:
    """Junta todo lo que el editor necesita desde la carpeta de trabajo."""
    dir_trabajo = Path(dir_trabajo)
    transcripcion = json.loads((dir_trabajo / "02_cortado.json").read_text(encoding="utf-8"))
    eventos = json.loads((dir_trabajo / "05_overlays.eventos.json").read_text(encoding="utf-8"))
    plan = json.loads((dir_trabajo / "03_retencion.plan.json").read_text(encoding="utf-8"))

    video = dir_trabajo / "06_video.mp4"
    if not video.exists():
        video = dir_trabajo / "02_cortado.mp4"
    duracion = _duracion(video)

    # SFX: se reconstruyen igual que en la corrida real, para que el editor
    # arranque exactamente con lo que suena hoy.
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import f5_audio
    sfx = f5_audio.construir_eventos_sfx(plan, eventos)

    # Vocabulario completo de sonidos, embebido para poder escucharlos
    dir_sfx = config.DIR_ASSETS / "sfx"
    sonidos = {}
    for p in sorted(dir_sfx.glob("*.mp3")):
        sonidos[p.name] = _b64(p, "audio/mpeg")

    # Solo se pueden mover los overlays que tienen posición propia; las
    # composiciones de Hyperframes ocupan el lienzo entero y se posicionan
    # dentro de su HTML, así que moverlas desde aquí no tendría efecto.
    movibles = []
    for i, ev in enumerate(eventos):
        if ev.get("medio") == "video":
            continue
        movibles.append({
            "idx": i,
            "tipo": ev["tipo"],
            "ini": ev["ini"], "fin": ev["fin"],
            "x": ev.get("x", 0), "y": ev.get("y", 0),
            "palabra": ev.get("palabra", ""),
            "miniatura": _miniatura(video, ev["ini"] + 0.2),
            "overlay": _b64(Path(ev["archivo"]), "image/png")
            if Path(ev["archivo"]).suffix.lower() == ".png" and Path(ev["archivo"]).exists() else None,
        })

    ruta_cortado = dir_trabajo / "02_cortado.mp4"
    resolucion_origen = _resolucion(ruta_cortado) if ruta_cortado.exists() else (config.ANCHO, config.ALTO)

    return {
        "nombre": dir_trabajo.name,
        "duracion": round(duracion, 3),
        "ancho": config.ANCHO, "alto": config.ALTO, "fps": config.FPS,
        "resolucion_origen": list(resolucion_origen),  # w_in/h_in reales del recorte de f4_retencion
        "encuadre": muestras_encuadre(dir_trabajo, duracion),
        "palabras": [{"t": p["inicio"], "fin": p["fin"], "texto": p["texto"]}
                     for p in transcripcion["palabras"]],
        "sfx": sfx,
        "overlays": [{
            "idx": i, "tipo": ev["tipo"], "ini": ev["ini"], "fin": ev["fin"],
            "x": ev.get("x", 0), "y": ev.get("y", 0),
            "medio": ev.get("medio", "imagen"),
            # ruta absoluta: f11_servidor la sirve por /archivo con lista blanca de raíces
            "archivo": str(Path(ev["archivo"]).resolve()) if ev.get("archivo") else None,
        } for i, ev in enumerate(eventos)],
        "movibles": movibles,
        "sonidos": sonidos,
        "volumenes": {k: v["volumen"] for k, v in config.SFX_POR_EVENTO.items()},
    }


PLANTILLA = """<div id="app">
  <header>
    <h1>Editor visual · <span id="nombre"></span></h1>
    <p class="sub">Arrastra los efectos sobre la línea de tiempo y mueve los insertos sobre el
       fotograma. Al terminar, exporta el JSON y pásalo al pipeline.</p>
  </header>

  <section class="panel">
    <h2>1 · Efectos de sonido</h2>
    <div class="barra">
      <label>Sonido a insertar
        <select id="selSonido"></select>
      </label>
      <button id="btnEscuchar" type="button">▶ Escuchar</button>
      <button id="btnAgregar" type="button">+ Agregar en el centro</button>
      <span class="hint" id="infoSel"></span>
    </div>

    <div id="pista" class="pista">
      <div id="reglas"></div>
      <div id="palabras" class="palabras"></div>
      <div id="marcadores"></div>
    </div>

    <div class="tabla-wrap">
      <table id="tabla">
        <thead><tr><th>t</th><th>sonido</th><th>volumen</th><th>motivo</th><th></th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </section>

  <section class="panel">
    <h2>2 · Posición de los insertos</h2>
    <p class="sub" id="sinMovibles" hidden>Este video no tiene insertos movibles.
       Las tarjetas de Hyperframes se colocan solas dentro de su plantilla.</p>
    <div class="lienzos" id="lienzos"></div>
  </section>

  <section class="panel">
    <h2>3 · Exportar</h2>
    <div class="barra">
      <button id="btnJson" type="button">Descargar ajustes.json</button>
      <button id="btnCopiar" type="button">Copiar al portapapeles</button>
    </div>
    <pre id="salida"></pre>
    <p class="sub">Después, en la carpeta del proyecto:</p>
    <pre class="cmd">python editor/editor.py "contexto/VIDEO.mp4" --sfx-manual ajustes.sfx.json --posiciones-manual ajustes.pos.json</pre>
    <p class="sub">El botón de descarga genera los dos archivos por separado, ya con el nombre correcto.</p>
  </section>
</div>
"""


def construir_html(datos: dict) -> str:
    # Identidad tomada de la marca real (sección 5.3 del plan): navy #0A2A3E y
    # cian #4FD1D9. Los grises no son neutros puros — llevan una pizca de azul
    # verdoso para que el conjunto se lea como una sola familia con el cian.
    css = """
:root {
  color-scheme: light dark;
  --navy:#0A2A3E; --cian:#4FD1D9;
  --bg:#eef3f4; --panel:#ffffff; --fg:#0b2029; --fg-2:#4a6572;
  --linea:#cfdde1; --acento:#0d6d75; --acento-suave:#e2f2f3;
  --alerta:#c2582f;
  --r:12px;
}
@media (prefers-color-scheme: dark) {
  :root { --bg:#081217; --panel:#0f1e25; --fg:#e6eef1; --fg-2:#8fa8b3;
          --linea:#20353f; --acento:#4FD1D9; --acento-suave:#12303a; --alerta:#e8834f; }
}
:root[data-theme="dark"] { --bg:#081217; --panel:#0f1e25; --fg:#e6eef1; --fg-2:#8fa8b3;
  --linea:#20353f; --acento:#4FD1D9; --acento-suave:#12303a; --alerta:#e8834f; }
:root[data-theme="light"] { --bg:#eef3f4; --panel:#ffffff; --fg:#0b2029; --fg-2:#4a6572;
  --linea:#cfdde1; --acento:#0d6d75; --acento-suave:#e2f2f3; --alerta:#c2582f; }

* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--fg);
       font:16px/1.55 "Segoe UI",-apple-system,BlinkMacSystemFont,Roboto,sans-serif; }
#app { max-width:1120px; margin:0 auto; padding:28px 20px 72px;
       display:flex; flex-direction:column; gap:20px; }
header { border-left:4px solid var(--cian); padding-left:16px; }
header h1 { font-size:27px; line-height:1.15; margin:0 0 2px; letter-spacing:-.01em;
            text-wrap:balance; }
header h1 span { color:var(--acento); font-variant-numeric:tabular-nums; }
.sub { color:var(--fg-2); margin:0; font-size:14px; max-width:62ch; }
.panel { background:var(--panel); border:1px solid var(--linea); border-radius:var(--r);
         padding:20px; display:flex; flex-direction:column; gap:14px; }
.panel h2 { font-size:12px; text-transform:uppercase; letter-spacing:.09em;
            color:var(--fg-2); margin:0; font-weight:700; }
.barra { display:flex; gap:10px; align-items:flex-end; flex-wrap:wrap; }
label { font-size:12px; letter-spacing:.05em; text-transform:uppercase; color:var(--fg-2);
        display:flex; flex-direction:column; gap:5px; }
select, button, input { font:inherit; padding:8px 12px; border-radius:9px;
        border:1px solid var(--linea); background:var(--panel); color:var(--fg); }
button { cursor:pointer; font-size:14px; }
button:hover { border-color:var(--acento); color:var(--acento); }
:focus-visible { outline:2px solid var(--acento); outline-offset:2px; }
.hint { font-size:13px; color:var(--fg-2); align-self:center; }

.pista { position:relative; height:178px; border:1px solid var(--linea); border-radius:10px;
         background:var(--acento-suave); overflow:hidden; user-select:none; touch-action:none; }
#reglas div { position:absolute; top:0; bottom:0; width:1px; background:var(--linea); }
#reglas span { position:absolute; top:3px; font-size:10px; padding-left:5px; color:var(--fg-2);
               font-variant-numeric:tabular-nums; letter-spacing:.05em; }
.palabras { position:absolute; top:28px; left:0; right:0; height:100px; }
.palabras span { position:absolute; font-size:11px; white-space:nowrap; color:var(--fg-2); }
.marca { position:absolute; bottom:8px; width:14px; height:46px; margin-left:-7px;
         border-radius:4px; background:var(--acento); cursor:grab; border:2px solid var(--panel);
         box-shadow:0 2px 7px rgba(0,0,0,.3); }
.marca.sel { background:var(--alerta); }
.marca:active { cursor:grabbing; }

.tabla-wrap { overflow-x:auto; }
table { width:100%; border-collapse:collapse; font-size:14px; min-width:520px; }
th, td { text-align:left; padding:8px; border-bottom:1px solid var(--linea); }
th { font-size:11px; text-transform:uppercase; letter-spacing:.07em; color:var(--fg-2); }
td:first-child input { width:82px; font-variant-numeric:tabular-nums; }
td input[type=number] { width:78px; }

.lienzos { display:flex; gap:20px; flex-wrap:wrap; }
.lienzo { font-size:12px; color:var(--fg-2); display:flex; flex-direction:column; gap:6px; }
.marco { position:relative; width:270px; height:480px; border-radius:10px; overflow:hidden;
         border:1px solid var(--linea); background:#101a1f; touch-action:none; }
.marco img.fondo { width:100%; height:100%; object-fit:cover; display:block; }
.caja { position:absolute; border:2px dashed var(--cian); cursor:grab;
        background:rgba(79,209,217,.14); }
.caja img { width:100%; height:100%; display:block; }
.caja:active { cursor:grabbing; }

pre { background:var(--acento-suave); border:1px solid var(--linea); padding:12px;
      border-radius:9px; overflow-x:auto; font-size:12px; max-height:240px; margin:0;
      font-family:ui-monospace,"Cascadia Mono",Consolas,monospace; }
pre.cmd { max-height:none; }
@media (prefers-reduced-motion: reduce) { * { transition:none !important; animation:none !important; } }
"""

    js = """
const D = window.__DATOS__;
const pista = document.getElementById("pista");
const capaMarcas = document.getElementById("marcadores");
let sfx = D.sfx.map((e, i) => ({ ...e, id: i }));
let seleccion = null;

document.getElementById("nombre").textContent = D.nombre + " · " + D.duracion.toFixed(1) + "s";

// ---- reglas de tiempo y transcripción -------------------------------------
const reglas = document.getElementById("reglas");
for (let s = 0; s <= Math.floor(D.duracion); s += 5) {
  const x = (s / D.duracion) * 100;
  const l = document.createElement("div"); l.style.left = x + "%"; reglas.appendChild(l);
  const t = document.createElement("span"); t.style.left = x + "%"; t.textContent = s + "s";
  reglas.appendChild(t);
}
const capaPal = document.getElementById("palabras");
D.palabras.forEach((p, i) => {
  const s = document.createElement("span");
  s.textContent = p.texto;
  s.style.left = (p.t / D.duracion) * 100 + "%";
  s.style.top = ((i % 6) * 16) + "px";
  capaPal.appendChild(s);
});

// ---- vocabulario de sonidos ------------------------------------------------
const sel = document.getElementById("selSonido");
Object.keys(D.sonidos).forEach(n => {
  const o = document.createElement("option"); o.value = n; o.textContent = n; sel.appendChild(o);
});
const audio = new Audio();
function escuchar(nombre) { audio.src = D.sonidos[nombre]; audio.currentTime = 0; audio.play(); }
document.getElementById("btnEscuchar").onclick = () => escuchar(sel.value);
sel.onchange = () => escuchar(sel.value);

// ---- marcadores arrastrables ----------------------------------------------
function pintar() {
  capaMarcas.innerHTML = "";
  sfx.sort((a, b) => a.t - b.t);
  sfx.forEach(e => {
    const m = document.createElement("div");
    m.className = "marca" + (seleccion === e.id ? " sel" : "");
    m.style.left = (e.t / D.duracion) * 100 + "%";
    m.title = e.archivo + " · " + e.t.toFixed(2) + "s";
    m.onpointerdown = ev => {
      ev.preventDefault(); m.setPointerCapture(ev.pointerId);
      seleccion = e.id; escuchar(e.archivo); pintar();
      const mover = mv => {
        const r = pista.getBoundingClientRect();
        let t = ((mv.clientX - r.left) / r.width) * D.duracion;
        e.t = Math.max(0, Math.min(D.duracion, Math.round(t * 100) / 100));
        pintar(); tabla();
      };
      const soltar = () => {
        window.removeEventListener("pointermove", mover);
        window.removeEventListener("pointerup", soltar);
      };
      window.addEventListener("pointermove", mover);
      window.addEventListener("pointerup", soltar);
    };
    capaMarcas.appendChild(m);
  });
  document.getElementById("infoSel").textContent =
    sfx.length + " efecto(s). Clic en un marcador para escucharlo y arrastrarlo.";
}

function tabla() {
  const tb = document.querySelector("#tabla tbody");
  tb.innerHTML = "";
  sfx.forEach(e => {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td><input type="number" step="0.05" min="0" max="${D.duracion}" value="${e.t.toFixed(2)}"></td>` +
      `<td><select></select></td>` +
      `<td><input type="number" step="0.05" min="0" max="1.5" value="${e.volumen}"></td>` +
      `<td>${e.razon}</td><td><button type="button">quitar</button></td>`;
    const [inT, inV] = tr.querySelectorAll("input");
    const s = tr.querySelector("select");
    Object.keys(D.sonidos).forEach(n => {
      const o = document.createElement("option"); o.value = n; o.textContent = n;
      if (n === e.archivo) o.selected = true; s.appendChild(o);
    });
    inT.onchange = () => { e.t = parseFloat(inT.value) || 0; pintar(); volcar(); };
    inV.onchange = () => { e.volumen = parseFloat(inV.value) || 0; volcar(); };
    s.onchange = () => { e.archivo = s.value; escuchar(s.value); volcar(); };
    tr.querySelector("button").onclick = () => {
      sfx = sfx.filter(x => x.id !== e.id); pintar(); tabla(); volcar();
    };
    tb.appendChild(tr);
  });
  volcar();
}

document.getElementById("btnAgregar").onclick = () => {
  const t = Math.round(D.duracion / 2 * 100) / 100;
  sfx.push({ id: Date.now(), t, archivo: sel.value, volumen: 0.8, razon: "manual" });
  pintar(); tabla();
};

// ---- posición de los insertos ---------------------------------------------
const ESC = 270 / D.ancho;             // el marco mide 270px de ancho
const movibles = D.movibles.map(m => ({ ...m }));
const cont = document.getElementById("lienzos");
if (!movibles.length) document.getElementById("sinMovibles").hidden = false;

movibles.forEach(m => {
  const box = document.createElement("div");
  box.className = "lienzo";
  const marco = document.createElement("div");
  marco.className = "marco";
  if (m.miniatura) {
    const img = document.createElement("img");
    img.className = "fondo"; img.src = m.miniatura; marco.appendChild(img);
  }
  const caja = document.createElement("div");
  caja.className = "caja";
  const anchoCaja = m.overlay ? 0 : 400 * ESC;   // se ajusta al cargar la imagen
  caja.style.left = (m.x * ESC) + "px";
  caja.style.top = (m.y * ESC) + "px";
  if (m.overlay) {
    const io = document.createElement("img");
    io.src = m.overlay;
    io.onload = () => {
      caja.style.width = (io.naturalWidth * ESC) + "px";
      caja.style.height = (io.naturalHeight * ESC) + "px";
    };
    caja.appendChild(io);
  } else {
    caja.style.width = anchoCaja + "px";
    caja.style.height = (520 * ESC) + "px";
  }
  caja.onpointerdown = ev => {
    ev.preventDefault(); caja.setPointerCapture(ev.pointerId);
    const r0 = caja.getBoundingClientRect();
    const dx = ev.clientX - r0.left, dy = ev.clientY - r0.top;
    const mover = mv => {
      const r = marco.getBoundingClientRect();
      let px = mv.clientX - r.left - dx, py = mv.clientY - r.top - dy;
      px = Math.max(0, Math.min(r.width - r0.width, px));
      py = Math.max(0, Math.min(r.height - r0.height, py));
      caja.style.left = px + "px"; caja.style.top = py + "px";
      m.x = Math.round(px / ESC); m.y = Math.round(py / ESC);
      etiqueta.textContent = `${m.tipo} · ${m.ini.toFixed(1)}s · x=${m.x} y=${m.y}`;
      volcar();
    };
    const soltar = () => {
      window.removeEventListener("pointermove", mover);
      window.removeEventListener("pointerup", soltar);
    };
    window.addEventListener("pointermove", mover);
    window.addEventListener("pointerup", soltar);
  };
  marco.appendChild(caja);
  const etiqueta = document.createElement("div");
  etiqueta.textContent = `${m.tipo} · ${m.ini.toFixed(1)}s · x=${m.x} y=${m.y}`;
  box.appendChild(marco); box.appendChild(etiqueta);
  cont.appendChild(box);
});

// ---- exportar --------------------------------------------------------------
function ajustes() {
  return {
    sfx: sfx.map(e => ({ t: Math.round(e.t * 100) / 100, archivo: e.archivo,
                         volumen: e.volumen, razon: e.razon })).sort((a, b) => a.t - b.t),
    posiciones: movibles.map(m => ({ tipo: m.tipo, ini: m.ini, x: m.x, y: m.y })),
  };
}
function volcar() {
  document.getElementById("salida").textContent = JSON.stringify(ajustes(), null, 2);
}
function descargar(nombre, contenido) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([contenido], { type: "application/json" }));
  a.download = nombre; a.click(); URL.revokeObjectURL(a.href);
}
document.getElementById("btnJson").onclick = () => {
  const a = ajustes();
  descargar("ajustes.sfx.json", JSON.stringify(a.sfx, null, 2));
  descargar("ajustes.pos.json", JSON.stringify(a.posiciones, null, 2));
};
document.getElementById("btnCopiar").onclick = () =>
  navigator.clipboard.writeText(JSON.stringify(ajustes(), null, 2));

pintar(); tabla();
"""

    datos_js = json.dumps(datos, ensure_ascii=False)
    return (f"<title>Editor visual · {datos['nombre']}</title>\n"
            f"<style>{css}</style>\n{PLANTILLA}\n"
            f"<script>window.__DATOS__ = {datos_js};</script>\n"
            f"<script>{js}</script>\n")


def main():
    ap = argparse.ArgumentParser(description="Editor visual de sonidos y posiciones")
    ap.add_argument("dir_trabajo", type=str,
                    help=r"Carpeta de la corrida, p.ej. C:\ai-video\salida\mi_video")
    ap.add_argument("--salida", type=str, default=None)
    args = ap.parse_args()

    dir_trabajo = Path(args.dir_trabajo)
    if not (dir_trabajo / "05_overlays.eventos.json").exists():
        print(f"ERROR: {dir_trabajo} no parece una carpeta de trabajo del pipeline "
              "(falta 05_overlays.eventos.json)", file=sys.stderr)
        sys.exit(1)

    datos = recolectar(dir_trabajo)
    html = construir_html(datos)
    salida = Path(args.salida) if args.salida else dir_trabajo / "09_editor-visual.html"
    salida.write_text(html, encoding="utf-8")
    kb = salida.stat().st_size / 1024
    print(f"Editor visual: {salida}  ({kb:.0f} KB, autocontenido)")
    print(f"  {len(datos['sfx'])} efectos · {len(datos['movibles'])} insertos movibles · "
          f"{len(datos['sonidos'])} sonidos embebidos")


if __name__ == "__main__":
    main()
