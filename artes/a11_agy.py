"""Puente a Antigravity CLI (`agy`) en modo headless, para redactar copy y
prompts de imagen con un LLM en vez de rellenar plantillas fijas.

Por que agy y no la API de Anthropic/OpenAI: es la CLI que Jose ya tiene
instalada y logueada con su cuenta de Google AI Pro (ver contexto/PLAN-ARTES.md
y la conversacion que instalo esto el 2026-08-03) -- sin key de API aparte, sin
facturacion por separado, sin modelo local. Cada llamada gasta de esa misma
cuota, la que usa interactivamente.

`agy` no guarda memoria entre llamadas: cada `-p` es un proceso nuevo. Para que
el boton "regenerar con correccion" del panel no tenga que repetir todo el
contexto de negocio, se reusa `--conversation <id>` (el id que devuelve la
llamada anterior) y se manda solo la correccion.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

_INSTALL_POR_DEFECTO = Path(os.environ.get("LOCALAPPDATA", "")) / "agy" / "bin" / "agy.exe"

# agy escribe cada corrida en su propio log (cli.log siempre apunta a la mas
# reciente). Encontrado 2026-08-03: cuando el fallo es por cuota (429
# RESOURCE_EXHAUSTED), el JSON de --output-format json NO trae ese detalle --
# solo dice algo generico como "Image failed to generate." -- pero el log SI
# tiene el mensaje real y hasta cuando se resetea la cuota.
_LOG_AGY = Path.home() / ".gemini" / "antigravity-cli" / "cli.log"

# Cache propio de agy: cada conversacion deja sus archivos generados en una
# carpeta con su mismo conversation_id (confirmado 2026-08-03, ver
# panel-artes-integracion-agy.md). Generar una imagen ahi NO pide permiso;
# lo que SI pide permiso es que agy la mueva el mismo con un comando de
# PowerShell -- por eso la copiamos nosotros con shutil, sin pedirle nada.
_BRAIN = Path.home() / ".gemini" / "antigravity-cli" / "brain"


def _binario() -> str:
    en_path = shutil.which("agy")
    if en_path:
        return en_path
    if _INSTALL_POR_DEFECTO.exists():
        return str(_INSTALL_POR_DEFECTO)
    raise RuntimeError(
        "No se encontro agy.exe (ni en PATH ni en "
        f"{_INSTALL_POR_DEFECTO}). Antigravity CLI no esta instalado, o el "
        "proceso que corre el panel arranco antes de que el PATH se actualizara."
    )


def disponible() -> bool:
    try:
        _binario()
        return True
    except RuntimeError:
        return False


def _causa_real_si_es_cuota() -> str | None:
    """Lee el log de la corrida que acaba de terminar (cli.log siempre es la
    mas reciente, un proceso nuevo por cada llamada) y, si el fallo fue por
    cuota agotada, devuelve el mensaje real de Google con el tiempo de reset.
    Si no hay rastro de cuota en el log, devuelve None -- no inventa una causa.
    """
    try:
        texto = _LOG_AGY.read_text(encoding="utf-8", errors="replace")[-6000:]
    except OSError:
        return None
    if "RESOURCE_EXHAUSTED" not in texto and "QUOTA_EXHAUSTED" not in texto:
        return None
    mensaje = re.search(r'"message":\s*"([^"]+)"', texto)
    reset = re.search(r'"quotaResetTimeStamp":\s*"([^"]+)"', texto)
    partes = [mensaje.group(1) if mensaje else "cuota agotada (RESOURCE_EXHAUSTED)"]
    if reset:
        partes.append(f"reset: {reset.group(1)}")
    return " -- ".join(partes)


def generar(prompt: str, conversation_id: str | None = None,
            timeout: int = 150, modelo: str | None = None) -> tuple[str, str]:
    """Manda `prompt` a agy en modo headless. Devuelve (texto, conversation_id).

    Si `conversation_id` viene, continua esa conversacion en vez de arrancar
    una nueva -- agy ya tiene el prompt y la respuesta anteriores en contexto.

    `modelo` es opcional -- si no viene, agy usa su propio default (no lo
    elegimos). Solo afecta al modelo de TEXTO/razonamiento: la cuota de
    Google es por modelo (confirmado 2026-08-03 en el mensaje de error de
    RESOURCE_EXHAUSTED, "exhausted your capacity on THIS model"), asi que
    forzar otro (ej. "claude-sonnet-4-6") puede seguir funcionando aunque el
    default de Gemini este sin cuota. Ver `agy models` para la lista completa.
    Generar IMAGENES no tiene este control -- esa herramienta siempre pega
    contra un modelo de imagen fijo de Google sin importar este flag.
    """
    cmd = [_binario(), "-p", prompt, "--output-format", "json",
           "--disable-slash-commands"]
    if conversation_id:
        cmd += ["--conversation", conversation_id]
    if modelo:
        cmd += ["--model", modelo]

    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"agy no respondio en {timeout}s")
    except FileNotFoundError as e:
        raise RuntimeError(f"no se pudo ejecutar agy: {e}")

    if r.returncode != 0:
        # Con codigo != 0 agy igual suele mandar un JSON con el motivo real
        # (ej. cuota agotada) por stdout -- mostrar ESE mensaje en vez de un
        # stderr vacio, que no dice nada. Encontrado 2026-08-03: un fallo real
        # de cuota (RESOURCE_EXHAUSTED) se vio primero como "agy fallo
        # (codigo 1): " sin mas info, hasta mirar el stdout a mano.
        try:
            datos_error = json.loads(r.stdout)
            motivo = datos_error.get("error") or datos_error.get("status")
            if motivo:
                detalle = _causa_real_si_es_cuota()
                raise RuntimeError(f"agy fallo: {motivo}"
                                    + (f" ({detalle})" if detalle else ""))
        except json.JSONDecodeError:
            pass
        raise RuntimeError(f"agy fallo (codigo {r.returncode}): {r.stderr.strip()[:500]}")

    try:
        datos = json.loads(r.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"agy no devolvio JSON valido: {r.stdout[:300]}")

    if datos.get("status") != "SUCCESS":
        motivo = datos.get("error") or datos.get("status")
        detalle = _causa_real_si_es_cuota()
        raise RuntimeError(f"agy fallo: {motivo}"
                            + (f" ({detalle})" if detalle else ""))

    return datos["response"].strip(), datos["conversation_id"]


def generar_con_respaldo(prompt: str, conversation_id: str | None = None,
                          timeout: int = 150, modelo: str | None = None) -> tuple[str, str]:
    """Como generar(), pero si agy falla por cuota agotada (RESOURCE_EXHAUSTED,
    lo que paso el 2026-08-03 con tantas pruebas seguidas) reintenta con
    a12_codex.generar() -- respaldo de TEXTO nada mas, cuota separada de
    Google. La generacion de imagen NO tiene respaldo: confirmado el mismo
    dia que Codex no genera imagenes en el plan gratis de ChatGPT (pide
    Plus, $20/mes -- ver panel-artes-integracion-agy.md).

    `modelo` se pasa tal cual a generar() (ver ahi el porque) -- no aplica
    cuando el proveedor termina siendo Codex, que elige su propio modelo.

    El conversation_id devuelto queda marcado con el proveedor
    ("agy:<id>" o "codex:<id>") para que una correccion siguiente vuelva a
    ESE mismo proveedor -- los ids de agy y de codex no son intercambiables.
    """
    proveedor, id_real = "agy", conversation_id
    if conversation_id and ":" in conversation_id:
        proveedor, id_real = conversation_id.split(":", 1)

    if proveedor == "codex":
        from artes import a12_codex
        texto, tid = a12_codex.generar(prompt, thread_id=id_real, timeout=timeout)
        return texto, f"codex:{tid}"

    try:
        texto, cid = generar(prompt, conversation_id=id_real, timeout=timeout, modelo=modelo)
        return texto, f"agy:{cid}"
    except RuntimeError as e:
        if "RESOURCE_EXHAUSTED" not in str(e) and "cuota" not in str(e).lower():
            raise
        from artes import a12_codex
        if not a12_codex.disponible():
            raise
        texto, tid = a12_codex.generar(prompt, timeout=timeout)
        return texto, f"codex:{tid}"


def generar_imagen(prompt: str, destino: Path,
                    referencias: list[Path] | None = None,
                    conversation_id: str | None = None,
                    timeout: int = 240) -> tuple[Path, str]:
    """Genera una imagen con el tool nativo de agy (Imagen) y la copia a `destino`.
    Devuelve (destino, conversation_id).

    No usa --dangerously-skip-permissions ni --mode accept-edits -- no hacen
    falta. El tool GenerateImage no pide aprobacion, solo escribe en su propio
    cache (`_BRAIN/<conversation_id>/`). Ahi la buscamos y la copiamos con
    Python, sin que agy tenga que tocar el resto del disco.

    Si `referencias` trae rutas (ej. la foto real del producto), agy las toma
    como entrada multimodal para combinar/editar en vez de generar de cero.
    Confirmado 2026-08-03 con una foto real de Kindle Paperwhite: preserva el
    diseno del aparato y el texto de la pantalla mucho mejor que Qwen (que lo
    rompia con denoise=1.0, ver artes-qwen-pipeline.md) -- alcanza con
    mencionar la ruta absoluta en el prompt, agy la lee solo.

    Si `conversation_id` viene, continua esa conversacion (para corregir una
    imagen ya generada sin repetir la referencia ni las reglas de nuevo) --
    mismo patron que generar(). La carpeta de cache es la misma en toda la
    conversacion, asi que el archivo mas nuevo ahi adentro es siempre el que
    se acaba de generar.
    """
    partes = [f"Reference image {i}: {r.resolve()}"
              for i, r in enumerate(referencias or [], 1)]
    partes.append(f"Generate an image with this description: {prompt}")
    instruccion = "\n\n".join(partes)

    _, cid = generar(instruccion, conversation_id=conversation_id, timeout=timeout)
    carpeta = _BRAIN / cid
    candidatos = [f for f in carpeta.glob("*") if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")]
    if not candidatos:
        raise RuntimeError(f"agy no dejo ninguna imagen en {carpeta}")
    origen = max(candidatos, key=lambda f: f.stat().st_mtime)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_bytes(origen.read_bytes())
    return destino, cid


def json_de(texto: str) -> dict:
    """Extrae el primer objeto JSON de la respuesta.

    Aunque se le pida "sin markdown", agy a veces envuelve el JSON en
    ```json ... ``` igual -- se lo quita antes de parsear.
    """
    t = texto.strip()
    if t.startswith("```"):
        t = t.strip("`")
        if t[:4].lower() == "json":
            t = t[4:]
        t = t.strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        inicio, fin = t.find("{"), t.rfind("}")
        if inicio == -1 or fin == -1:
            raise RuntimeError(f"agy no devolvio JSON: {texto[:300]}")
        return json.loads(t[inicio:fin + 1])
