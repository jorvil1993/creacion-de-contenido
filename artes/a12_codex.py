"""Puente a OpenAI Codex CLI (`codex`) en modo headless -- respaldo de a11_agy.py
cuando se agota la cuota de Google AI Pro/agy.

Misma logica que a11_agy.py: cuenta de Jose (ChatGPT, plan gratis desde
mayo 2026 -- ver panel-artes-integracion-agy.md), sin API key aparte, cuota
separada de la de Google.

OJO -- a diferencia de a11_agy.py, este modulo se escribio 2026-08-03 SIN
probarlo en vivo todavia (Jose pidio limitar las llamadas reales, en
particular de imagen, a una sola cuando el la autorice). El formato de salida
de `codex exec --json` esta confirmado contra la documentacion oficial y
varios parsers de terceros (JSONL, un evento por linea: thread.started con
thread_id, item.completed con item.type=agent_message y el texto, turn.completed
al final) pero no contra una corrida real -- la primera llamada real puede
revelar que algun nombre de campo no es exactamente este.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

# El instalador de PowerShell (irm https://chatgpt.com/codex/install.ps1) NO
# lo deja como un binario suelto tipo agy -- lo instala como app nativa de
# Windows en esta carpeta, con el .exe adentro de una subcarpeta con hash de
# build (confirmado 2026-08-03: .../bin/d7e8094cfb76a267/codex.exe). Ese hash
# cambia con cada actualizacion, por eso se busca con glob en vez de una ruta
# fija -- mismo problema de PATH que agy (un proceso ya abierto no ve el PATH
# actualizado por el instalador).
_INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"


def _binario() -> str:
    en_path = shutil.which("codex")
    if en_path:
        return en_path
    if _INSTALL_DIR.exists():
        candidatos = list(_INSTALL_DIR.glob("*/codex.exe"))
        if candidatos:
            return str(max(candidatos, key=lambda f: f.stat().st_mtime))
    raise RuntimeError(
        "No se encontro codex.exe (ni en PATH ni bajo "
        f"{_INSTALL_DIR}). OpenAI Codex CLI no esta instalado, o el proceso "
        "que corre el panel arranco antes de que el PATH se actualizara."
    )


def disponible() -> bool:
    try:
        _binario()
        return True
    except RuntimeError:
        return False


def generar(prompt: str, thread_id: str | None = None,
            timeout: int = 150, referencias: list[Path] | None = None) -> tuple[str, str]:
    """Manda `prompt` a codex en modo headless. Devuelve (texto, thread_id).

    Si `thread_id` viene, continua ese hilo (`codex exec resume <id>`) en vez
    de arrancar uno nuevo -- equivalente al --conversation de agy.

    `codex exec --json` imprime JSONL (un evento por linea), no un solo JSON
    como agy. Se recorren las lineas buscando el thread_id inicial y el texto
    del ultimo item tipo "agent_message".
    """
    # ``--image`` acepta varios archivos y por eso puede tragarse el prompt
    # que se deje despues. El guion ``-`` le pide a Codex que lea el prompt
    # desde stdin; el separador ``--`` cierra inequÃ­vocamente la lista de
    # imagenes antes de los argumentos posicionales.
    cmd = [_binario(), "exec"]
    if thread_id:
        cmd.append("resume")
    cmd.append("--json")
    for referencia in referencias or []:
        cmd += ["--image", str(referencia.resolve())]
    cmd.append("--")
    if thread_id:
        cmd.append(thread_id)
    cmd.append("-")

    # El servidor del panel se inicia desde un .bat y en Windows puede heredar
    # USERPROFILE sin HOME. Codex CLI usa HOME para encontrar su sesion y en
    # ese caso falla antes de autenticar. Se completa solo para este hijo.
    entorno = os.environ.copy()
    if not entorno.get("HOME") and entorno.get("USERPROFILE"):
        entorno["HOME"] = entorno["USERPROFILE"]
    try:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, env=entorno,
                            encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"codex no respondio en {timeout}s")
    except FileNotFoundError as e:
        raise RuntimeError(f"no se pudo ejecutar codex: {e}")

    tid = thread_id
    texto = None
    fallo = None
    for linea in r.stdout.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            evento = json.loads(linea)
        except json.JSONDecodeError:
            continue
        tipo = evento.get("type")
        if tipo == "thread.started":
            tid = evento.get("thread_id") or tid
        elif tipo == "item.completed":
            item = evento.get("item", {})
            if item.get("type") == "agent_message":
                texto = item.get("text")
        elif tipo in ("turn.failed", "error"):
            fallo = evento

    if fallo:
        raise RuntimeError(f"codex fallo: {fallo}")
    if r.returncode != 0:
        raise RuntimeError(f"codex fallo (codigo {r.returncode}): {r.stderr.strip()[:500]}")
    if texto is None:
        raise RuntimeError(f"codex no devolvio agent_message: {r.stdout[:500]}")
    if tid is None:
        raise RuntimeError(f"codex no devolvio thread_id: {r.stdout[:500]}")

    return texto.strip(), tid


def json_de(texto: str) -> dict:
    """Extrae el primer objeto JSON de la respuesta (mismo criterio que
    a11_agy.json_de: a veces el modelo lo envuelve en ```json aunque se le
    pida que no lo haga)."""
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
            raise RuntimeError(f"codex no devolvio JSON: {texto[:300]}")
        return json.loads(t[inicio:fin + 1])


def _imagen_generada_por_codex(thread_id: str) -> Path | None:
    """Busca el PNG que imagegen guarda automaticamente para ese hilo.

    Codex CLI persiste las imagenes en ``~/.codex/generated_images/<hilo>/``.
    A veces el agente puede generar bien la imagen pero no copiarla despues a
    la ruta que le pedimos; el panel recupera ese resultado local en vez de
    perder una generacion ya consumida.
    """
    perfil = Path(os.environ.get("USERPROFILE") or Path.home())
    carpeta = perfil / ".codex" / "generated_images" / thread_id
    if not carpeta.is_dir():
        return None
    extensiones = {".png", ".jpg", ".jpeg", ".webp"}
    candidatas = [f for f in carpeta.rglob("*")
                  if f.is_file() and f.suffix.lower() in extensiones]
    return max(candidatas, key=lambda f: f.stat().st_mtime) if candidatas else None


def generar_imagen(prompt: str, destino: Path,
                    referencias: list[Path] | None = None,
                    thread_id: str | None = None,
                    timeout: int = 480) -> tuple[Path, str]:
    """Genera una imagen con el $imagegen / GPT Image 2 de Codex.

    CONFIRMADA EN VIVO el 2026-08-05, con foto de referencia adjunta: dos
    slides de carrusel salieron bien por esta via y respetaron el equipo de la
    foto -- mejor incluso que agy en el contenido de la pantalla (conservo el
    texto real de la pagina). Queda desmentido lo que se creia el 2026-08-03
    ("Codex no genera imagenes en el plan gratis"). Sirve de plan B cuando agy
    se queda sin cuota de imagenes, que fue justo el caso ese dia.

    La instrucción le da al agente una ruta de salida concreta. Es importante:
    no se intenta adivinar el cache interno de Codex ni se depende de cómo
    redacte su respuesta final. En las dos corridas reales guardo directo en
    esa ruta, sin necesitar el respaldo de _imagen_generada_por_codex().
    """
    destino = destino.resolve()
    # Codex escribe solamente dentro de su espacio de trabajo. El resultado
    # publico vive en C:\\ai-video, asi que primero se genera en el proyecto
    # y este proceso lo mueve al destino final al terminar.
    temporales = Path(__file__).resolve().parent / "_codex_salidas"
    temporales.mkdir(parents=True, exist_ok=True)
    temporal = temporales / f"{destino.stem}-{uuid.uuid4().hex}.png"
    partes = [
        "Use the image-generation tool to generate ONE image.",
        f"Generate it with this description: {prompt}",
        f"Save the final PNG exactly at this Windows path: {temporal}",
        "If reference images were attached, use them as references. Do not merely describe an image.",
        "Reply only after the file exists at that exact path.",
    ]
    instruccion = "\n\n".join(partes)

    destino.parent.mkdir(parents=True, exist_ok=True)
    texto, tid = generar(instruccion, thread_id=thread_id, timeout=timeout,
                         referencias=referencias)
    if not temporal.is_file() or temporal.stat().st_size == 0:
        respaldo = _imagen_generada_por_codex(tid)
        if respaldo:
            shutil.copy2(respaldo, temporal)
    if not temporal.is_file() or temporal.stat().st_size == 0:
        raise RuntimeError(
            "Codex terminó sin guardar la imagen solicitada. "
            f"Respuesta: {texto[:500]}"
        )
    shutil.move(str(temporal), str(destino))
    return destino, tid
