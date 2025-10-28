from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import yt_dlp
import os
import uuid
import time
import re
from threading import Thread

import re
from urllib.parse import quote

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

def sanitize_filename(filename):
    """Limpia el nombre del archivo de caracteres problemáticos"""
    # Remover caracteres especiales pero mantener espacios, guiones y puntos
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Limitar longitud
    if len(filename) > 200:
        name, ext = os.path.splitext(filename)
        filename = name[:200] + ext
    return filename

def detect_platform(url):
    """Detecta la plataforma del video"""
    if 'tiktok.com' in url:
        return 'tiktok'
    elif 'instagram.com' in url:
        return 'instagram'
    elif 'twitter.com' in url or 'x.com' in url:
        return 'twitter'
    elif 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    elif 'facebook.com' in url or 'fb.watch' in url:
        return 'facebook'
    else:
        return 'unknown'

@app.route('/')
def home():
    return jsonify({
        "message": "Backend Multi-Plataforma funcionando",
        "status": "online",
        "platforms": ["TikTok", "Instagram", "Twitter/X", "YouTube", "Facebook"]
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
        
        # Detectar plataforma
        platform = detect_platform(url)
        
        # Generar nombre único para el archivo
        unique_id = str(uuid.uuid4())[:8]
        
        # Configurar opciones según la plataforma
        if platform == 'tiktok':
            # TikTok - SIN MARCA DE AGUA
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{unique_id}_%(title).100s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'extractor_args': {
                    'tiktok': {
                        'api_hostname': 'api16-normal-c-useast1a.tiktokv.com'
                    }
                },
                'restrictfilenames': True  # Evita caracteres problemáticos
            }
            
        elif platform == 'instagram':
            # Instagram
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{unique_id}_%(title).100s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'restrictfilenames': True
            }
            
        elif platform == 'twitter':
            # Twitter/X
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{unique_id}_%(title).100s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'restrictfilenames': True
            }
            
        elif platform == 'youtube':
            # YouTube (con opciones anti-bot)
            common_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'nocheckcertificate': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'extractor_args': {
                    'youtube': {
                        'skip': ['hls', 'dash'],
                        'player_client': ['android', 'web']
                    }
                }
            }
            
            if format_type == 'audio':
                ydl_opts = {
                    **common_opts,
                    'format': 'bestaudio/best',
                    'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{unique_id}_%(title).100s.%(ext)s'),
                    'restrictfilenames': True,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }]
                }
            else:
                format_string = 'best[height<=720]'
                if quality == '1080p':
                    format_string = 'best[height<=1080]'
                elif quality == '720p':
                    format_string = 'best[height<=720]'
                elif quality == '480p':
                    format_string = 'best[height<=480]'
                elif quality == '360p':
                    format_string = 'best[height<=360]'
                elif quality == 'highest':
                    format_string = 'best'
                
                ydl_opts = {
                    **common_opts,
                    'format': format_string,
                    'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{unique_id}_%(title).100s.%(ext)s'),
                    'restrictfilenames': True
                }
        
        elif platform == 'facebook':
            # Facebook
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(DOWNLOAD_FOLDER, f'{unique_id}_%(title).100s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'restrictfilenames': True
            }
            
        else:
            return jsonify({
                "error": "Plataforma no soportada. Usa: TikTok, Instagram, Twitter/X, YouTube o Facebook"
            }), 400
        
        # Descargar video
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Si es audio de YouTube, cambiar extensión a mp3
            if platform == 'youtube' and format_type == 'audio':
                filename = filename.rsplit('.', 1)[0] + '.mp3'
            
            # Verificar que el archivo existe
            if not os.path.exists(filename):
                # Buscar el archivo descargado en la carpeta
                downloaded_files = [f for f in os.listdir(DOWNLOAD_FOLDER) if f.startswith(unique_id)]
                if downloaded_files:
                    filename = os.path.join(DOWNLOAD_FOLDER, downloaded_files[0])
                else:
                    raise Exception("El archivo no se descargó correctamente")
            
            video_title = info.get('title', 'video')
            platform_name = platform.capitalize()
        
        return jsonify({
            "success": True,
            "message": f"Video de {platform_name} descargado exitosamente",
            "filename": os.path.basename(filename),
            "title": video_title,
            "platform": platform_name,
            "download_url": f"/api/file/{os.path.basename(filename)}"
        })
        
    except Exception as e:
        error_msg = str(e)
        
        # Mensajes de error más amigables
        if 'Sign in' in error_msg or 'bot' in error_msg.lower():
            error_msg = "La plataforma está bloqueando la descarga. YouTube puede requerir esperar unos minutos e intentar de nuevo."
        elif 'Video unavailable' in error_msg or 'not available' in error_msg:
            error_msg = "El video no está disponible, es privado o fue eliminado."
        elif 'age' in error_msg.lower():
            error_msg = "Este video tiene restricción de edad y no puede ser descargado."
        elif 'Private video' in error_msg:
            error_msg = "Este video es privado y no puede ser descargado."
        
        return jsonify({
            "success": False,
            "error": error_msg
        }), 500

@app.route('/api/file/<filename>')
def get_file(filename):
    try:
        # Sanitizar el nombre del archivo para evitar problemas de seguridad
        filename = os.path.basename(filename)
        filepath = os.path.join(DOWNLOAD_FOLDER, filename)
        
        # Buscar el archivo
        if not os.path.exists(filepath):
            # Si no existe con ese nombre exacto, buscar archivos similares
            for file in os.listdir(DOWNLOAD_FOLDER):
                if filename in file or file.startswith(filename.split('_')[0]):
                    filepath = os.path.join(DOWNLOAD_FOLDER, file)
                    break
        
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True, download_name=filename)
        else:
            return jsonify({"error": "Archivo no encontrado en el servidor"}), 404
    except Exception as e:
        return jsonify({"error": f"Error al enviar archivo: {str(e)}"}), 500

@app.route('/api/info', methods=['POST'])
def get_video_info():
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({"error": "URL no proporcionada"}), 400
        
        platform = detect_platform(url)
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
        return jsonify({
            "success": True,
            "title": info.get('title'),
            "duration": info.get('duration'),
            "thumbnail": info.get('thumbnail'),
            "uploader": info.get('uploader'),
            "platform": platform.capitalize()
        })
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
