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
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import f10_editor_visual as f10
import f15_silencios

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


def _guardar_broll(broll: list) -> Path:
    """B-rolls a pantalla completa. Van en su propio archivo porque el pipeline
    los recibe por `--broll-manual`, no por `--eventos-manual`: son dos listas
    distintas y mezclarlas convierte un clip a pantalla completa en una tarjeta
    PiP de esquina."""
    return _escritura_atomica(DIR_TRABAJO / "ajustes.broll.json", {"broll": broll})


def _guardar_sfx(sfx: list) -> Path:
    # --sfx-manual (f5_audio.py) espera una LISTA plana, no envuelta en dict.
    return _escritura_atomica(DIR_TRABAJO / "ajustes.sfx.json", sfx)


def _guardar_animaciones(animaciones: list) -> Path:
    return _escritura_atomica(DIR_TRABAJO / "ajustes.animaciones.json", {"animaciones": animaciones})


def _guardar_hook_cta(bloques: list) -> Path:
    """Tiempos del hook y del CTA movidos a mano en la línea de tiempo."""
    return _escritura_atomica(DIR_TRABAJO / "ajustes.hookcta.json", {"hook_cta": bloques})


def _guardar_hook(texto: str) -> Path:
    return _escritura_atomica(DIR_TRABAJO / "ajustes.hook.json", {"hook": texto})


def _guardar_subtitulos(datos: dict) -> Path:
    """Tamaño del subtítulo y correcciones de texto ajustados a mano (Bloque 5).

    `correcciones` es {indice_global_de_la_palabra: texto} — la MISMA clave
    que f3_subtitulos.generar_ass() usa para sustituir el texto sin tocar
    `palabras` (la transcripción real, la que usa f13_guion para alinear).
    """
    limpio = {}
    if datos.get("tamano_px"):
        limpio["tamano_px"] = int(datos["tamano_px"])
    correcciones = datos.get("correcciones") or {}
    if correcciones:
        limpio["correcciones"] = {str(k): str(v) for k, v in correcciones.items() if str(v).strip()}
    return _escritura_atomica(DIR_TRABAJO / "ajustes.subtitulos.json", limpio)


def _guardar_musica(datos: dict) -> Path:
    """Ajustes de música de fondo (pista, volumen, inicio_s, sin_musica) (Bloque 8)."""
    limpio = {}
    if "pista" in datos:
        limpio["pista"] = str(datos["pista"])
    if "volumen" in datos:
        limpio["volumen"] = float(datos["volumen"])
    if "inicio_s" in datos:
        limpio["inicio_s"] = float(datos["inicio_s"])
    if "sin_musica" in datos:
        limpio["sin_musica"] = bool(datos["sin_musica"])
    return _escritura_atomica(DIR_TRABAJO / "ajustes.musica.json", limpio)


def _guardar_silencios(datos: dict) -> Path:
    """Qué tramos recortados hay que devolver al video (Bloque B).

    Solo se guarda lo que se APARTA del corte automático: un tramo que no está
    en el archivo es un tramo que se corta como siempre. Así el archivo sigue
    siendo válido cuando el catálogo cambia (otro guion, otro `hooksegs`), en
    vez de fijar un estado para tramos que ya no existen.
    """
    limpio = {"cortes": {}}
    for cid, estado in (datos.get("cortes") or {}).items():
        if not isinstance(estado, dict):
            continue
        entrada = {}
        if estado.get("activo") is False:
            entrada["activo"] = False
        if estado.get("inicio") is not None:
            entrada["inicio"] = round(float(estado["inicio"]), 3)
        if estado.get("fin") is not None:
            entrada["fin"] = round(float(estado["fin"]), 3)
        if entrada:
            limpio["cortes"][str(cid)] = entrada
    return _escritura_atomica(DIR_TRABAJO / "ajustes.silencios.json", limpio)


def _datos_silencios_actuales() -> dict:
    """El catálogo de silencios de la corrida abierta.

    Existe como función de módulo, en vez de leerse `DIR_TRABAJO` desde el
    endpoint, porque `do_POST` declara `global DIR_TRABAJO` más abajo (en
    /cambiar-proyecto) y Python prohíbe usar el nombre antes de esa
    declaración: hacerlo es un SyntaxError que `ast.parse` no detecta y que
    solo aparece al importar el módulo.
    """
    return f15_silencios.datos_silencios(DIR_TRABAJO)


def _leer_corrida() -> dict:
    """Parámetros con los que se lanzó la corrida original (`00_corrida.json`,
    que escribe editor.py).

    Sin esto el re-render desde el editor llamaba a editor.py sin `--guion N`,
    y todo lo que el guion aportaba y no estuviera ya en 05_overlays.eventos.json
    —la hoja de sonido, las animaciones, la pista de música, el presentador— se
    perdía en silencio: 13 SFX curados volvían convertidos en 5 automáticos.
    """
    f = DIR_TRABAJO / "00_corrida.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Corridas anteriores a 00_corrida.json: el número de guion se puede
    # recuperar de la cabecera del reporte de alineación, que f13_guion ya
    # escribía ("# Reporte de Alineación de Guion 7: ...").
    alineado = DIR_TRABAJO / "10_guion-alineado.md"
    if alineado.exists():
        try:
            m = re.search(r"Guion\s+(\d+)",
                          alineado.read_text(encoding="utf-8", errors="replace")[:400])
            if m:
                return {"guion": int(m.group(1))}
        except Exception:
            pass
    return {}


def _guardar_encuadre(encuadre: dict) -> Path:
    """Punch-ins y planos cerrados ajustados a mano.

    Se escribe con la misma forma que `guion.encuadre.json`, que es lo que
    espera `f4_retencion --encuadre`: así el archivo que sale del editor y el
    que sale del guion son intercambiables y no hay dos formatos que mantener.
    """
    limpio = {
        "punch_ins": [{"t": round(float(p["t"]), 3), "razon": p.get("razon", "manual")}
                      for p in encuadre.get("punch_ins", [])],
        "planos_cerrados": [{"ini": round(float(c["ini"]), 3),
                             "fin": round(float(c["fin"]), 3),
                             "zoom": float(c.get("zoom", config.ZOOM_PLANO_CERRADO)),
                             "razon": c.get("razon", "manual")}
                            for c in encuadre.get("planos_cerrados", [])
                            if float(c["fin"]) > float(c["ini"])],
    }
    limpio["punch_ins"].sort(key=lambda p: p["t"])
    limpio["planos_cerrados"].sort(key=lambda c: c["ini"])
    return _escritura_atomica(DIR_TRABAJO / "ajustes.encuadre.json", limpio)


# Todo lo que compone "una edición": si mañana se añade otro ajuste, entra aquí
# y las versiones lo guardan sin tocar nada más.
ARCHIVOS_AJUSTES = (
    "ajustes.eventos.json", "ajustes.broll.json", "ajustes.sfx.json",
    "ajustes.animaciones.json", "ajustes.encuadre.json", "ajustes.hookcta.json",
    "ajustes.hook.json", "ajustes.sesion.json", "ajustes.subtitulos.json",
    "ajustes.musica.json", "ajustes.silencios.json",
)

# El PLAN sobre el que se hicieron esos ajustes. Va en la versión junto a ellos,
# porque el editor no enseña solo lo ajustado: lo monta ENCIMA de esto. El hook,
# el CTA y las animaciones que no se tocaron salen de aquí, igual que la curva
# de encuadre. Sin guardarlo, cargar una versión después de haber renderizado
# otra cosa devolvía un híbrido: tus ajustes sobre el plan nuevo.
ARCHIVOS_BASE = ("05_overlays.eventos.json", "03_retencion.plan.json")


def _huella_corte() -> dict:
    """Con qué corte se hizo esta edición.

    Si se vuelve a cortar el video (correr sin `--reaplicar`), la línea de
    tiempo entera cambia y una versión anterior deja de tener sentido: sus
    segundos apuntan a otro sitio. No se puede impedir, pero sí avisar.
    """
    f = DIR_TRABAJO / "02_cortado.json"
    if not f.exists():
        return {}
    try:
        palabras = json.loads(f.read_text(encoding="utf-8"))["palabras"]
    except Exception:
        return {}
    return {"palabras": len(palabras),
            "fin": round(float(palabras[-1]["fin"]), 2) if palabras else 0.0}


def _nombre_version(crudo: str) -> str | None:
    """Nombre de carpeta seguro a partir de lo que se escriba en la caja.

    Se filtra a propósito en vez de confiar: el nombre llega del navegador y
    acaba siendo una ruta en disco. Un `..` o una barra escribirían fuera de la
    carpeta de la corrida.
    """
    limpio = re.sub(r"[^\w\s.-]", "", (crudo or "").strip(), flags=re.UNICODE)
    limpio = re.sub(r"\s+", " ", limpio).strip(" .")
    return limpio[:60] or None


def _dir_versiones() -> Path:
    return DIR_TRABAJO / "_versiones"


def _listar_versiones() -> list:
    raiz = _dir_versiones()
    if not raiz.is_dir():
        return []
    versiones = []
    for d in sorted(raiz.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        def cuenta(archivo, clave):
            f = d / archivo
            if not f.exists():
                return None
            try:
                datos = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                return None
            lista = datos.get(clave, datos) if isinstance(datos, dict) else datos
            return len(lista) if isinstance(lista, list) else None

        versiones.append({
            "nombre": d.name,
            "fecha": datetime.fromtimestamp(d.stat().st_mtime).strftime("%d/%m %H:%M"),
            "insertos": cuenta("ajustes.eventos.json", "eventos"),
            "broll": cuenta("ajustes.broll.json", "broll"),
            "sfx": cuenta("ajustes.sfx.json", "sfx"),
            "animaciones": cuenta("ajustes.animaciones.json", "animaciones"),
        })
    return versiones


def _catalogo() -> list:
    global _CATALOGO_CACHE
    if _CATALOGO_CACHE is None:
        ruta = config.DIR_CONTEXTO / "catalogo-assets.json"
        _CATALOGO_CACHE = json.loads(ruta.read_text(encoding="utf-8"))["assets"]
    return _CATALOGO_CACHE


def _asset_por_id(asset_id: str) -> dict | None:
    encontrado = next((a for a in _catalogo() if a["id"] == asset_id), None)
    if encontrado is not None:
        return encontrado
    # Los clips de Flow no viven en catalogo-assets.json (los deja José a mano
    # en assets/generado/video/manual), pero la rejilla los ofrece igual y
    # necesita poder pedirles la miniatura.
    return next((c for c in f10.clips_manuales() if c["id"] == asset_id), None)


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
        "es_preview": bool(ESTADO_RENDER.get("es_preview")),
        "ok": (not activo) and proceso.returncode == 0,
        "error": (not activo) and proceso.returncode != 0,
        "progreso": {"actual": int(ultimo[0]), "total": int(ultimo[1])} if ultimo else None,
        "cola_log": texto[-2000:],
    }


def _listar_proyectos() -> list:
    raiz = config.DIR_SALIDA
    proyectos = []
    if raiz.exists():
        for d in sorted(raiz.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if d.is_dir() and not d.name.startswith("_") and (d / "02_cortado.json").exists():
                proyectos.append(d.name)
    return proyectos


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
            elif ruta == "/proyectos":
                self._json({
                    "actual": DIR_TRABAJO.name if DIR_TRABAJO else "",
                    "proyectos": _listar_proyectos()
                })
            elif ruta == "/datos":
                self._json(f10.recolectar(DIR_TRABAJO))
            elif ruta == "/silencios.js":
                # El JS del editor de silencios vive en su propio archivo en vez
                # de dentro de PAGINA: este módulo ya son 3500 líneas de Python
                # con HTML y JavaScript entretejidos, y hay otra sesión tocándolo
                # en paralelo. Un conflicto de merge dentro del texto de un
                # <script> produce Python válido con JS roto, y los tests, que
                # son de Python, pasan igual en verde.
                self._archivo(Path(__file__).parent / "web" / "silencios.js",
                              "application/javascript; charset=utf-8")
            elif ruta == "/video":
                # Tras una previsualización hay que mirar el 07_PREVIEW, no el
                # 07_FINAL, o el editor enseñaría el render anterior y parecería
                # que los cambios no se aplicaron.
                candidatos = ["07_FINAL.mp4", "06_video.mp4", "02_cortado.mp4"]
                if (qs.get("fuente") or [""])[0] == "preview":
                    candidatos = ["07_PREVIEW.mp4", "06_preview.mp4"] + candidatos
                v_target = next((DIR_TRABAJO / n for n in candidatos
                                 if (DIR_TRABAJO / n).exists()),
                                DIR_TRABAJO / "02_cortado.mp4")
                proxy = f10.generar_proxy(v_target, DIR_TRABAJO)
                self._archivo(proxy, "video/mp4")
            elif ruta in ("/tira.js", "/tira.css"):
                # Tira de capas apiladas (PLAN-TIRA.md). Su JS y su CSS viven en
                # editor/web/ y no dentro de PAGINA a propósito: un conflicto de
                # merge dentro del texto del JavaScript daría Python válido con
                # JS roto, y los tests son de Python.
                estatico = Path(__file__).resolve().parent / "web" / ruta.lstrip("/")
                self._archivo(estatico,
                              "application/javascript; charset=utf-8" if ruta.endswith(".js")
                              else "text/css; charset=utf-8")
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
            elif ruta == "/versiones":
                self._json({"versiones": _listar_versiones()})
            elif ruta == "/render/estado":
                self._json(_estado_render())
            elif ruta == "/animaciones-disponibles":
                self._json({"inventario": f10.inventario_animaciones()})
            elif ruta == "/anim-preview":
                # Un WebM corto de la animación, para verla moverse en la
                # tarjeta. Por ruta si ya está en el video, o por plantilla
                # (reusando cualquier MOV del caché de Hyperframes) para las
                # del inventario, que todavía no se han renderizado nunca.
                origen = None
                if qs.get("ruta"):
                    cand = Path(qs["ruta"][0])
                    if not _archivo_permitido(cand):
                        self.send_error(403, "ruta fuera de las carpetas permitidas")
                        return
                    origen = cand
                elif qs.get("plantilla") or qs.get("nombre"):
                    plantilla = (qs.get("plantilla") or [None])[0]
                    if plantilla is None:
                        # El editor conoce el nombre corto ("sol"); la plantilla
                        # ("anim-sol") la resuelve el vocabulario de f8.
                        import f8_hyperframes
                        plantilla = f8_hyperframes.plantilla_de(qs["nombre"][0])
                    origen = f10.mov_de_plantilla(plantilla)
                if origen is None or not origen.exists():
                    self.send_error(404, "sin animación que previsualizar")
                    return
                prev = f10.preview_animacion(origen)
                if prev is None:
                    self.send_error(404, "no se pudo generar el preview")
                    return
                self._archivo(prev, "video/webm")
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

        if partes.path == "/guardar-silencios":
            _guardar_silencios(datos)
            # Se devuelve el catálogo recalculado, no un simple ok: al desactivar
            # un tramo cambian los segundos que el video va a durar y cuántos
            # quedan restaurados, y el editor tiene que enseñar ESO y no lo que
            # el navegador supone que pasó.
            self._json({"ok": True, "silencios": _datos_silencios_actuales()})

        elif partes.path == "/cambiar-proyecto":
            nombre = datos.get("nombre")
            if not nombre:
                self.send_error(400, "falta 'nombre'")
                return
            cand = config.DIR_SALIDA / nombre
            if not cand.exists() or not cand.is_dir():
                self.send_error(404, f"No existe el proyecto {nombre}")
                return
            # Un render en curso escribe en la carpeta que tiene abierta. Si se
            # cambia de proyecto por debajo, la barra de progreso pasa a mostrar
            # el log del otro video y el 409 de "ya hay un render en curso"
            # bloquea el nuevo sin explicar por qué.
            proceso = ESTADO_RENDER.get("proceso")
            if proceso is not None and proceso.poll() is None:
                self._json({"ok": False,
                            "error": "hay un render en curso; esperá a que termine "
                                     "para cambiar de video"}, code=409)
                return
            global DIR_TRABAJO
            DIR_TRABAJO = cand
            ESTADO_RENDER["proceso"] = None
            ESTADO_RENDER["log"] = None
            self._json({"ok": True, "nombre": DIR_TRABAJO.name})
            return

        if partes.path == "/guardar":
            eventos = datos.get("eventos", [])
            destino = _guardar_eventos(eventos)
            resultado = {"ok": True, "ruta": str(destino), "n": len(eventos)}
            if "broll" in datos:
                destino_broll = _guardar_broll(datos["broll"])
                resultado["ruta_broll"] = str(destino_broll)
                resultado["n_broll"] = len(datos["broll"])
            if "hook" in datos:
                # Antes se ignoraba: escribías el hook, dabas a Guardar,
                # recargabas y volvía el anterior.
                _guardar_hook(datos["hook"])
                resultado["hook"] = datos["hook"]
            if "sfx" in datos:
                destino_sfx = _guardar_sfx(datos["sfx"])
                resultado["ruta_sfx"] = str(destino_sfx)
                resultado["n_sfx"] = len(datos["sfx"])
            if "hook_cta" in datos:
                resultado["ruta_hook_cta"] = str(_guardar_hook_cta(datos["hook_cta"]))
            if "sesion" in datos:
                # Dónde se dejó el reproductor, para volver al mismo segundo.
                _escritura_atomica(DIR_TRABAJO / "ajustes.sesion.json", datos["sesion"])
            if "animaciones" in datos:
                destino_anim = _guardar_animaciones(datos["animaciones"])
                resultado["ruta_animaciones"] = str(destino_anim)
                resultado["n_animaciones"] = len(datos["animaciones"])
            if "encuadre" in datos:
                destino_enc = _guardar_encuadre(datos["encuadre"])
                resultado["ruta_encuadre"] = str(destino_enc)
            if "subtitulos" in datos:
                resultado["ruta_subtitulos"] = str(_guardar_subtitulos(datos["subtitulos"]))
            if "musica" in datos:
                resultado["ruta_musica"] = str(_guardar_musica(datos["musica"]))
            self._json(resultado)

        elif partes.path == "/guardar-portada":
            segundo = float(datos.get("segundo", 0.0))
            resultado = f10.guardar_portada(DIR_TRABAJO, segundo)
            self._json(resultado)

        elif partes.path == "/version/guardar":
            nombre = _nombre_version(datos.get("nombre"))
            if not nombre:
                self.send_error(400, "hace falta un nombre para la versión")
                return
            destino = _dir_versiones() / nombre
            destino.mkdir(parents=True, exist_ok=True)
            # Se limpia primero: si la versión anterior con ese nombre tenía un
            # ajuste que ahora no existe, quedarse con él mezclaría dos ediciones.
            for viejo in destino.glob("*.json"):
                viejo.unlink()
            copiados = []
            for nombre_archivo in ARCHIVOS_AJUSTES + ARCHIVOS_BASE:
                origen = DIR_TRABAJO / nombre_archivo
                if origen.exists():
                    shutil.copy2(origen, destino / nombre_archivo)
                    copiados.append(nombre_archivo)
            _escritura_atomica(destino / "version.json", {"corte": _huella_corte()})
            self._json({"ok": True, "nombre": nombre, "archivos": len(copiados),
                        "versiones": _listar_versiones()})

        elif partes.path == "/version/cargar":
            nombre = _nombre_version(datos.get("nombre"))
            origen_dir = _dir_versiones() / nombre if nombre else None
            if not nombre or not origen_dir.is_dir():
                self.send_error(404, f"no existe la versión {datos.get('nombre')!r}")
                return
            # Se borran los ajustes actuales antes de copiar: si la versión que
            # se carga no tenía B-rolls y la de ahora sí, dejarlos sería mezclar
            # dos ediciones distintas y el resultado no sería ninguna de las dos.
            for actual in ARCHIVOS_AJUSTES:
                (DIR_TRABAJO / actual).unlink(missing_ok=True)
            restaurados = []
            for nombre_archivo in ARCHIVOS_AJUSTES + ARCHIVOS_BASE:
                archivo = origen_dir / nombre_archivo
                if archivo.exists():
                    shutil.copy2(archivo, DIR_TRABAJO / nombre_archivo)
                    restaurados.append(nombre_archivo)

            # Si se volvió a cortar el video desde que se guardó esta versión,
            # sus segundos apuntan a otro sitio. No se puede arreglar, pero
            # callarlo sería peor: se avisa y que decida quien edita.
            aviso = None
            meta = origen_dir / "version.json"
            if meta.exists():
                try:
                    guardada = json.loads(meta.read_text(encoding="utf-8")).get("corte", {})
                except Exception:
                    guardada = {}
                ahora = _huella_corte()
                if guardada and ahora and guardada != ahora:
                    aviso = ("Esta versión se guardó con otro corte del video "
                             f"({guardada.get('palabras')} palabras, {guardada.get('fin')}s) "
                             f"y ahora el corte tiene {ahora.get('palabras')} palabras y "
                             f"{ahora.get('fin')}s. Los tiempos pueden no cuadrar.")
            self._json({"ok": True, "nombre": nombre,
                        "archivos": len(restaurados), "aviso": aviso})

        elif partes.path == "/version/borrar":
            nombre = _nombre_version(datos.get("nombre"))
            destino = _dir_versiones() / nombre if nombre else None
            if not nombre or not destino.is_dir():
                self.send_error(404, "no existe esa versión")
                return
            shutil.rmtree(destino)
            self._json({"ok": True, "versiones": _listar_versiones()})

        elif partes.path == "/restablecer":
            # Volver al automático para los insertos. Sin esto, un
            # `ajustes.eventos.json` con la lista vacía era una trampa sin
            # salida: cada render arrancaba sin insertos y la única forma de
            # deshacerlo era borrar el archivo a mano desde el explorador.
            borrados = []
            for nombre in ("ajustes.eventos.json", "ajustes.broll.json"):
                f = DIR_TRABAJO / nombre
                if f.exists():
                    f.unlink()
                    borrados.append(nombre)
            self._json({"ok": True, "borrados": borrados})

        elif partes.path == "/encuadre/vista-previa":
            # La curva se recalcula en Python con la MISMA funcion del render.
            # Reimplementarla en JavaScript para la vista previa seria la forma
            # mas directa de que el editor y el video terminen enseñando cosas
            # distintas, que es justo lo que este editor existe para evitar.
            duracion = float(datos.get("duracion") or 0) or f10._duracion(
                DIR_TRABAJO / "06_video.mp4" if (DIR_TRABAJO / "06_video.mp4").exists()
                else DIR_TRABAJO / "02_cortado.mp4")
            muestras = f10.muestras_encuadre(DIR_TRABAJO, duracion, datos.get("encuadre"))
            self._json({"ok": True, "encuadre": muestras})

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

            ajustes_broll = None
            if "broll" in datos:
                ajustes_broll = _guardar_broll(datos["broll"])
            else:
                candidato_broll = DIR_TRABAJO / "ajustes.broll.json"
                if candidato_broll.exists():
                    ajustes_broll = candidato_broll

            ajustes_hc = None
            if "hook_cta" in datos:
                ajustes_hc = _guardar_hook_cta(datos["hook_cta"])
            else:
                cand_hc = DIR_TRABAJO / "ajustes.hookcta.json"
                if cand_hc.exists():
                    ajustes_hc = cand_hc

            ajustes_sfx = None
            if "sfx" in datos:
                ajustes_sfx = _guardar_sfx(datos["sfx"])
            else:
                candidato_sfx = DIR_TRABAJO / "ajustes.sfx.json"
                if candidato_sfx.exists():
                    ajustes_sfx = candidato_sfx

            ajustes_anim = None
            if "animaciones" in datos:
                ajustes_anim = _guardar_animaciones(datos["animaciones"])
            else:
                candidato_anim = DIR_TRABAJO / "ajustes.animaciones.json"
                if candidato_anim.exists():
                    ajustes_anim = candidato_anim

            ajustes_enc = None
            if "encuadre" in datos:
                ajustes_enc = _guardar_encuadre(datos["encuadre"])
            else:
                candidato_enc = DIR_TRABAJO / "ajustes.encuadre.json"
                if candidato_enc.exists():
                    ajustes_enc = candidato_enc

            if "subtitulos" in datos:
                _guardar_subtitulos(datos["subtitulos"])
            ajustes_sub_tamano, ajustes_sub_correcciones = None, None
            candidato_sub = DIR_TRABAJO / "ajustes.subtitulos.json"
            if candidato_sub.exists():
                try:
                    datos_sub = json.loads(candidato_sub.read_text(encoding="utf-8"))
                except Exception:
                    datos_sub = {}
                ajustes_sub_tamano = datos_sub.get("tamano_px")
                if datos_sub.get("correcciones"):
                    ajustes_sub_correcciones = candidato_sub

            # editor.py solo necesita que "entrada" exista — en --reaplicar no
            # se lee: la transcripción/corte/análisis ya están en dir_trabajo.
            dummy_entrada = DIR_TRABAJO / "02_cortado.mp4"
            py_bin = sys.executable
            if Path(r"C:\ai-video\venv312\Scripts\python.exe").exists():
                py_bin = r"C:\ai-video\venv312\Scripts\python.exe"
            # --sin-abrir-editor es imprescindible aquí: el editor se abre solo
            # al terminar una corrida, y sin esto el render lanzado DESDE el
            # editor levantaría un segundo servidor que nunca termina — el
            # proceso se quedaría vivo para siempre y la barra de progreso no
            # llegaría jamás al final.
            cmd = [py_bin, "editor.py", str(dummy_entrada),
                   "--nombre", DIR_TRABAJO.name, "--reaplicar",
                   "--sin-editor-visual", "--sin-abrir-editor"]

            # Los parámetros de la corrida original van PRIMERO y los ajustes
            # del editor después: editor.py solo deja que el guion rellene lo
            # que no vino a mano (`if not args.sfx_manual: ...`), así que lo
            # tocado en el editor sigue mandando y lo que no se tocó vuelve a
            # salir del guion en vez de re-derivarse del automático.
            corrida = _leer_corrida()
            if corrida.get("guion") is not None:
                cmd += ["--guion", str(corrida["guion"])]
            if corrida.get("presentador"):
                cmd += ["--presentador", corrida["presentador"]]
            f_mus = DIR_TRABAJO / "ajustes.musica.json"
            if f_mus.exists():
                try:
                    mus_aj = json.loads(f_mus.read_text(encoding="utf-8"))
                    if mus_aj.get("sin_musica"):
                        cmd.append("--sin-musica")
                    else:
                        if mus_aj.get("pista"):
                            cmd += ["--musica", str(mus_aj["pista"])]
                        if "volumen" in mus_aj:
                            cmd += ["--musica-volumen", str(mus_aj["volumen"])]
                        if "inicio_s" in mus_aj:
                            cmd += ["--musica-inicio", str(mus_aj["inicio_s"])]
                except Exception:
                    pass
            else:
                if corrida.get("musica"):
                    cmd += ["--musica", corrida["musica"]]
                if corrida.get("sin_musica"):
                    cmd.append("--sin-musica")
            if corrida.get("sol_pip_video"):
                cmd.append("--sol-pip-video")

            if ajustes is not None:
                cmd += ["--eventos-manual", str(ajustes)]
            if ajustes_broll is not None:
                cmd += ["--broll-manual", str(ajustes_broll)]
            if ajustes_hc is not None:
                cmd += ["--hook-cta-manual", str(ajustes_hc)]
            if ajustes_sfx is not None:
                cmd += ["--sfx-manual", str(ajustes_sfx)]
            if ajustes_anim is not None:
                cmd += ["--animaciones-manual", str(ajustes_anim)]
            if ajustes_enc is not None:
                cmd += ["--encuadre-manual", str(ajustes_enc)]
            if ajustes_sub_tamano:
                cmd += ["--sub-tamano", str(ajustes_sub_tamano)]
            if ajustes_sub_correcciones is not None:
                cmd += ["--sub-correcciones", str(ajustes_sub_correcciones)]

            # Silencios restaurados (Bloque B). Es la única bandera que hace que
            # --reaplicar vuelva a cortar, así que solo se pasa si de verdad hay
            # algo apartado del corte automático: sin este `if`, cada render
            # normal recortaría la grabación entera otra vez para nada.
            if "silencios" in datos:
                _guardar_silencios(datos["silencios"])
            f_sil = DIR_TRABAJO / "ajustes.silencios.json"
            if f_sil.exists() and f15_silencios.hay_cambios(DIR_TRABAJO):
                cmd += ["--silencios", str(f_sil)]

            hook = datos.get("hook")
            if hook is None:
                f_hook = DIR_TRABAJO / "ajustes.hook.json"
                if f_hook.exists():
                    try:
                        hook = json.loads(f_hook.read_text(encoding="utf-8")).get("hook")
                    except Exception:
                        hook = None
            elif hook:
                _guardar_hook(hook)
            if hook:
                cmd += ["--hook", hook]

            # Previsualización: media resolución, sin publicar y a sus propios
            # archivos, para comprobar un ajuste sin gastar el render bueno ni
            # pisar el que ya estaba listo para subir.
            es_preview = bool(datos.get("preview"))
            if es_preview:
                cmd.append("--preview")
            ESTADO_RENDER["es_preview"] = es_preview

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
/* Ancho completo, no 1200px: con el video ocupando una columna fija a la
   derecha, encajonar el resto dejaba la rejilla del catalogo y las lineas de
   tiempo demasiado apretadas. */
main { display: flex; align-items: flex-start; gap: 20px; padding: 20px;
       max-width: 100%; margin: 0 auto; }
@media (max-width: 1000px) {
  /* En pantalla estrecha no hay sitio para dos columnas: el video vuelve
     arriba, pero se queda pegado al borde superior al hacer scroll. */
  main { flex-direction: column; }
  .lienzo-wrap { order: 0; flex: none; align-self: stretch; top: 0;
                 background: var(--bg); padding-bottom: 8px; z-index: 5; }
  .columna-izq { align-self: stretch; }
}

/* El video se queda quieto a la derecha mientras se recorre el editor: los
   paneles son largos y, con el video arriba del todo, ajustar un B-roll o una
   animacion se hacia a ciegas — habia que subir a mirar y volver a bajar. */
.lienzo-wrap { display: flex; flex-direction: column; gap: 10px; align-items: center;
               order: 2; flex: 0 0 340px; position: sticky; top: 14px;
               max-height: calc(100vh - 28px); }
.columna-izq { order: 1; flex: 1 1 auto; min-width: 0;
               display: flex; flex-direction: column; gap: 20px; }
/* max-height ademas del ancho: el video es 9:16, y a 340px de ancho mide 604
   de alto. Sin el tope, en una pantalla baja la mitad inferior quedaba fuera
   justo despues de fijarlo. */
.lienzo { position: relative; width: 100%; max-width: 340px; aspect-ratio: 1080 / 1920;
          max-height: calc(100vh - 150px); margin: 0 auto;
          background: #000; overflow: hidden; border-radius: 10px; border: 1px solid var(--linea); }
.lienzo video { position: absolute; top: 0; left: 0; transform-origin: 0 0; }
.lienzo .overlay-img { position: absolute; top: 0; left: 0; transform-origin: 0 0;
                        cursor: grab; image-rendering: -webkit-optimize-contrast; }
.lienzo .overlay-img:active { cursor: grabbing; }
/* Zona segura de TikTok/Reels: franjas semitransparentes donde la app tapa el
   video con su propia interfaz. display:none por defecto — se prende con el
   botón y el estado se recuerda en localStorage. pointer-events:none para no
   robarle el arrastre a los PiP que queden debajo. */
.zona-segura { position: absolute; inset: 0; pointer-events: none; display: none; z-index: 8; }
.zona-segura.visible { display: block; }
.zona-segura .franja { position: absolute; background: repeating-linear-gradient(
    135deg, rgba(244,63,94,.28) 0 10px, rgba(244,63,94,.14) 10px 20px); }
.zona-segura .franja-inferior { left: 0; right: 0; bottom: 0; }
.zona-segura .franja-derecha { right: 0; bottom: 0; } /* el "top" lo fija pintarZonaSegura() */
/* Vista previa aproximada del subtítulo (BLOQUE 5). left/right/top/font-size
   se fijan en JS a partir de DATA.sub_posicion_altura_pct y del tamaño
   elegido — acá solo el look. transform centra el bloque verticalmente sobre
   la línea de posición, que es donde el ASS ancla el subtítulo real. */
.sub-preview { position: absolute; left: 6%; right: 6%; text-align: center;
               color: #fff; font-weight: 700; line-height: 1.25;
               text-shadow: 0 0 6px #000, 0 2px 3px #000, 0 -1px 3px #000;
               pointer-events: none; z-index: 7; display: none;
               transform: translateY(-50%); }
.sub-preview .activa { color: #4FD1D9; }
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
#infoDensidadSfx.sfx-denso { color: #ef4444; font-weight: 600; }

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
/* Los clips de Flow van primeros y se marcan en violeta, el mismo color con el
   que ya salen los B-Roll en la linea de tiempo. */
.grid-catalogo .item.clip { border-color: #8b5cf6; }
.grid-catalogo .item.clip:hover { border-color: #c4b5fd; }
.grid-catalogo .item .clip-badge { position: absolute; bottom: 2px; left: 2px;
                                    background: rgba(139,92,246,.9); color: #fff; font-size: 9px;
                                    padding: 1px 4px; border-radius: 3px; }
.editor-caja { border: 1px dashed var(--linea); border-radius: 8px; padding: 10px; margin-top: 10px;
               display: none; }
.editor-caja.activa { display: block; }

.pista-enc { position: relative; height: 46px; border: 1px solid var(--linea); border-radius: 8px;
             background: var(--bg); overflow: hidden; cursor: crosshair; }
.franjas-enc { position: absolute; inset: 0; }
.enc-cerrado { position: absolute; top: 6px; height: 34px; border-radius: 5px; cursor: grab;
               background: rgba(79,209,217,.22); border: 1px solid var(--acento);
               display: flex; align-items: center; justify-content: center;
               font-size: 11px; color: var(--fg); overflow: hidden; white-space: nowrap; }
.enc-cerrado.sel { background: rgba(79,209,217,.4); box-shadow: 0 0 0 2px var(--acento); }
.enc-tirador { position: absolute; top: 0; width: 8px; height: 100%; cursor: ew-resize; }
.enc-tirador.izq { left: 0; } .enc-tirador.der { right: 0; }
.enc-punch { position: absolute; top: 4px; width: 3px; height: 38px; margin-left: -1px;
             background: var(--sol, #ffc93c); border-radius: 2px; cursor: grab; }
.enc-punch.sel { box-shadow: 0 0 0 3px rgba(255,201,60,.45); }
.curva-zoom { width: 100%; height: 90px; margin-top: 6px; display: block;
              background: var(--bg); border: 1px solid var(--linea); border-radius: 8px; }
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

.hook-caja { display: flex; flex-direction: column; gap: 8px; }
.hook-caja textarea { font: inherit; background: var(--bg); color: var(--fg); border: 1px solid var(--linea);
                       border-radius: 6px; padding: 8px; resize: vertical; min-height: 44px; }
.hook-preview { display: flex; gap: 12px; align-items: flex-start; flex-wrap: wrap; }
.hook-preview img { width: 90px; border-radius: 6px; background: #000; }
.anim-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px; }
.anim-card { border: 1px solid var(--linea); border-radius: 8px; padding: 8px; display: flex;
             flex-direction: column; gap: 6px; }
.anim-card img { width: 100%; aspect-ratio: 16/9; object-fit: cover; border-radius: 4px; background: #000; }
/* El preview es vertical como el video, no apaisado: 16/9 recortaba justo la
   animación, que es lo unico que hay que ver en la tarjeta. */
.anim-preview { width: 100%; aspect-ratio: 4/5; object-fit: contain; border-radius: 4px;
                background: #16232b; display: block; }
.anim-sin-preview { width: 100%; aspect-ratio: 4/5; border-radius: 4px; background: #16232b;
                    display: flex; align-items: center; justify-content: center; text-align: center;
                    font-size: 12px; color: var(--fg-2); padding: 6px; }
.anim-card .info { font-size: 12px; color: var(--fg-2); }
.anim-card .info b { color: var(--fg); }
.anim-card .fila-botones { display: flex; gap: 6px; }
.inventario-item { border: 1px solid var(--linea); border-radius: 8px; padding: 8px; cursor: pointer;
                    display: flex; flex-direction: column; gap: 4px; }
.inventario-item:hover { border-color: var(--acento); }
.inventario-item .nombre { font-weight: 600; }
.inventario-item .detalle { font-size: 11px; color: var(--fg-2); display: block; }
.fila-variantes { display: flex; gap: 4px; flex-wrap: wrap; margin-top: 4px; }
.fila-variantes button { background: var(--panel); color: var(--fg); border: 1px solid var(--linea);
                          border-radius: 5px; padding: 2px 8px; font-size: 11px; cursor: pointer; }
.fila-variantes button:hover { border-color: var(--acento); color: var(--acento); }
.versiones-caja { border: 1px dashed var(--linea); border-radius: 8px; padding: 10px;
                  margin: 10px 0; display: flex; flex-direction: column; gap: 6px; }
.version-fila { display: flex; align-items: center; gap: 10px; padding: 6px 8px;
                border: 1px solid var(--linea); border-radius: 6px; font-size: 13px; }
.version-fila > div:first-child { flex: 1; min-width: 0; }
.version-fila .detalle { font-size: 11px; color: var(--fg-2); }
.version-fila button { background: var(--panel); color: var(--fg); border: 1px solid var(--linea);
                       border-radius: 6px; padding: 4px 10px; cursor: pointer; font-size: 12px; }
.version-fila button:hover { border-color: var(--acento); color: var(--acento); }
.version-fila button.quitar:hover { border-color: #f87171; color: #f87171; }
</style>
<link rel="stylesheet" href="/tira.css">
</head>
<body>
<header style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">
  <div>
    <h1 style="margin:0;">Editor visual v2 <span id="nombre"></span></h1>
    <span class="sub" id="resumen"></span>
  </div>
  <div style="display:flex; gap:8px; align-items:center; background:var(--panel); padding:6px 12px; border-radius:8px; border:1px solid var(--linea);">
    <label for="selProyecto" class="hint" style="font-weight:600; color:var(--fg);">🎬 Seleccionar Video:</label>
    <select id="selProyecto" style="font:inherit; background:var(--bg); color:var(--fg); border:1px solid var(--linea); border-radius:6px; padding:5px 8px; min-width:180px;"></select>
    <button id="btnCargarProyecto" class="btn-primario" type="button" style="margin-bottom:0;">📁 Cargar</button>
  </div>
</header>
<main>
  <div class="lienzo-wrap">
    <div class="lienzo" id="lienzo">
      <video id="video" playsinline preload="auto"></video>
      <div class="zona-segura" id="zonaSegura">
        <div class="franja franja-inferior" id="zonaSeguraInferior" title="Franja inferior que TikTok/Reels tapa con su interfaz"></div>
        <div class="franja franja-derecha" id="zonaSeguraDerecha" title="Franja derecha que TikTok/Reels tapa con sus botones"></div>
      </div>
      <div id="subPreview" class="sub-preview"></div>
    </div>
    <div class="controles">
      <button id="btnPlay" type="button">▶ Reproducir</button>
      <button id="btnSound" type="button">🔊 Desactivar Sonido</button>
      <input type="range" id="volumenVideo" min="0" max="1" step="0.05" value="1" title="Volumen del video">
      <span class="t" id="tActual">0.00s</span>
      <span class="t">/ <span id="tTotal">0.00s</span></span>
    </div>
    <div class="controles">
      <button id="btnZonaSegura" type="button">🛡 Ver zona segura de TikTok</button>
      <button id="btnGuardarPortada" type="button">📸 Guardar portada (1080x1920)</button>
    </div>
    <p class="hint">El encuadre (zoom + paneo) se calcula con la misma función que usa el
      render final. Puedes preescuchar todo el audio (voz + música + SFX) directamente en la vista previa.</p>
    <p class="hint">La zona segura marca dónde TikTok/Reels tapan el video con su propia
      interfaz (aproximado — calibrar contra una captura real). Un overlay que caiga ahí
      avisa en su panel.</p>
  </div>

  <div class="columna-izq">
  <div class="panel">
    <h2>Línea de tiempo multipista (Estilo CapCut)</h2>
    <p class="hint">Haz clic o arrastra sobre cualquier pista para mover la aguja o ajustar el tiempo de B-rolls, PiPs, animaciones y sonidos.</p>
    <div class="pista" id="pista">
      <div class="franjas" id="franjas"></div>
      <div class="palabras" id="palabras"></div>
    </div>
    <div id="tiraCapas"></div>
  </div>

  <div class="panel">
    <h2>Efectos de sonido</h2>
    <p class="hint">Arrastrá los marcadores para moverlos en el tiempo. El sonido de un PiP se
      mueve solo cuando movés el inserto (Fase 4: "el sonido acompaña al evento visual").</p>
    <div class="barra-sfx" style="display:flex; gap:8px; align-items:center; margin-bottom:8px; flex-wrap:wrap;">
      <select id="selSonido"></select>
      <button class="btn-primario" id="btnEscuchar" type="button">▶ Escuchar</button>
      <button class="btn-primario" id="btnAgregarSfx" type="button">+ Agregar en el centro</button>
      <span class="hint" id="infoSfx"></span>
    </div>
    <div class="barra-sfx" style="display:flex; gap:8px; align-items:center; margin-bottom:8px; flex-wrap:wrap;">
      <label class="hint" for="selDensidadSfx">Densidad</label>
      <select id="selDensidadSfx">
        <option value="sobrio">Sobrio</option>
        <option value="normal" selected>Normal</option>
        <option value="cargado">Cargado</option>
      </select>
      <span class="hint" id="infoDensidadSfx"></span>
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

  <div class="panel">
    <h2>Música de fondo</h2>
    <p class="hint">Elegí la pista de fondo, ajustá su volumen y el segundo desde el que arranca.
      Podés escucharla en tiempo real sobre la previa del video sin re-renderizar.</p>
    <div class="barra-sfx" style="display:flex; gap:12px; align-items:center; flex-wrap:wrap; margin-bottom:10px;">
      <label style="display:flex; align-items:center; gap:6px; font-size:13px; font-weight:600; cursor:pointer;">
        <input type="checkbox" id="chkSinMusica"> Omitir música de fondo
      </label>
    </div>
    <div id="panelMusicaOpciones" style="display:flex; gap:16px; align-items:center; flex-wrap:wrap;">
      <div>
        <label class="hint" for="selMusicaPista" style="display:block; margin-bottom:4px;">Pista</label>
        <select id="selMusicaPista" style="min-width:240px;"></select>
      </div>
      <div>
        <label class="hint" for="musicaVolumenInput" style="display:block; margin-bottom:4px;">Volumen: <span id="musicaVolumenValor">50%</span></label>
        <input type="range" id="musicaVolumenInput" min="0" max="1" step="0.05" value="0.5" style="width:140px;">
      </div>
      <div>
        <label class="hint" for="musicaInicioInput" style="display:block; margin-bottom:4px;">Inicio pista: <span id="musicaInicioValor">0.0s</span></label>
        <input type="range" id="musicaInicioInput" min="0" max="60" step="0.5" value="0" style="width:140px;">
      </div>
      <span class="hint" id="infoMusica" style="align-self:flex-end; padding-bottom:4px;"></span>
    </div>
  </div>

  <div class="panel">
    <h2>Subtítulos</h2>
    <p class="hint">Vista previa APROXIMADA sobre el reproductor: el tamaño y la posición reales
      los define el render y pueden no coincidir pixel a pixel. Si el video ya está renderizado,
      los subtítulos reales ya están quemados adentro — no se dibuja nada encima para no verlos doble.</p>
    <div class="barra-sfx" style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
      <label class="hint" for="subTamanoInput">Tamaño</label>
      <input type="range" id="subTamanoInput" min="50" max="140" step="2" value="88" style="width:160px;">
      <span class="hint" id="subTamanoValor"></span>
      <span class="badge aviso" id="subZonaAviso" style="display:none;"></span>
    </div>
    <p class="hint">Corregí acá las palabras que Whisper transcribió mal (nombres de producto,
      precios en Bs). Esto cambia SOLO lo que se lee en el subtítulo — los tiempos y la alineación
      con el guion no se tocan.</p>
    <div class="tabla-wrap" style="overflow-x:auto; overflow-y:auto; max-height:220px; margin-top:6px;">
      <table style="width:100%; border-collapse:collapse; font-size:13px;">
        <thead><tr><th>t</th><th>dice Whisper</th><th>se lee en el subtítulo</th></tr></thead>
        <tbody id="tablaCorreccionesSub"></tbody>
      </table>
    </div>
  </div>

  <div class="panel">
    <h2>Colección de PiP y B-Rolls <span class="hint" id="dominanteInfo"></span></h2>
    <p class="hint">Sustituí, añadí o quitá los insertos de producto y B-rolls. Arrastrá los bloques en la línea de tiempo para moverlos o estirar sus bordes.</p>
    <div class="pista-enc" id="pistaPipTimeline" style="margin-bottom:12px;">
      <div class="franjas-enc" id="franjasPipTimeline"></div>
    </div>
    <div class="pips-lista" id="pipsLista"></div>
    <button class="btn-primario" id="btnAñadirPip" type="button">+ Añadir PiP / B-Roll en el segundo actual</button>
    <button class="btn-primario" id="btnResetPips" type="button">Volver al automático</button>
    <span class="hint" id="infoPips"></span>

    <div class="editor-caja" id="cajaCatalogo">
      <div class="filtros">
        <strong id="editandoInfo">Elegí un asset:</strong>
        <label><input type="checkbox" id="chkTodos"> ver todos (<span id="totalCatalogo">198</span>)</label>
        <button type="button" id="btnCancelarEdicion">cancelar</button>
      </div>
      <div class="grid-catalogo" id="gridCatalogo"></div>
    </div>

    <div class="editor-caja" id="cajaSegmento">
      <div class="filtros">
        <strong id="segmentoInfo">Elegí el tramo del clip:</strong>
        <button type="button" id="btnCancelarSegmento">cancelar</button>
      </div>
      <video id="segmentoVideo" controls muted
             style="width:100%; max-width:280px; max-height:400px; display:block; margin:0 auto;
                    background:#000; border-radius:8px;"></video>
      <p class="hint" style="margin-top:8px;">
        El audio de este clip <b>no se usa</b>: un B-roll o un PiP de video entra mudo,
        solo se escucha tu voz (y la música/SFX, si van). Arrastrá las manijas para
        elegir el tramo — no se puede pedir más metraje del que el archivo tiene.
      </p>
      <div class="pista-enc" id="pistaSegmento" style="margin-top:8px;">
        <div class="franjas-enc" id="franjasSegmento">
          <div class="enc-cerrado" id="segmentoRango" style="background:rgba(139,92,246,.28); border-color:#8b5cf6;">
            <div class="enc-tirador izq" id="segTirIzq"></div>
            <div class="enc-tirador der" id="segTirDer"></div>
          </div>
        </div>
      </div>
      <p class="hint" id="segmentoResumen"></p>
      <button class="btn-primario" id="btnUsarSegmento" type="button">Usar este tramo</button>
    </div>
  </div>

  <div class="panel">
    <h2>Hook y CTA <span class="hint" id="infoHookCta"></span></h2>
    <p class="hint">El hook (primeros segundos) y el CTA (cierre) son tarjetas de Hyperframes —
      no se ven animadas acá (ningún navegador reproduce ProRes 4444), solo un fotograma
      representativo. El CTA repite un eco corto del hook para cerrar el loop; cambia solo.</p>
    <div class="hook-caja">
      <label class="hint" for="hookTexto">Texto del hook</label>
      <textarea id="hookTexto" maxlength="140"></textarea>
      <div class="hook-preview">
        <div id="hookMedio"><p class="hint">hook · <span id="hookRango">?</span>
          <span class="badge aviso" id="hookZonaAviso" style="display:none;"></span></p></div>
        <div id="ctaMedio"><p class="hint">cta · <span id="ctaRango">?</span> · eco: "<span id="ctaEco"></span>"
          <span class="badge aviso" id="ctaZonaAviso" style="display:none;"></span></p></div>
      </div>
    </div>
    <div class="pista-enc" id="pistaHookCta" style="margin-top:12px;">
      <div class="franjas-enc" id="franjasHookCta"></div>
    </div>
  </div>

  <div class="panel">
    <h2>Animaciones</h2>
    <p class="hint">Batería, splash, moto y sol — Hyperframes. Se ven como un fotograma
      representativo (al 45% del clip, no el primero: todas entran con fade). Quitar, mover o
      añadir acá reemplaza el disparo automático por palabra para TODAS las animaciones del video.</p>
    <div class="pista-enc" id="pistaAnimTimeline" style="margin-bottom:12px;">
      <div class="franjas-enc" id="franjasAnimTimeline"></div>
    </div>
    <div class="anim-grid" id="animGrid"></div>
    <button class="btn-primario" id="btnAñadirAnim" type="button" style="margin-top:8px;">+ Añadir animación en el segundo actual</button>

    <div class="editor-caja" id="cajaInventario">
      <div class="filtros">
        <strong>Elegí una animación del inventario:</strong>
        <button type="button" id="btnCancelarAnim">cancelar</button>
      </div>
      <div class="anim-grid" id="gridInventario"></div>
    </div>
  </div>

  <div class="panel" id="panelSilencios">
    <h2>Silencios recortados <span class="hint" id="silResumen"></span></h2>
    <p class="hint">Lo que el corte automático se llevó de la grabación: silencios largos,
      muletillas y tomas repetidas. Destildá uno para <b>devolverlo al video</b>, o arrastrá
      los bordes de un silencio para dejar más aire. La barra de abajo es la
      <b>grabación entera</b>, no el video que estás viendo: en gris lo que se conserva,
      en rojo lo que se corta.</p>
    <div id="silAvisoFuente" class="badge aviso" style="display:none; margin-bottom:8px;"></div>
    <div id="silAvisosRemapeo" style="display:none; margin-bottom:8px;"></div>
    <div class="pista-enc" id="pistaSilencios" style="margin-bottom:10px;">
      <div class="franjas-enc" id="franjasSilencios"></div>
    </div>
    <div id="silLista"></div>
    <div style="display:flex; gap:10px; align-items:center; margin-top:10px; flex-wrap:wrap;">
      <button class="btn-primario" id="btnResetSilencios" type="button">Volver al corte automático</button>
      <span class="hint" id="silPendiente"></span>
    </div>
  </div>

  <div class="panel">
    <h2>Encuadre <span class="hint" id="encOrigen"></span></h2>
    <p class="hint">Dos cosas distintas. Un <b>punch-in</b> es un acercamiento corto que subraya
      una palabra. Un <b>plano cerrado</b> es un tramo entero más íntimo: entra, se queda y sale.
      Arrastrá el cuerpo de una barra para moverla y sus bordes para estirarla. La curva de abajo
      es el zoom real del render, no un dibujo aproximado.</p>
    <div class="barra-sfx" style="display:flex; gap:8px; align-items:center; margin-bottom:8px; flex-wrap:wrap;">
      <button class="btn-primario" id="btnAddPunch" type="button">+ Punch-in en el segundo actual</button>
      <button class="btn-primario" id="btnAddCerrado" type="button">+ Plano cerrado desde aquí</button>
      <button class="btn-primario" id="btnBorrarEnc" type="button">Quitar el seleccionado</button>
      <button class="btn-primario" id="btnResetEnc" type="button">Volver al automático</button>
      <span class="hint" id="infoEnc"></span>
    </div>
    <div class="pista-enc" id="pistaEnc">
      <div class="franjas-enc" id="franjasEnc"></div>
    </div>
    <svg class="curva-zoom" id="curvaZoom" preserveAspectRatio="none" viewBox="0 0 1000 120">
      <polyline id="curvaLinea" fill="none" stroke="var(--acento)" stroke-width="2" points="" />
      <line id="curvaCursor" x1="0" y1="0" x2="0" y2="120" stroke="var(--fg-2)" stroke-width="1" />
    </svg>
    <div class="hint" id="leyendaZoom"></div>
  </div>

  <div class="panel">
    <p class="hint">
      <button class="btn-primario" id="btnGuardar" type="button">Guardar cambios</button>
      <span class="hint" id="estadoGuardado">se guarda solo</span>
    </p>
    <div class="versiones-caja">
      <div class="barra-sfx" style="display:flex; gap:8px; align-items:center; flex-wrap:wrap;">
        <label class="hint" for="nombreVersion" style="font-weight:600; color:var(--fg);">Versiones</label>
        <input type="text" id="nombreVersion" maxlength="60" placeholder="p. ej. sin b-roll del final"
               style="flex:1; min-width:200px; font:inherit; background:var(--bg); color:var(--fg);
                      border:1px solid var(--linea); border-radius:6px; padding:5px 8px;">
        <button class="btn-primario" id="btnGuardarVersion" type="button">Guardar esta versión</button>
      </div>
      <p class="hint">Guarda una copia con nombre de todo lo ajustado. Cargar una versión
         reemplaza lo que tengas ahora — guardá antes la actual si la querés conservar.</p>
      <div id="listaVersiones"></div>
    </div>
    <p class="hint">
      <button class="btn-primario" id="btnPreview" type="button">👁 Previsualizar</button>
      <button class="btn-primario" id="btnRender" type="button">🎬 Renderizar final</button>
      <br><span class="hint">Se guarda siempre antes de renderizar.
      <b>Previsualizar</b> compone exactamente igual pero a media resolución, no toca el archivo
      final y no publica nada — para comprobar un ajuste. <b>Renderizar final</b> hace el bueno
      y lo copia a OneDrive listo para subir.</span>
    </p>
    <div id="cajaProgreso" style="display:none;">
      <div style="background:var(--linea); border-radius:6px; height:8px; overflow:hidden; margin-bottom:6px;">
        <div id="barraProgreso" style="background:var(--acento); height:100%; width:0%; transition:width .3s;"></div>
      </div>
      <p class="hint" id="textoProgreso"></p>
    </div>
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
let edicionSfxCandidatos = []; // pool completo antes del tope de densidad (bloque 3)
let sfxModificado = false;      // si es false, no se manda --sfx-manual: sigue automático
let sfxSeleccion = null;

// Pool de audios para la previa de SFX: un solo Audio() compartido cortaba el
// sonido anterior cuando dos efectos caían cerca. Cada slot lleva su propio
// GainNode porque la ganancia real puede superar 0dB (archivos silenciosos del
// pack necesitan +30dB para llegar al pico común) y `<audio>.volume` no pasa
// de 1.0 — hace falta Web Audio API para eso.
const SFX_POOL_TAM = 8;
let sfxCtx = null;
let sfxPool = [];
let sfxPoolIdx = 0;

function poolSfx() {
  if (sfxPool.length) return sfxPool;
  const Ctx = window.AudioContext || window.webkitAudioContext;
  sfxCtx = new Ctx();
  for (let i = 0; i < SFX_POOL_TAM; i++) {
    const el = new Audio();
    const nodo = sfxCtx.createMediaElementSource(el);
    const ganancia = sfxCtx.createGain();
    nodo.connect(ganancia).connect(sfxCtx.destination);
    sfxPool.push({ el, ganancia });
  }
  return sfxPool;
}

// Misma cuenta que f5_audio.mezclar_audio: llevar el archivo a un pico común
// (DATA.sfx_pico_objetivo_db) compensa los ~20dB de dispersión del pack, y
// recién ahí se aplica el volumen artístico de la fila. Sin esto, subir o
// bajar el número de la tabla no cambiaba nada de lo que sonaba.
function gananciaSfxDb(nombreArchivo, volumen) {
  const pico = (DATA.niveles_sfx && DATA.niveles_sfx[nombreArchivo]) || 0.0;
  const objetivo = DATA.sfx_pico_objetivo_db != null ? DATA.sfx_pico_objetivo_db : -6.0;
  return (objetivo - pico) + 20 * Math.log10(Math.max(volumen, 0.001));
}

let edicionHookCta = [];        // [{tipo:"hook"|"cta", ini, fin, archivo}]
let hookCtaModificado = false;  // si es false, los tiempos siguen saliendo automáticos

let edicionAnimaciones = [];
let animacionesModificado = false;  // si es false, no se manda --animaciones-manual: sigue automático
let editandoAnimIdx = null;         // índice en edicionAnimaciones, o -1 para "nueva antes de agregar"

let encPunch = [];              // [{t, razon}]
let encCerrados = [];           // [{ini, fin, zoom, razon}]
let encModificado = false;      // si es false, no se manda --encuadre-manual
let encSeleccion = null;        // {tipo: "punch"|"cerrado", i}
let encPendiente = null;        // timer del recálculo de la curva

function escucharSfx(nombre, volumen) {
  if (!DATA || !DATA.sonidos[nombre]) return;
  const pool = poolSfx();
  if (sfxCtx.state === "suspended") sfxCtx.resume();
  const slot = pool[sfxPoolIdx];
  sfxPoolIdx = (sfxPoolIdx + 1) % pool.length;
  const db = gananciaSfxDb(nombre, volumen == null ? 1.0 : volumen);
  slot.ganancia.gain.value = Math.pow(10, db / 20);
  slot.el.src = DATA.sonidos[nombre];
  slot.el.currentTime = 0;
  slot.el.play().catch(() => {});
}

// --- Zona segura de TikTok/Reels (BLOQUE 2) --------------------------------
// Reutilizable: los bloques de subtítulos y texto destacado (CapCut-style)
// también necesitan saber si lo suyo cae donde la app tapa el video. Todas
// las coordenadas son en el espacio de salida (DATA.ancho x DATA.alto,
// 1080x1920), no en píxeles de pantalla.
function cajaEnZonaTapada(x, y, ancho, alto) {
  if (!DATA || !DATA.zona_segura) return null;
  const zs = DATA.zona_segura;
  const y2 = y + alto, x2 = x + ancho;
  // La franja inferior cubre TODO el ancho: alcanza con el solape vertical.
  const tocaInferior = y2 > (DATA.alto - zs.inferior_px);
  // La franja derecha (columna de íconos) no arranca arriba del todo: hace
  // falta solape horizontal Y vertical con el tramo donde sí hay íconos.
  const tocaDerecha = x2 > (DATA.ancho - zs.derecha_px)
                    && y2 > (DATA.alto * zs.derecha_desde_pct);
  if (tocaInferior && tocaDerecha) return "inferior y derecha";
  if (tocaInferior) return "inferior";
  if (tocaDerecha) return "derecha";
  return null;
}

function pintarZonaSegura() {
  if (!DATA || !DATA.zona_segura) return;
  const zs = DATA.zona_segura;
  const inf = document.getElementById("zonaSeguraInferior");
  const der = document.getElementById("zonaSeguraDerecha");
  if (inf) inf.style.height = (zs.inferior_px / DATA.alto * 100) + "%";
  if (der) {
    der.style.width = (zs.derecha_px / DATA.ancho * 100) + "%";
    der.style.top = (zs.derecha_desde_pct * 100) + "%";
  }

  // Hook y CTA no tienen x/y en el editor (son composiciones a pantalla
  // completa con posición fija en su plantilla) — se avisa una sola vez con
  // la caja aproximada de config, no en cada frame.
  const avisoHook = document.getElementById("hookZonaAviso");
  const avisoCta = document.getElementById("ctaZonaAviso");
  if (avisoHook) {
    const z = cajaEnZonaTapada(zs.hook_aprox.x, zs.hook_aprox.y, zs.hook_aprox.ancho, zs.hook_aprox.alto);
    avisoHook.style.display = z ? "" : "none";
    avisoHook.textContent = z ? `⚠ puede caer en zona tapada (${z})` : "";
  }
  if (avisoCta) {
    const z = cajaEnZonaTapada(zs.cta_aprox.x, zs.cta_aprox.y, zs.cta_aprox.ancho, zs.cta_aprox.alto);
    avisoCta.style.display = z ? "" : "none";
    avisoCta.textContent = z ? `⚠ puede caer en zona tapada (${z})` : "";
  }
}

const btnZonaSegura = document.getElementById("btnZonaSegura");
if (btnZonaSegura) {
  const zonaSeguraEl = document.getElementById("zonaSegura");
  const aplicarVisibilidadZona = (visible) => {
    zonaSeguraEl.classList.toggle("visible", visible);
    btnZonaSegura.textContent = visible ? "🛡 Ocultar zona segura de TikTok" : "🛡 Ver zona segura de TikTok";
  };
  aplicarVisibilidadZona(localStorage.getItem("zonaSeguraVisible") === "1");
  btnZonaSegura.addEventListener("click", () => {
    const visible = !zonaSeguraEl.classList.contains("visible");
    localStorage.setItem("zonaSeguraVisible", visible ? "1" : "0");
    aplicarVisibilidadZona(visible);
  });
}

const btnGuardarPortada = document.getElementById("btnGuardarPortada");
if (btnGuardarPortada) {
  btnGuardarPortada.addEventListener("click", async () => {
    const origText = btnGuardarPortada.textContent;
    btnGuardarPortada.disabled = true;
    btnGuardarPortada.textContent = "⏳ Guardando portada...";
    try {
      const res = await fetch("/guardar-portada", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ segundo: typeof video !== "undefined" && video ? video.currentTime : 0 })
      });
      const datos = await res.json();
      if (datos.ok) {
        alert(`🖼 Portada guardada exitosamente a 1080x1920:\n${datos.ruta_relativa || datos.ruta}`);
      } else {
        alert(`❌ Error al guardar portada: ${datos.error}`);
      }
    } catch (err) {
      alert(`❌ Error de conexión: ${err.message}`);
    } finally {
      btnGuardarPortada.disabled = false;
      btnGuardarPortada.textContent = origText;
    }
  });
}

// --- Densidad de SFX (BLOQUE 3) --------------------------------------------
// Misma cuenta que f5_audio.aplicar_tope_densidad: prioridad por tipo de
// evento (config.PRIORIDAD_SFX_POR_RAZON, expuesta como DATA.sfx_prioridades)
// y, entre eventos de igual prioridad, gana el más temprano en el tiempo.
function prioridadSfx(ev) {
  const p = (DATA && DATA.sfx_prioridades) || {};
  return ev.razon in p ? p[ev.razon] : ((DATA && DATA.sfx_prioridad_defecto) ?? 80);
}

function aplicarTopeDensidadSfx(eventos, separacionS) {
  const ordenados = [...eventos].sort((a, b) => (prioridadSfx(b) - prioridadSfx(a)) || (a.t - b.t));
  const aceptados = [];
  for (const ev of ordenados) {
    if (aceptados.some(a => Math.abs(ev.t - a.t) < separacionS)) continue;
    aceptados.push(ev);
  }
  aceptados.sort((a, b) => a.t - b.t);
  return aceptados;
}

function actualizarContadorSfx() {
  const el = document.getElementById("infoDensidadSfx");
  if (!el || !DATA) return;
  const n = edicionSfx.length;
  const dur = DATA.duracion || 0;
  const presets = DATA.sfx_densidad_presets || {};
  const umbral = presets.normal || 4.5;
  if (!n) {
    el.textContent = "sin efectos de sonido";
    el.classList.remove("sfx-denso");
    return;
  }
  const cada = dur / n;
  el.textContent = `${n} sonido(s) en ${dur.toFixed(0)}s · uno cada ${cada.toFixed(1)}s`;
  el.classList.toggle("sfx-denso", cada < umbral);
}

const selDensidadSfx = document.getElementById("selDensidadSfx");
if (selDensidadSfx) {
  selDensidadSfx.addEventListener("change", () => {
    const presets = DATA.sfx_densidad_presets || {};
    const sep = presets[selDensidadSfx.value];
    if (sep == null) return;
    const pool = edicionSfxCandidatos.length ? edicionSfxCandidatos : edicionSfx;
    edicionSfx = aplicarTopeDensidadSfx(pool, sep);
    sfxModificado = true;
    pintarSfx();
    tablaSfx();
  });
}

// --- Subtítulos: tamaño y correcciones de texto (BLOQUE 5) -----------------
let subTamano = 88;
let subCorrecciones = {};   // {indice_global_de_la_palabra: texto_corregido}
let subModificado = false;  // si es false, ajustes.subtitulos.json no se reescribe
let subBloques = [];        // precomputado en cargar(): [[{p, idx}, ...], ...]

// Misma regla que f3_subtitulos.agrupar_en_bloques: de 2 a 4 palabras,
// cerrando en pausas > 0.35s o en punto/interrogación/exclamación. Se
// precalcula UNA vez al cargar, no en cada frame — solo depende de los
// tiempos, que no cambian mientras se edita.
function agruparEnBloquesSub(palabras) {
  const bloques = [];
  let actual = [];
  const MIN = 2, MAX = 4;
  for (let i = 0; i < palabras.length; i++) {
    const p = palabras[i];
    actual.push({ p, idx: i });
    const esUltima = i === palabras.length - 1;
    const pausaSig = esUltima ? 999 : (palabras[i + 1].t - p.fin);
    const cierra = actual.length >= MAX || esUltima
      || (actual.length >= MIN && pausaSig > 0.35)
      || /[.!?]$/.test(p.texto);
    if (cierra) { bloques.push(actual); actual = []; }
  }
  if (actual.length) bloques.push(actual);
  return bloques;
}

function bloqueSubEnT(t) {
  for (const bloque of subBloques) {
    const ini = bloque[0].p.t, fin = bloque[bloque.length - 1].p.fin;
    if (t >= ini - 0.02 && t < fin + 0.15) return bloque;
  }
  return null;
}

// Aproximación del sitio donde el ASS real dibuja el subtítulo (BorderStyle
// centrado en config.SUB_POSICION_ALTURA_PCT, 88% del ancho). No es pixel a
// pixel — la vista previa lo dice explícitamente en su texto de ayuda.
function pintarSubPreview(t) {
  const el = document.getElementById("subPreview");
  if (!el || !DATA) return;
  // Igual que el bloque 1 con los SFX: si es_renderizado, los subtítulos YA
  // están quemados en el video — dibujar encima se vería doble.
  if (DATA.es_renderizado) { el.style.display = "none"; return; }
  const bloque = bloqueSubEnT(t);
  if (!bloque) { el.style.display = "none"; return; }
  const s = lienzo.clientWidth / DATA.ancho;
  el.style.display = "block";
  el.style.top = (DATA.sub_posicion_altura_pct * 100) + "%";
  el.style.fontSize = Math.max(8, subTamano * s) + "px";
  el.innerHTML = bloque.map(({ p, idx }) => {
    const corregido = subCorrecciones[idx];
    const texto = (corregido != null && corregido !== "") ? corregido : p.texto;
    const escapado = texto.replace(/&/g, "&amp;").replace(/</g, "&lt;");
    return (t >= p.t && t < p.fin) ? `<span class="activa">${escapado}</span>` : escapado;
  }).join(" ");
}

// Caja aproximada del bloque de subtítulo al tamaño actual, en el espacio de
// salida (1080x1920) — reusa cajaEnZonaTapada del bloque 2. Hasta 2 líneas
// visibles a la vez es una estimación generosa (los bloques son de 2-4
// palabras, casi siempre entran en una sola línea a este ancho).
function cajaSubActual() {
  const anchoBox = DATA.ancho * 0.88;
  const altoLinea = subTamano * 1.25;
  const altoBox = altoLinea * 2;
  const yCentro = DATA.sub_posicion_altura_pct * DATA.alto;
  return { x: DATA.ancho * 0.06, y: yCentro - altoBox / 2, ancho: anchoBox, alto: altoBox };
}

function actualizarSubZonaAviso() {
  const el = document.getElementById("subZonaAviso");
  if (!el || !DATA || !DATA.zona_segura) return;
  const caja = cajaSubActual();
  const zona = cajaEnZonaTapada(caja.x, caja.y, caja.ancho, caja.alto);
  el.style.display = zona ? "" : "none";
  el.textContent = zona ? `⚠ a este tamaño, puede caer en zona tapada (${zona})` : "";
}

function pintarTablaCorreccionesSub() {
  const tbody = document.getElementById("tablaCorreccionesSub");
  if (!tbody || !DATA) return;
  tbody.innerHTML = "";
  DATA.palabras.forEach((p, i) => {
    const tr = document.createElement("tr");
    const tdT = document.createElement("td");
    tdT.textContent = p.t.toFixed(2) + "s";
    const tdOriginal = document.createElement("td");
    tdOriginal.textContent = p.texto;
    tdOriginal.style.color = "var(--fg-2)";
    const tdCorregido = document.createElement("td");
    const inp = document.createElement("input");
    inp.type = "text";
    inp.value = (subCorrecciones[i] != null) ? subCorrecciones[i] : p.texto;
    inp.style.width = "140px";
    inp.addEventListener("change", () => {
      if (inp.value.trim() === "" || inp.value === p.texto) delete subCorrecciones[i];
      else subCorrecciones[i] = inp.value;
      subModificado = true;
    });
    tdCorregido.appendChild(inp);
    tr.appendChild(tdT); tr.appendChild(tdOriginal); tr.appendChild(tdCorregido);
    tbody.appendChild(tr);
  });
}

function subtitulosParaGuardar() {
  return { tamano_px: subTamano, correcciones: subCorrecciones };
}

const subTamanoInput = document.getElementById("subTamanoInput");
if (subTamanoInput) {
  subTamanoInput.addEventListener("input", () => {
    subTamano = parseInt(subTamanoInput.value, 10) || DATA.sub_tamano_defecto;
    subModificado = true;
    document.getElementById("subTamanoValor").textContent = subTamano + "px";
    actualizarSubZonaAviso();
  });
}

// --- Música de fondo (BLOQUE 8) --------------------------------------------
let edicionMusicaPista = "";
let edicionMusicaVolumen = 0.5;
let edicionMusicaInicio = 0.0;
let edicionSinMusica = false;
let musicaModificada = false;

let musicaAudio = null;
let musicaGainNode = null;
let musicaCtx = null;

function poolMusica() {
  if (musicaAudio) return musicaAudio;
  const Ctx = window.AudioContext || window.webkitAudioContext;
  musicaCtx = new Ctx();
  musicaAudio = new Audio();
  musicaAudio.loop = true;
  const nodo = musicaCtx.createMediaElementSource(musicaAudio);
  musicaGainNode = musicaCtx.createGain();
  nodo.connect(musicaGainNode).connect(musicaCtx.destination);
  return musicaAudio;
}

function inicializarPanelMusica() {
  if (!DATA || !DATA.musica_catalogo) return;
  const selPista = document.getElementById("selMusicaPista");
  const inVol = document.getElementById("musicaVolumenInput");
  const inIni = document.getElementById("musicaInicioInput");
  const chkSin = document.getElementById("chkSinMusica");
  if (!selPista) return;

  selPista.innerHTML = "";
  (DATA.musica_catalogo || []).forEach(item => {
    const o = document.createElement("option");
    o.value = item.archivo || item.id;
    o.textContent = `${item.nombre || item.id} (${item.mood || "fondo"})`;
    selPista.appendChild(o);
  });

  edicionMusicaPista = DATA.musica_pista || (DATA.musica_catalogo[0] ? DATA.musica_catalogo[0].archivo : "");
  edicionMusicaVolumen = DATA.musica_volumen != null ? DATA.musica_volumen : (DATA.musica_volumen_defecto || 0.5);
  edicionMusicaInicio = DATA.musica_inicio_s || 0.0;
  edicionSinMusica = !!DATA.sin_musica;
  musicaModificada = false;

  selPista.value = edicionMusicaPista;
  inVol.value = edicionMusicaVolumen;
  inIni.value = edicionMusicaInicio;
  chkSin.checked = edicionSinMusica;

  pintarEstadoMusica();
}

function pintarEstadoMusica() {
  const chkSin = document.getElementById("chkSinMusica");
  const selPista = document.getElementById("selMusicaPista");
  const inVol = document.getElementById("musicaVolumenInput");
  const inIni = document.getElementById("musicaInicioInput");
  const lblVol = document.getElementById("musicaVolumenValor");
  const lblIni = document.getElementById("musicaInicioValor");
  const info = document.getElementById("infoMusica");
  const panelOps = document.getElementById("panelMusicaOpciones");

  if (!selPista) return;
  edicionSinMusica = chkSin.checked;
  edicionMusicaPista = selPista.value;
  edicionMusicaVolumen = parseFloat(inVol.value) || 0.5;
  edicionMusicaInicio = parseFloat(inIni.value) || 0.0;

  if (lblVol) lblVol.textContent = Math.round(edicionMusicaVolumen * 100) + "%";
  if (lblIni) lblIni.textContent = edicionMusicaInicio.toFixed(1) + "s";
  if (panelOps) panelOps.style.opacity = edicionSinMusica ? "0.4" : "1";
  if (info) info.textContent = musicaModificada ? "· editado a mano" : "· automático";
}

function sincronizarMusicaPrevia() {
  if (!DATA || !DATA.musica_catalogo) return;
  if (edicionSinMusica || DATA.es_renderizado || video.paused) {
    if (musicaAudio && !musicaAudio.paused) musicaAudio.pause();
    return;
  }

  poolMusica();
  if (musicaCtx.state === "suspended") musicaCtx.resume();

  const src = `/archivo?ruta=${encodeURIComponent("assets/musica/" + edicionMusicaPista)}`;
  if (!musicaAudio.src.includes(encodeURIComponent(edicionMusicaPista))) {
    musicaAudio.src = src;
  }

  musicaGainNode.gain.value = edicionMusicaVolumen;
  const tObjetivo = edicionMusicaInicio + video.currentTime;
  if (Math.abs(musicaAudio.currentTime - tObjetivo) > 0.3) {
    musicaAudio.currentTime = tObjetivo;
  }
  if (musicaAudio.paused) {
    musicaAudio.play().catch(() => {});
  }
}

document.getElementById("chkSinMusica")?.addEventListener("change", () => {
  musicaModificada = true; pintarEstadoMusica(); sincronizarMusicaPrevia();
});
document.getElementById("selMusicaPista")?.addEventListener("change", () => {
  musicaModificada = true; pintarEstadoMusica(); sincronizarMusicaPrevia();
});
document.getElementById("musicaVolumenInput")?.addEventListener("input", () => {
  musicaModificada = true; pintarEstadoMusica(); sincronizarMusicaPrevia();
});
document.getElementById("musicaInicioInput")?.addEventListener("input", () => {
  musicaModificada = true; pintarEstadoMusica(); sincronizarMusicaPrevia();
});


async function cargar() {
  const r = await fetch("/datos");
  DATA = await r.json();
  document.getElementById("nombre").textContent = "· " + DATA.nombre;
  document.getElementById("resumen").textContent =
    `${DATA.duracion.toFixed(1)}s · ${DATA.overlays.length} overlays · ${DATA.palabras.length} palabras`;
  document.getElementById("tTotal").textContent = DATA.duracion.toFixed(2) + "s";

  video.src = "/video?t=" + Date.now() + (fuenteVideo ? "&fuente=" + fuenteVideo : "");
  construirTimeline();

  edicionPip = DATA.movibles.filter(m =>
    m.tipo !== "hook" && m.tipo !== "cta" && !m.tipo.startsWith("anim-")
  ).map(m => ({
    ini: m.ini, fin: m.fin, x: m.x, y: m.y,
    // Solo los assets que EXISTEN en el catálogo pueden volver como asset_id.
    // Adivinarlo por el prefijo del nombre dejaba pasar `video:…` y
    // `broll-manual:…`, que el pipeline no sabe resolver: buscaba el id en el
    // catálogo, no lo encontraba y descartaba el inserto entero. Los B-rolls y
    // los PiP de video del guion desaparecían del render sin más rastro que un
    // AVISO en el log.
    asset_id: m.asset_catalogo ? m.asset : null,
    asset: m.asset, tag: m.tag, codigo: m.codigo,
    broll_fullscreen: m.broll_fullscreen,
    archivo: m.archivo, tarjeta: m.overlay, miniatura: m.miniatura, medio: m.medio, tipo: m.tipo,
    palabra: m.palabra,
    // Tramo elegido del clip fuente (bloque 4): null si nunca se eligió uno.
    recorte_inicio: m.recorte_inicio ?? null, recorte_fin: m.recorte_fin ?? null,
  }));
  renderPipsLista();
  construirOverlays(); // depende de edicionPip: tiene que ir después de poblarlo

  edicionSfx = DATA.sfx.map((e, i) => ({ ...e, id: i }));
  // Pool completo para el selector sobrio/normal/cargado (bloque 3): si el
  // backend no manda uno más ancho (ajustes.sfx.json guardado a mano no lo
  // trae), el único pool posible es el propio DATA.sfx.
  edicionSfxCandidatos = (DATA.sfx_candidatos || DATA.sfx).map((e, i) => ({ ...e, id: i }));
  sfxModificado = false;
  sfxSeleccion = null;
  const selDens = document.getElementById("selDensidadSfx");
  if (selDens) selDens.value = "normal";
  construirSelectorSonidos();
  pintarSfx();
  tablaSfx();
  inicializarPanelMusica();

  const pe = DATA.plan_encuadre || { punch_ins: [], planos_cerrados: [], origen: "audio" };
  encPunch = (pe.punch_ins || []).map(p => ({ t: p.t, razon: p.razon || "" }));
  encCerrados = (pe.planos_cerrados || []).map(c => ({
    ini: c.ini, fin: c.fin, zoom: c.zoom || DATA.limites_zoom.plano_cerrado, razon: c.razon || "",
  }));
  encModificado = pe.origen === "manual";
  encSeleccion = null;
  document.getElementById("encOrigen").textContent = {
    manual: "· ajustado a mano",
    guion: "· sale de la columna «Qué se ve» del panel",
    audio: "· medido del volumen de la voz, no es una decisión editorial",
  }[pe.origen] || "";
  pintarEncuadre();
  dibujarCurva(DATA.encuadre);

  const hook = DATA.overlays.find(o => o.tipo === "hook");
  const cta = DATA.overlays.find(o => o.tipo === "cta");
  // El texto guardado a mano manda sobre el del último render.
  document.getElementById("hookTexto").value =
    (DATA.hook_guardado != null && DATA.hook_guardado !== "") ? DATA.hook_guardado : (hook?.texto || "");
  document.getElementById("ctaEco").textContent = cta?.eco || "";
  // Los tiempos guardados a mano mandan sobre los del ultimo render; el
  // `archivo` (para el preview animado) sale igual del render, que es donde
  // vive la tarjeta ya compuesta.
  const hcBase = [hook, cta].filter(Boolean);
  const hcGuardado = DATA.hook_cta_guardado;
  edicionHookCta = hcBase.map(o => {
    const g = (hcGuardado || []).find(x => x.tipo === o.tipo);
    return { tipo: o.tipo, ini: g ? g.ini : o.ini, fin: g ? g.fin : o.fin, archivo: o.archivo };
  });
  hookCtaModificado = !!(hcGuardado && hcGuardado.length);
  pintarHookCta();
  pintarZonaSegura();

  subTamano = DATA.sub_tamano_px || DATA.sub_tamano_defecto || 88;
  subCorrecciones = { ...(DATA.sub_correcciones || {}) };
  subModificado = false;
  subBloques = agruparEnBloquesSub(DATA.palabras);
  if (subTamanoInput) subTamanoInput.value = subTamano;
  const subTamanoValorEl = document.getElementById("subTamanoValor");
  if (subTamanoValorEl) subTamanoValorEl.textContent = subTamano + "px";
  pintarTablaCorreccionesSub();
  actualizarSubZonaAviso();

  const animDelRender = DATA.overlays.filter(o => o.tipo.startsWith("anim-")).map(o => ({
    nombre: o.anim || o.tipo.replace("anim-", ""), ini: o.ini, fin: o.fin,
    // La duración real del clip, para que mover la animación no falsee su
    // barra en la línea de tiempo (el render usa la del clip, no una fija).
    dur: Math.round((o.fin - o.ini) * 1000) / 1000,
    variante: o.variante, palabra: o.palabra, miniatura_archivo: o.miniatura_archivo,
    archivo: o.archivo,
  }));
  // Lo ajustado a mano manda. Solo guarda nombre/ini/variante, asi que la
  // duracion y el archivo del preview se recuperan de la animacion del mismo
  // nombre en el render; si es una que todavia no se ha renderizado nunca, el
  // preview cae a la plantilla por nombre y la duracion al valor por defecto.
  const animGuardadas = DATA.animaciones_guardadas;
  if (animGuardadas && animGuardadas.length) {
    edicionAnimaciones = animGuardadas.map(a => {
      const ref = animDelRender.find(o => o.nombre === a.nombre) || {};
      const dur = ref.dur || 2.4;
      return {
        nombre: a.nombre, ini: a.ini, fin: a.ini + dur, dur,
        variante: a.variante ?? ref.variante ?? null, palabra: a.palabra || "",
        miniatura_archivo: ref.miniatura_archivo || null, archivo: ref.archivo || null,
      };
    });
  } else {
    edicionAnimaciones = animDelRender;
  }
  animacionesModificado = !!(animGuardadas && animGuardadas.length);
  editandoAnimIdx = null;
  renderAnimGrid();

  // Volver al segundo en el que se dejo el video.
  if (DATA.sesion && typeof DATA.sesion.t === "number") {
    const t = Math.max(0, Math.min(DATA.duracion, DATA.sesion.t));
    video.addEventListener("loadedmetadata", () => { video.currentTime = t; }, { once: true });
  }

  // Referencia del autoguardado: a partir de aqui, solo se guarda lo que
  // CAMBIE respecto de lo que se acaba de cargar.
  ultimoGuardado = estadoSerializado();
  marcarGuardado("al día");

  // cargar() se vuelve a llamar después de cada render (Fase 5): el rAF loop
  // solo se arranca una vez, si no cada recarga sumaría otro loop corriendo
  // en paralelo.
  if (!loopArrancado) {
    loopArrancado = true;
    requestAnimationFrame(loop);
  }

  if (window.__silencios) window.__silencios.init(DATA);
  if (window.__tira) window.__tira.init(DATA);
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
  // Un B-roll a pantalla completa SIEMPRE "tapa" la zona segura — es normal,
  // igual que el video de la app real. Solo importa para la tarjeta PiP, que
  // mide 400x520 (f10_editor_visual.render_tarjeta_catalogo).
  edicionPip.forEach((ev, i) => {
    if (esBroll(ev)) return;
    const zona = cajaEnZonaTapada(ev.x, ev.y, 400, 520);
    if (zona) avisos[i].push(`tapado por la interfaz de la app (${zona})`);
  });
  return avisos;
}

function renderPipsLista() {
  const cont = document.getElementById("pipsLista");
  cont.innerHTML = "";
  if (edicionPip.length === 0) {
    cont.innerHTML = '<p class="hint">No hay insertos de producto o B-rolls en este video.</p>';
  }
  const avisos = avisosPip();
  edicionPip.forEach((ev, i) => {
    const div = document.createElement("div");
    div.className = "pip-card" + (editandoIdx === i ? " editando" : "");
    div.title = "Clic para ver este inserto en el video";
    div.addEventListener("click", (e) => {
      // No robar el clic a los controles de la tarjeta.
      if (e.target.closest("button, input, select")) return;
      irAlInicio(ev);
    });
    const img = document.createElement("img");
    let srcImg = ev.tarjeta;
    if (!srcImg && ev.miniatura) {
      srcImg = ev.miniatura.startsWith("data:") ? ev.miniatura : `/archivo?ruta=${encodeURIComponent(ev.miniatura)}`;
    }
    if (!srcImg && ev.asset_id) {
      srcImg = `/miniatura?asset_id=${encodeURIComponent(ev.asset_id)}`;
    }
    if (!srcImg && ev.archivo && (ev.archivo.endsWith(".png") || ev.archivo.endsWith(".jpg") || ev.archivo.endsWith(".jpeg"))) {
      srcImg = `/archivo?ruta=${encodeURIComponent(ev.archivo)}`;
    }
    img.src = srcImg || "";
    img.alt = ev.tipo;
    img.onerror = () => { img.style.display = "none"; };
    div.appendChild(img);
    
    const info = document.createElement("div");
    info.className = "info";
    const badges = (avisos[i] || []).map(a => `<span class="badge aviso">${a}</span>`).join("");
    // El badge miraba `medio === "video"` y llamaba B-Roll a CUALQUIER video,
    // incluido un PiP de video: decia una cosa y se guardaba otra. Ahora sale
    // de lo mismo que decide dónde se guarda el evento.
    const esVideo = ev.medio === "video";
    const tipoTag = esBroll(ev)
      ? `<span class="badge" style="background:#8b5cf6;color:#fff">B-Roll pantalla completa</span>`
      : (esVideo ? `<span class="badge" style="background:#0ea5e9;color:#fff">PiP video</span>`
                 : `<span class="badge">PiP imagen</span>`);

    info.innerHTML = `<b>${tipoTag} ${badges}</b><br>` +
      `ini: <input type="number" step="0.1" min="0" max="${DATA.duracion}" value="${ev.ini.toFixed(1)}" data-idx="${i}" class="in-ini-pip" style="width:55px;">s · ` +
      `fin: <input type="number" step="0.1" min="0" max="${DATA.duracion}" value="${ev.fin.toFixed(1)}" data-idx="${i}" class="in-fin-pip" style="width:55px;">s<br>` +
      `<small style="color:var(--fg-2);">${ev.asset || ev.asset_id || ev.archivo?.split(/[\\/]/).pop() || "sin asset"}</small>`;

    // Solo los VIDEOS pueden ser las dos cosas. Una foto no puede ir a pantalla
    // completa: el pipeline la compone como tarjeta y punto.
    if (esVideo) {
      const sel = document.createElement("select");
      sel.className = "sel-modo-video";
      for (const [val, txt] of [["broll", "A pantalla completa"], ["pip", "Como tarjeta PiP"]]) {
        const o = document.createElement("option");
        o.value = val; o.textContent = txt;
        if ((val === "broll") === esBroll(ev)) o.selected = true;
        sel.appendChild(o);
      }
      sel.addEventListener("change", () => {
        const aBroll = sel.value === "broll";
        ev.broll_fullscreen = aBroll;
        ev.tipo = aBroll ? "broll" : "pip-producto";
        // Un B-roll ocupa el cuadro entero: su posición no significa nada.
        // Al volverlo tarjeta hay que darle un sitio, o se compone en 0,0.
        if (aBroll) { ev.x = 0; ev.y = 0; }
        else if (!ev.x && !ev.y) { ev.x = 620; ev.y = 134; }
        renderPipsLista(); construirOverlays(); construirTimeline();
      });
      info.appendChild(sel);
    }
    div.appendChild(info);
    
    const btnSust = document.createElement("button");
    btnSust.className = "sustituir"; btnSust.textContent = "Sustituir";
    btnSust.addEventListener("click", () => abrirCatalogo(i));
    div.appendChild(btnSust);
    
    const btnQuitar = document.createElement("button");
    btnQuitar.className = "quitar"; btnQuitar.textContent = "Quitar";
    btnQuitar.addEventListener("click", () => { edicionPip.splice(i, 1); renderPipsLista(); construirOverlays(); construirTimeline(); });
    div.appendChild(btnQuitar);
    cont.appendChild(div);
  });

  cont.querySelectorAll(".in-ini-pip").forEach(inp => {
    inp.addEventListener("change", () => {
      const i = parseInt(inp.dataset.idx, 10);
      edicionPip[i].ini = parseFloat(inp.value) || 0;
      construirTimeline();
      pintarPipTimeline();
    });
  });
  cont.querySelectorAll(".in-fin-pip").forEach(inp => {
    inp.addEventListener("change", () => {
      const i = parseInt(inp.dataset.idx, 10);
      edicionPip[i].fin = parseFloat(inp.value) || 0;
      construirTimeline();
      pintarPipTimeline();
    });
  });
  const info = document.getElementById("infoPips");
  if (info) {
    const nB = edicionPip.filter(esBroll).length;
    info.textContent = `${edicionPip.length - nB} PiP · ${nB} B-roll` +
      (DATA.insertos_manuales ? " · ajustados a mano" : " · del guion / automáticos");
  }
  pintarPipTimeline();
}

// Poner la aguja justo donde empieza un bloque (con un pelo de aire antes, para
// ver la entrada y no el fotograma exacto del corte).
function irAlInicio(ev) {
  if (!DATA) return;
  const t = Math.max(0, (ev.ini ?? 0) - 0.15);
  video.currentTime = Math.min(t, DATA.duracion);
}

function pintarPipTimeline() {
  const cont = document.getElementById("franjasPipTimeline");
  const pista = document.getElementById("pistaPipTimeline");
  if (!cont || !pista || !DATA) return;
  cont.innerHTML = "";
  const dur = DATA.duracion;

  edicionPip.forEach((ev, i) => {
    const esVideo = ev.medio === "video" || ev.tipo === "broll";
    const barra = document.createElement("div");
    barra.className = "enc-cerrado" + (editandoIdx === i ? " sel" : "");
    barra.style.left = (ev.ini / dur * 100) + "%";
    barra.style.width = Math.max(0.6, (ev.fin - ev.ini) / dur * 100) + "%";
    barra.style.background = esVideo ? "rgba(139, 92, 246, 0.35)" : "rgba(79, 209, 217, 0.25)";
    barra.style.borderColor = esVideo ? "#8b5cf6" : "var(--acento)";
    barra.textContent = (esVideo ? "B-Roll: " : "PiP: ") + (ev.asset_id || ev.archivo?.split(/[\\/]/).pop() || ev.tipo);
    const maxClip = duracionMaximaClip(ev);
    barra.title = `${ev.ini.toFixed(1)}s - ${ev.fin.toFixed(1)}s`
      + (Number.isFinite(maxClip) ? ` (tramo elegido: ${maxClip.toFixed(1)}s como máximo)` : "");

    for (const lado of ["izq", "der"]) {
      const tir = document.createElement("div");
      tir.className = "enc-tirador " + lado;
      tir.addEventListener("pointerdown", (e) => {
        e.preventDefault(); e.stopPropagation();
        arrastrar((mv) => {
          const t = tiempoDesdeEvento(mv, pista);
          // El hueco no puede ser mas largo que el tramo elegido del clip
          // (bloque 4): estirarlo mas alla se frena, en vez de dejar que el
          // render se quede sin metraje y congele el ultimo cuadro.
          const tope = duracionMaximaClip(ev);
          if (lado === "izq") {
            const minIni = Number.isFinite(tope) ? ev.fin - tope : 0;
            ev.ini = Math.max(minIni, Math.min(t, ev.fin - 0.2));
          } else {
            const maxFin = Number.isFinite(tope) ? ev.ini + tope : Infinity;
            ev.fin = Math.min(maxFin, Math.max(t, ev.ini + 0.2));
          }
          renderPipsLista();
          construirTimeline();
        });
      });
      barra.appendChild(tir);
    }

    barra.addEventListener("pointerdown", (e) => {
      if (e.target.classList.contains("enc-tirador")) return;
      e.preventDefault();
      // Llevar el video al principio del bloque: al tocar un B-roll lo que se
      // quiere ver es ese B-roll, no el segundo en el que quedo la aguja.
      irAlInicio(ev);
      const t0 = tiempoDesdeEvento(e, pista);
      const ini0 = ev.ini, fin0 = ev.fin;
      arrastrar((mv) => {
        const d = tiempoDesdeEvento(mv, pista) - t0;
        const largo = fin0 - ini0;
        ev.ini = Math.max(0, Math.min(dur - largo, ini0 + d));
        ev.fin = ev.ini + largo;
        renderPipsLista();
        construirTimeline();
      });
    });

    cont.appendChild(barra);
  });

  const phPip = document.createElement("div");
  phPip.className = "playhead";
  phPip.id = "playheadPip";
  cont.appendChild(phPip);
}

document.getElementById("pistaPipTimeline").addEventListener("click", (ev) => {
  if (!DATA || ev.target.closest(".enc-cerrado")) return;
  const pista = document.getElementById("pistaPipTimeline");
  const r = pista.getBoundingClientRect();
  const frac = (ev.clientX - r.left) / r.width;
  video.currentTime = Math.max(0, Math.min(DATA.duracion, frac * DATA.duracion));
});

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
      escucharSfx(e.archivo, e.volumen);
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

  const phSfx = document.createElement("div");
  phSfx.className = "playhead";
  phSfx.id = "playheadSfx";
  cont.appendChild(phSfx);

  actualizarContadorSfx();
}

document.getElementById("pistaSfx").addEventListener("click", (ev) => {
  if (!DATA || ev.target.closest(".marca-sfx")) return;
  const pista = document.getElementById("pistaSfx");
  const r = pista.getBoundingClientRect();
  const frac = (ev.clientX - r.left) / r.width;
  video.currentTime = Math.max(0, Math.min(DATA.duracion, frac * DATA.duracion));
});

// ---- Encuadre: punch-ins y planos cerrados ---------------------------------
// La curva NO se calcula aca. Se le pide al servidor, que la saca con la misma
// funcion del render (f4_retencion.encuadre_en_t). Reimplementarla en JS para
// la vista previa seria la forma mas directa de que el editor y el video
// terminen enseñando cosas distintas, que es justo lo que este editor evita.
function tiempoDesdeEvento(ev, elemento) {
  const r = elemento.getBoundingClientRect();
  const t = (ev.clientX - r.left) / r.width * DATA.duracion;
  return Math.max(0, Math.min(DATA.duracion, Math.round(t * 100) / 100));
}

function arrastrar(alMover) {
  const mover = (mv) => alMover(mv);
  const soltar = () => {
    window.removeEventListener("pointermove", mover);
    window.removeEventListener("pointerup", soltar);
    recalcularCurva();
  };
  window.addEventListener("pointermove", mover);
  window.addEventListener("pointerup", soltar);
}

function pintarEncuadre() {
  const cont = document.getElementById("franjasEnc");
  const pista = document.getElementById("pistaEnc");
  cont.innerHTML = "";
  encCerrados.sort((a, b) => a.ini - b.ini);
  encPunch.sort((a, b) => a.t - b.t);

  encCerrados.forEach((c, i) => {
    const barra = document.createElement("div");
    barra.className = "enc-cerrado" + (encSeleccion?.tipo === "cerrado" && encSeleccion.i === i ? " sel" : "");
    barra.style.left = (c.ini / DATA.duracion * 100) + "%";
    barra.style.width = Math.max(0.6, (c.fin - c.ini) / DATA.duracion * 100) + "%";
    barra.textContent = `cerrado ${c.ini.toFixed(1)}–${c.fin.toFixed(1)}s`;
    barra.title = c.razon || "plano cerrado";

    for (const lado of ["izq", "der"]) {
      const tir = document.createElement("div");
      tir.className = "enc-tirador " + lado;
      tir.addEventListener("pointerdown", (ev) => {
        ev.preventDefault(); ev.stopPropagation();
        encSeleccion = { tipo: "cerrado", i }; pintarEncuadre();
        arrastrar((mv) => {
          const t = tiempoDesdeEvento(mv, pista);
          if (lado === "izq") c.ini = Math.min(t, c.fin - 0.2);
          else c.fin = Math.max(t, c.ini + 0.2);
          encModificado = true; pintarEncuadre();
        });
      });
      barra.appendChild(tir);
    }

    barra.addEventListener("pointerdown", (ev) => {
      if (ev.target.classList.contains("enc-tirador")) return;
      ev.preventDefault();
      encSeleccion = { tipo: "cerrado", i }; pintarEncuadre();
      const t0 = tiempoDesdeEvento(ev, pista);
      const ini0 = c.ini, fin0 = c.fin;
      arrastrar((mv) => {
        const d = tiempoDesdeEvento(mv, pista) - t0;
        const largo = fin0 - ini0;
        c.ini = Math.max(0, Math.min(DATA.duracion - largo, ini0 + d));
        c.fin = c.ini + largo;
        encModificado = true; pintarEncuadre();
      });
    });
    cont.appendChild(barra);
  });

  encPunch.forEach((p, i) => {
    const m = document.createElement("div");
    m.className = "enc-punch" + (encSeleccion?.tipo === "punch" && encSeleccion.i === i ? " sel" : "");
    m.style.left = (p.t / DATA.duracion * 100) + "%";
    m.title = `punch-in ${p.t.toFixed(2)}s · ${p.razon || "manual"}`;
    m.addEventListener("pointerdown", (ev) => {
      ev.preventDefault(); ev.stopPropagation();
      encSeleccion = { tipo: "punch", i }; pintarEncuadre();
      arrastrar((mv) => {
        p.t = tiempoDesdeEvento(mv, pista);
        encModificado = true; pintarEncuadre();
      });
    });
    cont.appendChild(m);
  });

  document.getElementById("infoEnc").textContent =
    `${encPunch.length} punch-in(s) · ${encCerrados.length} plano(s) cerrado(s)` +
    (encModificado ? " · editado a mano" : "");

  const phEnc = document.createElement("div");
  phEnc.className = "playhead";
  phEnc.id = "playheadEnc";
  cont.appendChild(phEnc);
}

function dibujarCurva(muestras) {
  if (!muestras || !muestras.length) return;
  const zMax = Math.max(DATA.limites_zoom.punch_in, DATA.limites_zoom.plano_cerrado);
  const zMin = DATA.limites_zoom.base;
  const paso = Math.max(1, Math.floor(muestras.length / 1000));
  const pts = [];
  for (let i = 0; i < muestras.length; i += paso) {
    const [t, , , z] = muestras[i];
    const x = t / DATA.duracion * 1000;
    const y = 115 - (z - zMin) / (zMax - zMin || 1) * 110;
    pts.push(`${x.toFixed(1)},${y.toFixed(1)}`);
  }
  document.getElementById("curvaLinea").setAttribute("points", pts.join(" "));
  const zs = muestras.map(m => m[3]);
  document.getElementById("leyendaZoom").textContent =
    `zoom ${Math.min(...zs).toFixed(3)}× a ${Math.max(...zs).toFixed(3)}× ` +
    `(la base sube sola de ${zMin.toFixed(2)}× a lo largo del plano; un punch-in llega a ` +
    `${DATA.limites_zoom.punch_in}× durante ${DATA.limites_zoom.punch_in_dur}s)`;
}

function recalcularCurva() {
  // Se agrupa: arrastrando se disparan decenas de eventos por segundo y no
  // hace falta una vuelta al servidor por cada pixel.
  clearTimeout(encPendiente);
  encPendiente = setTimeout(async () => {
    const r = await fetch("/encuadre/vista-previa", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ duracion: DATA.duracion, encuadre: encuadreParaGuardar() }),
    });
    const datos = await r.json();
    if (datos.ok) { DATA.encuadre = datos.encuadre; dibujarCurva(datos.encuadre); }
  }, 180);
}

function encuadreParaGuardar() {
  return {
    punch_ins: encPunch.map(p => ({ t: p.t, razon: p.razon || "manual" })),
    planos_cerrados: encCerrados.map(c => ({
      ini: c.ini, fin: c.fin, zoom: c.zoom, razon: c.razon || "manual",
    })),
  };
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
      e.archivo = selFila.value; sfxModificado = true; escucharSfx(e.archivo, e.volumen);
    });
    tdSonido.appendChild(selFila); tr.appendChild(tdSonido);

    const tdVol = document.createElement("td");
    const inV = document.createElement("input");
    inV.type = "number"; inV.step = "0.05"; inV.min = "0"; inV.max = "1.5";
    inV.value = e.volumen;
    inV.addEventListener("change", () => {
      e.volumen = parseFloat(inV.value) || 0; sfxModificado = true;
      escucharSfx(e.archivo, e.volumen); // se oye el cambio al instante
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

// La animación EN MOVIMIENTO, no un rectángulo negro. Son ProRes 4444 con
// alfa: ningún navegador los reproduce, y el <img> que había antes apuntaba a
// un .mov, así que la tarjeta salía negra y no había forma de distinguir una
// animación de otra. El servidor devuelve un WebM chico ya compuesto sobre el
// color del panel. Si no hay ninguno (plantilla nunca renderizada), se cae a
// una ficha de texto en vez de dejar un hueco.
function medioAnimacion(a) {
  const src = a.archivo
    ? `/anim-preview?ruta=${encodeURIComponent(a.archivo)}`
    : `/anim-preview?nombre=${encodeURIComponent(a.nombre)}`;
  const v = document.createElement("video");
  v.src = src;
  v.autoplay = true; v.loop = true; v.muted = true;
  v.playsInline = true; v.preload = "metadata";
  v.className = "anim-preview";
  v.title = "Pasá el ratón para reproducir desde el principio";
  v.addEventListener("mouseenter", () => { v.currentTime = 0; v.play().catch(() => {}); });
  v.addEventListener("error", () => {
    const ficha = document.createElement("div");
    ficha.className = "anim-sin-preview";
    ficha.textContent = a.nombre;
    if (v.parentNode) v.parentNode.replaceChild(ficha, v);
  });
  return v;
}

// El hook y el CTA son tarjetas de Hyperframes: ProRes 4444 en .mov, que un
// <img> no puede pintar — de ahi los dos iconos rotos que se veian. Se enseñan
// con el mismo preview animado que las animaciones, y en su propia pista para
// ver donde entran y poder moverlos o estirarlos.
function pintarHookCta() {
  const cont = document.getElementById("franjasHookCta");
  const pista = document.getElementById("pistaHookCta");
  if (!cont || !pista || !DATA) return;
  cont.innerHTML = "";

  for (const bloque of edicionHookCta) {
    const caja = document.getElementById(bloque.tipo === "hook" ? "hookMedio" : "ctaMedio");
    if (caja && !caja.querySelector("video, .anim-sin-preview")) {
      caja.insertBefore(medioAnimacion({ nombre: bloque.tipo, archivo: bloque.archivo }),
                        caja.firstChild);
    }
    const et = document.getElementById(bloque.tipo === "hook" ? "hookRango" : "ctaRango");
    if (et) et.textContent = `${bloque.ini.toFixed(1)}-${bloque.fin.toFixed(1)}s`;

    const barra = document.createElement("div");
    barra.className = "enc-cerrado";
    barra.style.left = (bloque.ini / DATA.duracion * 100) + "%";
    barra.style.width = Math.max(0.6, (bloque.fin - bloque.ini) / DATA.duracion * 100) + "%";
    barra.style.background = bloque.tipo === "hook"
      ? "rgba(16,185,129,.28)" : "rgba(244,114,182,.28)";
    barra.style.borderColor = bloque.tipo === "hook" ? "#10b981" : "#f472b6";
    barra.textContent = bloque.tipo === "hook" ? "HOOK" : "CTA";
    barra.title = `${bloque.tipo} · ${bloque.ini.toFixed(1)}-${bloque.fin.toFixed(1)}s`;

    for (const lado of ["izq", "der"]) {
      const tir = document.createElement("div");
      tir.className = "enc-tirador " + lado;
      tir.addEventListener("pointerdown", (e) => {
        e.preventDefault(); e.stopPropagation();
        arrastrar((mv) => {
          const t = tiempoDesdeEvento(mv, pista);
          if (lado === "izq") bloque.ini = Math.min(t, bloque.fin - 0.5);
          else bloque.fin = Math.max(t, bloque.ini + 0.5);
          hookCtaModificado = true;
          pintarHookCta();
        });
      });
      barra.appendChild(tir);
    }

    barra.addEventListener("pointerdown", (e) => {
      if (e.target.classList.contains("enc-tirador")) return;
      e.preventDefault();
      irAlInicio(bloque);
      const t0 = tiempoDesdeEvento(e, pista);
      const ini0 = bloque.ini, largo = bloque.fin - bloque.ini;
      arrastrar((mv) => {
        bloque.ini = Math.max(0, Math.min(DATA.duracion - largo,
                                          ini0 + (tiempoDesdeEvento(mv, pista) - t0)));
        bloque.fin = bloque.ini + largo;
        hookCtaModificado = true;
        pintarHookCta();
      });
    });
    cont.appendChild(barra);
  }

  const ph = document.createElement("div");
  ph.className = "playhead"; ph.id = "playheadHookCta";
  cont.appendChild(ph);

  const info = document.getElementById("infoHookCta");
  if (info) info.textContent = hookCtaModificado ? "· ajustado a mano" : "· automático";
}

document.getElementById("pistaHookCta").addEventListener("click", (ev) => {
  if (!DATA || ev.target.closest(".enc-cerrado")) return;
  video.currentTime = tiempoDesdeEvento(ev, ev.currentTarget);
});

function hookCtaParaGuardar() {
  return edicionHookCta.map(b => ({
    tipo: b.tipo, ini: Math.round(b.ini * 100) / 100, fin: Math.round(b.fin * 100) / 100,
  }));
}

function renderAnimGrid() {
  const cont = document.getElementById("animGrid");
  cont.innerHTML = "";
  if (edicionAnimaciones.length === 0) {
    cont.innerHTML = '<p class="hint">Este video no tiene animaciones.</p>';
  }
  edicionAnimaciones.forEach((a, i) => {
    const card = document.createElement("div");
    card.className = "anim-card";
    card.title = "Clic para ver esta animación en el video";
    card.addEventListener("click", (e) => {
      if (e.target.closest("button, input, select")) return;
      irAlInicio(a);
    });
    card.appendChild(medioAnimacion(a));
    const info = document.createElement("div");
    info.className = "info";
    // La variante va en la etiqueta: `anim-apps` son DOS animaciones distintas
    // (una enseña TikTok/WhatsApp/Facebook y la otra Instagram/YouTube) y con
    // el mismo nombre las dos tarjetas parecian repetidas.
    const vtag = (a.variante !== null && a.variante !== undefined)
      ? ` <span class="badge">v${a.variante + 1}</span>` : "";
    info.innerHTML = `<b>${a.nombre}</b>${vtag}${a.palabra ? ` · "${a.palabra}"` : ""}<br>` +
      `ini: <input type="number" step="0.1" min="0" max="${DATA.duracion}" value="${a.ini.toFixed(1)}" data-idx="${i}" class="in-ini-anim" style="width:60px;">s`;
    card.appendChild(info);
    const botones = document.createElement("div");
    botones.className = "fila-botones";
    const btnQuitar = document.createElement("button");
    btnQuitar.type = "button"; btnQuitar.textContent = "Quitar";
    btnQuitar.addEventListener("click", () => {
      edicionAnimaciones.splice(i, 1); animacionesModificado = true; renderAnimGrid();
    });
    botones.appendChild(btnQuitar);
    card.appendChild(botones);
    cont.appendChild(card);
  });
  cont.querySelectorAll(".in-ini-anim").forEach(inp => {
    inp.addEventListener("change", () => {
      const i = parseInt(inp.dataset.idx, 10);
      moverAnimacion(edicionAnimaciones[i], parseFloat(inp.value) || 0);
      renderAnimGrid();
    });
  });
  pintarAnimTimeline();
}

// Una animación no se estira: dura lo que dura su clip. Mover = trasladar, y
// el fin se recalcula siempre desde la duración real (antes eran 2.4s fijos,
// así que la barra mentía para todas las que no midieran eso).
function moverAnimacion(a, ini) {
  const dur = a.dur || 2.4;
  a.ini = Math.max(0, Math.min(DATA.duracion - dur, ini));
  a.fin = a.ini + dur;
  animacionesModificado = true;
}

function pintarAnimTimeline() {
  const cont = document.getElementById("franjasAnimTimeline");
  const pista = document.getElementById("pistaAnimTimeline");
  if (!cont || !pista || !DATA) return;
  cont.innerHTML = "";
  const dur = DATA.duracion;

  edicionAnimaciones.forEach((a, i) => {
    const barra = document.createElement("div");
    barra.className = "enc-cerrado";
    barra.style.left = (a.ini / dur * 100) + "%";
    barra.style.width = Math.max(0.6, ((a.fin - a.ini) / dur) * 100) + "%";
    barra.style.background = "rgba(234, 179, 8, .28)";
    barra.style.borderColor = "#eab308";
    barra.textContent = a.nombre;
    barra.title = `${a.nombre} · ${a.ini.toFixed(1)}s - ${a.fin.toFixed(1)}s`;

    barra.addEventListener("pointerdown", (e) => {
      e.preventDefault();
      irAlInicio(a);
      const t0 = tiempoDesdeEvento(e, pista);
      const ini0 = a.ini;
      arrastrar((mv) => {
        moverAnimacion(a, ini0 + (tiempoDesdeEvento(mv, pista) - t0));
        // Solo la pista y la casilla de segundos. Rehacer la rejilla entera en
        // cada frame reiniciaría los <video> de todas las tarjetas y el
        // arrastre iría a tirones.
        pintarAnimTimeline();
        const inp = document.querySelector(`.in-ini-anim[data-idx="${i}"]`);
        if (inp) inp.value = a.ini.toFixed(1);
      });
    });
    cont.appendChild(barra);
  });

  const ph = document.createElement("div");
  ph.className = "playhead";
  ph.id = "playheadAnim";
  cont.appendChild(ph);
}

document.getElementById("pistaAnimTimeline").addEventListener("click", (ev) => {
  if (!DATA || ev.target.closest(".enc-cerrado")) return;
  video.currentTime = tiempoDesdeEvento(ev, ev.currentTarget);
});

async function abrirInventarioAnim(idx) {
  editandoAnimIdx = idx;
  document.getElementById("cajaInventario").classList.add("activa");
  const r = await fetch("/animaciones-disponibles");
  const datos = await r.json();
  const grid = document.getElementById("gridInventario");
  grid.innerHTML = "";
  for (const a of datos.inventario) {
    const item = document.createElement("div");
    item.className = "inventario-item";
    // Elegir a ciegas por el nombre era adivinar: "splash" o "moto" no dicen
    // cómo se ven. Ahora cada una se enseña moviéndose.
    if (a.preview) item.appendChild(medioAnimacion({ nombre: a.nombre }));
    const txt = document.createElement("div");
    txt.innerHTML = `<span class="nombre">${a.etiqueta || a.nombre}</span>` +
      `<span class="detalle">${a.nombre} · ${a.duracion.toFixed(1)}s · ${a.motor}` +
      `${a.preview ? "" : " (sin render todavía)"}</span>`;
    item.appendChild(txt);

    // Con varias variantes hay que poder decir CUÁL: `anim-apps` v1 y v2
    // enseñan redes distintas. Sin elegir, la escoge el pipeline por la
    // semilla del video, que es lo de antes y sigue valiendo.
    if (a.variantes > 1) {
      const fila = document.createElement("div");
      fila.className = "fila-variantes";
      for (let v = 0; v < a.variantes; v++) {
        const b = document.createElement("button");
        b.type = "button"; b.textContent = "v" + (v + 1);
        b.title = `Añadir la variante ${v + 1} de ${a.nombre}`;
        b.addEventListener("click", (e) => { e.stopPropagation(); elegirAnimacion(a, v); });
        fila.appendChild(b);
      }
      const cual = document.createElement("span");
      cual.className = "detalle";
      cual.textContent = "o elegí variante:";
      txt.appendChild(cual);
      item.appendChild(fila);
    }

    item.addEventListener("click", () => elegirAnimacion(a));
    grid.appendChild(item);
  }
}

function elegirAnimacion(a, variante = null) {
  const nueva = {
    nombre: a.nombre, ini: video.currentTime, fin: video.currentTime + a.duracion,
    dur: a.duracion,
    variante, palabra: "", miniatura_archivo: null,
  };
  if (editandoAnimIdx === -1) {
    edicionAnimaciones.push(nueva);
  } else {
    edicionAnimaciones[editandoAnimIdx] = nueva;
  }
  animacionesModificado = true;
  document.getElementById("cajaInventario").classList.remove("activa");
  editandoAnimIdx = null;
  renderAnimGrid();
}

document.getElementById("btnAñadirAnim").addEventListener("click", () => abrirInventarioAnim(-1));
document.getElementById("btnCancelarAnim").addEventListener("click", () => {
  editandoAnimIdx = null;
  document.getElementById("cajaInventario").classList.remove("activa");
});

function animacionesParaGuardar() {
  return edicionAnimaciones.map(a => {
    const base = { nombre: a.nombre, ini: Math.round(a.ini * 100) / 100 };
    if (a.variante !== null && a.variante !== undefined) base.variante = a.variante;
    if (a.palabra) base.palabra = a.palabra;
    return base;
  });
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
    item.className = "item" + (a.es_clip ? " clip" : "");
    item.title = a.es_clip
      ? `Clip de Flow · ${a.producto} · ${a.duracion_s}s · entra como B-Roll a pantalla completa`
      : `${a.producto} · ${a.tipo} · ${a.color || ""}`;
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = `/miniatura?asset_id=${encodeURIComponent(a.id)}`;
    item.appendChild(img);
    if (a.es_clip) {
      const et = document.createElement("span");
      et.className = "clip-badge";
      et.textContent = `▶ ${a.duracion_s}s`;
      item.appendChild(et);
    }
    if (a.fondo_pendiente) {
      const pend = document.createElement("span");
      pend.className = "pend"; pend.textContent = "sin recorte";
      item.appendChild(pend);
    }
    item.addEventListener("click", () => {
      // Un clip de verdad (no una imagen) puede tener cualquier duración —
      // hoy 8 de los de assets/generado/video/manual/ pasan los 15s. Antes
      // se usaba siempre desde el segundo 0; el modal deja elegir el tramo
      // (bloque 4 del plan de mejoras).
      if (a.es_clip) abrirModalSegmento(a);
      else elegirAsset(a);
    });
    grid.appendChild(item);
  }
}

function elegirAsset(asset) {
  // Un clip de Flow entra como B-ROLL a pantalla completa, no como tarjeta:
  // asi es como los usa el pipeline (`broll-manual:`) y como estan pensados.
  // Su id no es del catalogo, asi que viaja por `archivo`, no por `asset_id`.
  const nuevo = asset.es_clip
    ? {
        ini: video.currentTime,
        fin: Math.min(DATA.duracion, video.currentTime + (asset.duracion_s || 3)),
        x: 0, y: 0, asset_id: null, asset: asset.id, archivo: asset.archivo,
        tarjeta: null, tipo: "broll", medio: "video", broll_fullscreen: true,
      }
    : {
        ini: video.currentTime, fin: Math.min(DATA.duracion, video.currentTime + 2.8),
        x: 620, y: 134, asset_id: asset.id, asset: asset.id, archivo: null,
        tarjeta: null, tipo: "pip-producto", medio: "imagen", broll_fullscreen: false,
      };

  if (editandoIdx === -1) {
    edicionPip.push(nuevo);
  } else {
    // Sustituir conserva el hueco de tiempo que ya tenia el inserto.
    const viejo = edicionPip[editandoIdx];
    edicionPip[editandoIdx] = { ...nuevo, ini: viejo.ini, fin: viejo.fin };
  }
  document.getElementById("cajaCatalogo").classList.remove("activa");
  editandoIdx = null;
  renderPipsLista();
  construirOverlays();
}

// --- Modal para elegir el tramo de un clip de B-roll (BLOQUE 4) -----------
let segmentoAsset = null;
let segmentoIni = 0, segmentoFin = 0, segmentoDur = 0;

// Cuánto puede durar como máximo el hueco de un inserto de VIDEO sin pedirle
// al clip más metraje del que tiene. Infinity si no aplica (una imagen no se
// "acaba") o si el evento nunca pasó por el modal (comportamiento de
// siempre: sin tope nuevo).
function duracionMaximaClip(ev) {
  if (ev.medio !== "video") return Infinity;
  if (ev.recorte_inicio != null && ev.recorte_fin != null) return ev.recorte_fin - ev.recorte_inicio;
  return Infinity;
}

function arrastrarSimple(alMover) {
  const mover = (mv) => alMover(mv);
  const soltar = () => {
    window.removeEventListener("pointermove", mover);
    window.removeEventListener("pointerup", soltar);
  };
  window.addEventListener("pointermove", mover);
  window.addEventListener("pointerup", soltar);
}

function tiempoSegmento(ev, elemento) {
  const r = elemento.getBoundingClientRect();
  const t = (ev.clientX - r.left) / r.width * segmentoDur;
  return Math.max(0, Math.min(segmentoDur, Math.round(t * 100) / 100));
}

function abrirModalSegmento(asset) {
  segmentoAsset = asset;
  segmentoDur = asset.duracion_s || 0;
  segmentoIni = 0;
  segmentoFin = segmentoDur;
  document.getElementById("cajaCatalogo").classList.remove("activa");
  document.getElementById("cajaSegmento").classList.add("activa");
  document.getElementById("segmentoInfo").textContent =
    `Elegí el tramo de "${asset.producto}" (dura ${segmentoDur.toFixed(1)}s en total):`;
  const v = document.getElementById("segmentoVideo");
  v.pause();
  v.src = `/archivo?ruta=${encodeURIComponent(asset.archivo)}`;
  v.currentTime = 0;
  pintarSegmento();
}

function cerrarModalSegmento() {
  document.getElementById("cajaSegmento").classList.remove("activa");
  document.getElementById("segmentoVideo").pause();
  segmentoAsset = null;
}

function pintarSegmento() {
  const rango = document.getElementById("segmentoRango");
  if (!rango || !segmentoDur) return;
  rango.style.left = (segmentoIni / segmentoDur * 100) + "%";
  rango.style.width = Math.max(1, (segmentoFin - segmentoIni) / segmentoDur * 100) + "%";
  document.getElementById("segmentoResumen").textContent =
    `${segmentoIni.toFixed(1)}s a ${segmentoFin.toFixed(1)}s de ${segmentoDur.toFixed(1)}s · `
    + `el tramo elegido dura ${(segmentoFin - segmentoIni).toFixed(1)}s`;
}

document.getElementById("segTirIzq").addEventListener("pointerdown", (e) => {
  e.preventDefault(); e.stopPropagation();
  const pista = document.getElementById("pistaSegmento");
  arrastrarSimple((mv) => {
    // tiempoSegmento ya frena en 0 y en segmentoDur: no se puede pedir mas
    // metraje del que el archivo tiene.
    segmentoIni = Math.min(tiempoSegmento(mv, pista), segmentoFin - 0.3);
    document.getElementById("segmentoVideo").currentTime = segmentoIni;
    pintarSegmento();
  });
});
document.getElementById("segTirDer").addEventListener("pointerdown", (e) => {
  e.preventDefault(); e.stopPropagation();
  const pista = document.getElementById("pistaSegmento");
  arrastrarSimple((mv) => {
    segmentoFin = Math.max(tiempoSegmento(mv, pista), segmentoIni + 0.3);
    document.getElementById("segmentoVideo").currentTime = segmentoFin;
    pintarSegmento();
  });
});
document.getElementById("btnCancelarSegmento").addEventListener("click", cerrarModalSegmento);
document.getElementById("btnUsarSegmento").addEventListener("click", () => {
  if (!segmentoAsset) return;
  const asset = segmentoAsset, recorteIni = segmentoIni, recorteFin = segmentoFin;
  const duracionTramo = recorteFin - recorteIni;
  const nuevo = {
    ini: video.currentTime,
    fin: Math.min(DATA.duracion, video.currentTime + duracionTramo),
    x: 0, y: 0, asset_id: null, asset: asset.id, archivo: asset.archivo,
    tarjeta: null, tipo: "broll", medio: "video", broll_fullscreen: true,
    recorte_inicio: recorteIni, recorte_fin: recorteFin,
  };
  if (editandoIdx === -1) {
    edicionPip.push(nuevo);
  } else {
    const viejo = edicionPip[editandoIdx];
    // El hueco queda atado al tramo elegido: no puede quedar mas largo que
    // el tramo, aunque el hueco viejo si lo fuera.
    const fin = Math.min(viejo.fin, viejo.ini + duracionTramo);
    edicionPip[editandoIdx] = { ...nuevo, ini: viejo.ini, fin };
  }
  cerrarModalSegmento();
  editandoIdx = null;
  renderPipsLista();
  construirOverlays();
});

document.getElementById("btnAñadirPip").addEventListener("click", () => abrirCatalogo(-1));
document.getElementById("btnResetPips").addEventListener("click", async () => {
  if (!confirm("Se descartan los insertos y B-rolls ajustados a mano y vuelven los del guion / los automáticos. ¿Seguir?")) return;
  await fetch("/restablecer", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
  await cargar();
});
document.getElementById("btnCancelarEdicion").addEventListener("click", () => {
  editandoIdx = null;
  document.getElementById("cajaCatalogo").classList.remove("activa");
  renderPipsLista();
});
document.getElementById("chkTodos").addEventListener("change", cargarGridCatalogo);
// Un B-roll ocupa el cuadro entero y viaja por --broll-manual; un PiP es una
// tarjeta y viaja por --eventos-manual. Son dos listas distintas en el
// pipeline, así que hay que separarlas al guardar: mandar un B-roll como
// inserto lo devolvía convertido en una estampita de 400x520 en una esquina.
function esBroll(ev) {
  return ev.broll_fullscreen === true || ev.tipo === "broll";
}

// `archivo` va SIEMPRE, incluso junto a asset_id: es el respaldo con el que el
// pipeline puede recuperar el inserto si el id no resuelve.
function eventoBase(ev) {
  const base = {
    ini: ev.ini, fin: ev.fin, x: ev.x, y: ev.y,
    tipo: ev.tipo, medio: ev.medio,
    palabra: ev.palabra || "", tag: ev.tag || "",
  };
  if (ev.asset_id) base.asset_id = ev.asset_id;
  if (ev.asset) base.asset = ev.asset;
  if (ev.archivo) base.archivo = ev.archivo;
  if (ev.codigo) base.codigo = ev.codigo;
  // Tramo elegido del clip fuente (bloque 4): sin esto, guardar y recargar
  // olvidaba el recorte y el render volvía a leer desde el segundo 0.
  if (ev.recorte_inicio != null) base.recorte_inicio = ev.recorte_inicio;
  if (ev.recorte_fin != null) base.recorte_fin = ev.recorte_fin;
  return base;
}

function eventosParaGuardar() {
  return edicionPip.filter(ev => !esBroll(ev)).map(eventoBase);
}

function brollParaGuardar() {
  return edicionPip.filter(esBroll).map(ev => {
    const base = eventoBase(ev);
    base.broll_fullscreen = true;
    base.medio = "video";
    return base;
  });
}

function cuerpoAjustes() {
  // Si el panel de sonidos/animaciones no se tocó, no se manda --sfx-manual/
  // --animaciones-manual: siguen derivándose automático (así "acompañan"
  // cualquier PiP que se mueva, sustituya o quite — Fase 4, punto 2 del plan).
  // El hook SÍ se manda siempre: si no, --reaplicar lo volvería a derivar de
  // la transcripción y pisaría en silencio un texto que José ya haya elegido.
  const cuerpo = {
    eventos: eventosParaGuardar(),
    broll: brollParaGuardar(),
    hook: document.getElementById("hookTexto").value,
  };
  if (sfxModificado) cuerpo.sfx = sfxParaGuardar();
  if (animacionesModificado) cuerpo.animaciones = animacionesParaGuardar();
  if (encModificado) cuerpo.encuadre = encuadreParaGuardar();
  if (hookCtaModificado) cuerpo.hook_cta = hookCtaParaGuardar();
  if (subModificado) cuerpo.subtitulos = subtitulosParaGuardar();
  if (musicaModificada || edicionSinMusica) {
    cuerpo.musica = {
      pista: edicionMusicaPista,
      volumen: edicionMusicaVolumen,
      inicio_s: edicionMusicaInicio,
      sin_musica: edicionSinMusica
    };
  }
  return cuerpo;
}

document.getElementById("btnAddPunch").addEventListener("click", () => {
  encPunch.push({ t: Math.round(video.currentTime * 100) / 100, razon: "manual" });
  encSeleccion = null; encModificado = true; pintarEncuadre(); recalcularCurva();
});

document.getElementById("btnAddCerrado").addEventListener("click", () => {
  const ini = Math.round(video.currentTime * 100) / 100;
  const fin = Math.min(DATA.duracion, ini + 4);
  if (fin - ini < 0.5) return;
  encCerrados.push({ ini, fin, zoom: DATA.limites_zoom.plano_cerrado, razon: "manual" });
  encSeleccion = null; encModificado = true; pintarEncuadre(); recalcularCurva();
});

document.getElementById("btnBorrarEnc").addEventListener("click", () => {
  if (!encSeleccion) return;
  if (encSeleccion.tipo === "punch") encPunch.splice(encSeleccion.i, 1);
  else encCerrados.splice(encSeleccion.i, 1);
  encSeleccion = null; encModificado = true; pintarEncuadre(); recalcularCurva();
});

document.getElementById("btnResetEnc").addEventListener("click", () => {
  const pe = DATA.plan_encuadre || { punch_ins: [], planos_cerrados: [] };
  encPunch = (pe.punch_ins || []).map(p => ({ t: p.t, razon: p.razon || "" }));
  encCerrados = (pe.planos_cerrados || []).map(c => ({
    ini: c.ini, fin: c.fin, zoom: c.zoom || DATA.limites_zoom.plano_cerrado, razon: c.razon || "",
  }));
  encModificado = false; encSeleccion = null; pintarEncuadre(); recalcularCurva();
});

// Clic en la pista (fuera de una barra) = mover el video ahi, para poder ver
// que esta pasando en pantalla en el segundo que se esta ajustando.
document.getElementById("pistaEnc").addEventListener("click", (ev) => {
  if (!DATA || ev.target.closest(".enc-cerrado") || ev.target.closest(".enc-punch")) return;
  video.currentTime = tiempoDesdeEvento(ev, ev.currentTarget);
});

// ---- Versiones con nombre --------------------------------------------------
// Una version es una copia de todos los ajustes.*.json en _versiones/<nombre>/.
// Sirve para probar dos montajes distintos del mismo video y volver al que
// gustara, sin tener que rehacerlo a mano.
function pintarVersiones(versiones) {
  const cont = document.getElementById("listaVersiones");
  cont.innerHTML = "";
  if (!versiones || !versiones.length) {
    cont.innerHTML = '<p class="hint">Todavía no hay ninguna versión guardada.</p>';
    return;
  }
  for (const v of versiones) {
    const fila = document.createElement("div");
    fila.className = "version-fila";
    const partes = [];
    if (v.insertos != null) partes.push(`${v.insertos} PiP`);
    if (v.broll != null) partes.push(`${v.broll} B-roll`);
    if (v.sfx != null) partes.push(`${v.sfx} sonidos`);
    if (v.animaciones != null) partes.push(`${v.animaciones} animaciones`);

    const info = document.createElement("div");
    info.innerHTML = `<b>${v.nombre}</b><br><span class="detalle">${v.fecha}` +
      `${partes.length ? " · " + partes.join(" · ") : ""}</span>`;
    fila.appendChild(info);

    const bCargar = document.createElement("button");
    bCargar.type = "button"; bCargar.textContent = "Cargar";
    bCargar.addEventListener("click", () => cargarVersion(v.nombre));
    fila.appendChild(bCargar);

    const bBorrar = document.createElement("button");
    bBorrar.type = "button"; bBorrar.textContent = "Borrar"; bBorrar.className = "quitar";
    bBorrar.addEventListener("click", async () => {
      if (!confirm(`¿Borrar la versión "${v.nombre}"?`)) return;
      const r = await fetch("/version/borrar", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre: v.nombre }),
      });
      pintarVersiones((await r.json()).versiones);
    });
    fila.appendChild(bBorrar);
    cont.appendChild(fila);
  }
}

async function refrescarVersiones() {
  try {
    const r = await fetch("/versiones");
    pintarVersiones((await r.json()).versiones);
  } catch (e) { /* sin versiones no se rompe nada */ }
}

document.getElementById("btnGuardarVersion").addEventListener("click", async () => {
  const caja = document.getElementById("nombreVersion");
  const nombre = caja.value.trim();
  if (!nombre) { caja.focus(); return; }
  // Lo que se guarda es lo que hay EN DISCO, asi que primero se vuelca el
  // estado actual del editor; si no, la version saldria con lo de antes.
  await guardarAhora(false);
  const r = await fetch("/version/guardar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nombre }),
  });
  const resp = await r.json();
  if (resp.ok) { caja.value = ""; pintarVersiones(resp.versiones); }
});

async function cargarVersion(nombre) {
  if (!confirm(`Cargar "${nombre}" reemplaza los ajustes actuales. ¿Seguir?`)) return;
  await guardarAhora(false);   // por si acaso: lo de ahora queda en disco
  const r = await fetch("/version/cargar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nombre }),
  });
  const resp = await r.json();
  if (!resp.ok) return;
  // Se recarga desde el servidor: los paneles se repueblan solos con los
  // ajustes de la version, igual que al abrir la corrida.
  ultimoGuardado = null;       // que el autoguardado no pise lo recien cargado
  await cargar();
  marcarGuardado(`versión «${nombre}» cargada`);
  if (resp.aviso) alert(resp.aviso);
}

// ---- Guardado automatico ---------------------------------------------------
// "Estoy editando y me tengo que ir": cerrar la pestaña no puede costar el
// trabajo. En vez de instrumentar cada sitio donde se toca algo —que es la
// forma de olvidarse de uno— se compara el estado entero cada par de segundos
// y se guarda solo si cambio de verdad.
let ultimoGuardado = null;   // se fija al terminar cargar(): asi abrir una
                             // corrida y no tocar nada NO crea ajustes.
let guardando = false;

function estadoSerializado() {
  return JSON.stringify({ ...cuerpoAjustes(), t: Math.round(video.currentTime * 10) / 10 });
}

function marcarGuardado(txt) {
  const el = document.getElementById("estadoGuardado");
  if (el) el.textContent = txt;
}

async function guardarAhora(auto = true) {
  if (guardando) return;
  const instantanea = estadoSerializado();
  if (auto && (ultimoGuardado === null || instantanea === ultimoGuardado)) return;
  guardando = true;
  try {
    const cuerpo = { ...cuerpoAjustes(), sesion: { t: video.currentTime } };
    const r = await fetch("/guardar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(cuerpo),
    });
    if ((await r.json()).ok) {
      ultimoGuardado = instantanea;
      const h = new Date();
      marcarGuardado(`guardado ${h.getHours()}:${String(h.getMinutes()).padStart(2, "0")}`);
    } else {
      marcarGuardado("no se pudo guardar");
    }
  } catch (e) {
    marcarGuardado("no se pudo guardar");
  } finally {
    guardando = false;
  }
}

setInterval(() => guardarAhora(true), 2000);

// Ultimo cartucho si se cierra la pestaña con algo sin guardar: sendBeacon
// sobrevive a la descarga de la pagina, un fetch normal no.
window.addEventListener("beforeunload", (e) => {
  if (ultimoGuardado === null || estadoSerializado() === ultimoGuardado) return;
  try {
    navigator.sendBeacon("/guardar", new Blob(
      [JSON.stringify({ ...cuerpoAjustes(), sesion: { t: video.currentTime } })],
      { type: "application/json" }));
  } catch (err) { /* si falla, al menos avisamos abajo */ }
  e.preventDefault();
  e.returnValue = "";
});

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

// Que archivo esta mirando el reproductor: "" = el render bueno, "preview" = el
// de prueba a media resolucion.
let fuenteVideo = "";

let sondeoRender = null;

async function iniciarRender(preview = false) {
  const btn = document.getElementById("btnRender");
  const btnP = document.getElementById("btnPreview");
  const caja = document.getElementById("cajaProgreso");
  const barra = document.getElementById("barraProgreso");
  const texto = document.getElementById("textoProgreso");

  const r = await fetch("/render", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...cuerpoAjustes(), preview }),
  });
  const resp = await r.json();
  if (!resp.ok) {
    texto.textContent = "No se pudo iniciar: " + (resp.error || "");
    caja.style.display = "";
    return;
  }

  btn.disabled = true;
  btnP.disabled = true;
  caja.style.display = "";
  barra.style.width = "0%";
  texto.textContent = preview ? "Previsualizando (media resolución)..." : "Renderizando el final...";

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
      btnP.disabled = false;
      if (est.ok) {
        barra.style.width = "100%";
        texto.textContent = "Listo — recargando...";
        // El preview vive en sus propios archivos, asi que hay que pedir esa
        // fuente: si no, el reproductor seguiria con el render anterior y
        // pareceria que los cambios no se aplicaron.
        fuenteVideo = preview ? "preview" : "";
        await cargar(); // recarga /datos y el <video src> con los cambios ya aplicados
        video.load();
        texto.textContent = preview
          ? "Previsualización lista (media resolución, sin publicar)."
          : "Render final listo y copiado a OneDrive.";
      } else {
        texto.textContent = "Error en el render — revisar " + (est.cola_log ? "el log" : "");
        console.error("Render falló:", est.cola_log);
      }
    }
  }, 1000);
}

document.getElementById("btnRender").addEventListener("click", () => iniciarRender(false));
document.getElementById("btnPreview").addEventListener("click", () => iniciarRender(true));

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

let sfxDisparados = new Set();

video.addEventListener("play", () => { sfxDisparados.clear(); });
video.addEventListener("seeking", () => { sfxDisparados.clear(); });

function construirTimeline() {
  const franjas = document.getElementById("franjas");
  const palabrasEl = document.getElementById("palabras");
  franjas.innerHTML = "";
  palabrasEl.innerHTML = "";
  const dur = DATA.duracion;

  // Renderizar B-rolls y PiPs en la pista de eventos
  for (const ov of edicionPip) {
    const div = document.createElement("div");
    const esVideo = ov.medio === "video" || ov.tipo === "broll";
    div.className = "franja" + (esVideo ? " video" : "");
    if (esVideo) div.style.background = "#8b5cf6";
    div.style.left = (ov.ini / dur * 100) + "%";
    div.style.width = Math.max(0.5, (ov.fin - ov.ini) / dur * 100) + "%";
    div.textContent = (esVideo ? "B-Roll: " : "PiP: ") + (ov.asset_id || ov.archivo?.split(/[\\/]/).pop() || ov.tipo);
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
  if (DATA && DATA.es_renderizado) {
    video.style.width = "100%";
    video.style.height = "100%";
    video.style.transform = "none";
    return;
  }
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
  const pct = (Math.min(1, t / dur) * 100) + "%";

  // Todas las agujas a la vez, por clase y no por id: cada pista dibuja la
  // suya con class="playhead", y enumerarlas una por una hacia que la pista
  // que se olvidara se quedara con la aguja clavada en el 0 (le paso a la de
  // PiP y B-Rolls). Una pista nueva ya la trae andando sin tocar esto.
  for (const ph of document.querySelectorAll(".playhead")) ph.style.left = pct;

  const cur = document.getElementById("curvaCursor");
  if (cur) {
    const x = Math.min(1, t / dur) * 1000;
    cur.setAttribute("x1", x); cur.setAttribute("x2", x);
  }
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
    pintarSubPreview(t);
    sincronizarMusicaPrevia();

    // Disparar efectos SFX en tiempo real si el video está reproduciéndose.
    // Si es_renderizado, los SFX ya están mezclados dentro del propio archivo
    // (07_FINAL.mp4 / 06_video.mp4) — dispararlos de nuevo aquí se oía dos
    // veces cada uno.
    if (!video.paused && !DATA.es_renderizado) {
      edicionSfx.forEach(e => {
        if (!sfxDisparados.has(e.id) && Math.abs(t - e.t) < 0.22) {
          sfxDisparados.add(e.id);
          escucharSfx(e.archivo, e.volumen || 1.0);
        }
      });
    }

    if (window.__tira) window.__tira.cursor(video.currentTime);
  }
  requestAnimationFrame(loop);
}

const btnSound = document.getElementById("btnSound");
const volumenVideo = document.getElementById("volumenVideo");
if (btnSound && volumenVideo) {
  btnSound.addEventListener("click", () => {
    video.muted = !video.muted;
    btnSound.textContent = video.muted ? "🔇 Activar Sonido" : "🔊 Desactivar Sonido";
  });
  volumenVideo.addEventListener("input", (e) => {
    video.volume = parseFloat(e.target.value);
    video.muted = (video.volume === 0);
    btnSound.textContent = video.muted ? "🔇 Activar Sonido" : "🔊 Desactivar Sonido";
  });
}

function alternarPlay() {
  const btn = document.getElementById("btnPlay");
  if (video.paused) { video.play(); btn.textContent = "⏸ Pausar"; }
  else { video.pause(); btn.textContent = "▶ Reproducir"; }
}
document.getElementById("btnPlay").addEventListener("click", alternarPlay);

// Espacio = reproducir/pausar desde cualquier parte del editor, que es lo que
// hace cualquier editor de video. Con dos cuidados: si se esta escribiendo
// (hook, nombre de version, casillas de segundos) el espacio es un espacio; y
// si el foco esta en un boton hay que quitarselo, o el navegador ademas lo
// pulsaria y el video se reproduciria y se pararia en el mismo golpe.
window.addEventListener("keydown", (e) => {
  if (e.code !== "Space" && e.key !== " ") return;
  if (e.ctrlKey || e.altKey || e.metaKey) return;
  const el = document.activeElement;
  if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" ||
             el.tagName === "SELECT" || el.isContentEditable)) return;
  e.preventDefault();          // si no, la pagina baja de golpe
  if (el && el.tagName === "BUTTON") el.blur();
  alternarPlay();
});

async function cargarProyectos() {
  try {
    const r = await fetch("/proyectos");
    const data = await r.json();
    const sel = document.getElementById("selProyecto");
    if (!sel) return;
    sel.innerHTML = "";
    (data.proyectos || []).forEach(p => {
      const opt = document.createElement("option");
      opt.value = p; opt.textContent = p;
      if (p === data.actual) opt.selected = true;
      sel.appendChild(opt);
    });
  } catch (e) {
    console.error("Error al cargar lista de proyectos:", e);
  }
}

const btnCargarProyecto = document.getElementById("btnCargarProyecto");
if (btnCargarProyecto) {
  btnCargarProyecto.addEventListener("click", async () => {
    const sel = document.getElementById("selProyecto");
    const nombre = sel ? sel.value : "";
    if (!nombre) return;
    btnCargarProyecto.disabled = true;
    btnCargarProyecto.textContent = "Cargando...";
    try {
      const r = await fetch("/cambiar-proyecto", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nombre }),
      });
      const res = await r.json();
      if (res.ok) {
        await cargar();
        video.src = "/video?t=" + Date.now() + (fuenteVideo ? "&fuente=" + fuenteVideo : "");
        video.load();
      } else {
        alert(res.error || "No se pudo cambiar de video.");
      }
    } catch (err) {
      alert("Error al cargar proyecto: " + err);
    } finally {
      btnCargarProyecto.disabled = false;
      btnCargarProyecto.textContent = "📁 Cargar";
    }
  });
}

cargarProyectos();
refrescarVersiones();
cargar();
</script>
<script src="/silencios.js"></script>
<script src="/tira.js"></script>
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
