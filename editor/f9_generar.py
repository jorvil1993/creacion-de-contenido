"""
Fase 6 — Generación de imágenes en la GPU (ComfyUI + Flux.1-schnell GGUF).

Hasta ahora la GPU generaba CERO imágenes por video: ComfyUI estaba instalado y
Flux descargado, pero nada en `editor/` lo invocaba. Este módulo cierra ese
hueco.

Cómo encaja en el pipeline (importante — no es "genera todo con IA"):

    1. El guion nombra un concepto  ->  se busca en el catálogo de fotos REALES
    2. Si el catálogo no tiene nada ->  se genera aquí con Flux
    3. Si la imagen no convence     ->  el prompt queda listo en
                                        contexto/prompts-externos.md para
                                        pegarlo en Google Flow / Nano Banana

Para el PRODUCTO siempre gana la foto real: la sesión B verificó que Flux
produce un e-reader genérico creíble, no un Kindle. Flux sirve para ambientes y
conceptos (agua, viaje, noche, café...), que es justo lo que ninguna foto del
catálogo cubre.

Render reproducible: la semilla se deriva del hash del prompt, no es aleatoria.
El mismo prompt da siempre la misma imagen, y además queda cacheada.

⚠️ GOTCHA DOCUMENTADO (BITACORA-B, punto 8): lanzar ComfyUI con
`subprocess.Popen(stdout=PIPE)` lo CUELGA — imprime el banner y ~150 tipos de
nodo al arrancar, nadie lee el pipe, se llena el buffer del sistema operativo y
el hijo se bloquea en el primer write(). Por eso stdout/stderr van a un ARCHIVO.

Uso:
    python f9_generar.py --estado
    python f9_generar.py --tag "#agua"
    python f9_generar.py --prompt "close-up of water droplets" --nombre agua
    python f9_generar.py --prompts-externos      # solo reescribe el .md
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

import config

BASE = f"http://127.0.0.1:{config.COMFY_PUERTO}"
LOG_SERVIDOR = config.RAIZ_AI_VIDEO / "comfyui-servidor.log"
INDICE = config.DIR_GENERADO_AUTO / "_indice.json"


def _log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Servidor de ComfyUI: se levanta bajo demanda y se apaga al terminar
# ---------------------------------------------------------------------------
def servidor_vivo(timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(f"{BASE}/system_stats", timeout=timeout):
            return True
    except Exception:
        return False


def instalado() -> bool:
    """¿Están ComfyUI, su venv y el modelo donde se espera?"""
    if not (config.COMFY_PYTHON.exists() and config.COMFY_MAIN.exists()):
        return False
    unet = config.DIR_COMFYUI / "models" / "unet" / config.COMFY_UNET_GGUF
    return unet.exists()


class Servidor:
    """Context manager: arranca ComfyUI si hace falta y lo apaga al salir.

    Si ya había un ComfyUI corriendo (José lo abrió a mano), se reutiliza y
    NO se lo apaga al terminar — apagarle el servidor por debajo sería grosero
    y además perdería su trabajo.
    """

    def __init__(self):
        self.proc = None
        self.era_ajeno = False

    def __enter__(self):
        if servidor_vivo():
            self.era_ajeno = True
            _log("  ComfyUI ya estaba corriendo: se reutiliza.")
            return self
        if not instalado():
            raise RuntimeError(
                f"ComfyUI no está instalado donde se espera ({config.DIR_COMFYUI}). "
                "Ver contexto/BITACORA-B.md punto 8."
            )

        cmd = [str(config.COMFY_PYTHON), str(config.COMFY_MAIN),
               "--port", str(config.COMFY_PUERTO),
               "--listen", "127.0.0.1",
               "--disable-auto-launch"]
        _log(f"  Arrancando ComfyUI (log: {LOG_SERVIDOR})...")
        t0 = time.time()
        # stdout/stderr a un ARCHIVO, nunca a un pipe sin lector — ver el
        # gotcha del docstring de este módulo.
        self._flog = open(LOG_SERVIDOR, "wb")
        self.proc = subprocess.Popen(
            cmd, cwd=str(config.DIR_COMFYUI),
            stdin=subprocess.DEVNULL, stdout=self._flog, stderr=self._flog,
        )

        limite = time.time() + config.COMFY_ARRANQUE_TIMEOUT_S
        while time.time() < limite:
            if self.proc.poll() is not None:
                cola = LOG_SERVIDOR.read_text(encoding="utf-8", errors="replace")[-1500:]
                raise RuntimeError(f"ComfyUI murió al arrancar:\n{cola}")
            if servidor_vivo():
                _log(f"  ComfyUI listo en {time.time() - t0:.1f}s")
                return self
            time.sleep(1.0)

        self.__exit__(None, None, None)
        raise RuntimeError(f"ComfyUI no respondió en {config.COMFY_ARRANQUE_TIMEOUT_S}s "
                           f"(ver {LOG_SERVIDOR})")

    def __exit__(self, *exc):
        if self.proc is not None and not self.era_ajeno:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            _log("  ComfyUI apagado (VRAM liberada).")
        flog = getattr(self, "_flog", None)
        if flog is not None and not flog.closed:
            flog.close()
        return False


class ServidorCompartido:
    """Un solo arranque de ComfyUI para todas las imágenes de un video.

    Arrancar el servidor cuesta ~40s (importa torch y registra ~150 nodos) y la
    primera imagen paga además la carga de 13 GB de modelos a la VRAM. Pagar eso
    por CADA imagen sería absurdo. Y como arranca *perezosamente*, un video cuyas
    imágenes están todas en caché no lo levanta nunca: cuesta cero.
    """

    def __init__(self):
        self._servidor = None

    def usar(self) -> Servidor:
        if self._servidor is None:
            self._servidor = Servidor().__enter__()
        return self._servidor

    def cerrar(self):
        if self._servidor is not None:
            self._servidor.__exit__(None, None, None)
            self._servidor = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.cerrar()
        return False


# ---------------------------------------------------------------------------
# Workflow en formato API
# ---------------------------------------------------------------------------
# El JSON de assets/comfyui-workflows/ está en formato de INTERFAZ (nodes/links,
# el que guarda el navegador). El endpoint /prompt necesita el formato API
# (id -> class_type + inputs). Se construye aquí a partir de los mismos nodos y
# valores de ese archivo; los nombres de cada input se verificaron leyendo el
# código instalado (nodes.py, comfy_extras/nodes_flux.py y el custom node
# ComfyUI-GGUF), no de memoria.
def workflow_api(prompt: str, semilla: int, ancho: int, alto: int, prefijo: str) -> dict:
    return {
        "38": {"class_type": "UnetLoaderGGUF",
               "inputs": {"unet_name": config.COMFY_UNET_GGUF}},
        "40": {"class_type": "DualCLIPLoader",
               "inputs": {"clip_name1": config.COMFY_CLIP_L,
                          "clip_name2": config.COMFY_T5,
                          "type": "flux", "device": "default"}},
        "39": {"class_type": "VAELoader",
               "inputs": {"vae_name": config.COMFY_VAE}},
        "27": {"class_type": "EmptySD3LatentImage",
               "inputs": {"width": ancho, "height": alto, "batch_size": 1}},
        "41": {"class_type": "CLIPTextEncodeFlux",
               "inputs": {"clip": ["40", 0], "clip_l": prompt, "t5xxl": prompt,
                          "guidance": config.COMFY_GUIDANCE}},
        "42": {"class_type": "ConditioningZeroOut",
               "inputs": {"conditioning": ["41", 0]}},
        "31": {"class_type": "KSampler",
               "inputs": {"model": ["38", 0], "positive": ["41", 0],
                          "negative": ["42", 0], "latent_image": ["27", 0],
                          "seed": semilla, "steps": config.COMFY_PASOS,
                          "cfg": config.COMFY_CFG,
                          "sampler_name": config.COMFY_SAMPLER,
                          "scheduler": config.COMFY_SCHEDULER, "denoise": 1.0}},
        "8": {"class_type": "VAEDecode",
              "inputs": {"samples": ["31", 0], "vae": ["39", 0]}},
        "9": {"class_type": "SaveImage",
              "inputs": {"images": ["8", 0], "filename_prefix": prefijo}},
    }


def _post_json(ruta: str, datos: dict) -> dict:
    cuerpo = json.dumps(datos).encode("utf-8")
    req = urllib.request.Request(f"{BASE}{ruta}", data=cuerpo,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _get_json(ruta: str) -> dict:
    with urllib.request.urlopen(f"{BASE}{ruta}", timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _semilla_de(texto: str) -> int:
    """Semilla determinista: el mismo prompt produce siempre la misma imagen.

    El plan exige render reproducible, así que no se usa `random`."""
    return int(hashlib.sha1(texto.encode("utf-8")).hexdigest()[:12], 16)


def _clave(prompt: str, ancho: int, alto: int) -> str:
    crudo = f"{prompt}|{ancho}x{alto}|{config.COMFY_PASOS}|{config.COMFY_UNET_GGUF}"
    return hashlib.sha1(crudo.encode("utf-8")).hexdigest()[:12]


def _slug(texto: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-")
    return (s[:40] or "img").rstrip("-")


# ---------------------------------------------------------------------------
# Índice de lo generado (alimenta también contexto/prompts-externos.md)
# ---------------------------------------------------------------------------
def _leer_indice() -> dict:
    if INDICE.exists():
        try:
            return json.loads(INDICE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _guardar_indice(indice: dict):
    config.DIR_GENERADO_AUTO.mkdir(parents=True, exist_ok=True)
    INDICE.write_text(json.dumps(indice, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Generación
# ---------------------------------------------------------------------------
def _esperar_resultado(prompt_id: str, timeout: float) -> list:
    limite = time.time() + timeout
    while time.time() < limite:
        try:
            hist = _get_json(f"/history/{prompt_id}")
        except urllib.error.URLError:
            hist = {}
        entrada = hist.get(prompt_id)
        if entrada:
            estado = entrada.get("status", {})
            if estado.get("status_str") == "error" or estado.get("completed") is False:
                raise RuntimeError(f"ComfyUI reportó error: {estado}")
            imagenes = []
            for salida in entrada.get("outputs", {}).values():
                imagenes += salida.get("images", [])
            if imagenes:
                return imagenes
        time.sleep(1.0)
    raise TimeoutError(f"ComfyUI no terminó en {timeout:.0f}s")


def _descargar(imagen: dict, destino: Path):
    q = urllib.parse.urlencode({"filename": imagen["filename"],
                                "subfolder": imagen.get("subfolder", ""),
                                "type": imagen.get("type", "output")})
    with urllib.request.urlopen(f"{BASE}/view?{q}", timeout=120) as r:
        destino.write_bytes(r.read())


def generar(prompt: str, nombre: str = None, tag: str = None,
            ancho: int = None, alto: int = None,
            servidor: "ServidorCompartido" = None) -> Path | None:
    """Genera una imagen (o devuelve la cacheada) y la ruta donde quedó.

    `servidor`: pasar un ServidorCompartido para que varias imágenes del mismo
    video reutilicen un solo arranque de ComfyUI. Si no se pasa, cada llamada
    levanta y apaga el suyo.
    """
    ancho = ancho or config.COMFY_ANCHO
    alto = alto or config.COMFY_ALTO
    texto = f"{prompt}, {config.PROMPT_ESTILO}"
    clave = _clave(texto, ancho, alto)
    nombre = nombre or _slug(tag or prompt)

    config.DIR_GENERADO_AUTO.mkdir(parents=True, exist_ok=True)
    destino = config.DIR_GENERADO_AUTO / f"{nombre}_{clave}.png"

    indice = _leer_indice()
    if destino.exists() and destino.stat().st_size > 1024:
        _log(f"  [caché] {destino.name}")
        return destino

    if not instalado():
        _log("AVISO: ComfyUI no está instalado — no se puede generar.")
        return None

    propio = servidor is None
    servidor = servidor or ServidorCompartido()
    try:
        servidor.usar()
        semilla = _semilla_de(texto)
        wf = workflow_api(texto, semilla, ancho, alto, f"deviceshop-auto/{nombre}")
        t0 = time.time()
        respuesta = _post_json("/prompt", {"prompt": wf, "client_id": str(uuid.uuid4())})
        prompt_id = respuesta.get("prompt_id")
        if not prompt_id:
            _log(f"AVISO: ComfyUI rechazó el workflow: {respuesta}")
            return None
        imagenes = _esperar_resultado(prompt_id, config.COMFY_GENERACION_TIMEOUT_S)
        _descargar(imagenes[0], destino)
        _log(f"  generada en {time.time() - t0:.1f}s -> {destino.name}")
    except Exception as e:
        _log(f"AVISO: falló la generación de '{nombre}': {e}")
        return None
    finally:
        if propio:
            servidor.cerrar()

    indice[clave] = {
        "archivo": str(destino.relative_to(config.RAIZ_PROYECTO)).replace("\\", "/"),
        "prompt": texto,
        "tag": tag or "",
        "nombre": nombre,
        "semilla": _semilla_de(texto),
        "tamano": f"{ancho}x{alto}",
    }
    _guardar_indice(indice)
    escribir_prompts_externos()
    return destino


def prompt_para_tag(tag: str, contexto_guion: str = "") -> str | None:
    """Prompt derivado del GUION: base del concepto + lo que José dijo alrededor.

    Sin el contexto, dos videos que mencionan "agua" producirían exactamente la
    misma imagen. Con él, el prompt (y por lo tanto la semilla, y por lo tanto
    la imagen) cambia con el guion.
    """
    base = config.PROMPTS_POR_TAG.get(tag)
    if not base:
        return None
    frase = " ".join(contexto_guion.split())[:110].strip(" ,.")
    return f"{base}, scene inspired by: {frase}" if frase else base


def generar_para_tag(tag: str, contexto_guion: str = "",
                     servidor: "ServidorCompartido" = None) -> Path | None:
    """Imagen para una etiqueta. Prioridad: la que puso José a mano > Flux.

    La versión manual gana siempre: si a José no le convenció lo que salió de
    Flux y la rehizo en Google Flow o Nano Banana, esa es la buena
    (ver contexto/prompts-externos.md).
    """
    manual = version_manual(tag)
    if manual is not None:
        _log(f"  [manual] {manual.name} para {tag}")
        return manual
    prompt = prompt_para_tag(tag, contexto_guion)
    if prompt is None:
        return None
    return generar(prompt, nombre=_slug(tag.lstrip("#")), tag=tag, servidor=servidor)


# ---------------------------------------------------------------------------
# Prompts para generadores externos (pedido explícito de José)
# ---------------------------------------------------------------------------
def escribir_prompts_externos(pendientes: list = None):
    """Deja los prompts listos para pegar en Google Flow / Nano Banana.

    Dos casos: (a) la imagen generada por Flux no convence y José quiere
    rehacerla con otra herramienta, (b) el concepto no tiene prompt en la tabla
    y Flux no lo intentó siquiera. En ambos, lo que hace falta es el prompt
    exacto y la carpeta donde dejar el archivo para que el pipeline lo levante.
    """
    indice = _leer_indice()
    ruta = config.DIR_CONTEXTO / "prompts-externos.md"
    rel_manual = "assets/generado/manual"

    L = [
        "# Prompts para generadores externos",
        "",
        "*(Archivo generado por `editor/f9_generar.py` — se reescribe solo en cada",
        "corrida que genere imágenes. No editar a mano: los cambios se pierden.)*",
        "",
        "Si una imagen generada por Flux no te convence, acá tienes el prompt exacto",
        "para pegarlo en **Google Flow**, **Nano Banana** o cualquier otro generador,",
        "y la ruta donde dejar el resultado para que el pipeline lo use.",
        "",
        "## Cómo reemplazar una imagen",
        "",
        f"1. Genera la imagen donde quieras con el prompt de abajo.",
        f"2. Guárdala como **PNG o JPG** en `{rel_manual}/` con el nombre que dice la tabla.",
        "3. Vuelve a correr el pipeline. La versión manual **gana siempre** sobre la",
        "   generada por Flux — no hace falta borrar nada ni pasar ninguna opción.",
        "",
        "> Formato recomendado: vertical, alrededor de "
        f"{config.COMFY_ANCHO}×{config.COMFY_ALTO} px. Se recorta al centro para la",
        "> tarjeta del inserto, así que deja el motivo centrado.",
        "",
    ]

    if indice:
        # Agrupado por concepto, no por imagen: el reemplazo manual es UNO por
        # etiqueta (`manual/<etiqueta>.png`), así que listar dos entradas del
        # mismo concepto apuntando al mismo archivo se leía como un error.
        # Un mismo concepto puede tener varias imágenes porque el prompt
        # incorpora la frase del guion, y esa cambia en cada momento del video.
        por_nombre = {}
        for datos in indice.values():
            por_nombre.setdefault(datos["nombre"], []).append(datos)

        L += ["## Imágenes generadas en este proyecto", ""]
        for nombre in sorted(por_nombre):
            grupo = sorted(por_nombre[nombre], key=lambda d: d["archivo"])
            tag = next((g["tag"] for g in grupo if g["tag"]), "")
            L += [
                f"### {nombre}" + (f"  ·  etiqueta `{tag}`" if tag else ""),
                "",
                f"- **Para reemplazarla, guarda tu versión en:** `{rel_manual}/{nombre}.png`",
                "  (una sola imagen por concepto; sustituye a todas las de abajo)",
                "",
            ]
            if len(grupo) > 1:
                L += [f"Flux generó {len(grupo)} variantes de este concepto, porque el prompt "
                      "incluye la frase del guion y esa cambia en cada momento del video. "
                      "Elige el prompt que más te sirva:", ""]
            for g in grupo:
                L += [
                    f"- `{g['archivo']}` · semilla `{g['semilla']}` · {g['tamano']}",
                    "",
                    "```text",
                    g["prompt"],
                    "```",
                    "",
                ]

    if pendientes:
        L += ["## Conceptos SIN imagen (ni catálogo ni Flux)", "",
              "El guion los nombró, no hay foto real y tampoco hay un prompt definido",
              "para ellos en `config.PROMPTS_POR_TAG`. Si quieres que aparezcan,",
              "genera la imagen externamente y déjala en la ruta indicada.", ""]
        for tag, frase in pendientes:
            nombre = _slug(tag.lstrip("#"))
            L += [
                f"### etiqueta `{tag}`",
                "",
                f"- Se dijo: *\"{frase}\"*",
                f"- **Guarda tu imagen en:** `{rel_manual}/{nombre}.png`",
                "",
                "```text",
                f"{tag.lstrip('#')} concept image, {config.PROMPT_ESTILO}",
                "```",
                "",
            ]

    (config.DIR_ASSETS / "generado" / "manual").mkdir(parents=True, exist_ok=True)
    ruta.write_text("\n".join(L), encoding="utf-8")
    return ruta


def version_manual(tag: str) -> Path | None:
    """Imagen puesta a mano por José para esta etiqueta (gana sobre Flux)."""
    dir_manual = config.DIR_GENERADO / "manual"
    if not dir_manual.is_dir():
        return None
    nombre = _slug(tag.lstrip("#"))
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        cand = dir_manual / f"{nombre}{ext}"
        if cand.exists():
            return cand
    return None


def main():
    ap = argparse.ArgumentParser(description="Generación de imágenes con ComfyUI + Flux")
    ap.add_argument("--estado", action="store_true", help="Diagnóstico de la instalación")
    ap.add_argument("--prompt", type=str, default=None)
    ap.add_argument("--tag", type=str, default=None, help="Etiqueta del catálogo, ej. '#agua'")
    ap.add_argument("--guion", type=str, default="", help="Contexto del guion para el prompt")
    ap.add_argument("--nombre", type=str, default=None)
    ap.add_argument("--prompts-externos", action="store_true",
                    help="Solo reescribe contexto/prompts-externos.md")
    args = ap.parse_args()

    if args.estado:
        print(f"ComfyUI instalado:   {instalado()}")
        print(f"  python venv-comfy: {config.COMFY_PYTHON} ({config.COMFY_PYTHON.exists()})")
        print(f"  main.py:           {config.COMFY_MAIN} ({config.COMFY_MAIN.exists()})")
        unet = config.DIR_COMFYUI / "models" / "unet" / config.COMFY_UNET_GGUF
        print(f"  modelo:            {unet.name} ({unet.exists()})")
        print(f"  servidor vivo:     {servidor_vivo()}")
        print(f"  caché:             {config.DIR_GENERADO_AUTO} "
              f"({len(list(config.DIR_GENERADO_AUTO.glob('*.png'))) if config.DIR_GENERADO_AUTO.exists() else 0} imágenes)")
        print(f"  etiquetas con prompt: {', '.join(sorted(config.PROMPTS_POR_TAG))}")
        return

    if args.prompts_externos:
        print(f"-> {escribir_prompts_externos()}")
        return

    if args.tag:
        ruta = generar_para_tag(args.tag, args.guion)
    elif args.prompt:
        ruta = generar(args.prompt, nombre=args.nombre)
    else:
        ap.error("indica --tag, --prompt, --estado o --prompts-externos")
        return

    print(f"-> {ruta}" if ruta else "-> falló")
    sys.exit(0 if ruta else 1)


if __name__ == "__main__":
    main()
