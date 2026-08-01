import json
import os
import uuid
import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import yt_dlp
from faster_whisper import WhisperModel

DIR_TRABAJO = Path("c:/Users/devic/OneDrive/CLAUDE CODE/creacion-de-contenido")
DIR_TEMP = DIR_TRABAJO / "temp_viral"
DIR_TEMP.mkdir(exist_ok=True)

print("Cargando modelo Whisper...")
try:
    # Usar int8 para reducir consumo de VRAM
    whisper_model = WhisperModel("small", device="cuda", compute_type="int8_float16")
    print("Modelo Whisper cargado en CUDA.")
except Exception as e:
    print(f"Error cargando CUDA, intentando CPU: {e}")
    whisper_model = WhisperModel("small", device="cpu", compute_type="int8")

def descargar_y_extraer_datos(url):
    temp_id = str(uuid.uuid4())[:8]
    # Hacemos que yt-dlp guarde como .mp3 directamente después del postprocesamiento
    base_template = str(DIR_TEMP / f'audio_{temp_id}')
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': base_template + '.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False,
        'no_warnings': True,
        'extract_flat': False
    }

    metadata = {}
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info_dict = ydl.extract_info(url, download=True)
        
        metadata = {
            "title": info_dict.get('title', 'Sin título'),
            "description": info_dict.get('description', ''),
            "view_count": info_dict.get('view_count', 0),
            "like_count": info_dict.get('like_count', 0),
            "comment_count": info_dict.get('comment_count', 0),
            "duration": info_dict.get('duration', 0),
            "uploader": info_dict.get('uploader', ''),
            "tags": info_dict.get('tags', []),
            "platform": info_dict.get('extractor_key', '')
        }

    # El archivo resultante será mp3
    audio_path = base_template + '.mp3'
    return metadata, audio_path

def transcribir_audio(audio_path):
    segments, info = whisper_model.transcribe(audio_path, beam_size=5)
    
    texto_completo = []
    tramos = []
    for segment in segments:
        texto_completo.append(segment.text)
        tramos.append({
            "start": segment.start,
            "end": segment.end,
            "text": segment.text
        })
        
    return " ".join(texto_completo), tramos

class ViralHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200, "ok")
        self.end_headers()

    def do_POST(self):
        if self.path == '/api/analizar':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            datos = json.loads(post_data.decode('utf-8'))
            
            url = datos.get('url')
            if not url:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No URL provided"}).encode('utf-8'))
                return

            try:
                print(f"\\n---> [1/2] Extrayendo datos y descargando audio de: {url}")
                metadata, audio_path = descargar_y_extraer_datos(url)
                
                print(f"---> [2/2] Transcribiendo audio: {audio_path}")
                texto, tramos = transcribir_audio(audio_path)
                
                if os.path.exists(audio_path):
                    os.remove(audio_path)
                    
                resultado = {
                    "metadata": metadata,
                    "transcripcion": {
                        "texto_completo": texto,
                        "segmentos": tramos
                    }
                }
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(resultado).encode('utf-8'))
                
            except Exception as e:
                import traceback
                traceback.print_exc()
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    port = 8777
    server_address = ('', port)
    httpd = HTTPServer(server_address, ViralHandler)
    print(f"Servidor de Laboratorio Viral escuchando en puerto {port}...")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
