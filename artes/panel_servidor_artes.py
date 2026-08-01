"""Panel de artes conectado — servidor local.

Hermano de `editor/panel_servidor.py`, no una extension suya. Se dejo aparte a
proposito: aquel son 642 lineas atadas a la estructura de PANEL-PRODUCCION.html
(posiciones de guion/fila, f0_preparar), y mezclarle rutas de artes haria mas
pesados y mas fragiles a los dos. Ademas se van a usar a la vez: el panel de
artes abierto mientras se renderiza un video.

Solo libreria estandar, igual que el otro. No agrega ni una dependencia: reusa
el venv que ya tiene PIL, rembg y onnxruntime.

    C:\\ai-video\\venv312\\Scripts\\python.exe artes/panel_servidor_artes.py
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from artes import a3_copy, a6_qwen, a8_conceptos, a9_prompts, a10_comfy  # noqa: E402
from artes.a1_marca import ESCENAS, FORMATOS, Arte, render  # noqa: E402
from artes.a2_recorte import FOTOS_AMAZON, recortar  # noqa: E402

PANEL = RAIZ / "PANEL-ARTES.html"
SALIDA = RAIZ / "salida" / "artes"
TRABAJO = Path(r"C:\ai-video\artes")
# Las dos mitades que Jose genera a mano en Gemini Studio (con los prompts de
# a9_prompts) se dejan caer aca. El boton "abrir carpeta" del panel abre esto.
SUBIR = TRABAJO / "subir"

# Estado de la corrida en curso. Un arte por vez: renderizar dos a la vez no
# aporta nada (el cuello es el recorte, que usa la GPU) y complica el log.
TRABAJOS: dict[str, dict] = {}


def _productos() -> list[dict]:
    """Productos con las fotos que hay de cada uno.

    El panel muestra las miniaturas para que Jose elija cual recortar. NO se
    adivina: se probo suponer que la `img2` era siempre el hero limpio y en el
    Kobo Libra esa foto era una infografia — el recorte salio con texto en
    ingles adentro.
    """
    por_producto: dict[str, list[str]] = {}
    for f in sorted(FOTOS_AMAZON.glob("fotos-amazon_*_img*.jpg")):
        resto = f.stem[len("fotos-amazon_"):]
        prod = resto.rsplit("_img", 1)[0]
        por_producto.setdefault(prod, []).append(f.name)
    return [
        {"clave": k, "fotos": v, "fichas": bool(a8_conceptos.FICHAS.get(k)),
         "copy": k in a3_copy.PRODUCTOS}
        for k, v in sorted(por_producto.items())
    ]


def _fotos_en(carpeta: Path) -> list[str]:
    if not carpeta.exists():
        return []
    exts = (".jpg", ".jpeg", ".png", ".webp")
    return sorted(f.name for f in carpeta.iterdir() if f.suffix.lower() in exts)


def _escena_qwen(tid: str, cfg: dict, concepto, origen: Path, paso) -> Path:
    """Genera (o reusa) el fondo con Qwen para el concepto elegido.

    Se cachea por (concepto, foto de origen): dos corridas del mismo par no
    vuelven a pagar los ~150-185s que tarda Qwen (medido en a10_comfy.py).
    """
    cache = TRABAJO / f"qwen-{concepto.clave}-{origen.stem}.png"
    if cache.exists():
        paso(f"escena IA ya generada, se reusa: {cache.name}")
        return cache

    if not a10_comfy.arrancar(avisar=paso):
        raise RuntimeError("ComfyUI no arranco — revisa C:\\ai-video\\comfy-artes.log")

    vram = a10_comfy.vram()
    if vram:
        usada, total = vram
        paso(f"VRAM: {usada} / {total} MiB")

    paso(f"generando escena con Qwen ({concepto.clave})... esto tarda 2-3 min")
    semilla = abs(hash(concepto.clave)) % (2**31)
    try:
        salida_comfy = a6_qwen.editar(origen, concepto.escena, semilla=semilla)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_bytes(salida_comfy.read_bytes())
    finally:
        # Docstring de a10_comfy.py: dejar ComfyUI prendido no ahorra tiempo
        # (el modelo no entra en 16GB igual) y le saca la GPU al pipeline de
        # video. Se apaga apenas termina, siempre.
        a10_comfy.apagar(avisar=paso)
    return cache


def _generar(tid: str, cfg: dict) -> None:
    log = TRABAJOS[tid]["log"]

    def paso(t: str) -> None:
        log.append(t)

    try:
        modo = cfg["modo"]
        concepto = a8_conceptos.por_clave(cfg["concepto"])
        titular = cfg.get("titular") or concepto.titular
        paso(f"concepto: {concepto.clave} · modo: {modo} · formato: {cfg['formato']}")

        if modo == "split":
            izq, der = cfg["split_izq"], cfg["split_der"]
            par = a9_prompts.SPLIT[cfg["comparativa"]]
            chip_izq = next((p.chip for p in par if p.clave.endswith("-mal")), "")
            chip_der = next((p.chip for p in par if p.clave.endswith("-bien")), "")
            paso(f"comparativa: {cfg['comparativa']} · {izq} / {der}")
            arte = Arte(
                titular=titular,
                producto=cfg["nombre"],
                escena=cfg.get("escena", "navy"),
                formato=cfg["formato"],
                sello=cfg.get("sello", ""),
                split=(SUBIR / izq, chip_izq, SUBIR / der, chip_der),
            )
        else:
            paso(f"foto: {cfg['foto']}")
            origen = FOTOS_AMAZON / cfg["foto"]
            recorte = TRABAJO / f"{Path(cfg['foto']).stem}-recorte.png"
            if not recorte.exists():
                paso("recortando el fondo (rembg isnet-general-use)...")
                recortar(origen, recorte)
            else:
                paso("recorte ya existente, se reusa")

            foto_fondo = None
            if cfg.get("foto_gemini"):
                foto_gemini_path = SUBIR / Path(cfg["foto_gemini"]).name
                if foto_gemini_path.exists():
                    paso(f"usando fondo generado con Gemini: {foto_gemini_path.name}")
                    foto_fondo = foto_gemini_path
                else:
                    paso(f"aviso: foto de Gemini {cfg['foto_gemini']} no encontrada en subir/, se usa fondo por defecto")
            elif cfg.get("qwen_escena"):
                foto_fondo = _escena_qwen(tid, cfg, concepto, origen, paso)

            # En vertical el lienzo gana ~840px de alto que el bloque de texto y
            # el pie NO usan (su tamano sale de ancho, no de alto — ver
            # a1_marca.py). Con los mismos % que cuadrado el producto quedaba
            # chico y sobraba aire arriba y abajo (medido 2026-08-01, ver
            # salida/artes/_test-formato-vertical*.jpg). Se agranda y se sube el
            # centro para que ocupe el mismo hueco visual que en cuadrado.
            vertical = cfg["formato"] == "vertical"
            arte = Arte(
                titular=titular,
                producto=cfg["nombre"],
                escena=cfg["escena"],
                foto_fondo=foto_fondo,
                recorte=recorte,
                recorte_alto=(60 if modo == "limpio" else 48) if vertical
                             else (44 if modo == "limpio" else 38),
                recorte_y=(52 if modo == "limpio" else 54) if vertical else 57,
                recorte_x=(50 if modo == "limpio" else 66) if vertical
                          else (50 if modo == "limpio" else 79),
                formato=cfg["formato"],
                sello=cfg.get("sello", ""),
                fichas=(a8_conceptos.FICHAS.get(cfg["producto"], [])
                        if modo == "fichas" else []),
                fichas_vidrio=bool(cfg.get("vidrio")),
                dolores=(a8_conceptos.DOLORES[:min(int(cfg.get("n_dolores", 3)),
                                                     len(a8_conceptos.DOLORES))]
                         if modo == "dolores" else []),
            )

        nombre = f"{cfg['producto']}-{concepto.clave}-{modo}.jpg"
        paso("renderizando (Chrome headless, 2x y bajado con LANCZOS)...")
        destino = render(arte, SALIDA / nombre)

        # Bug corregido 2026-08-01: antes se llamaba siempre con PAPERWHITE sin
        # importar el producto elegido — publicaba el copy equivocado. Ahora,
        # si el producto todavia no tiene copy verificado (caso del accesorio
        # kobo-stylus, ver a3_copy.PRODUCTOS), se avisa en el log en vez de
        # tirar el arte ya renderizado a la basura.
        copys = None
        try:
            paso("generando las 3 variantes de copy...")
            copys = a3_copy.variantes(a3_copy.por_clave(cfg["producto"]))
            (SALIDA / f"{destino.stem}.copys.json").write_text(
                json.dumps(copys, ensure_ascii=False), encoding="utf-8"
            )
        except KeyError as e:
            paso(f"sin copy verificado para este producto ({e}) — el arte se generó igual")

        TRABAJOS[tid].update(estado="listo", arte=destino.name, copys=copys)
        paso(f"LISTO: {destino.name}")
    except Exception:
        TRABAJOS[tid]["estado"] = "error"
        log.append("ERROR:\n" + traceback.format_exc())


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # silencia el log de acceso
        pass

    def _json(self, datos, codigo=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def _bytes(self, datos: bytes, tipo: str):
        self.send_response(200)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _miniatura_de(self, carpeta: Path, q: dict):
        from PIL import Image
        f = carpeta / Path(q["f"][0]).name
        if not f.exists():
            return self._json({"error": "no existe"}, 404)
        with Image.open(f) as im:
            im = im.convert("RGB")
            im.thumbnail((260, 260), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=82)
        return self._bytes(buf.getvalue(), "image/jpeg")

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)

        if u.path in ("/", "/PANEL-ARTES.html"):
            return self._bytes(PANEL.read_bytes(), "text/html; charset=utf-8")

        if u.path == "/api/estado":
            return self._json({
                "ok": True,
                "productos": _productos(),
                "conceptos": [
                    {"clave": c.clave, "titular": c.titular, "modo": c.modo,
                     "nota": c.nota}
                    for c in a8_conceptos.CONCEPTOS
                ],
                "escenas": list(ESCENAS),
                "formatos": list(FORMATOS),
                "confianza": a8_conceptos.CONFIANZA,
                "n_dolores_max": len(a8_conceptos.DOLORES),
                "prompts": {k: [vars(p) for p in v]
                            for k, v in a9_prompts.SPLIT.items()},
            })

        if u.path == "/api/miniatura":
            return self._miniatura_de(FOTOS_AMAZON, q)

        if u.path == "/api/subir-miniatura":
            return self._miniatura_de(SUBIR, q)

        if u.path == "/api/subir-fotos":
            return self._json({"fotos": _fotos_en(SUBIR)})

        if u.path == "/api/abrir-subir":
            SUBIR.mkdir(parents=True, exist_ok=True)
            try:
                import subprocess
                subprocess.run(["explorer.exe", str(SUBIR)], check=False)
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        if u.path == "/api/abrir-foto-base":
            f = q.get("f", [""])[0]
            ruta = FOTOS_AMAZON / f if f else FOTOS_AMAZON
            target = ruta if ruta.exists() else FOTOS_AMAZON
            try:
                import subprocess
                if target.is_file():
                    subprocess.run(["explorer.exe", f"/select,{target}"], check=False)
                else:
                    subprocess.run(["explorer.exe", str(target)], check=False)
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 500)

        if u.path == "/api/comfy":
            return self._json({"vivo": a10_comfy.vivo(), "vram": a10_comfy.vram()})

        if u.path == "/api/arte":
            f = SALIDA / Path(q["f"][0]).name
            if not f.exists():
                return self._json({"error": "no existe"}, 404)
            return self._bytes(f.read_bytes(), "image/jpeg")

        if u.path == "/api/historial":
            items = []
            for f in sorted(SALIDA.glob("*.jpg"), key=lambda p: p.stat().st_mtime,
                             reverse=True)[:40]:
                sidecar = SALIDA / f"{f.stem}.copys.json"
                items.append({
                    "arte": f.name,
                    "tiene_copy": sidecar.exists(),
                })
            return self._json({"items": items})

        if u.path == "/api/historial-copys":
            f = SALIDA / Path(q["f"][0]).name
            sidecar = SALIDA / f"{f.stem}.copys.json"
            if not sidecar.exists():
                return self._json({"copys": None})
            return self._json({"copys": json.loads(sidecar.read_text(encoding="utf-8"))})

        if u.path == "/api/trabajo":
            t = TRABAJOS.get(q["id"][0])
            return self._json(t or {"estado": "desconocido"})

        self.send_error(404)

    def do_POST(self):
        u = urlparse(self.path)

        if u.path == "/api/comfy/encender":
            avisos: list[str] = []
            ok = a10_comfy.arrancar(avisar=avisos.append)
            return self._json({"ok": ok, "log": avisos, "vram": a10_comfy.vram()})

        if u.path == "/api/comfy/apagar":
            avisos: list[str] = []
            a10_comfy.apagar(avisar=avisos.append)
            return self._json({"ok": True, "log": avisos})

        if u.path != "/api/generar":
            return self.send_error(404)
        n = int(self.headers.get("Content-Length", 0))
        cfg = json.loads(self.rfile.read(n).decode("utf-8"))
        tid = f"t{len(TRABAJOS) + 1}"
        TRABAJOS[tid] = {"estado": "corriendo", "log": []}
        threading.Thread(target=_generar, args=(tid, cfg), daemon=True).start()
        return self._json({"id": tid})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--puerto", type=int, default=8791)
    ap.add_argument("--sin-abrir", action="store_true")
    a = ap.parse_args()

    SALIDA.mkdir(parents=True, exist_ok=True)
    TRABAJO.mkdir(parents=True, exist_ok=True)
    SUBIR.mkdir(parents=True, exist_ok=True)

    s = ThreadingHTTPServer(("127.0.0.1", a.puerto), Handler)
    url = f"http://127.0.0.1:{a.puerto}/"
    print(f"Panel de artes en {url}  (Ctrl+C para salir)")
    if not a.sin_abrir:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        s.serve_forever()
    except KeyboardInterrupt:
        print("\ncerrado")


if __name__ == "__main__":
    main()
