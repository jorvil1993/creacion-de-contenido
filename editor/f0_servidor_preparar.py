"""
Fase 0 — Pantalla de preparación (servidor local).

La superficie que faltaba: elegir qué grabaciones entran, recortarles el
principio y el final mirándolas, ordenarlas, ver cómo quedan unidas y arrancar
el pipeline. Después de esto, hacer un video no obliga a escribir en la
terminal.

Mismo patrón que `f11_servidor.py` (http.server de stdlib, JS y CSS planos,
127.0.0.1 y nada más), pero en un ARCHIVO APARTE a propósito: f11 son 122 KB de
servidor + HTML + JS en un solo módulo, y meter esto ahí sería garantizar
conflictos con cualquier otra sesión que lo esté tocando. La lógica de verdad
—recortar, unir, detectar bordes— vive en `f0_preparar.py`, sin HTTP.

A diferencia de f11, este servidor NO se queda escuchando para siempre: cuando
José pulsa «Empezar», guarda la orden, se apaga y devuelve el control a
`preparar.py`, que es quien lanza el pipeline en la MISMA terminal. Así el
progreso de la transcripción y del render se ve donde se hizo doble clic, y al
final se abre el editor visual como en cualquier otra corrida.

Uso:
    python f0_servidor_preparar.py            # abre el navegador
    python f0_servidor_preparar.py --sin-abrir --puerto 8790
"""
import argparse
import json
import mimetypes
import re
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import f0_preparar

# Lo que José eligió. `main()` lo devuelve para que preparar.py lance el
# pipeline; queda en None si cerró la pestaña sin arrancar nada.
ORDEN = None

# Preparación de cada clip (proxy + detección de bordes) en segundo plano: el
# proxy de una grabación de 50s tarda ~11s la primera vez (medido), y bloquear
# la petición HTTP durante 11s deja la pantalla congelada sin explicar por qué.
_CLIPS = {}
_LOCK = threading.Lock()
_SERVIDOR = None


def _permitida(ruta: Path) -> bool:
    """Solo se sirven archivos de `entrada/` y de la carpeta de preparación.

    Mismo criterio que `f11_servidor._archivo_permitido`: el navegador manda
    rutas y no hay que creerle ninguna. `resolve()` antes de comparar, para que
    un `..` no se escape de la carpeta.
    """
    try:
        ruta = Path(ruta).resolve()
    except Exception:
        return False
    for raiz in (config.DIR_ENTRADA, config.DIR_PREPARACION):
        try:
            ruta.relative_to(Path(raiz).resolve())
            return True
        except ValueError:
            continue
    return False


def _preparar_clip_async(ruta: Path):
    """Genera el proxy y detecta los bordes de un clip, en un hilo aparte."""
    clave = str(ruta)
    with _LOCK:
        if clave in _CLIPS and _CLIPS[clave].get("estado") in ("trabajando", "listo"):
            return
        _CLIPS[clave] = {"estado": "trabajando"}

    def trabajo():
        try:
            bordes = f0_preparar.detectar_bordes(ruta)
            f0_preparar.proxy_clip(ruta)
            with _LOCK:
                _CLIPS[clave] = {"estado": "listo", "bordes": bordes}
        except Exception as e:
            with _LOCK:
                _CLIPS[clave] = {"estado": "error", "error": str(e)}

    threading.Thread(target=trabajo, daemon=True).start()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    # -- helpers ----------------------------------------------------------
    def _json(self, datos, code=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(cuerpo)

    def _archivo(self, ruta: Path, mime: str = None):
        """Sirve un archivo con soporte de Range. Sin Range el navegador no
        puede saltar dentro del video, que es justo lo que hay que hacer para
        elegir un punto de corte."""
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

    def _html(self, cuerpo_str: str):
        cuerpo = cuerpo_str.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _ruta_pedida(self, qs) -> Path | None:
        valores = qs.get("ruta")
        if not valores:
            self.send_error(400, "falta ?ruta=")
            return None
        objetivo = Path(valores[0])
        if not _permitida(objetivo):
            self.send_error(403, "ruta fuera de las carpetas permitidas")
            return None
        return objetivo

    # -- rutas -------------------------------------------------------------
    def do_GET(self):
        partes = urlparse(self.path)
        ruta, qs = partes.path, parse_qs(partes.query)
        try:
            if ruta == "/":
                self._html(PAGINA)
            elif ruta == "/datos":
                videos = f0_preparar.listar_entrada()
                prev = None
                if videos:
                    # La preparación se guarda al lado del PRIMER clip, así que
                    # se busca una por cada video de la carpeta: el material que
                    # ya se preparó puede no ser el más reciente.
                    for v in videos:
                        prev = f0_preparar.leer_preparado(Path(v["ruta"]))
                        if prev:
                            break
                self._json({
                    "videos": videos,
                    "guiones": f0_preparar.listar_guiones(),
                    "preparado": prev,
                    "dir_entrada": str(config.DIR_ENTRADA),
                })
            elif ruta == "/clip":
                objetivo = self._ruta_pedida(qs)
                if objetivo is None:
                    return
                with _LOCK:
                    self._json(_CLIPS.get(str(objetivo), {"estado": "sin-empezar"}))
            elif ruta == "/proxy":
                objetivo = self._ruta_pedida(qs)
                if objetivo is None:
                    return
                self._archivo(f0_preparar.proxy_clip(objetivo), "video/mp4")
            elif ruta == "/previa":
                objetivo = config.DIR_PREPARACION / "previa.mp4"
                self._archivo(objetivo, "video/mp4")
            else:
                self.send_error(404, "Ruta desconocida")
        except Exception as e:
            self.send_error(500, str(e))

    def do_POST(self):
        global ORDEN
        partes = urlparse(self.path)
        largo = int(self.headers.get("Content-Length", 0))
        crudo = self.rfile.read(largo) if largo else b"{}"
        try:
            datos = json.loads(crudo.decode("utf-8")) if crudo else {}
        except Exception as e:
            self.send_error(400, f"JSON inválido: {e}")
            return
        try:
            if partes.path == "/clip":
                objetivo = Path(datos.get("ruta", ""))
                if not _permitida(objetivo):
                    self.send_error(403, "ruta fuera de las carpetas permitidas")
                    return
                _preparar_clip_async(objetivo)
                with _LOCK:
                    self._json(_CLIPS.get(str(objetivo), {"estado": "trabajando"}))

            elif partes.path == "/previa":
                clips = datos.get("clips") or []
                for c in clips:
                    if not _permitida(Path(c["ruta"])):
                        self.send_error(403, "ruta fuera de las carpetas permitidas")
                        return
                destino = config.DIR_PREPARACION / "previa.mp4"
                destino.parent.mkdir(parents=True, exist_ok=True)
                # `escala` es lo único que separa esta llamada de la de verdad:
                # el recorte y la unión los hace la MISMA función que usa
                # editor.py, así que lo que se ve aquí es lo que va a entrar al
                # pipeline, no una aproximación.
                ruta, empalmes = f0_preparar.preparar_entrada(
                    clips, destino, escala=config.PREVIEW_ESCALA)
                self._json({
                    "url": f"/previa?v={int(Path(ruta).stat().st_mtime)}",
                    "duracion": round(f0_preparar.duracion(ruta), 2),
                    "empalmes": empalmes,
                })

            elif partes.path == "/guardar":
                ruta = f0_preparar.guardar_preparado(
                    datos.get("clips") or [], datos.get("guion"))
                self._json({"ok": True, "archivo": str(ruta)})

            elif partes.path == "/empezar":
                clips = datos.get("clips") or []
                guion = datos.get("guion")
                nombre = (datos.get("nombre") or "").strip() or None
                archivo = f0_preparar.guardar_preparado(clips, guion, nombre)
                ORDEN = {
                    "clips": [str(Path(c["ruta"]).resolve()) for c in clips],
                    "guion": guion,
                    "nombre": nombre,
                    "preparado": str(archivo),
                }
                self._json({"ok": True})
                # Apagar desde el propio hilo del handler se bloquea a sí mismo:
                # shutdown() espera a que el bucle termine y el bucle espera a
                # que esta respuesta se cierre.
                threading.Thread(target=_SERVIDOR.shutdown, daemon=True).start()

            else:
                self.send_error(404, "Ruta desconocida")
        except Exception as e:
            self._json({"ok": False, "error": str(e)}, code=500)


PAGINA = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Preparar grabación — DeviceShop</title>
<style>
:root {
  --bg: #0b1216; --panel: #101a1f; --linea: #1c2b33; --fg: #e8f1f4; --fg-2: #9db3bc;
  --acento: #4fd1d9; --acento-suave: rgba(79,209,217,.15); --alerta: #ffb454;
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg);
       font-family: ui-sans-serif, system-ui, "Segoe UI", Arial, sans-serif; }
header { padding: 14px 20px; border-bottom: 1px solid var(--linea);
         display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
header h1 { font-size: 16px; margin: 0; }
header .sub { color: var(--fg-2); font-size: 13px; }
main { display: flex; align-items: flex-start; gap: 20px; padding: 20px; }
@media (max-width: 900px) { main { flex-direction: column; } .col-izq { align-self: stretch; } }
.col-izq { flex: 0 0 260px; position: sticky; top: 14px; }
.col-der { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 14px; }
.panel { background: var(--panel); border: 1px solid var(--linea); border-radius: 10px; padding: 14px; }
.panel h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .04em;
            color: var(--fg-2); margin: 0 0 10px; }
.hint { color: var(--fg-2); font-size: 12px; line-height: 1.5; }
button { background: var(--panel); color: var(--fg); border: 1px solid var(--linea);
         border-radius: 8px; padding: 7px 12px; cursor: pointer; font-size: 13px; }
button:hover:not(:disabled) { border-color: var(--acento); }
button:disabled { opacity: .4; cursor: default; }
button.primario { background: var(--acento); color: #06181c; border-color: var(--acento);
                  font-weight: 600; padding: 10px 18px; font-size: 14px; }
select, input[type=text] { background: #0b1216; color: var(--fg); border: 1px solid var(--linea);
                           border-radius: 8px; padding: 7px 10px; font-size: 13px; }

/* --- lista de entrada/ --- */
.vid { display: flex; gap: 10px; align-items: center; padding: 8px; border-radius: 8px;
       cursor: pointer; border: 1px solid transparent; }
.vid:hover { border-color: var(--linea); background: rgba(255,255,255,.03); }
.vid .n { font-size: 13px; word-break: break-all; }
.vid .m { font-size: 11px; color: var(--fg-2); font-variant-numeric: tabular-nums; }
.vid.puesto { opacity: .45; }

/* --- tarjeta de clip --- */
.clip { display: flex; gap: 14px; }
.clip video { width: 180px; aspect-ratio: 1080/1920; background: #000; border-radius: 8px;
              border: 1px solid var(--linea); flex: none; }
.clip .cuerpo { flex: 1 1 auto; min-width: 0; display: flex; flex-direction: column; gap: 10px; }
.clip .cab { display: flex; align-items: center; gap: 8px; }
.clip .cab .titulo { font-size: 13px; font-weight: 600; flex: 1 1 auto;
                     overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.clip.activo { outline: 1px solid var(--acento); outline-offset: 6px; border-radius: 6px; }

/* --- barra de recorte --- */
.barra { position: relative; height: 44px; background: #0b1216; border: 1px solid var(--linea);
         border-radius: 6px; cursor: pointer; user-select: none; touch-action: none; }
.barra .fuera { position: absolute; top: 0; bottom: 0; background: rgba(0,0,0,.55); }
.barra .sel { position: absolute; top: 0; bottom: 0; background: var(--acento-suave);
              border-left: 1px solid var(--acento); border-right: 1px solid var(--acento); }
.barra .manija { position: absolute; top: -3px; bottom: -3px; width: 12px; margin-left: -6px;
                 cursor: ew-resize; border-radius: 4px; background: var(--acento);
                 box-shadow: 0 0 0 1px #06181c; }
.barra .manija::after { content: ""; position: absolute; left: 5px; top: 50%; width: 2px;
                        height: 14px; margin-top: -7px; background: #06181c; }
.barra .aguja { position: absolute; top: 0; bottom: 0; width: 2px; background: #ff5566;
                pointer-events: none; }
.barra .etq { position: absolute; bottom: 3px; font-size: 10px; color: var(--fg-2);
              pointer-events: none; font-variant-numeric: tabular-nums; }

.fila { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; font-size: 12px;
        color: var(--fg-2); font-variant-numeric: tabular-nums; }
.aviso { border-left: 3px solid var(--alerta); background: rgba(255,180,84,.08);
         padding: 8px 10px; border-radius: 0 6px 6px 0; font-size: 12px; color: #ffd9a3;
         line-height: 1.5; }
.pie { display: flex; gap: 14px; align-items: center; flex-wrap: wrap; }
.pie .total { font-size: 22px; font-variant-numeric: tabular-nums; }
.pie .total.malo { color: var(--alerta); }
#previaCaja { display: none; gap: 14px; align-items: flex-start; }
#previaCaja video { width: 240px; aspect-ratio: 1080/1920; background: #000;
                    border-radius: 8px; border: 1px solid var(--linea); }
.vacio { color: var(--fg-2); font-size: 13px; padding: 20px; text-align: center; }
</style>
</head>
<body>
<header>
  <h1>Preparar grabación</h1>
  <span class="sub">Elegí, recortá, ordená y arrancá — sin tocar la terminal</span>
  <span class="sub" style="margin-left:auto" id="atajos">Espacio: reproducir el clip activo</span>
</header>

<main>
  <div class="col-izq">
    <div class="panel">
      <h2>Videos en entrada/</h2>
      <div id="listaVideos"></div>
      <p class="hint" id="rutaEntrada"></p>
    </div>
  </div>

  <div class="col-der">
    <div class="panel">
      <h2>Clips elegidos</h2>
      <div id="clips"></div>
    </div>

    <div class="panel">
      <h2>Guion y arranque</h2>
      <div class="pie">
        <label class="hint">Guion&nbsp;
          <select id="guion"><option value="">— sin guion (improvisa) —</option></select>
        </label>
        <label class="hint">Nombre&nbsp;
          <input type="text" id="nombre" size="16" placeholder="(el del archivo)">
        </label>
        <span style="margin-left:auto" class="hint">Total&nbsp;</span>
        <span class="total" id="total">0.0s</span>
      </div>
      <div id="avisoGuion"></div>
      <div class="pie" style="margin-top:12px">
        <button id="btnPrevia">Ver cómo quedan unidas</button>
        <button id="btnGuardar">Guardar y salir</button>
        <button class="primario" id="btnEmpezar">Empezar</button>
        <span class="hint" id="estado"></span>
      </div>
      <div id="previaCaja" style="margin-top:14px">
        <video id="previaVideo" controls></video>
        <div class="hint" id="previaInfo"></div>
      </div>
    </div>

    <p class="hint">
      El recorte se aplica <b>antes</b> de transcribir, así que nada del resto del
      pipeline se entera: los sonidos, los insertos y el encuadre se calculan ya
      sobre el material recortado. El encuadre fino (acercamientos) no se toca acá —
      va en el panel de Encuadre del editor visual.
    </p>
  </div>
</main>

<script>
const $ = s => document.querySelector(s);
let DATOS = {videos: [], guiones: []};
let CLIPS = [];              // [{ruta, nombre, duracion, desde, hasta, listo, error}]
let ACTIVO = -1;             // índice del clip que responde a la barra espaciadora

const fmt = t => (t == null || isNaN(t)) ? "—" : t.toFixed(2) + "s";

// ---------------------------------------------------------------------------
// Arranque
// ---------------------------------------------------------------------------
async function cargar() {
  DATOS = await (await fetch("/datos")).json();
  $("#rutaEntrada").textContent = DATOS.dir_entrada;
  pintarVideos();

  const sel = $("#guion");
  for (const g of DATOS.guiones) {
    const o = document.createElement("option");
    o.value = g.n;
    o.textContent = `${g.n} — ${g.titulo}`;
    sel.appendChild(o);
  }
  sel.onchange = () => { pintarAvisoGuion(); };

  // Volver a abrir la pantalla sobre el mismo material devuelve los recortes
  // donde se dejaron. Es el motivo de que exista el .preparado.json.
  const prev = DATOS.preparado;
  if (prev && prev.clips) {
    let puestos = 0, perdidos = [];
    for (const c of prev.clips) {
      // Por ruta exacta primero y por nombre de archivo después. La ruta
      // guardada puede no coincidir carácter a carácter con la de la carpeta
      // (un enlace de directorio, una unidad mapeada, otra caja de letras) y
      // sin el respaldo la recuperación fallaba EN SILENCIO: el cartel decía
      // que la había recuperado y la lista salía vacía.
      const base = c.ruta.split(/[\\/]/).pop();
      const v = DATOS.videos.find(v => v.ruta === c.ruta)
             || DATOS.videos.find(v => v.nombre === base);
      if (v) { agregar(v, c.desde, c.hasta); puestos++; } else perdidos.push(base);
    }
    if (prev.guion != null) sel.value = prev.guion;
    if (prev.nombre) $("#nombre").value = prev.nombre;
    if (puestos) nota("Se recuperó la preparación guardada" +
                      (perdidos.length ? ` (falta ${perdidos.join(", ")})` : "."));
    else nota("Había una preparación guardada, pero sus archivos ya no están en entrada/.");
  }
  pintar();
}

function pintarVideos() {
  const cont = $("#listaVideos");
  cont.innerHTML = "";
  if (!DATOS.videos.length) {
    cont.innerHTML = '<p class="vacio">No hay ningún video en entrada/</p>';
    return;
  }
  for (const v of DATOS.videos) {
    const d = document.createElement("div");
    d.className = "vid" + (CLIPS.some(c => c.ruta === v.ruta) ? " puesto" : "");
    d.innerHTML = `<div><div class="n"></div><div class="m">${v.duracion.toFixed(1)}s · ${v.mb} MB</div></div>`;
    d.querySelector(".n").textContent = v.nombre;
    d.onclick = () => { agregar(v); pintar(); };
    cont.appendChild(d);
  }
}

// ---------------------------------------------------------------------------
// Clips elegidos
// ---------------------------------------------------------------------------
function agregar(v, desde, hasta) {
  if (CLIPS.some(c => c.ruta === v.ruta)) return;   // el mismo archivo dos veces no
  const c = {ruta: v.ruta, nombre: v.nombre, duracion: v.duracion,
             desde: desde != null ? desde : 0, hasta: hasta != null ? hasta : v.duracion,
             listo: false, propuesto: desde == null};
  CLIPS.push(c);
  if (ACTIVO < 0) ACTIVO = 0;
  prepararClip(c);
}

async function prepararClip(c) {
  await fetch("/clip", {method: "POST", headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({ruta: c.ruta})});
  // Sondeo y no espera bloqueante: el proxy tarda ~11s la primera vez por
  // archivo y hay que poder decir en pantalla que se está trabajando.
  const timer = setInterval(async () => {
    const r = await (await fetch("/clip?ruta=" + encodeURIComponent(c.ruta))).json();
    if (r.estado === "listo") {
      clearInterval(timer);
      c.listo = true;
      // La propuesta solo se aplica si José todavía no tocó nada: si venía de
      // un .preparado.json o ya arrastró una manija, manda lo suyo.
      if (c.propuesto && r.bordes) { c.desde = r.bordes.desde; c.hasta = r.bordes.hasta;
                                     c.detectado = r.bordes.detectado; }
      pintar();
    } else if (r.estado === "error") {
      clearInterval(timer);
      c.error = r.error; pintar();
    }
  }, 700);
}

function quitar(i) {
  CLIPS.splice(i, 1);
  ACTIVO = Math.min(ACTIVO, CLIPS.length - 1);
  pintar();
}

function mover(i, paso) {
  const j = i + paso;
  if (j < 0 || j >= CLIPS.length) return;
  [CLIPS[i], CLIPS[j]] = [CLIPS[j], CLIPS[i]];
  ACTIVO = j;
  pintar();
}

// ---------------------------------------------------------------------------
// Dibujado
// ---------------------------------------------------------------------------
function pintar() {
  const cont = $("#clips");
  const scroll = window.scrollY;
  cont.innerHTML = "";
  if (!CLIPS.length) {
    cont.innerHTML = '<p class="vacio">Elegí un video de la izquierda. Podés poner varios: se unen en este orden.</p>';
  }
  CLIPS.forEach((c, i) => cont.appendChild(tarjeta(c, i)));
  pintarVideos();
  pintarTotal();
  pintarAvisoGuion();
  window.scrollTo(0, scroll);
}

function tarjeta(c, i) {
  const div = document.createElement("div");
  div.className = "panel clip" + (i === ACTIVO ? " activo" : "");
  div.style.marginBottom = "10px";
  div.innerHTML = `
    <video preload="metadata" playsinline></video>
    <div class="cuerpo">
      <div class="cab">
        <span class="hint">${i + 1}.</span>
        <span class="titulo"></span>
        <button data-a="sube" title="Subir">↑</button>
        <button data-a="baja" title="Bajar">↓</button>
        <button data-a="quita" title="Quitar">✕</button>
      </div>
      <div class="barra">
        <div class="fuera izq"></div><div class="fuera der"></div>
        <div class="sel"></div>
        <div class="manija ma"></div><div class="manija mb"></div>
        <div class="aguja"></div>
        <div class="etq e0" style="left:4px">0.00s</div>
        <div class="etq e1" style="right:4px"></div>
      </div>
      <div class="fila">
        <button data-a="play">▶ Espacio</button>
        <button data-a="ini">Inicio aquí</button>
        <button data-a="fin">Fin aquí</button>
        <button data-a="proponer">Proponer solo</button>
        <button data-a="todo">Sin recorte</button>
        <span class="estado"></span>
      </div>
      <div class="fila">
        <span>Recorte: <b class="rec"></b></span>
        <span>· Queda <b class="dur"></b></span>
      </div>
    </div>`;

  div.querySelector(".titulo").textContent = c.nombre;
  div.querySelector(".e1").textContent = c.duracion.toFixed(2) + "s";
  div.querySelector(".rec").textContent = fmt(c.desde) + " → " + fmt(c.hasta);
  div.querySelector(".dur").textContent = fmt(c.hasta - c.desde);

  const est = div.querySelector(".estado");
  if (c.error) est.innerHTML = '<span style="color:var(--alerta)">Error: ' + c.error + "</span>";
  else if (!c.listo) est.textContent = "preparando la previsualización (solo la primera vez)…";
  else if (c.detectado) est.textContent = "puntos propuestos por el primer y el último sonido";

  const vid = div.querySelector("video");
  if (c.listo) vid.src = "/proxy?ruta=" + encodeURIComponent(c.ruta);
  vid.onclick = () => { ACTIVO = i; alternarPlay(); };
  vid.ontimeupdate = () => {
    const a = div.querySelector(".aguja");
    a.style.left = (vid.currentTime / c.duracion * 100) + "%";
    // Reproducir se detiene en el punto de corte: es lo que hay que juzgar.
    if (!vid.paused && vid.currentTime >= c.hasta) vid.pause();
  };
  c._video = vid;

  div.onmousedown = () => { if (ACTIVO !== i) { ACTIVO = i; marcarActivo(); } };
  div.querySelector('[data-a="sube"]').onclick = () => mover(i, -1);
  div.querySelector('[data-a="baja"]').onclick = () => mover(i, 1);
  div.querySelector('[data-a="quita"]').onclick = () => quitar(i);
  div.querySelector('[data-a="play"]').onclick = () => { ACTIVO = i; alternarPlay(); };
  div.querySelector('[data-a="ini"]').onclick = () => {
    c.desde = Math.min(vid.currentTime, c.hasta - 0.1); c.propuesto = false; pintar(); };
  div.querySelector('[data-a="fin"]').onclick = () => {
    c.hasta = Math.max(vid.currentTime, c.desde + 0.1); c.propuesto = false; pintar(); };
  div.querySelector('[data-a="todo"]').onclick = () => {
    c.desde = 0; c.hasta = c.duracion; c.propuesto = false; c.detectado = false; pintar(); };
  div.querySelector('[data-a="proponer"]').onclick = async () => {
    est.textContent = "buscando el primer y el último sonido…";
    const r = await (await fetch("/clip?ruta=" + encodeURIComponent(c.ruta))).json();
    if (r.bordes) { c.desde = r.bordes.desde; c.hasta = r.bordes.hasta;
                    c.detectado = r.bordes.detectado; c.propuesto = false; pintar(); }
  };

  montarBarra(div.querySelector(".barra"), c, vid);
  return div;
}

function montarBarra(barra, c, vid) {
  const pinta = () => {
    const a = c.desde / c.duracion * 100, b = c.hasta / c.duracion * 100;
    barra.querySelector(".izq").style.left = "0"; barra.querySelector(".izq").style.width = a + "%";
    barra.querySelector(".der").style.right = "0"; barra.querySelector(".der").style.width = (100 - b) + "%";
    const sel = barra.querySelector(".sel");
    sel.style.left = a + "%"; sel.style.width = (b - a) + "%";
    barra.querySelector(".ma").style.left = a + "%";
    barra.querySelector(".mb").style.left = b + "%";
  };
  pinta();

  const tiempoEn = ev => {
    const r = barra.getBoundingClientRect();
    return Math.max(0, Math.min(c.duracion, (ev.clientX - r.left) / r.width * c.duracion));
  };

  let arrastrando = null;
  const empezar = (cual) => (ev) => {
    ev.preventDefault(); ev.stopPropagation();
    arrastrando = cual;
    barra.setPointerCapture(ev.pointerId);
  };
  barra.querySelector(".ma").onpointerdown = empezar("a");
  barra.querySelector(".mb").onpointerdown = empezar("b");

  barra.onpointermove = ev => {
    if (!arrastrando) return;
    const t = tiempoEn(ev);
    if (arrastrando === "a") c.desde = Math.min(t, c.hasta - 0.1);
    else c.hasta = Math.max(t, c.desde + 0.1);
    c.propuesto = false;
    pinta();
    // Mientras se arrastra, el video sigue la manija: es la única forma de
    // saber en qué fotograma se está cortando sin adivinar.
    if (vid.readyState) vid.currentTime = arrastrando === "a" ? c.desde : c.hasta;
    barra.closest(".clip").querySelector(".rec").textContent = fmt(c.desde) + " → " + fmt(c.hasta);
    barra.closest(".clip").querySelector(".dur").textContent = fmt(c.hasta - c.desde);
    pintarTotal();
  };
  barra.onpointerup = ev => {
    if (!arrastrando) return;
    arrastrando = null;
    barra.releasePointerCapture(ev.pointerId);
    pintarAvisoGuion();
  };
  // Clic en la barra (fuera de las manijas) = saltar a ese segundo.
  barra.onclick = ev => {
    if (ev.target.classList.contains("manija")) return;
    if (vid.readyState) vid.currentTime = tiempoEn(ev);
  };
}

function marcarActivo() {
  document.querySelectorAll(".clip").forEach((el, i) =>
    el.classList.toggle("activo", i === ACTIVO));
}

function pintarTotal() {
  const t = CLIPS.reduce((s, c) => s + Math.max(0, c.hasta - c.desde), 0);
  const el = $("#total");
  el.textContent = t.toFixed(1) + "s";
  // El objetivo del pipeline son 30-40s, pero el corte de silencios de f2
  // todavía va a quitar lo suyo: por eso se avisa por debajo de 30, no por
  // encima de 40. Un material de 50s puede terminar perfecto.
  el.classList.toggle("malo", CLIPS.length > 0 && t < 30);
}

function pintarAvisoGuion() {
  const cont = $("#avisoGuion");
  cont.innerHTML = "";
  const n = $("#guion").value;
  if (!n || !CLIPS.length) return;
  const g = DATOS.guiones.find(g => String(g.n) === String(n));
  if (!g || !g.hooksegs) return;
  // `hooksegs` son los segundos de silencio ANTES de la primera palabra que
  // f2_cortar conserva a propósito: el hook físico (entrar al cuadro,
  // sentarse). Si este recorte se los lleva, no queda nada que conservar y el
  // gesto de apertura desaparece sin que nada dé error.
  const d = document.createElement("div");
  d.className = "aviso";
  d.innerHTML = `El guion ${g.n} pide <b>${g.hooksegs}s de hook físico</b>: f2_cortar conserva
    ese silencio antes de la primera palabra para no comerse el gesto de entrar al cuadro.
    Comprobá que al primer clip le quede ese aire por delante del recorte.
    <button style="margin-left:8px" id="btnAire">Dejar ${g.hooksegs}s de aire</button>`;
  cont.appendChild(d);
  $("#btnAire").onclick = () => {
    CLIPS[0].desde = Math.max(0, CLIPS[0].desde - g.hooksegs);
    CLIPS[0].propuesto = false;
    pintar();
  };
}

function nota(txt) { $("#estado").textContent = txt; }

// ---------------------------------------------------------------------------
// Reproducción con la barra espaciadora
// ---------------------------------------------------------------------------
function alternarPlay() {
  const c = CLIPS[ACTIVO];
  if (!c || !c._video) return;
  CLIPS.forEach((o, i) => { if (i !== ACTIVO && o._video) o._video.pause(); });
  const v = c._video;
  if (v.paused) {
    if (v.currentTime < c.desde || v.currentTime >= c.hasta) v.currentTime = c.desde;
    v.play();
  } else v.pause();
  marcarActivo();
}

document.addEventListener("keydown", ev => {
  if (ev.code !== "Space") return;
  if (["INPUT", "TEXTAREA", "SELECT"].includes(ev.target.tagName)) return;
  ev.preventDefault();
  alternarPlay();
});

// ---------------------------------------------------------------------------
// Previa, guardar, empezar
// ---------------------------------------------------------------------------
function cuerpoClips() {
  return CLIPS.map(c => ({ruta: c.ruta, desde: +c.desde.toFixed(3), hasta: +c.hasta.toFixed(3)}));
}

$("#btnPrevia").onclick = async () => {
  if (!CLIPS.length) return nota("Elegí al menos un clip.");
  const b = $("#btnPrevia");
  b.disabled = true; nota("armando la previa…");
  try {
    const r = await (await fetch("/previa", {method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({clips: cuerpoClips()})})).json();
    if (r.error) { nota("Error: " + r.error); return; }
    $("#previaCaja").style.display = "flex";
    $("#previaVideo").src = r.url;
    $("#previaInfo").innerHTML = `Así queda: <b>${r.duracion}s</b>.` +
      (r.empalmes && r.empalmes.length
        ? `<br>Cambio de plano en ${r.empalmes.map(e => e.toFixed(2) + "s").join(", ")}.`
        : "<br>Un solo plano, sin empalmes.") +
      "<br><span class='hint'>Está en baja resolución a propósito: es para juzgar el " +
      "montaje, no la calidad.</span>";
    nota("");
  } catch (e) { nota("Error: " + e); }
  finally { b.disabled = false; }
};

$("#btnGuardar").onclick = async () => {
  if (!CLIPS.length) return nota("Elegí al menos un clip.");
  const r = await (await fetch("/guardar", {method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({clips: cuerpoClips(), guion: $("#guion").value || null})})).json();
  nota(r.ok ? "Guardado. Podés cerrar la pestaña." : "Error: " + r.error);
};

$("#btnEmpezar").onclick = async () => {
  if (!CLIPS.length) return nota("Elegí al menos un clip.");
  if (!$("#guion").value &&
      !confirm("Sin guion el pipeline improvisa el hook, los sonidos y los insertos " +
               "desde la transcripción. ¿Seguir igual?")) return;
  $("#btnEmpezar").disabled = true;
  nota("arrancando…");
  await fetch("/empezar", {method: "POST", headers: {"Content-Type": "application/json"},
    body: JSON.stringify({clips: cuerpoClips(), guion: $("#guion").value || null,
                          nombre: $("#nombre").value})});
  document.body.innerHTML =
    '<div style="padding:60px;text-align:center;font-family:ui-sans-serif,system-ui">' +
    '<h1 style="color:#4fd1d9">Arrancando el pipeline</h1>' +
    '<p style="color:#9db3bc">El progreso sale en la ventana negra desde donde se abrió ' +
    'esta pantalla. Cuando termine se abre solo el editor visual.</p>' +
    '<p style="color:#9db3bc">Ya podés cerrar esta pestaña.</p></div>';
};

cargar();
</script>
</body>
</html>
"""


def main(puerto: int = 8790, abrir: bool = True) -> dict | None:
    """Levanta la pantalla y devuelve la orden elegida (o None si se cerró).

    Devolver la orden en vez de lanzar el pipeline desde aquí es lo que permite
    que todo ocurra en una sola terminal: `preparar.py` recibe esto y llama a
    editor.py con el control ya devuelto.
    """
    global _SERVIDOR, ORDEN
    ORDEN = None
    config.DIR_PREPARACION.mkdir(parents=True, exist_ok=True)

    servidor = None
    p = puerto
    while servidor is None:
        try:
            servidor = ThreadingHTTPServer(("127.0.0.1", p), Handler)
        except OSError:
            p += 1
            if p > puerto + 20:
                print(f"ERROR: no se encontró un puerto libre cerca de {puerto}",
                      file=sys.stderr)
                sys.exit(1)
    _SERVIDOR = servidor

    url = f"http://127.0.0.1:{p}/"
    print(f"Pantalla de preparación: {url}")
    print(f"Grabaciones en: {config.DIR_ENTRADA}")
    print("(se cierra sola al pulsar «Empezar», o con Ctrl+C)")
    if abrir:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nPreparación cancelada.")
    finally:
        servidor.server_close()
    return ORDEN


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Pantalla de preparación (Fase 0)")
    ap.add_argument("--puerto", type=int, default=8790)
    ap.add_argument("--sin-abrir", action="store_true")
    args = ap.parse_args()
    orden = main(args.puerto, not args.sin_abrir)
    print(json.dumps(orden, ensure_ascii=False, indent=2) if orden else "Sin orden.")
