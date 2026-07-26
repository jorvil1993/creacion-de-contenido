import subprocess
import shutil
from pathlib import Path
from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent.parent
ENTRADA = RAIZ / "contexto" / "sol video kindle.mp4"
SALIDA = RAIZ / "assets" / "sol_video_pip.mov"

def main():
    if not ENTRADA.exists():
        print(f"No existe {ENTRADA}")
        return

    ancho, alto = 400, 520
    radio = 36
    borde = 10
    w_tarjeta, h_tarjeta = ancho + borde * 2, alto + borde * 2
    NAVY = (10, 42, 62, 255)
    CIAN = (79, 209, 217, 255)
    BLANCO = (255, 255, 255, 255)

    mascara = Image.new("L", (ancho, alto), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([0, 0, ancho - 1, alto - 1], radius=radio, fill=255)

    cmd_in = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(ENTRADA),
        "-f", "image2pipe", "-vcodec", "rawvideo", "-pix_fmt", "rgb24", "-"
    ]
    p_in = subprocess.Popen(cmd_in, stdout=subprocess.PIPE)

    cmd_out = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-pix_fmt", "rgba",
        "-s", f"{w_tarjeta}x{h_tarjeta}", "-r", "24",
        "-i", "pipe:0",
        "-c:v", "prores_ks", "-profile:v", "4444", "-pix_fmt", "yuva444p10le",
        str(SALIDA)
    ]
    p_out = subprocess.Popen(cmd_out, stdin=subprocess.PIPE)

    frame_bytes = 1280 * 720 * 3
    aspecto_obj = ancho / alto

    try:
        while True:
            raw = p_in.stdout.read(frame_bytes)
            if not raw or len(raw) < frame_bytes:
                break
            img = Image.frombytes("RGB", (1280, 720), raw).convert("RGBA")
            
            # Crop center
            w, h = img.size
            nuevo_w = int(h * aspecto_obj)
            x0 = (w - nuevo_w) // 2
            img_crop = img.crop((x0, 0, x0 + nuevo_w, h)).resize((ancho, alto), Image.LANCZOS)

            marco = Image.new("RGBA", (w_tarjeta, h_tarjeta), (0, 0, 0, 0))
            draw_marco = ImageDraw.Draw(marco)
            draw_marco.rounded_rectangle([0, 0, w_tarjeta - 1, h_tarjeta - 1], radius=radio + borde, fill=BLANCO)
            draw_marco.rounded_rectangle([0, 0, w_tarjeta - 1, h_tarjeta - 1], radius=radio + borde, outline=CIAN, width=3)
            marco.paste(img_crop, (borde, borde), mascara)

            p_out.stdin.write(marco.tobytes())
    finally:
        p_in.stdout.close()
        p_in.wait()
        p_out.stdin.close()
        p_out.wait()

    print(f"Creado {SALIDA} ({SALIDA.stat().st_size} bytes)")

if __name__ == "__main__":
    main()
