#!/usr/bin/env python3
"""
Paso 3: Generar audio TTS y enviar a Telegram.

Entrada: data/translated/YYYYMMDD.json
Salida: 
  - output/markdown/briefing_YYYYMMDD.md
  - output/audio/briefing_YYYYMMDD.ogg
  - output/audio/script_YYYYMMDD.txt
  - Envío a Telegram (texto + audio)

Ejecutar:
  python3 scripts/03_publish.py --date 20260528
  python3 scripts/03_publish.py  # usa fecha actual
"""

import os
import sys
import json
import argparse
import subprocess
from datetime import datetime
from pathlib import Path

# ==================== CONFIGURACIÓN ====================

BASE_DIR = Path(__file__).parent.parent

# TTS settings - Edge TTS (voces neuronales de Microsoft)
# Voces disponibles en español:
# - es-ES-AlvaroNeural (España, masculino)
# - es-ES-ElviraNeural (España, femenino)
# - es-MX-JorgeNeural (México, masculino)
# - es-MX-DaliaNeural (México, femenino) ⭐ RECOMENDADA (user favorite)
# - es-AR-ElenaNeural (Argentina, femenino)
# - es-AR-TomasNeural (Argentina, masculino)
TTS_VOICE = os.getenv('TTS_VOICE', 'es-MX-DaliaNeural')  # ⭐ México, femenina
TTS_OUTPUT_FORMAT = 'ogg'  # ogg para Telegram voice bubble
AUDIO_BITRATE = '32k'
AUDIO_SAMPLE_RATE = '48000'  # 48kHz para Telegram

# ==================== FUNCIONES ====================

def load_translated_data(date_str):
    """Carga el JSON traducido del paso 2."""
    input_file = BASE_DIR / 'data' / 'translated' / f"{date_str}.json"
    
    if not input_file.exists():
        raise FileNotFoundError(f"No se encontró: {input_file}")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_markdown_briefing(data):
    """Genera el markdown para Telegram."""
    
    date_es = data.get('date_es', data['date'])
    weather = data['weather']
    categories = data['categories']
    
    # Header
    md = f"🎙️ **Hermes Morning Briefing**\n\n"
    md += f"{date_es} | Jülich, Alemania\n\n"
    md += f"☀️ **Clima:** {weather['temp']}°C, {weather['condition']}\n"
    md += f"- Máxima: {weather['temp_max']}°C\n"
    md += f"- Mínima: {weather['temp_min']}°C\n\n"
    md += f"---\n\n"
    
    # Categorías
    for category, items in categories.items():
        if not items:
            continue
        
        md += f"**{category}**:\n\n"
        
        for i, item in enumerate(items, 1):
            title = item.get('title_es', item.get('title', 'Sin título'))
            summary = item.get('summary_es', item.get('description', '')[:200])
            url = item.get('url', '')
            
            md += f"{i}. **{title}**\n"
            md += f"   {summary}\n"
            if url:
                md += f"   [Más info]({url})\n"
            md += "\n"
    
    # Footer
    md += "---\n"
    md += "🎧 *Nota de voz con el resumen completo a continuación*\n"
    
    return md

def generate_audio_script(data):
    """Genera el guión de audio (texto plano para TTS)."""
    
    # El audio_script ya viene traducido del paso 2
    # Solo validamos que exista y tenga contenido
    script = data.get('audio_script', '')
    
    if not script:
        # Fallback: generar script básico desde los datos
        date_es = data.get('date_es', data['date'])
        weather = data['weather']
        categories = data['categories']
        
        script = f"Buenos días. Es {date_es}.\n\n"
        script += f"En Jülich tenemos {weather['temp']} grados, {weather['condition']}.\n"
        script += f"La máxima de hoy será de {weather['temp_max']} grados y la mínima de {weather['temp_min']} grados.\n\n"
        
        for category, items in categories.items():
            if items:
                script += f"{category}:\n\n"
                for item in items[:3]:  # Máximo 3 por categoría
                    summary = item.get('summary_es', item.get('description', '')[:150])
                    script += f"- {summary}\n"
                script += "\n"
        
        script += "Esto ha sido todo por ahora. Que tengas un gran día."
    
    return script

def generate_audio_tts_edge(script_text, output_path):
    """
    Genera audio usando Edge TTS (voces neuronales de Microsoft).
    
    Formato: OGG/Opus 48kHz mono 32kbps (óptimo para Telegram voice bubble)
    
    Requiere: pip install edge-tts
    """
    
    audio_dir = output_path.parent
    audio_dir.mkdir(parents=True, exist_ok=True)
    
    # Paso 1: Generar MP3 temporal con Edge TTS
    temp_mp3 = audio_dir / f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3"
    
    print(f"   🎙️  Generando audio con Edge TTS (voz: {TTS_VOICE})...")
    
    # Edge TTS command: edge-tts --voice es-MX-DaliaNeural --text "texto" --write-media output.mp3
    try:
        edge_result = subprocess.run(
            [
                'edge-tts',
                '--voice', TTS_VOICE,
                '--text', script_text,
                '--write-media', str(temp_mp3)
            ],
            capture_output=True,
            text=True,
            timeout=300  # 5 minutos máx
        )
        
        if edge_result.returncode != 0:
            print(f"   ❌ Error en edge-tts: {edge_result.stderr[:200]}")
            print(f"   💡 ¿Instalaste edge-tts? Ejecutá: pip install edge-tts")
            return None
        
        # Esperar que el archivo exista
        import time
        for _ in range(10):
            if temp_mp3.exists() and temp_mp3.stat().st_size > 0:
                break
            time.sleep(0.5)
        
        if not temp_mp3.exists():
            print(f"   ❌ El archivo MP3 no se generó")
            return None
        
        print(f"   ✓ MP3 generado: {temp_mp3.stat().st_size / 1024:.1f} KB")
        
        # Paso 2: Convertir a OGG/Opus con ffmpeg
        print(f"   🎵 Convirtiendo a OGG/Opus...")
        
        ffmpeg_result = subprocess.run(
            [
                'ffmpeg', '-y',
                '-i', str(temp_mp3),
                '-codec:a', 'libopus',
                '-b:a', AUDIO_BITRATE,
                '-ar', AUDIO_SAMPLE_RATE,
                '-ac', '1',  # mono
                '-vbr', 'on',
                '-application', 'voip',  # CRÍTICO: optimización para voz en Telegram
                str(output_path)
            ],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # Limpiar temporal
        if temp_mp3.exists():
            temp_mp3.unlink()
        
        if ffmpeg_result.returncode != 0:
            print(f"   ❌ Error en ffmpeg: {ffmpeg_result.stderr[:200]}")
            return None
        
        print(f"   ✓ OGG generado: {output_path.stat().st_size / 1024:.1f} KB")
        
        # Esperar que el archivo esté completamente escrito
        time.sleep(0.5)
        
        return str(output_path)
        
    except subprocess.TimeoutExpired:
        print(f"   ❌ Timeout en edge-tts (más de 5 minutos)")
        return None
    except FileNotFoundError:
        print(f"   ❌ edge-tts no encontrado. Instalá con: pip install edge-tts")
        return None
    except Exception as e:
        print(f"   ❌ Error inesperado: {e}")
        return None

def generate_audio_tts_macos(script_text, output_path):
    """
    Fallback: Genera audio usando macOS 'say' + ffmpeg.
    
    Formato: OGG/Opus 48kHz mono 32kbps (óptimo para Telegram voice bubble)
    """
    
    audio_dir = output_path.parent
    audio_dir.mkdir(parents=True, exist_ok=True)
    
    # Paso 1: Generar AIFF temporal con macOS say
    temp_aiff = audio_dir / f"temp_{datetime.now().strftime('%Y%m%d_%H%M%S')}.aiff"
    
    print(f"   🎙️  Generando audio con macOS say (voz: Monica)...")
    
    say_result = subprocess.run(
        ['say', '-o', str(temp_aiff), '-v', 'Monica', script_text],
        capture_output=True,
        text=True,
        timeout=300  # 5 minutos máx
    )
    
    if say_result.returncode != 0:
        print(f"   ❌ Error en 'say': {say_result.stderr}")
        return None
    
    # Esperar que el archivo exista
    import time
    for _ in range(10):
        if temp_aiff.exists() and temp_aiff.stat().st_size > 0:
            break
        time.sleep(0.5)
    
    if not temp_aiff.exists():
        print(f"   ❌ El archivo AIFF no se generó")
        return None
    
    print(f"   ✓ AIFF generado: {temp_aiff.stat().st_size / 1024:.1f} KB")
    
    # Paso 2: Convertir a OGG/Opus con ffmpeg
    print(f"   🎵 Convirtiendo a OGG/Opus...")
    
    ffmpeg_result = subprocess.run(
        [
            'ffmpeg', '-y',
            '-i', str(temp_aiff),
            '-codec:a', 'libopus',
            '-b:a', AUDIO_BITRATE,
            '-ar', AUDIO_SAMPLE_RATE,
            '-ac', '1',  # mono
            '-vbr', 'on',
            '-application', 'voip',  # CRÍTICO: optimización para voz en Telegram
            str(output_path)
        ],
        capture_output=True,
        text=True,
        timeout=120
    )
    
    # Limpiar temporal
    if temp_aiff.exists():
        temp_aiff.unlink()
    
    if ffmpeg_result.returncode != 0:
        print(f"   ❌ Error en ffmpeg: {ffmpeg_result.stderr[:200]}")
        return None
    
    print(f"   ✓ OGG generado: {output_path.stat().st_size / 1024:.1f} KB")
    
    # Esperar que el archivo esté completamente escrito
    time.sleep(0.5)
    
    return str(output_path)

def generate_audio_tts(script_text, output_path):
    """
    Genera audio usando el mejor TTS disponible.
    
    Prioridad:
    1. Edge TTS (voces neuronales, más natural)
    2. macOS say (fallback, voz robótica)
    """
    
    # Intentar Edge TTS primero
    result = generate_audio_tts_edge(script_text, output_path)
    
    if result is None:
        print(f"   ⚠️  Edge TTS falló, usando fallback macOS say...")
        result = generate_audio_tts_macos(script_text, output_path)
    
    return result

def send_to_telegram(markdown_text, audio_path):
    """
    Envía el briefing a Telegram.
    
    IMPORTANTE: Para que Telegram muestre la barra de progreso,
    debemos usar la etiqueta [[audio_as_voice]] antes del MEDIA:
    """
    
    print(f"   📬 Enviando a Telegram...")
    
    # Opción A: Usar hermes send (recomendado)
    try:
        # Enviar texto primero
        print(f"   📤 Enviando markdown...")
        hermes_text = subprocess.run(
            ['hermes', 'send', '--to', 'telegram', markdown_text],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if hermes_text.returncode != 0:
            print(f"   ⚠️  Error enviando texto: {hermes_text.stderr[:100]}")
        else:
            print(f"   ✓ Texto enviado")
        
        # Enviar audio como voice message con barra de progreso
        # CRÍTICO: Usar etiqueta [[audio_as_voice]] para que Telegram lo muestre como nota de voz
        print(f"   🎵 Enviando audio (voice message con barra de progreso)...")
        
        # Construir mensaje con etiqueta especial para voice
        voice_message = "[[audio_as_voice]]\nMEDIA:" + str(audio_path)
        
        hermes_audio = subprocess.run(
            ['hermes', 'send', '--to', 'telegram', voice_message],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if hermes_audio.returncode != 0:
            print(f"   ⚠️  Error enviando audio: {hermes_audio.stderr[:100]}")
        else:
            print(f"   ✓ Audio enviado como nota de voz")
        
        return True
        
    except FileNotFoundError:
        print(f"   ⚠️  Comando 'hermes' no encontrado")
        print(f"   💡 Alternativa: enviar manualmente los archivos")
        return False
    except Exception as e:
        print(f"   ❌ Error enviando: {e}")
        return False

# ==================== MAIN ====================

def main():
    parser = argparse.ArgumentParser(description='Paso 3: Publicar briefing')
    parser.add_argument(
        '--date',
        type=str,
        default=datetime.now().strftime('%Y%m%d'),
        help='Fecha a procesar (YYYYMMDD)'
    )
    
    args = parser.parse_args()
    date_str = args.date
    
    print(f"======================================================================")
    print(f"🎙️ Hermes Morning Briefing - Paso 3: Publicar")
    print(f"   Fecha: {date_str}")
    print(f"   Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"======================================================================")
    
    # 1. Cargar datos traducidos
    print(f"\n▶️ Cargando datos traducidos...")
    try:
        data = load_translated_data(date_str)
        print(f"   ✅ Datos cargados")
    except FileNotFoundError as e:
        print(f"   ❌ Error: {e}")
        print(f"   Ejecutá primero: python3 scripts/02_translate_news.py --date {date_str}")
        return 1
    
    # 2. Generar markdown
    print(f"\n▶️ Generando markdown...")
    markdown_text = generate_markdown_briefing(data)
    
    md_path = BASE_DIR / 'output' / 'markdown' / f"briefing_{date_str}.md"
    md_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(markdown_text)
    
    print(f"   ✓ Markdown: {md_path} ({md_path.stat().st_size / 1024:.1f} KB)")
    
    # 3. Generar audio script
    print(f"\n▶️ Generando audio script...")
    audio_script = generate_audio_script(data)
    
    script_path = BASE_DIR / 'output' / 'audio' / f"script_{date_str}.txt"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(audio_script)
    
    print(f"   ✓ Script: {script_path} ({script_path.stat().st_size / 1024:.1f} KB)")
    print(f"      Palabras: {len(audio_script.split())}")
    
    # 4. Generar audio TTS
    print(f"\n▶️ Generando audio TTS...")
    audio_path = BASE_DIR / 'output' / 'audio' / f"briefing_{date_str}.ogg"
    
    audio_file = generate_audio_tts(audio_script, audio_path)
    
    if audio_file is None:
        print(f"   ❌ Error generando audio")
        print(f"   💡 Verificá que edge-tts esté instalado: pip install edge-tts")
        return 1
    
    # 5. Enviar a Telegram
    print(f"\n▶️ Enviando a Telegram...")
    send_success = send_to_telegram(markdown_text, audio_path)
    
    if send_success:
        print(f"   ✅ Briefing enviado a Telegram")
    else:
        print(f"   ⚠️  Error enviando a Telegram")
        print(f"   💡 Los archivos están guardados en:")
        print(f"      - Markdown: {md_path}")
        print(f"      - Audio: {audio_path}")
    
    print(f"\n✅ Paso 3 completado")
    
    return 0

if __name__ == '__main__':
    exit(main())
