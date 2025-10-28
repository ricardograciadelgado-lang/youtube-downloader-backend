from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import uuid
import time
from threading import Thread

app = Flask(__name__)
CORS(app)  # Permitir peticiones desde tu frontend

# Crear carpeta para descargas temporales
DOWNLOAD_FOLDER = 'downloads'
if not os.path.exists(DOWNLOAD_FOLDER):
    os.makedirs(DOWNLOAD_FOLDER)

# Limpiar archivos antiguos (más de 1 hora)
def cleanup_old_files():
    while True:
        try:
            current_time = time.time()
            for filename in os.listdir(DOWNLOAD_FOLDER):
                filepath = os.path.join(DOWNLOAD_FOLDER, filename)
                if os.path.isfile(filepath):
                    if current_time - os.path.getmtime(filepath) > 3600:  # 1 hora
                        os.remove(filepath)
        except Exception as e:
            print(f"Error en limpieza: {e}")
        time.sleep(600)  # Revisar cada 10 minutos

# Iniciar limpieza en segundo plano
cleanup_thread = Thread(target=cleanup_old_files, daemon=True)
cleanup_thread.start()

@app.route('/')
def home():
    return jsonify({
        "message": "Backend de Descargador de YouTube funcionando",
        "status": "online"
    })

@app.route('/api/download', methods=['POST'])
def download_video():
    try:
        data = request.get_json()
        url = data.get('url')
        format_type = data.get('format', 'video')
        quality = data.get('quality', '720p')
        
        if not url:
            return jsonify({"error": "URL no proporcionada"}), 400
        
        # Generar nombre único para el archivo
        unique_id = str(uuid.uuid4())[:8]
        
        # Opciones comunes para evitar detección de bot
        common_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'nocheckcertificate': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'referer': 'https://www.youtube.com/',
            'http_headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            }
        }
        
        # Configurar opciones de descarga
        if format_type == 'audio':
            ydl_opts = {
                **common_opts,
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{unique_id}_%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            }
        else:
            # Configurar calidad de video
            format_string = 'best'
            if quality == '1080p':
                format_string = 'bestvideo[height<=1080]+bestaudio/best[height<=1080]'
            elif quality == '720p':
                format_string = 'bestvideo[height<=720]+bestaudio/best[height<=720]'
            elif quality == '480p':
                format_string = 'bestvideo[height<=480]+bestaudio/best[height<=480]'
            elif quality == '360p':
                format_string = 'bestvideo[height<=360]+bestaudio/best[height<=360]'
            
            ydl_opts = {
                **common_opts,
                'format': format_string,
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{unique_id}_%(title)s.%(ext)s'),
                'merge_output_format': 'mp4'
            }
        
        # Descargar video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Si es audio, cambiar extensión a mp3
            if format_type == 'audio':
                filename = filename.rsplit('.', 1)[0] + '.mp3'
            
            video_title = info.get('title', 'video')
        
        return jsonify({
            "success": True,
            "message": "Video descargado exitosamente",
            "filename": os.path.basename(filename),
            "title": video_title,
            "download_url": f"/api/file/{os.path.basename(filename)}"
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@app.route('/api/file/<filename>')
def get_file(filename):
    try:
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        else:
            return jsonify({"error": "Archivo no encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/info', methods=['POST'])
def get_video_info():
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({"error": "URL no proporcionada"}), 400
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
        return jsonify({
            "success": True,
            "title": info.get('title'),
            "duration": info.get('duration'),
            "thumbnail": info.get('thumbnail'),
            "uploader": info.get('uploader')
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
