"""Arranca y apaga ComfyUI a demanda.

Medido el 2026-08-01: con Qwen cargado, ComfyUI retiene **13.9 GB de los 16.3 GB
de VRAM** (85%). Eso deja sin GPU al pipeline de video, que la usa para el matte
de fondo con RVM.

Y dejarlo abierto casi no ahorra tiempo: el modelo pesa 20,5 GB y no entra en
16 GB, asi que ComfyUI lo trae desde RAM en cada corrida igual. Cuatro
generaciones seguidas dieron 170 s, 185 s, 166 s y 155 s — sin diferencia entre
"frio" y "caliente". Beneficio chico, costo alto: se apaga.

El stdout va a un ARCHIVO y no a un pipe. Con un pipe sin nadie leyendo, ComfyUI
llena el buffer imprimiendo su banner y se cuelga en el primer write() antes de
abrir el puerto. Esta documentado en contexto/BITACORA-B.md, seccion 9.
"""
from __future__ import annotations

import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

PYTHON = Path(r"C:\ai-video\venv-comfy\Scripts\python.exe")
MAIN = Path(r"C:\ai-video\comfyui\main.py")
LOG = Path(r"C:\ai-video\comfy-artes.log")
SERVIDOR = "http://127.0.0.1:8188"

_proc: subprocess.Popen | None = None


def vivo(timeout: float = 2.0) -> bool:
    try:
        urllib.request.urlopen(f"{SERVIDOR}/system_stats", timeout=timeout)
        return True
    except Exception:
        return False


def arrancar(espera: int = 180, avisar=print) -> bool:
    """Lo levanta si no esta. Devuelve True cuando responde."""
    global _proc
    if vivo():
        avisar("ComfyUI ya estaba encendido")
        return True

    avisar("encendiendo ComfyUI…")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    salida = open(LOG, "w", encoding="utf-8", errors="replace")
    _proc = subprocess.Popen(
        [str(PYTHON), str(MAIN), "--listen", "127.0.0.1", "--port", "8188"],
        stdout=salida, stderr=subprocess.STDOUT, cwd=str(MAIN.parent),
    )

    t0 = time.time()
    ultimo_aviso = 0
    while time.time() - t0 < espera:
        if vivo(timeout=3):
            avisar(f"ComfyUI listo en {time.time() - t0:.0f}s")
            return True
        transcurridos = int(time.time() - t0)
        if transcurridos >= ultimo_aviso + 15:
            ultimo_aviso = transcurridos
            avisar(f"esperando a ComfyUI… ({transcurridos}s / {espera}s)")
        time.sleep(3)
    avisar(f"ComfyUI no respondio en {espera}s — ver {LOG}")
    return False


def apagar(avisar=print) -> None:
    """Lo cierra y libera la VRAM."""
    global _proc
    if _proc is not None and _proc.poll() is None:
        _proc.terminate()
        try:
            _proc.wait(timeout=25)
        except subprocess.TimeoutExpired:
            _proc.kill()
        avisar("ComfyUI apagado, VRAM liberada")
        _proc = None
        return

    # Si lo arranco otra sesion, no hay handle: se pide por su propia API que
    # suelte los modelos, que es lo que ocupa la VRAM.
    if vivo():
        try:
            req = urllib.request.Request(
                f"{SERVIDOR}/free", data=b'{"unload_models":true,"free_memory":true}',
                headers={"Content-Type": "application/json"}, method="POST")
            urllib.request.urlopen(req, timeout=20)
            avisar("modelos descargados de la VRAM (el servidor sigue abierto)")
        except Exception as e:
            avisar(f"no se pudo liberar: {e}")
    else:
        avisar("ComfyUI no estaba corriendo")
        return

    _matar_por_comando(avisar)


def _matar_por_comando(avisar=print) -> None:
    """Cierra ComfyUI cuando lo arranco otra sesion y no hay handle.

    Se busca por la linea de comando con WMI: en Windows no sirve buscar por
    nombre de imagen, porque el proceso se llama `python.exe` como cualquier
    otro script del proyecto (probado el 2026-08-01: pkill no lo encuentra).
    """
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
        "Where-Object { $_.CommandLine -like '*comfyui*main.py*' } | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=40)
        avisar("ComfyUI cerrado, VRAM liberada")
    except Exception as e:
        avisar(f"no se pudo cerrar: {e}")


def vram() -> tuple[int, int] | None:
    """(usada, total) en MiB, o None si no se pudo leer."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, encoding="utf-8", timeout=10)
        u, t = (int(x) for x in r.stdout.strip().split(",")[:2])
        return u, t
    except Exception:
        return None
