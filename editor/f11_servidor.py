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
import subprocess
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
_CATALOGO_CACHE: list = None
ESTADO_RENDER = {"proceso": None, "log": None}


def _escritura_atomica(destino: Path, datos) -> Path:
    """A .tmp y renombrar (sección 3 del plan): si José tiene el JSON abierto
    en otra parte, nunca debe quedar a medio escribir."""
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(destino)
    return destino


def _guardar_eventos(eventos: list) -> Path:
    return _escritura_atomica(DIR_TRABAJO / "ajustes.eventos.json", {"eventos": eventos})


def _guardar_sfx(sfx: list) -> Path:
    # --sfx-manual (f5_audio.py) espera una LISTA plana, no envuelta en dict.
    return _escritura_atomica(DIR_TRABAJO / "ajustes.sfx.json", sfx)


def _catalogo() -> list:
    global _CATALOGO_CACHE
    if _CATALOGO_CACHE is None:
        ruta = config.DIR_CONTEXTO / "catalogo-assets.json"
        _CATALOGO_CACHE = json.loads(ruta.read_text(encoding="utf-8"))["assets"]
    return _CATALOGO_CACHE


def _asset_por_id(asset_id: str) -> dict | None:
    return next((a for a in _catalogo() if a["id"] == asset_id), None)


def _archivo_permitido(ruta: Path) -> bool:
    """Solo sirve archivos dentro de las carpetas del proyecto/salida — nunca
    el filesystem entero, aunque el servidor solo escuche en localhost."""
    try:
        ruta = ruta.resolve()
    except OSError:
        return False
    return any(ruta.is_relative_to(raiz) for raiz in RAICES_PERMITIDAS)


def _estado_render() -> dict:
    proceso = ESTADO_RENDER.get("proceso")
    log_path = ESTADO_RENDER.get("log")
    if proceso is None:
        return {"activo": False, "corrio_alguna_vez": False}

    activo = proceso.poll() is None
    if not activo and ESTADO_RENDER.get("archivo_log"):
        try:
            ESTADO_RENDER["archivo_log"].close()
        except Exception:
            pass
        ESTADO_RENDER["archivo_log"] = None

    texto = ""
    if log_path and log_path.exists():
        texto = log_path.read_text(encoding="utf-8", errors="replace")
    progreso = re.findall(r"render: (\d+)/(\d+) frames", texto)
    ultimo = progreso[-1] if progreso else None

    return {
        "activo": activo,
        "corrio_alguna_vez": True,
        "ok": (not activo) and proceso.returncode == 0,
        "error": (not activo) and proceso.returncode != 0,
        "progreso": {"actual": int(ultimo[0]), "total": int(ultimo[1])} if ultimo else None,
        "cola_log": texto[-2000:],
    }


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
            elif ruta == "/catalogo":
                todos = qs.get("todos", ["0"])[0] in ("1", "true")
                self._json(f10.catalogo_pip(DIR_TRABAJO, todos=todos))
            elif ruta == "/miniatura":
                asset = _asset_por_id((qs.get("asset_id") or [""])[0])
                if asset is None:
                    self.send_error(404, "asset_id desconocido")
                    return
                ruta_thumb = f10.miniatura_catalogo(asset)
                if ruta_thumb is None:
                    self.send_error(404, "no se pudo generar la miniatura")
                    return
                self._archivo(ruta_thumb, "image/jpeg")
            elif ruta == "/tarjeta":
                asset = _asset_por_id((qs.get("asset_id") or [""])[0])
                if asset is None:
                    self.send_error(404, "asset_id desconocido")
                    return
                ruta_tarjeta = f10.render_tarjeta_catalogo(asset)
                if ruta_tarjeta is None:
                    self.send_error(404, "no se pudo renderizar la tarjeta")
                    return
                self._archivo(ruta_tarjeta, "image/png")
            elif ruta == "/render/estado":
                self._json(_estado_render())
            else:
                self.send_error(404, "Ruta desconocida")
        except FileNotFoundError as e:
            self.send_error(404, str(e))
        except Exception as e:  # nunca tirar el servidor por un dato faltante
            self.send_error(500, str(e))

    def do_POST(self):
        partes = urlparse(self.path)
        largo = int(self.headers.get("Content-Length", 0))
        cuerpo = self.rfile.read(largo) if largo else b"{}"
        try:
            datos = json.loads(cuerpo.decode("utf-8")) if cuerpo else {}
        except Exception as e:
            self.send_error(400, f"JSON inválido: {e}")
            return

        if partes.path == "/guardar":
            eventos = datos.get("eventos", [])
            destino = _guardar_eventos(eventos)
            resultado = {"ok": True, "ruta": str(destino), "n": len(eventos)}
            if "sfx" in datos:
                destino_sfx = _guardar_sfx(datos["sfx"])
                resultado["ruta_sfx"] = str(destino_sfx)
                resultado["n_sfx"] = len(datos["sfx"])
            self._json(resultado)

        elif partes.path == "/render":
            proceso_previo = ESTADO_RENDER.get("proceso")
            if proceso_previo is not None and proceso_previo.poll() is None:
                self._json({"ok": False, "error": "ya hay un render en curso"}, code=409)
                return

            # "Guardar siempre antes de renderizar" (Fase 5, punto 4): que un
            # fallo de ffmpeg nunca pierda los ajustes que se iban a probar.
            ajustes = None
            if "eventos" in datos:
                ajustes = _guardar_eventos(datos["eventos"])
            else:
                candidato = DIR_TRABAJO / "ajustes.eventos.json"
                if candidato.exists():
                    ajustes = candidato

            ajustes_sfx = None
            if "sfx" in datos:
                ajustes_sfx = _guardar_sfx(datos["sfx"])
            else:
                candidato_sfx = DIR_TRABAJO / "ajustes.sfx.json"
                if candidato_sfx.exists():
                    ajustes_sfx = candidato_sfx

            # editor.py solo necesita que "entrada" exista — en --reaplicar no
            # se lee: la transcripción/corte/análisis ya están en dir_trabajo.
            dummy_entrada = DIR_TRABAJO / "02_cortado.mp4"
            cmd = [sys.executable, "editor.py", str(dummy_entrada),
                   "--nombre", DIR_TRABAJO.name, "--reaplicar", "--sin-editor-visual"]
            if ajustes is not None:
                cmd += ["--eventos-manual", str(ajustes)]
            if ajustes_sfx is not None:
                cmd += ["--sfx-manual", str(ajustes_sfx)]

            dir_log = DIR_TRABAJO / "_editor"
            dir_log.mkdir(exist_ok=True)
            log_path = dir_log / "render.log"
            # stdout/stderr a un archivo, NUNCA a un pipe sin leer (trampa #5
            # del plan: ffmpeg se cuelga si nadie vacía el buffer).
            archivo_log = open(log_path, "wb")
            proceso = subprocess.Popen(cmd, cwd=str(Path(__file__).resolve().parent),
                                       stdout=archivo_log, stderr=subprocess.STDOUT)
            ESTADO_RENDER["proceso"] = proceso
            ESTADO_RENDER["log"] = log_path
            ESTADO_RENDER["archivo_log"] = archivo_log
            self._json({"ok": True, "pid": proceso.pid, "log": str(log_path)})

        else:
            self.send_error(404, "Ruta desconocida")


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
                        cursor: grab; image-rendering: -webkit-optimize-contrast; }
.lienzo .overlay-img:active { cursor: grabbing; }
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
.badge.aviso { background: rgba(230,180,40,.18); color: #e6b428; }

.pips-lista { display: flex; flex-direction: column; gap: 8px; margin-bottom: 12px; }
.pip-card { display: flex; gap: 10px; align-items: center; border: 1px solid var(--linea);
            border-radius: 8px; padding: 6px; }
.pip-card img { width: 46px; height: 60px; object-fit: cover; border-radius: 4px; background: #000; }
.pip-card .info { flex: 1; font-size: 12px; color: var(--fg-2); }
.pip-card .info b { color: var(--fg); font-weight: 600; }
.pip-card button { background: var(--panel); color: var(--fg); border: 1px solid var(--linea);
                    border-radius: 6px; padding: 4px 8px; font-size: 12px; cursor: pointer; }
.pip-card button.quitar:hover { border-color: #ff5566; color: #ff5566; }
.pip-card button.sustituir:hover, .btn-primario:hover { border-color: var(--acento); color: var(--acento); }
.pip-card.editando { border-color: var(--acento); }

.btn-primario { background: var(--acento-suave); color: var(--acento); border: 1px solid var(--acento);
                border-radius: 6px; padding: 6px 12px; font-size: 13px; cursor: pointer; margin-bottom: 10px; }

.filtros { display: flex; gap: 8px; align-items: center; margin-bottom: 10px; font-size: 12px;
           color: var(--fg-2); flex-wrap: wrap; }
.filtros label { display: flex; gap: 4px; align-items: center; cursor: pointer; }
.grid-catalogo { display: grid; grid-template-columns: repeat(auto-fill, minmax(76px, 1fr));
                  gap: 6px; max-height: 340px; overflow-y: auto; }
.grid-catalogo .item { position: relative; cursor: pointer; border: 2px solid transparent;
                        border-radius: 6px; overflow: hidden; }
.grid-catalogo .item:hover { border-color: var(--acento); }
.grid-catalogo .item img { width: 100%; aspect-ratio: 400/520; object-fit: cover; display: block;
                            background: #000; }
.grid-catalogo .item .pend { position: absolute; top: 2px; right: 2px; background: rgba(230,180,40,.85);
                              color: #201800; font-size: 9px; padding: 1px 4px; border-radius: 3px; }
.editor-caja { border: 1px dashed var(--linea); border-radius: 8px; padding: 10px; margin-top: 10px;
               display: none; }
.editor-caja.activa { display: block; }

.pista-sfx { position: relative; height: 54px; border: 1px solid var(--linea); border-radius: 8px;
             background: rgba(79,209,217,.06); cursor: pointer; touch-action: none; }
.franjas-sfx { position: relative; width: 100%; height: 100%; }
.marca-sfx { position: absolute; bottom: 6px; width: 12px; height: 38px; margin-left: -6px;
             border-radius: 4px; background: var(--acento); cursor: grab;
             border: 2px solid var(--panel); box-shadow: 0 2px 6px rgba(0,0,0,.3); }
.marca-sfx.sel { background: #ff5566; }
.marca-sfx:active { cursor: grabbing; }
#tablaSfx th, #tablaSfx td { text-align: left; padding: 6px; border-bottom: 1px solid var(--linea); }
#tablaSfx th { font-size: 10px; text-transform: uppercase; color: var(--fg-2); }
#tablaSfx input, #tablaSfx select { font: inherit; background: var(--bg); color: var(--fg);
                                     border: 1px solid var(--linea); border-radius: 4px; padding: 3px 5px; }
#tablaSfx input[type=number] { width: 64px; }
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

  <div class="panel" style="grid-column: 1 / -1;">
    <h2>Efectos de sonido</h2>
    <p class="hint">Arrastrá los marcadores para moverlos en el tiempo. El sonido de un PiP se
      mueve solo cuando movés el inserto (Fase 4: "el sonido acompaña al evento visual").</p>
    <div class="barra-sfx" style="display:flex; gap:8px; align-items:center; margin-bottom:8px; flex-wrap:wrap;">
      <select id="selSonido"></select>
      <button class="btn-primario" id="btnEscuchar" type="button">▶ Escuchar</button>
      <button class="btn-primario" id="btnAgregarSfx" type="button">+ Agregar en el centro</button>
      <span class="hint" id="infoSfx"></span>
    </div>
    <div class="pista-sfx" id="pistaSfx">
      <div class="franjas-sfx" id="franjasSfx"></div>
    </div>
    <div class="tabla-wrap" style="overflow-x:auto; margin-top:10px;">
      <table id="tablaSfx" style="width:100%; border-collapse:collapse; font-size:13px;">
        <thead><tr><th>t</th><th>sonido</th><th>volumen</th><th>motivo</th><th></th></tr></thead>
        <tbody></tbody>
      </table>
    </div>
  </div>

  <div class="panel" style="grid-column: 1 / -1;">
    <h2>Colección de PiP <span class="hint" id="dominanteInfo"></span></h2>
    <p class="hint">Sustituí, añadí o quitá los insertos de producto. Los overlays con animación
      (hook, ficha, batería, splash, sol, cta) no se editan todavía acá — llega en la Fase 3.</p>
    <div class="pips-lista" id="pipsLista"></div>
    <button class="btn-primario" id="btnAñadirPip" type="button">+ Añadir PiP en el segundo actual</button>

    <div class="editor-caja" id="cajaCatalogo">
      <div class="filtros">
        <strong id="editandoInfo">Elegí un asset:</strong>
        <label><input type="checkbox" id="chkTodos"> ver todos (<span id="totalCatalogo">198</span>)</label>
        <button type="button" id="btnCancelarEdicion">cancelar</button>
      </div>
      <div class="grid-catalogo" id="gridCatalogo"></div>
    </div>

    <p class="hint" style="margin-top:10px;">
      <button class="btn-primario" id="btnGuardar" type="button">Guardar cambios</button>
      <button class="btn-primario" id="btnRender" type="button">Re-renderizar</button>
      Guarda siempre antes de renderizar. El video final tarda ~34s en actualizarse.
    </p>
    <div id="cajaProgreso" style="display:none;">
      <div style="background:var(--linea); border-radius:6px; height:8px; overflow:hidden; margin-bottom:6px;">
        <div id="barraProgreso" style="background:var(--acento); height:100%; width:0%; transition:width .3s;"></div>
      </div>
      <p class="hint" id="textoProgreso"></p>
    </div>
  </div>
</main>

<script>
let DATA = null;
const video = document.getElementById("video");
const lienzo = document.getElementById("lienzo");

let edicionPip = [];
let editandoIdx = null; // índice en edicionPip, o -1 para "nuevo antes de agregar"
let loopArrancado = false;

let edicionSfx = [];
let sfxModificado = false;      // si es false, no se manda --sfx-manual: sigue automático
let sfxSeleccion = null;
const audioPreview = new Audio();

function escucharSfx(nombre) {
  if (!DATA.sonidos[nombre]) return;
  audioPreview.src = DATA.sonidos[nombre];
  audioPreview.currentTime = 0;
  audioPreview.play();
}

async function cargar() {
  const r = await fetch("/datos");
  DATA = await r.json();
  document.getElementById("nombre").textContent = "· " + DATA.nombre;
  document.getElementById("resumen").textContent =
    `${DATA.duracion.toFixed(1)}s · ${DATA.overlays.length} overlays · ${DATA.palabras.length} palabras`;
  document.getElementById("tTotal").textContent = DATA.duracion.toFixed(2) + "s";

  video.src = "/video";
  construirTimeline();

  edicionPip = DATA.movibles.filter(m => m.tipo === "pip-producto").map(m => ({
    ini: m.ini, fin: m.fin, x: m.x, y: m.y,
    asset_id: (m.asset && !m.asset.startsWith("generado:") && !m.asset.startsWith("manual")) ? m.asset : null,
    archivo: m.archivo, tarjeta: m.overlay,
  }));
  renderPipsLista();
  construirOverlays(); // depende de edicionPip: tiene que ir después de poblarlo

  edicionSfx = DATA.sfx.map((e, i) => ({ ...e, id: i }));
  sfxModificado = false;
  sfxSeleccion = null;
  construirSelectorSonidos();
  pintarSfx();
  tablaSfx();

  // cargar() se vuelve a llamar después de cada render (Fase 5): el rAF loop
  // solo se arranca una vez, si no cada recarga sumaría otro loop corriendo
  // en paralelo.
  if (!loopArrancado) {
    loopArrancado = true;
    requestAnimationFrame(loop);
  }
}

function avisosPip() {
  // Límites automáticos como AVISO, no bloqueo (Fase 2, punto 7 del plan):
  // en modo manual José puede romperlos a propósito.
  const lim = DATA.limites;
  const avisos = edicionPip.map(() => []);
  if (edicionPip.length > lim.insertos_max) {
    avisos.forEach(a => a.push(`más de ${lim.insertos_max} insertos`));
  }
  const orden = edicionPip.map((ev, i) => ({ i, ini: ev.ini })).sort((a, b) => a.ini - b.ini);
  for (let k = 1; k < orden.length; k++) {
    const sep = orden[k].ini - orden[k - 1].ini;
    if (sep < lim.separacion_min_s) {
      avisos[orden[k].i].push(`a ${sep.toFixed(1)}s del anterior (mínimo ${lim.separacion_min_s}s)`);
      avisos[orden[k - 1].i].push(`muy cerca del siguiente`);
    }
  }
  return avisos;
}

function renderPipsLista() {
  const cont = document.getElementById("pipsLista");
  cont.innerHTML = "";
  if (edicionPip.length === 0) {
    cont.innerHTML = '<p class="hint">No hay insertos de producto en este video.</p>';
  }
  const avisos = avisosPip();
  edicionPip.forEach((ev, i) => {
    const div = document.createElement("div");
    div.className = "pip-card" + (editandoIdx === i ? " editando" : "");
    const img = document.createElement("img");
    img.src = ev.tarjeta || (ev.asset_id ? `/tarjeta?asset_id=${encodeURIComponent(ev.asset_id)}` : "");
    div.appendChild(img);
    const info = document.createElement("div");
    info.className = "info";
    const badges = avisos[i].map(a => `<span class="badge aviso">${a}</span>`).join("");
    info.innerHTML = `<b>${ev.ini.toFixed(1)}s - ${ev.fin.toFixed(1)}s</b> ${badges}<br>${ev.asset_id || ev.archivo?.split(/[\\/]/).pop() || "sin asset"}`;
    div.appendChild(info);
    const btnSust = document.createElement("button");
    btnSust.className = "sustituir"; btnSust.textContent = "Sustituir";
    btnSust.addEventListener("click", () => abrirCatalogo(i));
    div.appendChild(btnSust);
    const btnQuitar = document.createElement("button");
    btnQuitar.className = "quitar"; btnQuitar.textContent = "Quitar";
    btnQuitar.addEventListener("click", () => { edicionPip.splice(i, 1); renderPipsLista(); construirOverlays(); });
    div.appendChild(btnQuitar);
    cont.appendChild(div);
  });
}

function construirSelectorSonidos() {
  const sel = document.getElementById("selSonido");
  sel.innerHTML = "";
  Object.keys(DATA.sonidos).forEach(n => {
    const o = document.createElement("option");
    o.value = n; o.textContent = n;
    sel.appendChild(o);
  });
}

function pintarSfx() {
  const cont = document.getElementById("franjasSfx");
  cont.innerHTML = "";
  const pista = document.getElementById("pistaSfx");
  edicionSfx.sort((a, b) => a.t - b.t);
  edicionSfx.forEach(e => {
    const m = document.createElement("div");
    m.className = "marca-sfx" + (sfxSeleccion === e.id ? " sel" : "");
    m.style.left = (e.t / DATA.duracion * 100) + "%";
    m.title = `${e.archivo} · ${e.t.toFixed(2)}s · ${e.razon}`;
    m.addEventListener("pointerdown", (ev) => {
      ev.preventDefault();
      try { m.setPointerCapture(ev.pointerId); } catch (err) { /* seguimos igual sin captura */ }
      sfxSeleccion = e.id;
      escucharSfx(e.archivo);
      pintarSfx();
      const mover = (mv) => {
        const r = pista.getBoundingClientRect();
        let t = (mv.clientX - r.left) / r.width * DATA.duracion;
        e.t = Math.max(0, Math.min(DATA.duracion, Math.round(t * 100) / 100));
        sfxModificado = true;
        pintarSfx();
        tablaSfx();
      };
      const soltar = () => {
        window.removeEventListener("pointermove", mover);
        window.removeEventListener("pointerup", soltar);
      };
      window.addEventListener("pointermove", mover);
      window.addEventListener("pointerup", soltar);
    });
    cont.appendChild(m);
  });
  document.getElementById("infoSfx").textContent =
    `${edicionSfx.length} efecto(s)` + (sfxModificado ? " · editado a mano" : " · automático");
}

function tablaSfx() {
  const tb = document.querySelector("#tablaSfx tbody");
  tb.innerHTML = "";
  edicionSfx.forEach(e => {
    const tr = document.createElement("tr");
    const tdT = document.createElement("td");
    const inT = document.createElement("input");
    inT.type = "number"; inT.step = "0.05"; inT.min = "0"; inT.max = String(DATA.duracion);
    inT.value = e.t.toFixed(2);
    inT.addEventListener("change", () => {
      e.t = parseFloat(inT.value) || 0; sfxModificado = true; pintarSfx(); tablaSfx();
    });
    tdT.appendChild(inT); tr.appendChild(tdT);

    const tdSonido = document.createElement("td");
    const selFila = document.createElement("select");
    Object.keys(DATA.sonidos).forEach(n => {
      const o = document.createElement("option");
      o.value = n; o.textContent = n;
      if (n === e.archivo) o.selected = true;
      selFila.appendChild(o);
    });
    selFila.addEventListener("change", () => {
      e.archivo = selFila.value; sfxModificado = true; escucharSfx(selFila.value);
    });
    tdSonido.appendChild(selFila); tr.appendChild(tdSonido);

    const tdVol = document.createElement("td");
    const inV = document.createElement("input");
    inV.type = "number"; inV.step = "0.05"; inV.min = "0"; inV.max = "1.5";
    inV.value = e.volumen;
    inV.addEventListener("change", () => {
      e.volumen = parseFloat(inV.value) || 0; sfxModificado = true;
    });
    tdVol.appendChild(inV); tr.appendChild(tdVol);

    const tdRazon = document.createElement("td");
    tdRazon.textContent = e.razon; tr.appendChild(tdRazon);

    const tdBtn = document.createElement("td");
    const btnQuitar = document.createElement("button");
    btnQuitar.type = "button"; btnQuitar.textContent = "quitar";
    btnQuitar.addEventListener("click", () => {
      edicionSfx = edicionSfx.filter(x => x.id !== e.id);
      sfxModificado = true; pintarSfx(); tablaSfx();
    });
    tdBtn.appendChild(btnQuitar); tr.appendChild(tdBtn);

    tb.appendChild(tr);
  });
}

document.getElementById("btnEscuchar").addEventListener("click", () => {
  escucharSfx(document.getElementById("selSonido").value);
});
document.getElementById("btnAgregarSfx").addEventListener("click", () => {
  const archivo = document.getElementById("selSonido").value;
  edicionSfx.push({
    id: Date.now(), t: Math.round(DATA.duracion / 2 * 100) / 100,
    archivo, volumen: 0.8, razon: "manual",
  });
  sfxModificado = true;
  pintarSfx(); tablaSfx();
});

function sfxParaGuardar() {
  return edicionSfx.map(e => ({
    t: Math.round(e.t * 100) / 100, archivo: e.archivo, volumen: e.volumen, razon: e.razon,
  })).sort((a, b) => a.t - b.t);
}

async function abrirCatalogo(idx) {
  editandoIdx = idx;
  document.getElementById("cajaCatalogo").classList.add("activa");
  document.getElementById("editandoInfo").textContent =
    idx === -1 ? "Elegí el asset para el nuevo PiP:" : `Sustituyendo el inserto de ${edicionPip[idx].ini.toFixed(1)}s:`;
  renderPipsLista();
  await cargarGridCatalogo();
}

async function cargarGridCatalogo() {
  const todos = document.getElementById("chkTodos").checked;
  const r = await fetch(`/catalogo?todos=${todos ? 1 : 0}`);
  const datos = await r.json();
  document.getElementById("totalCatalogo").textContent = datos.total_catalogo;
  document.getElementById("dominanteInfo").textContent =
    datos.producto_dominante ? `— producto detectado: ${datos.producto_dominante}` : "";
  const grid = document.getElementById("gridCatalogo");
  grid.innerHTML = "";
  for (const a of datos.assets) {
    const item = document.createElement("div");
    item.className = "item";
    item.title = `${a.producto} · ${a.tipo} · ${a.color || ""}`;
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = `/miniatura?asset_id=${encodeURIComponent(a.id)}`;
    item.appendChild(img);
    if (a.fondo_pendiente) {
      const pend = document.createElement("span");
      pend.className = "pend"; pend.textContent = "sin recorte";
      item.appendChild(pend);
    }
    item.addEventListener("click", () => elegirAsset(a));
    grid.appendChild(item);
  }
}

function elegirAsset(asset) {
  if (editandoIdx === -1) {
    edicionPip.push({
      ini: video.currentTime, fin: Math.min(DATA.duracion, video.currentTime + 2.8),
      x: 620, y: 134, asset_id: asset.id, archivo: null, tarjeta: null,
    });
  } else {
    edicionPip[editandoIdx].asset_id = asset.id;
    edicionPip[editandoIdx].archivo = null;
    edicionPip[editandoIdx].tarjeta = null;
  }
  document.getElementById("cajaCatalogo").classList.remove("activa");
  editandoIdx = null;
  renderPipsLista();
  construirOverlays();
}

document.getElementById("btnAñadirPip").addEventListener("click", () => abrirCatalogo(-1));
document.getElementById("btnCancelarEdicion").addEventListener("click", () => {
  editandoIdx = null;
  document.getElementById("cajaCatalogo").classList.remove("activa");
  renderPipsLista();
});
document.getElementById("chkTodos").addEventListener("change", cargarGridCatalogo);
function eventosParaGuardar() {
  return edicionPip.map(ev => {
    const base = { ini: ev.ini, fin: ev.fin, x: ev.x, y: ev.y };
    if (ev.asset_id) base.asset_id = ev.asset_id;
    else if (ev.archivo) base.archivo = ev.archivo;
    return base;
  });
}

function cuerpoAjustes() {
  // Si el panel de sonidos no se tocó, no se manda --sfx-manual: el SFX
  // sigue derivándose automático de los eventos (así "acompaña" cualquier
  // PiP que se mueva, sustituya o quite — Fase 4, punto 2 del plan).
  const cuerpo = { eventos: eventosParaGuardar() };
  if (sfxModificado) cuerpo.sfx = sfxParaGuardar();
  return cuerpo;
}

document.getElementById("btnGuardar").addEventListener("click", async () => {
  const r = await fetch("/guardar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpoAjustes()),
  });
  const datos = await r.json();
  const btn = document.getElementById("btnGuardar");
  const original = btn.textContent;
  btn.textContent = datos.ok ? `Guardado (${datos.n})` : "Error al guardar";
  setTimeout(() => { btn.textContent = original; }, 2000);
});

let sondeoRender = null;

async function iniciarRender() {
  const btn = document.getElementById("btnRender");
  const caja = document.getElementById("cajaProgreso");
  const barra = document.getElementById("barraProgreso");
  const texto = document.getElementById("textoProgreso");

  const r = await fetch("/render", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(cuerpoAjustes()),
  });
  const resp = await r.json();
  if (!resp.ok) {
    texto.textContent = "No se pudo iniciar: " + (resp.error || "");
    caja.style.display = "";
    return;
  }

  btn.disabled = true;
  caja.style.display = "";
  barra.style.width = "0%";
  texto.textContent = "Renderizando...";

  sondeoRender = setInterval(async () => {
    const er = await fetch("/render/estado");
    const est = await er.json();
    if (est.progreso) {
      const pct = Math.round(100 * est.progreso.actual / est.progreso.total);
      barra.style.width = pct + "%";
      texto.textContent = `Renderizando: ${est.progreso.actual}/${est.progreso.total} frames (${pct}%)`;
    }
    if (!est.activo) {
      clearInterval(sondeoRender);
      btn.disabled = false;
      if (est.ok) {
        barra.style.width = "100%";
        texto.textContent = "Listo — recargando preview...";
        await cargar(); // recarga /datos y el <video src> con los cambios ya aplicados
        video.load();
        texto.textContent = "Listo. El preview ya muestra el resultado nuevo.";
      } else {
        texto.textContent = "Error en el render — revisar " + (est.cola_log ? "el log" : "");
        console.error("Render falló:", est.cola_log);
      }
    }
  }, 1000);
}

document.getElementById("btnRender").addEventListener("click", iniciarRender);

function construirOverlays() {
  // Se reconstruye desde `edicionPip` (el estado editable), no desde
  // DATA.movibles (la foto fija del último /datos): así sustituir/añadir/
  // quitar en el panel de PiP se refleja también en el lienzo, y arrastrar
  // en el lienzo actualiza lo mismo que ve el panel.
  lienzo.querySelectorAll(".overlay-img").forEach(el => el.remove());
  edicionPip.forEach((ev, idx) => {
    const img = document.createElement("img");
    img.className = "overlay-img";
    img.dataset.idx = idx;
    img.src = ev.tarjeta || (ev.asset_id ? `/tarjeta?asset_id=${encodeURIComponent(ev.asset_id)}` : "");
    img.style.display = "none";
    img.title = "Arrastrar para reposicionar";
    img.addEventListener("pointerdown", iniciarArrastrePip);
    lienzo.appendChild(img);
  });
}

function iniciarArrastrePip(ev) {
  const img = ev.currentTarget;
  ev.preventDefault();
  try { img.setPointerCapture(ev.pointerId); } catch (e) { /* seguimos igual sin captura */ }
  const idx = parseInt(img.dataset.idx, 10);
  const item = edicionPip[idx];
  if (!item) return;
  const s = lienzo.clientWidth / DATA.resolucion_origen[0];
  const r = img.getBoundingClientRect();
  const offX = ev.clientX - r.left, offY = ev.clientY - r.top;
  arrastrandoIdx = idx;

  const mover = (mv) => {
    const rl = lienzo.getBoundingClientRect();
    let xPx = mv.clientX - rl.left - offX, yPx = mv.clientY - rl.top - offY;
    xPx = Math.max(0, Math.min(rl.width - r.width, xPx));
    yPx = Math.max(0, Math.min(rl.height - r.height, yPx));
    item.x = Math.round(xPx / s);
    item.y = Math.round(yPx / s);
    img.style.transform = `translate(${xPx.toFixed(2)}px, ${yPx.toFixed(2)}px) scale(${s.toFixed(4)})`;
  };
  const soltar = () => {
    window.removeEventListener("pointermove", mover);
    window.removeEventListener("pointerup", soltar);
    arrastrandoIdx = null;
    renderPipsLista();
  };
  window.addEventListener("pointermove", mover);
  window.addEventListener("pointerup", soltar);
}

function construirTimeline() {
  const franjas = document.getElementById("franjas");
  const palabrasEl = document.getElementById("palabras");
  franjas.innerHTML = "";
  palabrasEl.innerHTML = "";
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

  for (const p of DATA.palabras) {
    const span = document.createElement("span");
    span.className = "palabra";
    span.textContent = p.texto;
    span.dataset.t = p.t;
    span.addEventListener("click", () => { video.currentTime = p.t; });
    palabrasEl.appendChild(span);
  }
}

document.getElementById("pista").addEventListener("click", (ev) => {
  if (!DATA) return;
  if (ev.target.closest(".palabra")) return;
  const franjasEl = document.getElementById("franjas");
  const rect = franjasEl.getBoundingClientRect();
  if (ev.clientY < rect.top || ev.clientY > rect.bottom) return;
  const frac = (ev.clientX - rect.left) / rect.width;
  video.currentTime = Math.max(0, Math.min(DATA.duracion, frac * DATA.duracion));
});

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

let arrastrandoIdx = null; // mientras se arrastra un PiP, el loop no le pisa la posición

function actualizarOverlays(t) {
  const s = lienzo.clientWidth / DATA.resolucion_origen[0];
  for (const img of lienzo.querySelectorAll(".overlay-img")) {
    const idx = parseInt(img.dataset.idx, 10);
    const item = edicionPip[idx];
    if (!item) { img.style.display = "none"; continue; }
    const visible = t >= item.ini && t < item.fin;
    img.style.display = visible ? "" : "none";
    if (visible && arrastrandoIdx !== idx) {
      img.style.transform = `translate(${(item.x * s).toFixed(2)}px, ${(item.y * s).toFixed(2)}px) scale(${s.toFixed(4)})`;
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
