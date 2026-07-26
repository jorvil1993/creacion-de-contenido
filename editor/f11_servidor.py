"""
Editor visual v2 — servidor local (Fase 1+ de contexto/PLAN-EDITOR-VISUAL-V2.md).

http.server de stdlib, JS y CSS planos. Sin dependencias nuevas, sin red
externa. Escucha SOLO en 127.0.0.1 (nunca 0.0.0.0, sección 3 del plan).

v1 (`f10_editor_visual.py`) embebía todo en base64 en un solo HTML: no escala
a 198 miniaturas + video + MP3 (sección 3 del plan). Este módulo sirve los
mismos datos (reutiliza `f10_editor_visual.recolectar()`, no los duplica) por
HTTP, con streaming real para el video.

Uso:
    python f11_servidor.py "C:\\ai-video\\salida\\<nombre>"
    python f11_servidor.py "C:\\ai-video\\salida\\<nombre>" --puerto 8765 --sin-abrir
"""
import argparse
import json
import mimetypes
import re
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import f10_editor_visual as f10

DIR_TRABAJO: Path = None
RAICES_PERMITIDAS: list = None


def _archivo_permitido(ruta: Path) -> bool:
    """Solo sirve archivos dentro de las carpetas del proyecto/salida — nunca
    el filesystem entero, aunque el servidor solo escuche en localhost."""
    try:
        ruta = ruta.resolve()
    except OSError:
        return False
    return any(ruta.is_relative_to(raiz) for raiz in RAICES_PERMITIDAS)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # silencioso: un GET por frame de scrubbing ensuciaría la consola

    # -- helpers de respuesta --------------------------------------------
    def _json(self, datos, code=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _archivo(self, ruta: Path, mime: str = None):
        if not ruta.exists() or not ruta.is_file():
            self.send_error(404, "No existe")
            return
        mime = mime or mimetypes.guess_type(str(ruta))[0] or "application/octet-stream"
        tam = ruta.stat().st_size
        rango = self.headers.get("Range")
        if rango:
            m = re.match(r"bytes=(\d+)-(\d*)", rango)
            if not m:
                self.send_error(416, "Range inválido")
                return
            inicio = int(m.group(1))
            fin = int(m.group(2)) if m.group(2) else tam - 1
            fin = min(fin, tam - 1)
            if inicio > fin or inicio >= tam:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{tam}")
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Range", f"bytes {inicio}-{fin}/{tam}")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(fin - inicio + 1))
            self.end_headers()
            with open(ruta, "rb") as f:
                f.seek(inicio)
                restante = fin - inicio + 1
                while restante > 0:
                    trozo = f.read(min(65536, restante))
                    if not trozo:
                        break
                    self.wfile.write(trozo)
                    restante -= len(trozo)
        else:
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(tam))
            self.end_headers()
            with open(ruta, "rb") as f:
                while True:
                    trozo = f.read(65536)
                    if not trozo:
                        break
                    self.wfile.write(trozo)

    def _html(self, cuerpo_str: str, code=200):
        cuerpo = cuerpo_str.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    # -- rutas -------------------------------------------------------------
    def do_GET(self):
        partes = urlparse(self.path)
        ruta = partes.path
        qs = parse_qs(partes.query)
        try:
            if ruta == "/":
                self._html(PAGINA)
            elif ruta == "/datos":
                self._json(f10.recolectar(DIR_TRABAJO))
            elif ruta == "/video":
                proxy = f10.generar_proxy(DIR_TRABAJO / "02_cortado.mp4", DIR_TRABAJO)
                self._archivo(proxy, "video/mp4")
            elif ruta == "/archivo":
                valores = qs.get("ruta")
                if not valores:
                    self.send_error(400, "falta ?ruta=")
                    return
                objetivo = Path(valores[0])
                if not _archivo_permitido(objetivo):
                    self.send_error(403, "ruta fuera de las carpetas permitidas")
                    return
                self._archivo(objetivo)
            else:
                self.send_error(404, "Ruta desconocida")
        except FileNotFoundError as e:
            self.send_error(404, str(e))
        except Exception as e:  # nunca tirar el servidor por un dato faltante
            self.send_error(500, str(e))

    def do_POST(self):
        self.send_error(404, "Todavía no implementado (Fase 2/5)")


PAGINA = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Editor visual v2 — DeviceShop</title>
<style>
:root {
  --bg: #0b1216; --panel: #101a1f; --linea: #1c2b33; --fg: #e8f1f4; --fg-2: #9db3bc;
  --acento: #4fd1d9; --acento-suave: rgba(79,209,217,.15); --navy: #0a2a3e;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
       font-family: ui-sans-serif, system-ui, "Segoe UI", Arial, sans-serif; }
header { padding: 14px 20px; border-bottom: 1px solid var(--linea); display: flex;
         align-items: baseline; gap: 12px; flex-wrap: wrap; }
header h1 { font-size: 16px; margin: 0; }
header .sub { color: var(--fg-2); font-size: 13px; }
main { display: grid; grid-template-columns: minmax(280px, 420px) 1fr; gap: 20px; padding: 20px;
       max-width: 1200px; margin: 0 auto; }
@media (max-width: 820px) { main { grid-template-columns: 1fr; } }

.lienzo-wrap { display: flex; flex-direction: column; gap: 10px; align-items: center; }
.lienzo { position: relative; width: 100%; max-width: 380px; aspect-ratio: 1080 / 1920;
          background: #000; overflow: hidden; border-radius: 10px; border: 1px solid var(--linea); }
.lienzo video { position: absolute; top: 0; left: 0; transform-origin: 0 0; }
.lienzo .overlay-img { position: absolute; top: 0; left: 0; transform-origin: 0 0;
                        pointer-events: none; image-rendering: -webkit-optimize-contrast; }
.controles { display: flex; gap: 8px; align-items: center; }
.controles button { background: var(--panel); color: var(--fg); border: 1px solid var(--linea);
                     border-radius: 8px; padding: 8px 14px; cursor: pointer; font-size: 14px; }
.controles button:hover { border-color: var(--acento); }
.controles .t { font-variant-numeric: tabular-nums; color: var(--fg-2); font-size: 13px; }

.panel { background: var(--panel); border: 1px solid var(--linea); border-radius: 10px; padding: 14px; }
.panel h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .04em; color: var(--fg-2);
            margin: 0 0 10px; }

.pista { position: relative; border: 1px solid var(--linea); border-radius: 8px;
         padding: 10px; cursor: pointer; user-select: none; }
.pista .franjas { position: relative; height: 26px; margin-bottom: 8px; }
.pista .franja { position: absolute; top: 0; height: 100%; border-radius: 4px;
                  background: var(--acento-suave); border: 1px solid var(--acento);
                  font-size: 10px; color: var(--acento); overflow: hidden; white-space: nowrap;
                  padding: 2px 4px; }
.pista .franja.video { background: rgba(255,255,255,.06); border-color: var(--fg-2); color: var(--fg-2); }
.pista .palabras { display: flex; flex-wrap: wrap; gap: 2px 4px; max-height: 160px; overflow-y: auto; }
.pista .palabra { font-size: 13px; padding: 1px 3px; border-radius: 3px; cursor: pointer; }
.pista .palabra:hover { background: var(--acento-suave); }
.pista .palabra.activa { background: var(--acento); color: #06181c; }
.playhead { position: absolute; top: 0; bottom: 0; width: 2px; background: #ff5566; pointer-events: none; }

.hint { color: var(--fg-2); font-size: 12px; line-height: 1.5; }
.badge { display: inline-block; background: var(--acento-suave); color: var(--acento);
         border-radius: 4px; padding: 1px 6px; font-size: 11px; margin-left: 6px; }
</style>
</head>
<body>
<header>
  <h1>Editor visual v2 <span id="nombre"></span></h1>
  <span class="sub" id="resumen"></span>
</header>
<main>
  <div class="lienzo-wrap">
    <div class="lienzo" id="lienzo">
      <video id="video" muted playsinline preload="auto"></video>
    </div>
    <div class="controles">
      <button id="btnPlay" type="button">▶ Reproducir</button>
      <span class="t" id="tActual">0.00s</span>
      <span class="t">/ <span id="tTotal">0.00s</span></span>
    </div>
    <p class="hint">El encuadre (zoom + paneo) se calcula con la misma función que usa el
      render final — lo que ves aquí es lo que sale en el video, no una aproximación.
      Los overlays con animación (Hyperframes) todavía no se ven aquí — se agregan en la
      Fase 3 del plan.</p>
  </div>

  <div class="panel">
    <h2>Línea de tiempo</h2>
    <div class="pista" id="pista">
      <div class="franjas" id="franjas"></div>
      <div class="palabras" id="palabras"></div>
    </div>
  </div>
</main>

<script>
let DATA = null;
const video = document.getElementById("video");
const lienzo = document.getElementById("lienzo");

async function cargar() {
  const r = await fetch("/datos");
  DATA = await r.json();
  document.getElementById("nombre").textContent = "· " + DATA.nombre;
  document.getElementById("resumen").textContent =
    `${DATA.duracion.toFixed(1)}s · ${DATA.overlays.length} overlays · ${DATA.palabras.length} palabras`;
  document.getElementById("tTotal").textContent = DATA.duracion.toFixed(2) + "s";

  video.src = "/video";
  construirOverlays();
  construirTimeline();
  requestAnimationFrame(loop);
}

function construirOverlays() {
  for (const mov of DATA.movibles) {
    const img = document.createElement("img");
    img.className = "overlay-img";
    img.dataset.ini = mov.ini;
    img.dataset.fin = mov.fin;
    img.dataset.x = mov.x;
    img.dataset.y = mov.y;
    img.src = mov.overlay ? mov.overlay : "";
    img.style.display = "none";
    lienzo.appendChild(img);
  }
}

function construirTimeline() {
  const franjas = document.getElementById("franjas");
  const dur = DATA.duracion;
  for (const ov of DATA.overlays) {
    const div = document.createElement("div");
    div.className = "franja" + (ov.medio === "video" ? " video" : "");
    div.style.left = (ov.ini / dur * 100) + "%";
    div.style.width = Math.max(0.5, (ov.fin - ov.ini) / dur * 100) + "%";
    div.textContent = ov.tipo;
    franjas.appendChild(div);
  }
  const playhead = document.createElement("div");
  playhead.className = "playhead";
  playhead.id = "playhead";
  franjas.appendChild(playhead);

  const cont = document.getElementById("palabras");
  for (const p of DATA.palabras) {
    const span = document.createElement("span");
    span.className = "palabra";
    span.textContent = p.texto;
    span.dataset.t = p.t;
    span.addEventListener("click", () => { video.currentTime = p.t; });
    cont.appendChild(span);
  }

  document.getElementById("pista").addEventListener("click", (ev) => {
    if (ev.target.closest(".palabra")) return;
    const franjasEl = document.getElementById("franjas");
    const rect = franjasEl.getBoundingClientRect();
    if (ev.clientY < rect.top || ev.clientY > rect.bottom) return;
    const frac = (ev.clientX - rect.left) / rect.width;
    video.currentTime = Math.max(0, Math.min(DATA.duracion, frac * DATA.duracion));
  });
}

function muestraEn(t) {
  const arr = DATA.encuadre;
  const idx = Math.min(arr.length - 1, Math.max(0, Math.round(t * DATA.fps)));
  return arr[idx]; // [t, cx, cy, zoom]
}

function aplicarEncuadre(cx, cy, zoom) {
  const [wIn, hIn] = DATA.resolucion_origen;
  const s = lienzo.clientWidth / wIn;
  video.style.width = (wIn * s) + "px";
  video.style.height = (hIn * s) + "px";

  const aspectoSalida = DATA.ancho / DATA.alto;
  let hCrop = hIn / zoom;
  let wCrop = hCrop * aspectoSalida;
  if (wCrop > wIn) { wCrop = wIn; hCrop = wCrop / aspectoSalida; }

  let x0 = cx * wIn - wCrop / 2;
  let y0 = cy * hIn - hCrop / 2;
  x0 = Math.min(Math.max(x0, 0), wIn - wCrop);
  y0 = Math.min(Math.max(y0, 0), hIn - hCrop);

  video.style.transform = `scale(${zoom}) translate(${(-x0 * s).toFixed(2)}px, ${(-y0 * s).toFixed(2)}px)`;
}

function actualizarOverlays(t) {
  const s = lienzo.clientWidth / DATA.resolucion_origen[0];
  for (const img of lienzo.querySelectorAll(".overlay-img")) {
    const ini = parseFloat(img.dataset.ini), fin = parseFloat(img.dataset.fin);
    const visible = t >= ini && t < fin;
    img.style.display = visible ? "" : "none";
    if (visible) {
      const x = parseFloat(img.dataset.x), y = parseFloat(img.dataset.y);
      img.style.transform = `translate(${(x * s).toFixed(2)}px, ${(y * s).toFixed(2)}px) scale(${s.toFixed(4)})`;
    }
  }
}

function actualizarUI(t) {
  document.getElementById("tActual").textContent = t.toFixed(2) + "s";
  const dur = DATA.duracion;
  const ph = document.getElementById("playhead");
  if (ph) ph.style.left = (Math.min(1, t / dur) * 100) + "%";
  for (const span of document.querySelectorAll(".palabra")) {
    const pt = parseFloat(span.dataset.t);
    span.classList.toggle("activa", Math.abs(pt - t) < 0.35 && t >= pt);
  }
}

function loop() {
  if (DATA) {
    const t = video.currentTime;
    const [, cx, cy, zoom] = muestraEn(t);
    aplicarEncuadre(cx, cy, zoom);
    actualizarOverlays(t);
    actualizarUI(t);
  }
  requestAnimationFrame(loop);
}

document.getElementById("btnPlay").addEventListener("click", () => {
  if (video.paused) { video.play(); document.getElementById("btnPlay").textContent = "⏸ Pausar"; }
  else { video.pause(); document.getElementById("btnPlay").textContent = "▶ Reproducir"; }
});

window.addEventListener("resize", () => {
  if (DATA) { const [, cx, cy, zoom] = muestraEn(video.currentTime); aplicarEncuadre(cx, cy, zoom); }
});

cargar();
</script>
</body>
</html>
"""


def main():
    global DIR_TRABAJO, RAICES_PERMITIDAS
    ap = argparse.ArgumentParser(description="Editor visual v2 — servidor local")
    ap.add_argument("dir_trabajo", type=str)
    ap.add_argument("--puerto", type=int, default=8765)
    ap.add_argument("--sin-abrir", action="store_true", help="No abrir el navegador automáticamente")
    args = ap.parse_args()

    DIR_TRABAJO = Path(args.dir_trabajo).resolve()
    if not DIR_TRABAJO.exists():
        print(f"ERROR: no existe {DIR_TRABAJO}", file=sys.stderr)
        sys.exit(1)

    RAICES_PERMITIDAS = [config.RAIZ_AI_VIDEO.resolve(), config.RAIZ_PROYECTO.resolve()]

    puerto = args.puerto
    servidor = None
    while servidor is None:
        try:
            servidor = ThreadingHTTPServer(("127.0.0.1", puerto), Handler)
        except OSError:
            puerto += 1
            if puerto > args.puerto + 20:
                print("ERROR: no se encontró un puerto libre cerca de "
                      f"{args.puerto}", file=sys.stderr)
                sys.exit(1)
    if puerto != args.puerto:
        print(f"Puerto {args.puerto} ocupado — usando {puerto} en su lugar.")

    url = f"http://127.0.0.1:{puerto}/"
    print(f"Editor visual: {url}")
    print(f"Carpeta: {DIR_TRABAJO}")
    if not args.sin_abrir:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")


if __name__ == "__main__":
    main()
