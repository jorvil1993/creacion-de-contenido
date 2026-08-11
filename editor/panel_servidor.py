"""
Panel de producción conectado — servidor local.

`PANEL-PRODUCCION.html` es la fuente de la verdad de los guiones y se publica
tal cual en GitHub Pages. Este servidor es lo que lo vuelve *ejecutable* cuando
se abre en la PC: el MISMO archivo, servido desde 127.0.0.1, descubre esta API y
enciende lo que en el celular no tendría sentido — elegir la grabación cruda,
cambiar el tipo de cada fila (YO / B-ROLL / PIP / ANIM) y correr el pipeline con
el guion que se está mirando.

Sin este servidor el panel no pierde nada de lo suyo: los controles se esconden
solos y queda la página de lectura. Esa es toda la razón por la que la detección
es un `fetch` a `/api/estado` y no una bandera: un solo archivo sirve para el
GitHub Pages público y para la PC, y no hay dos copias que se desincronicen.

Las escrituras sobre el panel se hacen POR POSICIÓN (guion `n`, fila `ri`) y no
buscando el texto de la fila. El texto no sirve como aguja: hay filas cuyo
fuente lleva comillas escapadas (`punch-in en \\"celular\\"`), así que la cadena
evaluada que ve el navegador no aparece literal en el archivo.

Uso:
    python panel_servidor.py                      # abre el navegador en el panel
    python panel_servidor.py --sin-abrir --puerto 8899
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import f0_preparar
import f_agy_video

AQUI = Path(__file__).resolve().parent
PANEL = config.RAIZ_PROYECTO / "PANEL-PRODUCCION.html"

# Los cuatro tipos de la columna "En pantalla". Cualquier otra cosa se rechaza
# antes de tocar el archivo: el panel es la entrada del pipeline, y un tipo
# inventado no da error en ningún lado — simplemente hace que la fila no aporte
# nada al video.
TIPOS_VALIDOS = ("YO", "B-ROLL", "PIP", "ANIM")

CAMPOS_SEGUNDOS = ("hooksegs", "cierresegs")

# Trabajos de IA en curso (imagen de ambiente, imagen con producto). Mismo
# patrón que artes/panel_servidor_artes.py: generar con agy tarda 15-40s (más
# en una corrección sobre una conversación existente), y sin polling el
# navegador lo ve colgado sin ningún aviso.
TRABAJOS: dict[str, dict] = {}


def _proveedor_de(conversation_id: str) -> str:
    """Extrae el proveedor que quedó guardado en una conversación de IA."""
    return conversation_id.split(":", 1)[0] if ":" in conversation_id else "agy"


# ---------------------------------------------------------------------------
# Edición del fuente del panel
# ---------------------------------------------------------------------------
def _bloque_guion(fuente: str, n: int) -> tuple[int, int]:
    """Rango `[ini, fin)` del objeto `{n:N, …}` del guion dentro del fuente.

    El bloque termina donde empieza el siguiente guion o donde cierra el array
    `G`. Acotar así es lo que impide que una fila del guion 7 se confunda con la
    del guion 8 cuando las dos dicen lo mismo.
    """
    m = re.search(r"\{n:" + str(int(n)) + r",", fuente)
    if not m:
        raise ValueError(f"No encontré el guion {n} en el panel")
    ini = m.start()
    sig = re.search(r"\n\{n:\d+,|\n\];", fuente[m.end():])
    fin = m.end() + sig.start() if sig else len(fuente)
    return ini, fin


def _lineas_filas(fuente: str, ini: int, fin: int) -> list[tuple[int, int]]:
    """Rangos de las líneas del `tl:[…]` del bloque, una por fila de la tabla.

    Cada fila de la línea de tiempo ocupa exactamente una línea del fuente (las
    120 del panel lo cumplen, y `test_regresion` lo comprueba). Apoyarse en eso
    evita tener que escribir un parser de JavaScript aquí dentro.
    """
    bloque = fuente[ini:fin]
    m = re.search(r"\n\s*tl:\[", bloque)
    if not m:
        raise ValueError("El guion no tiene línea de tiempo (`tl:[`)")
    desplazamiento = ini + m.end()
    filas = []
    pos = desplazamiento
    for linea in fuente[desplazamiento:fin].split("\n"):
        largo = len(linea)
        if linea.lstrip().startswith("["):
            arranque = pos + (largo - len(linea.lstrip()))
            filas.append((arranque, pos + largo))
        pos += largo + 1          # +1 por el \n que `split` se comió
    return filas


def _campos(linea: str) -> list[tuple[int, int]]:
    """Rangos del CONTENIDO de cada cadena entre comillas simples de la línea.

    Reconoce el escape con barra (`\\'`, `\\"`), que es lo único que aparece
    dentro de las cadenas del panel.
    """
    rangos, i, largo = [], 0, len(linea)
    while i < largo:
        if linea[i] == "'":
            j = i + 1
            while j < largo:
                if linea[j] == "\\":
                    j += 2
                    continue
                if linea[j] == "'":
                    break
                j += 1
            if j >= largo:
                break                      # comilla sin cerrar: línea rara, se ignora
            rangos.append((i + 1, j))
            i = j + 1
        else:
            i += 1
    return rangos


def _escapar(valor: str) -> str:
    """El valor tal como tiene que quedar dentro de una cadena `'…'` del fuente."""
    return valor.replace("\\", "\\\\").replace("'", "\\'")


def _desescapar(bruto: str) -> str:
    """Lo contrario: el texto que ve el navegador después de evaluar el fuente."""
    return re.sub(r"\\(.)", r"\1", bruto)


def leer_fila(fuente: str, n: int, ri: int) -> dict:
    """Los 6 campos de la fila `ri` del guion `n`, ya desescapados."""
    ini, fin = _bloque_guion(fuente, n)
    filas = _lineas_filas(fuente, ini, fin)
    if not 0 <= ri < len(filas):
        raise ValueError(f"El guion {n} no tiene una fila {ri} (tiene {len(filas)})")
    a, b = filas[ri]
    linea = fuente[a:b]
    campos = [_desescapar(linea[x:y]) for x, y in _campos(linea)]
    claves = ("momento", "dice", "tipo", "ve", "sonido", "musica")
    return {k: (campos[i] if i < len(campos) else "") for i, k in enumerate(claves)}


def escribir_fila(fuente: str, n: int, ri: int, tipo: str, ve: str) -> str:
    """Devuelve el fuente con el tipo y el 'qué se ve' de esa fila cambiados.

    No escribe en disco a propósito: así la misma función sirve para las pruebas
    y para el endpoint, y el que guarda decide cuándo.
    """
    if tipo not in TIPOS_VALIDOS:
        raise ValueError(f"Tipo inválido: {tipo!r} (válidos: {', '.join(TIPOS_VALIDOS)})")
    if "\n" in ve or "\r" in ve:
        raise ValueError("El texto de 'qué se ve' no puede tener saltos de línea")

    ini, fin = _bloque_guion(fuente, n)
    filas = _lineas_filas(fuente, ini, fin)
    if not 0 <= ri < len(filas):
        raise ValueError(f"El guion {n} no tiene una fila {ri} (tiene {len(filas)})")
    a, b = filas[ri]
    linea = fuente[a:b]
    campos = _campos(linea)
    if len(campos) < 4:
        raise ValueError(f"La fila {ri} del guion {n} no tiene los 4 campos esperados")

    # De atrás para adelante: reemplazar el 3.º primero desplazaría el 4.º.
    nueva = linea
    for indice, valor in ((3, ve), (2, tipo)):
        x, y = campos[indice]
        # Un campo que ya dice eso no se toca. No es un ahorro: el panel está
        # escrito a mano y hay campos con escapes que no hacen falta (`\"celular\"`),
        # así que reescribirlos "igual" cambiaría bytes sin cambiar nada.
        if _desescapar(nueva[x:y]) == valor:
            continue
        nueva = nueva[:x] + _escapar(valor) + nueva[y:]
    return fuente[:a] + nueva + fuente[b:]


def escribir_tele(fuente: str, n: int, tele: str) -> str:
    """Devuelve el fuente con `t:`, `tele:`, `tomas:[...]` y `tl:[...]` del guion `n` reemplazados.

    Sincroniza absolutamente todas las secciones del guion en PANEL-PRODUCCION.html:
    1. `tele`: Texto completo del teleprompter.
    2. `t`: Título/Hook principal en el encabezado del guion.
    3. `tomas`: Lista de tomas para el teleprompter de la tablet.
    4. `tl`: Línea de tiempo que lee f13_guion para alinear los beats con el audio.
    """
    if "\n" in tele or "\r" in tele:
        raise ValueError("El texto del teleprompter no puede tener saltos de línea")
    if not tele.strip():
        raise ValueError("El texto del teleprompter no puede estar vacío")

    parrafos = [p.strip() for p in tele.split(" || ") if p.strip()]
    if not parrafos:
        raise ValueError("Sin párrafos válidos en tele")

    frases = [f.strip() for f in re.split(r"(?<=[.?!])\s+", tele.replace(" || ", " ")) if f.strip()]
    if not frases:
        frases = parrafos

    ini, fin = _bloque_guion(fuente, n)
    bloque = fuente[ini:fin]

    # 1. Reemplazar tele:'...'
    m_tele = re.search(r" tele:'((?:[^'\\]|\\.)*)',", bloque)
    if not m_tele:
        raise ValueError(f"El guion {n} no tiene campo `tele:`")
    tele_escapado = _escapar(tele)
    bloque = bloque[:m_tele.start(1)] + tele_escapado + bloque[m_tele.end(1):]

    # 2. Reemplazar t:'...' (Título / Hook principal)
    m_t = re.search(r"t:'((?:[^'\\]|\\.)*)',", bloque)
    if m_t:
        nuevo_titulo = parrafos[0]
        bloque = bloque[:m_t.start(1)] + _escapar(nuevo_titulo) + bloque[m_t.end(1):]

    # 3. Reemplazar tomas:[...]
    m_tomas = re.search(r"tomas:\[\r?\n([\s\S]*?)\],\r?\n\s*tl:", bloque)
    if m_tomas:
        lineas_tomas = m_tomas.group(1).splitlines()
        nuevas_lineas = []
        num_tomas = len(lineas_tomas)
        for k, linea in enumerate(lineas_tomas):
            campos = _campos(linea)
            if len(campos) >= 4:
                idx_start = int(k * len(parrafos) / num_tomas)
                idx_end = int((k + 1) * len(parrafos) / num_tomas)
                sub = parrafos[idx_start:idx_end]
                if not sub and parrafos:
                    sub = [parrafos[-1]]
                nuevo_texto_toma = " ".join(sub)
                x, y = campos[3]
                linea = linea[:x] + _escapar(nuevo_texto_toma) + linea[y:]
            nuevas_lineas.append(linea)
        nuevo_tomas_str = "\n".join(nuevas_lineas)
        bloque = bloque[:m_tomas.start(1)] + nuevo_tomas_str + bloque[m_tomas.end(1):]

    # 4. Reemplazar tl:[...] (Línea de tiempo para f13_guion)
    m_tl = re.search(r"tl:\[\r?\n([\s\S]*?)\]\]", bloque)
    if m_tl:
        lineas_tl = m_tl.group(1).splitlines()
        nuevas_lineas_tl = []
        num_beats = len(lineas_tl)
        for r, linea in enumerate(lineas_tl):
            campos = _campos(linea)
            if len(campos) >= 2:
                idx_start = int(r * len(frases) / num_beats)
                idx_end = int((r + 1) * len(frases) / num_beats)
                sub = frases[idx_start:idx_end]
                if not sub and frases:
                    sub = [frases[-1]]
                nuevo_texto_beat = " ".join(sub)
                x, y = campos[1]
                linea = linea[:x] + _escapar(nuevo_texto_beat) + linea[y:]
            nuevas_lineas_tl.append(linea)
        nuevo_tl_str = "\n".join(nuevas_lineas_tl)
        bloque = bloque[:m_tl.start(1)] + nuevo_tl_str + bloque[m_tl.end(1):]

    return fuente[:ini] + bloque + fuente[fin:]


def escribir_segundos(fuente: str, n: int, campo: str, valor: float) -> str:
    """Devuelve el fuente con `hooksegs`/`cierresegs` del guion `n` cambiado."""
    if campo not in CAMPOS_SEGUNDOS:
        raise ValueError(f"Campo inválido: {campo!r}")
    valor = float(valor)
    if not 0 <= valor <= 30:
        raise ValueError(f"Segundos fuera de rango: {valor}")
    ini, fin = _bloque_guion(fuente, n)
    bloque = fuente[ini:fin]
    m = re.search(campo + r":([0-9.]+)", bloque)
    if not m:
        raise ValueError(f"El guion {n} no tiene `{campo}`")
    # Sin decimales cuando es entero: el panel los escribe así (`hooksegs:3.0`
    # vs `hooksegs:0`), y respetarlo mantiene el diff del archivo pequeño.
    texto = f"{valor:g}" if valor != int(valor) else f"{valor:.1f}"
    nuevo = bloque[:m.start(1)] + texto + bloque[m.end(1):]
    return fuente[:ini] + nuevo + fuente[fin:]


def escribir_audio(fuente: str, n: int, ri: int, sonido: str = None, musica: str = None) -> str:
    """Devuelve el fuente con el sonido y/o la música de esa fila cambiados.

    Mismo mecanismo posicional que escribir_fila() (campos 4 y 5 en vez de 2 y
    3), para los dos únicos campos de la fila que hoy no tienen ningún
    endpoint — solo se podían tocar editando el HTML a mano.
    """
    if sonido is None and musica is None:
        raise ValueError("Hace falta sonido o musica")
    for valor, campo in ((sonido, "sonido"), (musica, "musica")):
        if valor is not None and ("\n" in valor or "\r" in valor):
            raise ValueError(f"El texto de '{campo}' no puede tener saltos de línea")

    ini, fin = _bloque_guion(fuente, n)
    filas = _lineas_filas(fuente, ini, fin)
    if not 0 <= ri < len(filas):
        raise ValueError(f"El guion {n} no tiene una fila {ri} (tiene {len(filas)})")
    a, b = filas[ri]
    linea = fuente[a:b]
    campos = _campos(linea)
    if len(campos) < 6:
        raise ValueError(f"La fila {ri} del guion {n} no tiene los 6 campos esperados")

    # De atrás para adelante, igual que escribir_fila(): el campo 5 (música) se
    # reemplaza antes que el 4 (sonido) para no invalidar el rango ya calculado.
    nueva = linea
    for indice, valor in ((5, musica), (4, sonido)):
        if valor is None:
            continue
        x, y = campos[indice]
        if _desescapar(nueva[x:y]) == valor:
            continue
        nueva = nueva[:x] + _escapar(valor) + nueva[y:]
    return fuente[:a] + nueva + fuente[b:]


def leer_panel() -> str:
    """El fuente del panel con sus finales de línea intactos.

    `newline=""` no es un detalle: el archivo es CRLF de punta a punta y
    `read_text()` normal lo entrega con `\\n`. Al reescribirlo así, cambiar UN
    campo dejaba un diff de 1.797 líneas y el archivo entero convertido a LF.
    """
    with open(PANEL, "r", encoding="utf-8", newline="") as f:
        return f.read()


def _hacer_push_git(mensaje: str = "Actualizar PANEL-PRODUCCION.html") -> None:
    """Ejecuta git add, commit y push de PANEL-PRODUCCION.html en segundo plano.

    Así GitHub Pages recibe inmediatamente la actualización sin demorar la
    respuesta HTTP en la pantalla.
    """
    def _run():
        try:
            raiz = config.RAIZ_PROYECTO
            # 1. git add PANEL-PRODUCCION.html
            res_add = subprocess.run(["git", "add", "PANEL-PRODUCCION.html"],
                                     cwd=str(raiz), capture_output=True, text=True)
            if res_add.returncode != 0:
                print(f"  AVISO: `git add` falló: {res_add.stderr.strip()}")
                return

            # 2. git commit (específico para PANEL-PRODUCCION.html)
            res_commit = subprocess.run(["git", "commit", "-m", mensaje, "PANEL-PRODUCCION.html"],
                                        cwd=str(raiz), capture_output=True, text=True)
            if res_commit.returncode != 0:
                if "nothing to commit" in res_commit.stdout or "no changes added to commit" in res_commit.stdout:
                    return
                print(f"  AVISO: `git commit` falló: {res_commit.stderr.strip()}")
                return

            print(f"  [Git] Commit realizado: \"{mensaje}\"")

            # 3. git push a la rama master (la que sirve GitHub Pages)
            res_push = subprocess.run(["git", "push", "origin", "HEAD:master"],
                                      cwd=str(raiz), capture_output=True, text=True)
            if res_push.returncode == 0:
                print("  [Git] Push a GitHub Pages (master) completado exitosamente.")
            else:
                print(f"  AVISO: `git push` falló: {res_push.stderr.strip()}")
        except Exception as e:
            print(f"  AVISO: Error en auto-push git: {e}")

    threading.Thread(target=_run, daemon=True).start()


def _guardar_panel(fuente_nuevo: str, comprobacion, mensaje_commit: str = "Actualizar PANEL-PRODUCCION.html", auto_push: bool = False) -> None:
    """Escribe el panel solo si el fuente nuevo se relee como se esperaba.

    `comprobacion(fuente_nuevo)` tiene que devolver True. Es una red barata
    contra la clase de fallo peor de todas aquí: dejar el panel corrupto y que
    el pipeline —que lo parsea con `eval`— falle después, lejos, sin que nada
    apunte a este servidor.
    """
    if not comprobacion(fuente_nuevo):
        raise ValueError("La comprobación de relectura falló: el panel NO se tocó")
    tmp = PANEL.with_suffix(".html.tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        f.write(fuente_nuevo)
    os.replace(tmp, PANEL)
    if auto_push:
        _hacer_push_git(mensaje_commit)




# ---------------------------------------------------------------------------
# Elegir la grabación cruda con el diálogo de Windows
# ---------------------------------------------------------------------------
def elegir_video_nativo(inicial: Path = None) -> str | None:
    """Abre el selector de archivos de Windows y devuelve la ruta elegida.

    El navegador no puede dar la ruta absoluta de un archivo (`<input type=file>`
    solo entrega el contenido), y el pipeline necesita la ruta. Como el servidor
    corre en la misma máquina que el navegador, el diálogo lo abre él.
    """
    if os.name != "nt":
        return None
    inicial = Path(inicial or config.DIR_ENTRADA)
    salida = Path(tempfile.gettempdir()) / f"panel_video_{os.getpid()}.txt"
    salida.unlink(missing_ok=True)
    # La ventana se crea con TopMost y se le pasa como dueña al diálogo: sin
    # eso el selector puede abrirse DETRÁS del navegador y parece que el botón
    # no hizo nada.
    ps = f"""
Add-Type -AssemblyName System.Windows.Forms
$due = New-Object System.Windows.Forms.Form
$due.TopMost = $true
$d = New-Object System.Windows.Forms.OpenFileDialog
$d.Title = 'Elegí la grabación cruda'
$d.Filter = 'Video (*.mp4;*.mov;*.m4v;*.mkv;*.avi;*.webm)|*.mp4;*.mov;*.m4v;*.mkv;*.avi;*.webm|Todos (*.*)|*.*'
$d.InitialDirectory = '{str(inicial).replace("'", "''")}'
if ($d.ShowDialog($due) -eq [System.Windows.Forms.DialogResult]::OK) {{
  Set-Content -LiteralPath '{str(salida).replace("'", "''")}' -Value $d.FileName -Encoding utf8
}}
$due.Dispose()
"""
    try:
        subprocess.run(["powershell", "-STA", "-NoProfile", "-Command", ps],
                       capture_output=True, timeout=600)
    except Exception:
        return None
    if not salida.exists():
        return None                      # canceló el diálogo
    try:
        # utf-8-sig: `Set-Content -Encoding utf8` de Windows PowerShell 5.1
        # escribe BOM, y sin quitarlo la ruta empieza por \ufeff y no existe.
        elegido = salida.read_text(encoding="utf-8-sig").strip()
    finally:
        salida.unlink(missing_ok=True)
    return elegido or None


# ---------------------------------------------------------------------------
# La corrida del pipeline
# ---------------------------------------------------------------------------
CORRIDA = {"estado": "libre"}
_PROC = None
_LOCK = threading.Lock()


def _estado_corrida() -> dict:
    """Copia de la corrida sin el log (que se pide aparte y por tramos)."""
    with _LOCK:
        d = dict(CORRIDA)
    d["lineas"] = len(d.pop("log", []) or [])
    return d


def lanzar_pipeline(video: Path, guion: int, extras: list = None) -> dict:
    """Lanza `editor.py` en segundo plano y deja el log a mano del panel."""
    global _PROC
    with _LOCK:
        if CORRIDA.get("estado") == "corriendo":
            raise RuntimeError("Ya hay una corrida en marcha")

    video = Path(video).resolve()
    if not video.exists():
        raise ValueError(f"No existe la grabación: {video}")

    nombre = video.stem
    dir_trabajo = config.DIR_SALIDA / nombre
    cmd = [sys.executable, str(AQUI / "editor.py"), str(video),
           "--guion", str(int(guion)),
           # El editor visual es un servidor que no termina nunca: si se abriera
           # desde aquí, la corrida se quedaría "corriendo" para siempre en el
           # panel. Se abre después, con el botón, ya como proceso suelto.
           "--sin-abrir-editor"]
    cmd += list(extras or [])
    # Con --preview el render se escribe en 07_PREVIEW.mp4 a propósito, para no
    # pisar el archivo bueno con una prueba a media resolución.
    salida = "07_PREVIEW.mp4" if "--preview" in cmd else "07_FINAL.mp4"

    entorno = dict(os.environ)
    entorno["PYTHONIOENCODING"] = "utf-8"     # sin esto el log llega con las tildes rotas
    entorno["PYTHONUNBUFFERED"] = "1"         # y línea a línea, no en bloques al final

    proc = subprocess.Popen(
        cmd, cwd=str(config.RAIZ_PROYECTO), env=entorno,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", bufsize=1)

    with _LOCK:
        CORRIDA.clear()
        CORRIDA.update({
            "estado": "corriendo", "guion": int(guion), "video": str(video),
            "nombre": nombre, "dir": str(dir_trabajo), "cmd": cmd,
            "ini": time.time(), "fin": None, "codigo": None,
            "log": [f"$ {' '.join(cmd)}", ""],
        })
    _PROC = proc

    def _leer():
        try:
            for linea in proc.stdout:
                with _LOCK:
                    CORRIDA["log"].append(linea.rstrip("\n"))
        finally:
            codigo = proc.wait()
            with _LOCK:
                CORRIDA["codigo"] = codigo
                CORRIDA["fin"] = time.time()
                if CORRIDA.get("estado") == "cancelando":
                    CORRIDA["estado"] = "cancelada"
                else:
                    CORRIDA["estado"] = "ok" if codigo == 0 else "error"
                # Solo si la corrida salió bien: el archivo puede existir de una
                # corrida anterior, y anunciarlo tras un fallo haría creer que
                # esta dejó un video.
                destino = dir_trabajo / salida
                CORRIDA["final"] = (str(destino)
                                    if codigo == 0 and destino.exists() else None)

    threading.Thread(target=_leer, daemon=True).start()
    return _estado_corrida()


def detener_pipeline() -> dict:
    with _LOCK:
        if CORRIDA.get("estado") != "corriendo":
            return _estado_corrida()
        CORRIDA["estado"] = "cancelando"
    if _PROC is not None:
        # taskkill /T: editor.py lanza ffmpeg y whisper como hijos, y matar solo
        # al padre deja el render corriendo y la GPU ocupada.
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(_PROC.pid)],
                           capture_output=True)
        else:
            _PROC.kill()
    return _estado_corrida()


def abrir_editor_visual(nombre: str = None) -> dict:
    """Abre el editor visual de una corrida, como proceso suelto."""
    destino = config.DIR_SALIDA / nombre if nombre else None
    if destino is not None and not destino.is_dir():
        raise ValueError(f"No existe la corrida {nombre}")
    cmd = [sys.executable, str(AQUI / "abrir_editor.py")]
    if destino is not None:
        cmd.append(str(destino))
    creacion = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
    subprocess.Popen(cmd, cwd=str(config.RAIZ_PROYECTO), creationflags=creacion)
    return {"ok": True, "corrida": nombre}


# ---------------------------------------------------------------------------
# Generación con agy — imagen de ambiente / imagen con el producto real
# ---------------------------------------------------------------------------
def _imagen_ambiente_ia(tid: str, cfg: dict) -> None:
    """Trabajo async para /api/imagen-ambiente-ia — ver f_agy_video.generar_ambiente."""
    log = TRABAJOS[tid]["log"]

    def paso(t: str) -> None:
        log.append(t)

    try:
        nombre = (cfg.get("nombre") or "").strip()
        if not nombre:
            raise RuntimeError("falta el nombre/código de esa fila (el mismo que va en 'Qué se ve')")
        proveedor = cfg.get("proveedor", "agy")
        paso(f"generando imagen de ambiente con {proveedor}... esto tarda 15-40s, más si es una corrección")
        ruta, cid = f_agy_video.generar_ambiente(
            nombre, cfg.get("idea", ""), cfg.get("contexto_guion", ""),
            conversation_id=cfg.get("conversation_id"),
            proveedor=proveedor,
        )
        paso(f"LISTO: {ruta.name}")
        TRABAJOS[tid]["estado"] = "listo"
        TRABAJOS[tid]["archivo"] = str(ruta.relative_to(config.RAIZ_PROYECTO)).replace("\\", "/")
        TRABAJOS[tid]["conversation_id"] = cid
    except Exception as e:
        paso(f"ERROR: {e}")
        TRABAJOS[tid]["estado"] = "error"


def _imagen_producto_ia(tid: str, cfg: dict) -> None:
    """Trabajo async para /api/imagen-producto-ia — ver f_agy_video.generar_producto."""
    log = TRABAJOS[tid]["log"]

    def paso(t: str) -> None:
        log.append(t)

    try:
        nombre = (cfg.get("nombre") or "").strip()
        foto = cfg.get("foto", "")
        if not nombre:
            raise RuntimeError("falta el nombre/código de esa fila (el mismo que va en 'Qué se ve')")
        if not foto:
            raise RuntimeError("elegí un producto primero")
        origen = config.RAIZ_PROYECTO / foto
        if not origen.exists():
            raise RuntimeError(f"no existe la foto {foto}")
        proveedor = cfg.get("proveedor", "agy")
        paso(f"generando imagen con el producto real ({proveedor})... esto tarda 15-40s, más si es una corrección")
        ruta, cid = f_agy_video.generar_producto(
            nombre, cfg.get("escena", ""), origen,
            correccion=cfg.get("correccion", ""),
            conversation_id=cfg.get("conversation_id"),
            prompt_armado=cfg.get("prompt", ""),
            proveedor=proveedor,
        )
        paso(f"LISTO: {ruta.name}")
        TRABAJOS[tid]["estado"] = "listo"
        TRABAJOS[tid]["archivo"] = str(ruta.relative_to(config.RAIZ_PROYECTO)).replace("\\", "/")
        TRABAJOS[tid]["conversation_id"] = cid
    except Exception as e:
        paso(f"ERROR: {e}")
        TRABAJOS[tid]["estado"] = "error"


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _cabeceras_comunes(self):
        # El panel también se abre como file:// y desde GitHub Pages; en los dos
        # casos el origen no es este servidor y el navegador exige CORS. La
        # cabecera de red privada es lo que pide Chrome cuando una página
        # pública llama a 127.0.0.1.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def _json(self, datos, code=200):
        cuerpo = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self._cabeceras_comunes()
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_OPTIONS(self):
        self.send_response(204)
        self._cabeceras_comunes()
        self.end_headers()

    def do_GET(self):
        partes = urlparse(self.path)
        ruta, qs = partes.path, parse_qs(partes.query)
        try:
            if ruta in ("/", "/index.html", "/PANEL-PRODUCCION.html"):
                cuerpo = PANEL.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(cuerpo)))
                self.send_header("Cache-Control", "no-store")
                self._cabeceras_comunes()
                self.end_headers()
                self.wfile.write(cuerpo)

            elif ruta == "/api/estado":
                self._json({
                    "ok": True,
                    "raiz": str(config.RAIZ_PROYECTO),
                    "panel": str(PANEL),
                    "dir_entrada": str(config.DIR_ENTRADA),
                    "dir_salida": str(config.DIR_SALIDA),
                    "videos": f0_preparar.listar_entrada(),
                    "corrida": _estado_corrida(),
                    "agy": f_agy_video.disponible(),
                    "proveedores_ia": f_agy_video.proveedores_disponibles(),
                    "productos_ia": f_agy_video.productos_disponibles(),
                })

            elif ruta == "/api/trabajo":
                tid = (qs.get("id") or [""])[0]
                self._json(TRABAJOS.get(tid) or {"estado": "desconocido"})

            elif ruta == "/api/fotos-producto":
                producto = (qs.get("producto") or [""])[0]
                self._json({"fotos": f_agy_video.fotos_de_producto(producto)})

            elif ruta == "/api/foto-producto":
                # Sirve cualquier foto real DENTRO de assets/productos/ (para
                # la galería de referencia) — acotado a esa carpeta con
                # is_relative_to, mismo criterio que /api/imagen-manual.
                nombre = (qs.get("f") or [""])[0]
                candidato = (config.RAIZ_PROYECTO / nombre).resolve()
                dir_productos = (config.DIR_ASSETS / "productos").resolve()
                if not nombre or not candidato.is_relative_to(dir_productos) or not candidato.exists():
                    self.send_error(404, "no existe")
                    return
                cuerpo = candidato.read_bytes()
                tipo = "image/png" if candidato.suffix.lower() == ".png" else "image/jpeg"
                self.send_response(200)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(cuerpo)))
                self.send_header("Cache-Control", "no-store")
                self._cabeceras_comunes()
                self.end_headers()
                self.wfile.write(cuerpo)

            elif ruta == "/api/imagen-manual":
                # Solo sirve por NOMBRE de archivo (sin ruta) y solo desde
                # assets/generado/manual/ — igual que /api/arte en el panel de
                # artes: acotado a una carpeta fija, sin traversal posible.
                nombre = Path((qs.get("f") or [""])[0]).name
                archivo = config.DIR_GENERADO / "manual" / nombre
                if not nombre or not archivo.exists():
                    self.send_error(404, "no existe")
                    return
                cuerpo = archivo.read_bytes()
                tipo = "image/png" if archivo.suffix.lower() == ".png" else "image/jpeg"
                self.send_response(200)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(cuerpo)))
                self.send_header("Cache-Control", "no-store")
                self._cabeceras_comunes()
                self.end_headers()
                self.wfile.write(cuerpo)

            elif ruta == "/api/log":
                desde = int((qs.get("desde") or ["0"])[0])
                with _LOCK:
                    log = list(CORRIDA.get("log") or [])
                estado = _estado_corrida()
                estado["desde"] = max(0, desde)
                estado["log"] = log[max(0, desde):]
                self._json(estado)

            else:
                self.send_error(404, "Ruta desconocida")
        except Exception as e:
            self._json({"ok": False, "error": str(e)}, code=500)

    def do_POST(self):
        ruta = urlparse(self.path).path
        largo = int(self.headers.get("Content-Length", 0))
        crudo = self.rfile.read(largo) if largo else b"{}"
        try:
            datos = json.loads(crudo.decode("utf-8")) if crudo.strip() else {}
        except Exception as e:
            self._json({"ok": False, "error": f"JSON inválido: {e}"}, code=400)
            return
        try:
            if ruta == "/api/fila":
                n, ri = int(datos["n"]), int(datos["ri"])
                tipo, ve = str(datos["tipo"]), str(datos.get("ve") or "")
                nuevo = escribir_fila(leer_panel(), n, ri, tipo, ve)

                def releida_ok(f, n=n, ri=ri, tipo=tipo, ve=ve):
                    fila = leer_fila(f, n, ri)
                    return fila["tipo"] == tipo and fila["ve"] == ve

                _guardar_panel(nuevo, releida_ok, f"Actualizar fila {ri} de guion {n} en panel")
                self._json({"ok": True, "fila": leer_fila(nuevo, n, ri)})

            elif ruta == "/api/segundos":
                n, campo = int(datos["n"]), str(datos["campo"])
                valor = float(datos["valor"])
                nuevo = escribir_segundos(leer_panel(), n, campo, valor)

                def releida_ok(f, n=n, campo=campo, valor=valor):
                    i, j = _bloque_guion(f, n)
                    m = re.search(campo + r":([0-9.]+)", f[i:j])
                    return bool(m) and float(m.group(1)) == valor

                _guardar_panel(nuevo, releida_ok, f"Actualizar {campo} de guion {n} en panel")
                self._json({"ok": True, "valor": valor})

            elif ruta == "/guardar-guion-tele":
                n = int(datos["guion"])
                tele = str(datos["tele"])
                fuente_actual = leer_panel()
                nuevo = escribir_tele(fuente_actual, n, tele)

                def releida_tele(f, n=n, tele=tele):
                    i, j = _bloque_guion(f, n)
                    m = re.search(r" tele:'((?:[^'\\]|\\.)*)',", f[i:j])
                    return bool(m) and _desescapar(m.group(1)) == tele

                _guardar_panel(nuevo, releida_tele, f"Actualizar texto teleprompter guion {n} en panel", auto_push=True)
                self._json({"ok": True})

            elif ruta == "/api/elegir-video":
                elegido = elegir_video_nativo(datos.get("desde"))
                self._json({"ok": True, "ruta": elegido})

            elif ruta == "/api/fila-audio":
                n, ri = int(datos["n"]), int(datos["ri"])
                sonido = datos.get("sonido")
                musica = datos.get("musica")
                nuevo = escribir_audio(leer_panel(), n, ri, sonido, musica)

                def releida_ok(f, n=n, ri=ri, sonido=sonido, musica=musica):
                    fila = leer_fila(f, n, ri)
                    if sonido is not None and fila["sonido"] != sonido:
                        return False
                    if musica is not None and fila["musica"] != musica:
                        return False
                    return True

                _guardar_panel(nuevo, releida_ok, f"Actualizar sonido/música fila {ri} de guion {n} en panel")
                self._json({"ok": True, "fila": leer_fila(nuevo, n, ri)})

            elif ruta == "/api/imagen-ambiente-ia":
                # Trabajo async (ver _imagen_ambiente_ia) — agy tarda 15-40s,
                # más en una corrección; sin polling el navegador lo ve colgado.
                tid = f"t{len(TRABAJOS) + 1}"
                TRABAJOS[tid] = {"estado": "corriendo", "log": []}
                threading.Thread(target=_imagen_ambiente_ia, args=(tid, datos), daemon=True).start()
                self._json({"id": tid})

            elif ruta == "/api/imagen-producto-ia":
                if not datos.get("foto"):
                    raise ValueError("elegí un producto primero")
                tid = f"t{len(TRABAJOS) + 1}"
                TRABAJOS[tid] = {"estado": "corriendo", "log": []}
                threading.Thread(target=_imagen_producto_ia, args=(tid, datos), daemon=True).start()
                self._json({"id": tid})

            elif ruta == "/api/prompt-producto-ia":
                correccion = datos.get("correccion", "")
                es_correccion = bool(correccion and datos.get("conversation_id"))
                if not datos.get("escena") and not es_correccion:
                    raise ValueError("escribí la idea de la escena primero")
                prompt, cid = f_agy_video.prompt_producto_texto(
                    datos.get("escena", ""), correccion=correccion,
                    conversation_id=datos.get("conversation_id"))
                self._json({"ok": True, "prompt": prompt, "conversation_id": cid,
                            "proveedor": _proveedor_de(cid)})

            elif ruta == "/api/prompt-veo-ia":
                correccion = datos.get("correccion", "")
                es_correccion = bool(correccion and datos.get("conversation_id"))
                if not datos.get("idea") and not es_correccion:
                    raise ValueError("escribí la idea del concepto primero")
                prompt, cid = f_agy_video.generar_prompt_veo(
                    datos.get("idea", ""), datos.get("contexto_guion", ""),
                    correccion=correccion, conversation_id=datos.get("conversation_id"))
                self._json({"ok": True, "prompt": prompt, "conversation_id": cid,
                            "proveedor": _proveedor_de(cid)})

            elif ruta == "/api/correr":
                video = datos.get("video")
                if not video:
                    raise ValueError("Falta la grabación")
                extras = []
                if datos.get("sin_musica"):
                    extras.append("--sin-musica")
                if datos.get("preview"):
                    extras.append("--preview")
                if datos.get("sin_generar"):
                    extras.append("--sin-generar")
                self._json({"ok": True,
                            "corrida": lanzar_pipeline(video, int(datos["guion"]), extras)})

            elif ruta == "/api/detener":
                self._json({"ok": True, "corrida": detener_pipeline()})

            elif ruta == "/api/abrir-editor":
                self._json(abrir_editor_visual(datos.get("nombre")))

            else:
                self.send_error(404, "Ruta desconocida")
        except Exception as e:
            self._json({"ok": False, "error": str(e)}, code=400)


def main(puerto: int = 8899, abrir: bool = True):
    if not PANEL.exists():
        print(f"ERROR: no existe {PANEL}", file=sys.stderr)
        sys.exit(1)

    servidor, p = None, puerto
    while servidor is None:
        try:
            servidor = ThreadingHTTPServer(("127.0.0.1", p), Handler)
        except OSError:
            p += 1
            if p > puerto + 20:
                print(f"ERROR: no encontré un puerto libre cerca de {puerto}",
                      file=sys.stderr)
                sys.exit(1)
    if p != puerto:
        print(f"Puerto {puerto} ocupado — usando {p}.")

    url = f"http://127.0.0.1:{p}/"
    print(f"Panel conectado: {url}")
    print(f"Grabaciones en:  {config.DIR_ENTRADA}")
    print("(Ctrl+C para cerrar)")
    if abrir:
        webbrowser.open(url)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nPanel cerrado.")
    finally:
        servidor.server_close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Panel de producción conectado")
    ap.add_argument("--puerto", type=int, default=8899)
    ap.add_argument("--sin-abrir", action="store_true")
    args = ap.parse_args()
    main(args.puerto, not args.sin_abrir)
