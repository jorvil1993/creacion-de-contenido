"""
Fase 17 — Recorte de José del fondo (el "pantalla verde" del B-roll al 70%).

Para qué: en el modo `recorte` un B-roll ocupa la franja de arriba del cuadro y
José se compone ENCIMA, recortado de su cuarto, en vez de quedar tapado. Este
módulo produce la capa de José: un .mov ProRes 4444 con canal alfa que dura
exactamente lo que dura el B-roll.

Quién lo usa: f4_retencion.py, que le presta su función de encuadre para que
la capa recortada lleve EXACTAMENTE el mismo zoom y paneo que el video de
fondo. Sin eso, José saldría desplazado respecto de sí mismo — es el motivo de
que el matte se genere acá dentro del render y no como una fase suelta.

Modelo: Robust Video Matting (resnet50). El porqué de resnet50 y no del modelo
chico está en config.RVM_MODELO; en resumen, mobilenetv3 se lleva el respaldo de
la silla pegado a la cabeza.

Uso suelto (diagnóstico):
    python f17_matte.py --estado
    python f17_matte.py video.mp4 --ini 24 --fin 27 --salida matte.mov
"""
import argparse
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np

import config


def _log(msg):
    print(msg, flush=True)


# ---------------------------------------------------------------------------
# Modelo
# ---------------------------------------------------------------------------
def instalado() -> bool:
    return config.RVM_ARCHIVO.exists() and config.RVM_ARCHIVO.stat().st_size > 1_000_000


def asegurar_modelo() -> bool:
    """Descarga el checkpoint si falta (~100 MB). True si está listo."""
    if instalado():
        return True
    config.RVM_ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
    _log(f"  descargando {config.RVM_ARCHIVO.name} (~100 MB)...")
    try:
        tmp = config.RVM_ARCHIVO.with_suffix(".parcial")
        urllib.request.urlretrieve(config.RVM_URL, tmp)
        tmp.replace(config.RVM_ARCHIVO)
        _log(f"  modelo listo: {config.RVM_ARCHIVO}")
        return True
    except Exception as e:
        _log(f"AVISO: no se pudo descargar el modelo de matting ({e}).")
        return False


class Matte:
    """Segmentador con memoria entre cuadros.

    RVM es recurrente: cada llamada a `alfa()` recibe el estado de la anterior.
    Eso es lo que hace que el borde no tiemble (a diferencia de rembg, que trata
    cada frame como una foto suelta). Por lo mismo, los frames hay que pasarlos
    EN ORDEN, y al empezar una ventana nueva hay que llamar a `reiniciar()`.
    """

    def __init__(self):
        import torch

        if not asegurar_modelo():
            raise RuntimeError("falta el modelo de matting (ver config.RVM_ARCHIVO)")
        self.torch = torch
        self.dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if self.dev.type == "cpu":
            _log("  AVISO: sin CUDA — el matting por CPU es MUY lento "
                 "(minutos por segundo de video).")
        modelo = torch.jit.load(str(config.RVM_ARCHIVO)).eval().to(self.dev)
        self.modelo = torch.jit.freeze(modelo)
        self.rec = [None] * 4

    def reiniciar(self):
        self.rec = [None] * 4

    def alfa(self, frame_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """(rgb_primer_plano, alfa) del frame. Ambos uint8, mismo alto/ancho."""
        torch = self.torch
        rgb = frame_bgr[:, :, ::-1].copy()          # BGR de cv2 -> RGB
        with torch.no_grad():
            src = (torch.from_numpy(rgb).to(self.dev)
                   .permute(2, 0, 1).float().div_(255).unsqueeze(0))
            fgr, pha, *self.rec = self.modelo(src, *self.rec, config.RVM_RATIO)
            fgr_u8 = fgr[0].clamp(0, 1).mul(255).byte().permute(1, 2, 0).cpu().numpy()
            pha_u8 = pha[0, 0].clamp(0, 1).mul(255).byte().cpu().numpy()
        return fgr_u8, pha_u8


# ---------------------------------------------------------------------------
# Máscara de opacidad del B-roll
# ---------------------------------------------------------------------------
def mascara_degradado(ancho: int, alto: int, degradado: int, destino: Path) -> Path:
    """PNG en escala de grises: opaco arriba, transparente en el borde de abajo.

    La curva es smoothstep y no una rampa recta a propósito: una rampa lineal
    deja ver dónde empieza y dónde termina la transición como dos líneas tenues,
    que es justo lo que el degradado viene a evitar.

    Se cachea por (ancho, alto, degradado): el mismo archivo sirve para todos los
    B-rolls del video, que miden todos igual.
    """
    from PIL import Image

    if destino.exists():
        return destino
    degradado = max(1, min(degradado, alto))
    y = np.arange(alto, dtype=np.float32)
    t = np.clip((y - (alto - degradado)) / degradado, 0.0, 1.0)
    opacidad = 1.0 - (t * t * (3.0 - 2.0 * t))
    col = (opacidad * 255).astype(np.uint8)
    destino.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.tile(col[:, None], (1, ancho)), mode="L").save(destino)
    return destino


# ---------------------------------------------------------------------------
# Render de la capa
# ---------------------------------------------------------------------------
def render_ventana(ruta_video: Path, ini: float, fin: float, ruta_salida: Path,
                   w_out: int, h_out: int, fps: float,
                   encuadrar=None, matte: Matte = None) -> Path | None:
    """Escribe un .mov con alfa que cubre el tramo [ini, fin) del video.

    `encuadrar(frame, t)` -> frame ya recortado a w_out x h_out. f4_retencion le
    pasa la suya para que la capa lleve el mismo zoom que el fondo; si no se
    pasa ninguna, se escala el frame entero.

    Devuelve None si el tramo no tiene frames.
    """
    import cv2

    matte = matte or Matte()
    matte.reiniciar()

    cap = cv2.VideoCapture(str(ruta_video))
    if not cap.isOpened():
        _log(f"AVISO: no se pudo abrir {ruta_video} para el matte.")
        return None

    # Arrancar antes de la ventana para que la máscara llegue asentada al primer
    # frame que se ve; esos frames de calentamiento se procesan y se tiran.
    t_calienta = max(0.0, ini - config.RVM_CALENTAMIENTO_S)
    cap.set(cv2.CAP_PROP_POS_FRAMES, int(round(t_calienta * fps)))

    ruta_salida.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w_out}x{h_out}", "-r", f"{fps}",
        "-i", "pipe:0",
        # ProRes 4444: el alfa sobrevive sin el submuestreo de croma que
        # destrozaría el borde del pelo.
        "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
        str(ruta_salida),
    ]
    log_ffmpeg = ruta_salida.with_suffix(".ffmpeg.log")
    escritos, t0 = 0, time.time()
    with open(log_ffmpeg, "wb") as flog:
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=flog, stderr=flog)
        idx = 0
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                t = t_calienta + idx / fps
                idx += 1
                if t >= fin:
                    break
                enc = encuadrar(frame, t) if encuadrar else cv2.resize(frame, (w_out, h_out))
                fgr, pha = matte.alfa(enc)
                if t < ini:
                    continue                      # calentamiento: no se escribe
                proc.stdin.write(np.dstack([fgr, pha]).tobytes())
                escritos += 1
        except BrokenPipeError:
            pass
        finally:
            cap.release()
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
            proc.wait()

    if proc.returncode != 0 or escritos == 0:
        cola = log_ffmpeg.read_text(encoding="utf-8", errors="replace")[-2000:]
        _log(f"AVISO: falló el matte de {ini:.1f}-{fin:.1f}s:\n{cola}")
        return None
    log_ffmpeg.unlink(missing_ok=True)
    dt = time.time() - t0
    _log(f"  matte {ini:.1f}-{fin:.1f}s: {escritos} frames en {dt:.1f}s "
         f"({escritos / dt:.1f} fps) -> {ruta_salida.name}")
    return ruta_salida


def main():
    ap = argparse.ArgumentParser(description="Recorte de persona con RVM")
    ap.add_argument("video", nargs="?", default=None)
    ap.add_argument("--ini", type=float, default=0.0)
    ap.add_argument("--fin", type=float, default=3.0)
    ap.add_argument("--salida", type=str, default="matte.mov")
    ap.add_argument("--estado", action="store_true")
    args = ap.parse_args()

    if args.estado:
        import torch
        print(f"modelo:        {config.RVM_ARCHIVO} ({instalado()})")
        print(f"  variante:    {config.RVM_MODELO} · ratio {config.RVM_RATIO}")
        print(f"CUDA:          {torch.cuda.is_available()}"
              + (f" ({torch.cuda.get_device_name(0)})" if torch.cuda.is_available() else ""))
        print(f"franja B-roll: {config.BROLL_RECORTE_ALTO_PCT:.0%} "
              f"({int(config.ALTO * config.BROLL_RECORTE_ALTO_PCT)} px) · "
              f"degradado {config.BROLL_RECORTE_DEGRADADO_PX} px")
        return

    if not args.video:
        ap.error("indica un video o --estado")
    ruta = render_ventana(Path(args.video), args.ini, args.fin, Path(args.salida),
                          config.ANCHO, config.ALTO, config.FPS)
    sys.exit(0 if ruta else 1)


if __name__ == "__main__":
    main()
