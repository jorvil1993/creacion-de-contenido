"""
Fase 1a — Transcripción con WhisperX.

Genera un JSON con timestamps por palabra (±50ms vía alineación forzada wav2vec2)
y los segmentos de silencio detectados por el VAD integrado.

Uso:
    python f1_transcribir.py "ruta/al/video.mp4" [--salida ruta/salida.json]
"""
import argparse
import json
import sys
from pathlib import Path

import config


def transcribir(ruta_media: Path) -> dict:
    import gc
    import torch
    import whisperx

    device = config.WHISPER_DEVICE if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print("ADVERTENCIA: CUDA no disponible, transcribiendo en CPU (será lento).", file=sys.stderr)

    compute_type = config.WHISPER_COMPUTE_TYPE if device == "cuda" else "int8"

    print(f"Cargando modelo {config.WHISPER_MODELO} ({device}, {compute_type})...")
    modelo = whisperx.load_model(
        config.WHISPER_MODELO,
        device,
        compute_type=compute_type,
        language=config.WHISPER_IDIOMA,
        download_root=str(config.DIR_MODELOS),
    )

    audio = whisperx.load_audio(str(ruta_media))
    print("Transcribiendo...")
    resultado = modelo.transcribe(audio, batch_size=config.WHISPER_BATCH_SIZE, language=config.WHISPER_IDIOMA)

    del modelo
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()

    print("Alineando (timestamps por palabra)...")
    modelo_align, metadata = whisperx.load_align_model(
        language_code=config.WHISPER_IDIOMA, device=device
    )
    resultado_alineado = whisperx.align(
        resultado["segments"], modelo_align, metadata, audio, device,
        return_char_alignments=False,
    )

    del modelo_align
    gc.collect()
    if device == "cuda":
        torch.cuda.empty_cache()

    palabras = []
    segmentos = []
    for segmento in resultado_alineado["segments"]:
        palabras_segmento = []
        for palabra in segmento.get("words", []):
            if "start" not in palabra or "end" not in palabra:
                # whisperx a veces omite tiempos en palabras con baja confianza de alineación
                continue
            item = {
                "texto": palabra["word"].strip(),
                "inicio": round(palabra["start"], 3),
                "fin": round(palabra["end"], 3),
                "confianza": round(palabra.get("score", 0.0), 3),
            }
            palabras.append(item)
            palabras_segmento.append(item)
        if palabras_segmento:
            segmentos.append({
                "texto": segmento.get("text", "").strip(),
                "inicio": palabras_segmento[0]["inicio"],
                "fin": palabras_segmento[-1]["fin"],
            })

    silencios = _detectar_silencios(palabras, audio_duracion_s=len(audio) / 16000)

    return {
        "fuente": str(ruta_media),
        "idioma": config.WHISPER_IDIOMA,
        "modelo": config.WHISPER_MODELO,
        "palabras": palabras,
        "segmentos": segmentos,
        "silencios": silencios,
        "texto_completo": resultado.get("segments", []) and " ".join(
            s["text"].strip() for s in resultado["segments"]
        ) or "",
    }


def _detectar_silencios(palabras: list, audio_duracion_s: float) -> list:
    """Deriva huecos entre palabras consecutivas (incluye inicio/fin del audio)."""
    silencios = []
    cursor = 0.0
    for p in palabras:
        hueco = p["inicio"] - cursor
        if hueco > 0:
            silencios.append({"inicio": round(cursor, 3), "fin": round(p["inicio"], 3), "duracion": round(hueco, 3)})
        cursor = p["fin"]
    if audio_duracion_s - cursor > 0:
        silencios.append({"inicio": round(cursor, 3), "fin": round(audio_duracion_s, 3), "duracion": round(audio_duracion_s - cursor, 3)})
    return silencios


def main():
    parser = argparse.ArgumentParser(description="Transcribe un video/audio con WhisperX")
    parser.add_argument("entrada", type=str, help="Ruta al video o audio de entrada")
    parser.add_argument("--salida", type=str, default=None, help="Ruta del JSON de salida")
    args = parser.parse_args()

    ruta_entrada = Path(args.entrada)
    if not ruta_entrada.exists():
        print(f"ERROR: no existe {ruta_entrada}", file=sys.stderr)
        sys.exit(1)

    ruta_salida = Path(args.salida) if args.salida else ruta_entrada.with_suffix(".transcripcion.json")

    resultado = transcribir(ruta_entrada)
    ruta_salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Transcripción guardada en {ruta_salida}")
    print(f"  {len(resultado['palabras'])} palabras, {len(resultado['silencios'])} silencios detectados")


if __name__ == "__main__":
    main()
