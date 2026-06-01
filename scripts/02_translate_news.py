#!/usr/bin/env python3
"""
Paso 2: Traducir noticias con LLM.

Entrada: data/raw/YYYYMMDD.json
Salida: data/translated/YYYYMMDD.json

Ejecutar:
  python3 scripts/02_translate_news.py --date 20260528
"""

import json
import httpx
import argparse
from datetime import datetime
from pathlib import Path

# ==================== CONFIG ====================

LLM_MODEL = "gemini-3-flash-preview:latest"
LLM_TIMEOUT = 120  # segundos
MAX_NEWS_PER_CATEGORY = 3

# ==================== FUNCIONES ====================

def load_raw_data(date_str):
    """Carga el JSON crudo del paso 1."""
    
    raw_path = Path(f"data/raw/{date_str}.json")
    
    if not raw_path.exists():
        raise FileNotFoundError(f"No se encontró {raw_path}")
    
    with open(raw_path) as f:
        return json.load(f)

def build_prompt(raw_data):
    """Construye el prompt para el LLM."""
    
    date_str = raw_data['date']
    # Formato: "Jueves, 28 de mayo de 2026"
    date_obj = datetime.strptime(date_str, '%Y%m%d')
    
    # Traducir día y mes manualmente (strftime usa locale del sistema)
    dias = {
        'Monday': 'Lunes', 'Tuesday': 'Martes', 'Wednesday': 'Miércoles',
        'Thursday': 'Jueves', 'Friday': 'Viernes', 'Saturday': 'Sábado', 'Sunday': 'Domingo'
    }
    meses = {
        'January': 'enero', 'February': 'febrero', 'March': 'marzo',
        'April': 'abril', 'May': 'mayo', 'June': 'junio',
        'July': 'julio', 'August': 'agosto', 'September': 'septiembre',
        'October': 'octubre', 'November': 'noviembre', 'December': 'diciembre'
    }
    
    day_name = dias.get(date_obj.strftime('%A'), date_obj.strftime('%A'))
    month_name = meses.get(date_obj.strftime('%B'), date_obj.strftime('%B'))
    date_es = f"{day_name}, {date_obj.day} de {month_name} de {date_obj.year}"
    
    weather = raw_data['weather']
    categories = raw_data['categories']
    
    # Lista compacta de noticias (máximo 3 por categoría)
    news_lines = []
    for cat, items in categories.items():
        if not items:
            continue
        for item in items[:MAX_NEWS_PER_CATEGORY]:
            title = item['title'][:100]  # Truncar título
            desc = item['description'][:200]  # Truncar descripción (más largo para contexto)
            url = item['url']
            news_lines.append(f"• [{cat}] {title}\n  Descripción: {desc}\n  URL: {url}")
    
    news_text = "\n".join(news_lines)
    
    prompt = f"""Tu tarea: Traducir noticias al español y generar un briefing matutino.

FECHA: {date_es}
CLIMA: {weather['temp']}°C, {weather['condition']} (Máx: {weather['temp_max']}°C, Mín: {weather['temp_min']}°C)

NOTICIAS ORIGINALES:
{news_text}

---

GENERÁ este JSON exacto (sin markdown, sin texto extra):

{{
  "date": "{raw_data['date']}",
  "date_es": "{date_es}",
  "weather": {{
    "temp": {weather['temp']},
    "temp_max": {weather['temp_max']},
    "temp_min": {weather['temp_min']},
    "condition": "{weather['condition']}"
  }},
  "categories": {{
    "INTERNACIONALES": [
      {{"title_es": "título traducido", "summary_es": "resumen 1-2 oraciones completas", "url": "https://www.bbc.com/news/..."}}
    ],
    "ALEMANIA": [...],
    "CIENCIA": [...],
    "TECNOLOGÍA": [...],
    "IA / MACHINE LEARNING": [...],
    "DESARROLLO": [...]
  }},
  "audio_script": "Guión para locución en español, texto plano, sin emojis, sin URLs, fluido como radio.

Estructura OBLIGATORIA:
1. Saludo: 'Buenos días. Es {date_es}. En Jülich tenemos...'
2. Clima: temperatura, condición, máxima y mínima
3. Mencionar balance: 'Hoy tienes un balance equilibrado de noticias positivas y negativas para una perspectiva completa'
4. Noticias por categoría (mencionar 2-3 noticias por categoría):
   - 'En las noticias internacionales...' (mencionar 2-3 titulares)
   - 'En Alemania...' (mencionar 2-3 titulares)
   - 'En ciencia...' (mencionar 2-3 titulares, destacar que son mayormente positivas)
   - 'En tecnología...' (mencionar 2-3 titulares)
   - 'En inteligencia artificial...' (mencionar 2-3 titulares, destacar avances positivos)
   - 'En desarrollo...' (mencionar 2-3 titulares)
5. Cierre: 'Esto ha sido todo. Que tengas un gran día.'

Reglas CRÍTICAS:
- Formato de fecha: '{date_es}' (NUNCA usar formato numérico como '2026-05-28')
- Para dominios web: decir 'JD com' (NUNCA 'JD punto com')
- Mencionar al menos 2 noticias por categoría (el script debe cubrir TODAS las categorías)
- Longitud: 180-220 palabras (~1.5-2 minutos de locución a 130 palabras/minuto)
- Texto FLUIDO para locución, sin saltos de línea, sin emojis, sin URLs
- Destacar cuando una categoría es mayormente positiva (CIENCIA, IA, TECNOLOGÍA suelen serlo)"
}}

REGLAS CRÍTICAS:
1. Máximo 3 noticias por categoría
2. Títulos y resúmenes en español natural
3. **URLS: Copiar URLs EXACTAS de las noticias originales (NUNCA poner "Fuente original", "link", "más info", etc.)**
4. **Resúmenes: 1-2 oraciones COMPLETAS con contexto suficiente (NO cortar a la mitad, NO ser demasiado breve)**
5. audio_script: texto PLANO para TTS, sin formato, sin emojis, sin URLs

IMPORTANTE: Las URLs deben ser IDÉNTICAS a las URLs originales. No acortar, no reemplazar, no omitir.
"""
    
    return prompt

def call_ollama(prompt):
    """Llama a Ollama vía API HTTP."""
    
    endpoint = "http://127.0.0.1:11434/v1/chat/completions"
    
    print(f"   📡 Enviando prompt ({len(prompt)} chars)...")
    
    try:
        response = httpx.post(
            endpoint,
            headers={"Content-Type": "application/json"},
            json={
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 8000,
                "stream": False,
            },
            timeout=LLM_TIMEOUT
        )
        
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"].strip()
        
        print(f"   ✅ Respuesta recibida ({len(content)} chars)")
        return content
    
    except httpx.TimeoutException:
        raise Exception(f"Timeout después de {LLM_TIMEOUT}s")
    except httpx.HTTPError as e:
        raise Exception(f"HTTP error: {e}")
    except Exception as e:
        raise Exception(f"Error: {e}")

def parse_json_response(response_text):
    """Extrae JSON válido de la respuesta."""
    
    # Intento 1: Parsear directo
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass
    
    # Intento 2: Buscar JSON entre llaves
    import re
    match = re.search(r'\{.*\}', response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    
    # Intento 3: Quitar markdown code blocks
    cleaned = response_text.replace('```json', '').replace('```', '').strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    print(f"   ⚠️  No se pudo parsear JSON")
    print(f"      Primeros 200 chars: {response_text[:200]}")
    return None

def validate_urls(translated_data, raw_data):
    """Valida que las URLs se preservaron correctamente."""
    
    errors = []
    
    for cat in translated_data['categories']:
        if cat not in raw_data['categories']:
            continue
        
        original_urls = {item['url'] for item in raw_data['categories'][cat][:MAX_NEWS_PER_CATEGORY]}
        translated_items = translated_data['categories'][cat]
        
        for i, item in enumerate(translated_items):
            url = item.get('url', '')
            if url == 'Fuente original' or url == 'link' or url == 'más info' or len(url) < 20:
                errors.append(f"{cat}[{i+1}]: URL inválida '{url}'")
            elif url not in original_urls:
                # URL diferente pero quizás válida (ej: versión móvil vs desktop)
                if not url.startswith('http'):
                    errors.append(f"{cat}[{i+1}]: URL no comienza con http: '{url}'")
    
    return errors

def validate_audio_script(audio_script):
    """Valida que el audio script cumple las reglas."""
    
    errors = []
    warnings = []
    
    # Verificar formato de fecha
    if '2026-05-28' in audio_script or '20260528' in audio_script:
        errors.append("Fecha en formato numérico (debe ser '28 de mayo de 2026')")
    
    # Verificar "punto com"
    if 'punto com' in audio_script.lower():
        warnings.append("Contiene 'punto com' (la TTS lo leerá literal)")
    
    # Verificar longitud
    words = len(audio_script.split())
    if words < 150:
        warnings.append(f"Script muy corto ({words} palabras, ideal 180-220)")
    elif words > 250:
        warnings.append(f"Script muy largo ({words} palabras, ideal 180-220)")
    
    # Verificar categorías
    categorias_requeridas = ['internacionales', 'alemania', 'ciencia', 'tecnología', 'inteligencia artificial', 'desarrollo']
    audio_lower = audio_script.lower()
    for cat in categorias_requeridas:
        if cat not in audio_lower:
            warnings.append(f"No menciona la categoría '{cat}'")
    
    return errors, warnings

def translate_news(raw_data):
    """Traduce las noticias usando Ollama."""
    
    prompt = build_prompt(raw_data)
    response_text = call_ollama(prompt)
    result = parse_json_response(response_text)
    
    if result is None:
        raise Exception("El LLM no devolvió JSON válido")
    
    # Validar estructura mínima
    required = ['date', 'date_es', 'weather', 'categories', 'audio_script']
    for key in required:
        if key not in result:
            raise Exception(f"JSON inválido: falta '{key}'")
    
    # Validar URLs
    url_errors = validate_urls(result, raw_data)
    if url_errors:
        print(f"   ⚠️  URLs inválidas detectadas:")
        for error in url_errors:
            print(f"      - {error}")
    
    # Validar audio script
    script_errors, script_warnings = validate_audio_script(result['audio_script'])
    if script_errors:
        print(f"   ❌ Errores en audio_script:")
        for error in script_errors:
            print(f"      - {error}")
    if script_warnings:
        print(f"   ⚠️  Advertencias en audio_script:")
        for warning in script_warnings:
            print(f"      - {warning}")
    
    print(f"   ✅ Traducción completada")
    print(f"      Categorías: {len(result['categories'])}")
    print(f"      Audio script: {len(result['audio_script'])} chars, {len(result['audio_script'].split())} palabras")
    
    return result

# ==================== MAIN ====================

def main():
    parser = argparse.ArgumentParser(description='Paso 2: Traducir noticias con LLM')
    parser.add_argument(
        '--date',
        type=str,
        default=datetime.now().strftime('%Y%m%d'),
        help='Fecha a procesar (YYYYMMDD)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Mostrar logs detallados'
    )
    
    args = parser.parse_args()
    date_str = args.date
    
    print(f"======================================================================")
    print(f"🎙️ Hermes Morning Briefing - Paso 2: Traducir")
    print(f"   Fecha: {date_str}")
    print(f"   Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"======================================================================")
    
    # 1. Cargar datos crudos
    print(f"\n▶️ Cargando datos crudos...")
    try:
        raw_data = load_raw_data(date_str)
        print(f"   ✅ {len(raw_data['categories'])} categorías, {sum(len(v) for v in raw_data['categories'].values())} noticias")
    except FileNotFoundError as e:
        print(f"   ❌ Error: {e}")
        print(f"   Ejecutá primero: python3 scripts/01_fetch_news.py --date {date_str}")
        return 1
    
    # 2. Traducir con LLM
    print(f"\n▶️ Traduciendo con LLM ({LLM_MODEL})...")
    try:
        translated_data = translate_news(raw_data)
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return 1
    
    # 3. Guardar JSON traducido
    output_path = Path(f"data/translated/{date_str}.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(translated_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Paso 2 completado")
    print(f"   Output: {output_path}")
    print(f"   Tamaño: {output_path.stat().st_size / 1024:.1f} KB")
    
    return 0

if __name__ == '__main__':
    exit(main())
