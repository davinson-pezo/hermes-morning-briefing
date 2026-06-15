# 🔄 Workflow — Hermes Morning Briefing

**Guía detallada del flujo de ejecución paso a paso**

---

## 1. Visión General del Workflow

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│ ORQUESTADOR │─────▶│   PASO 1    │─────▶│   PASO 2    │─────▶│   PASO 3    │
│             │      │   FETCH     │      │  TRANSLATE  │      │   PUBLISH   │
└─────────────┘      └─────────────┘      └─────────────┘      └─────────────┘
                            │                    │                    │
                            ▼                    ▼                    ▼
                       data/raw/            data/translated/     output/
                       JSON crudo           JSON traducido       markdown + audio
```

---

## 2. Orquestador (`orchestrator.py`)

### 2.1 Responsabilidades

1. Validar fecha de ejecución
2. Crear estructura de directorios si no existe
3. Ejecutar pasos en secuencia (1 → 2 → 3)
4. Verificar exit code de cada paso
5. Escribir logs de ejecución
6. Detenerse si algún paso falla

### 2.2 Flujo Detallado

```python
# 1. Inicialización
date_str = datetime.now().strftime('%Y%m%d')
log_file = f"data/logs/{date_str}.log"

log(f"Inicio del workflow - {date_str}")

# 2. Ejecutar Paso 1
log("Paso 1/3: fetch")
result = subprocess.run(['python3', 'scripts/01_fetch_news.py', '--date', date_str])
if result.returncode != 0:
    log("❌ Paso 1 falló", level='ERROR')
    sys.exit(1)
log("✅ Paso 1 completado")

# 3. Ejecutar Paso 2
log("Paso 2/3: translate")
result = subprocess.run(['python3', 'scripts/02_translate_news.py', '--date', date_str])
if result.returncode != 0:
    log("❌ Paso 2 falló", level='ERROR')
    sys.exit(1)
log("✅ Paso 2 completado")

# 4. Ejecutar Paso 3
log("Paso 3/3: publish")
result = subprocess.run(['python3', 'scripts/03_publish.py', '--date', date_str])
if result.returncode != 0:
    log("❌ Paso 3 falló", level='ERROR')
    sys.exit(1)
log("✅ Paso 3 completado")

# 5. Finalizar
log(f"Workflow completado en {duration:.1f}s")
```

### 2.3 Manejo de Errores

| Escenario | Acción |
|-----------|--------|
| Paso 1 falla | Detener, log error, no ejecutar pasos 2-3 |
| Paso 2 falla | Detener, log error, Paso 1 ya está guardado |
| Paso 3 falla | Detener, log error, Pasos 1-2 ya están guardados |
| Todos exitosos | Log resumen, cleanup opcional |

---

## 3. Paso 1: Fetch News (`01_fetch_news.py`)

### 3.1 Entradas

- `config.yaml` — Lista de RSS feeds por categoría
- `--date YYYYMMDD` — Fecha para procesar (opcional, default: hoy)

### 3.2 Procesamiento

```python
# 1. Cargar configuración
config = load_config('config.yaml')

# 2. Obtener clima (Open-Meteo API)
weather = fetch_weather(location='Jülich, Germany')
# → {"temp": 21.7, "temp_max": 27.0, "temp_min": 13.8, "condition": "despejado"}

# 3. Obtener noticias de cada categoría (paralelo)
categories = {}
with concurrent.futures.ThreadPoolExecutor() as executor:
    future_to_category = {
        executor.submit(fetch_rss, feed_list): category
        for category, feed_list in config['rss_feeds'].items()
    }
    for future in concurrent.futures.as_completed(future_to_category):
        category = future_to_category[future]
        categories[category] = future.result()

# 4. Filtrar duplicados (por URL)
all_urls = set()
unique_categories = {}
for category, items in categories.items():
    unique_items = []
    for item in items:
        if item['url'] not in all_urls:
            all_urls.add(item['url'])
            unique_items.append(item)
    unique_categories[category] = unique_items

# 5. Guardar JSON crudo
output = {
    "date": date_str,
    "fetched_at": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    "weather": weather,
    "categories": unique_categories
}

with open(f"data/raw/{date_str}.json", 'w') as f:
    json.dump(output, f, indent=2)
```

### 3.3 Salidas

- `data/raw/YYYYMMDD.json` — JSON crudo con todas las noticias

### 3.4 Ejemplo de Output

```json
{
  "date": "20260528",
  "fetched_at": "2026-05-28 08:00:00",
  "weather": {
    "temp": 21.7,
    "temp_max": 27.0,
    "temp_min": 13.8,
    "condition": "despejado"
  },
  "categories": {
    "INTERNACIONALES": [
      {
        "title": "Iran attacks US base after new airstrikes",
        "description": "The hostilities come during a fragile ceasefire...",
        "url": "https://www.bbc.com/news/world-middle-east",
        "published": "2026-05-28T06:30:00Z",
        "source": "BBC"
      }
    ],
    ...
  }
}
```

---

## 4. Paso 2: Translate News (`02_translate_news.py`)

### 4.1 Entradas

- `data/raw/YYYYMMDD.json` — JSON crudo del Paso 1

### 4.2 Procesamiento

```python
# 1. Cargar JSON crudo
with open(f"data/raw/{date_str}.json") as f:
    raw_data = json.load(f)

# 2. Construir prompt para LLM
prompt = build_prompt(raw_data)
# → Prompt con:
#   - Fecha en español
#   - Clima
#   - Máximo 3 noticias por categoría
#   - Instrucciones de formato JSON

# 3. Llamar LLM (Gemini vía Ollama Cloud)
response = httpx.post(
    "http://127.0.0.1:11434/v1/chat/completions",
    json={
        "model": "gemini-3-flash-preview:latest",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 8000,
        "stream": False,
    },
    timeout=120
)

# 4. Parsear respuesta JSON
content = response.json()["choices"][0]["message"]["content"]
translated_data = parse_json_response(content)
# → Maneja: JSON directo, JSON con markdown, JSON incompleto

# 5. Validar estructura
required_keys = ['date', 'date_es', 'weather', 'categories', 'audio_script']
for key in required_keys:
    assert key in translated_data, f"Falta '{key}'"

# 6. Guardar JSON traducido
translated_data['translated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
with open(f"data/translated/{date_str}.json", 'w') as f:
    json.dump(translated_data, f, indent=2, ensure_ascii=False)
```

### 4.3 Salidas

- `data/translated/YYYYMMDD.json` — JSON traducido con audio_script

### 4.4 Prompt para LLM

```
Tu tarea: Traducir noticias al español y generar un briefing matutino.

FECHA: Jueves, 28 de mayo de 2026
CLIMA: 21.7°C, despejado (Máx: 27.0°C, Mín: 13.8°C)

NOTICIAS ORIGINALES:
• [INTERNACIONALES] Iran attacks US base — The hostilities come during...
• [INTERNACIONALES] 16 students die in Kenya school fire — Dozens injured...
• [ALEMANIA] Ex-CIA agent accused of embezzling gold — Agency suspected...
...

---

GENERÁ este JSON exacto (sin markdown, sin texto extra):

{
  "date": "20260528",
  "date_es": "Jueves, 28 de mayo de 2026",
  "weather": {...},
  "categories": {
    "INTERNACIONALES": [
      {"title_es": "...", "summary_es": "...", "url": "..."}
    ],
    ...
  },
  "audio_script": "Buenos días. Es Jueves, 28 de mayo de 2026..."
}

REGLAS:
- Máximo 3 noticias por categoría
- Títulos y resúmenes en español natural
- Mantener URLs originales
- audio_script: texto PLANO para TTS, sin formato, sin emojis
```

---

## 5. Paso 3: Publish (`03_publish.py`)

### 5.1 Entradas

- `data/translated/YYYYMMDD.json` — JSON traducido del Paso 2

### 5.2 Procesamiento

```python
# 1. Cargar JSON traducido
with open(f"data/translated/{date_str}.json") as f:
    translated = json.load(f)

# 2. Generar markdown para Telegram
markdown = generate_markdown(translated)
# → Formato con emojis, negritas, links

with open(f"output/markdown/briefing_{date_str}.md", 'w') as f:
    f.write(markdown)

# 3. Extraer audio_script
audio_script = translated['audio_script']

with open(f"output/audio/script_{date_str}.txt", 'w') as f:
    f.write(audio_script)

# 4. Generar audio (macOS TTS)
# 4a. Generar AIFF con say
subprocess.run([
    'say',
    '-v', 'Monica',
    '-o', f'output/audio/briefing_{date_str}.aiff',
    audio_script
])

# 4b. Convertir a OGG con ffmpeg
subprocess.run([
    'ffmpeg', '-i', f'output/audio/briefing_{date_str}.aiff',
    '-c:a', 'libopus',
    f'output/audio/briefing_{date_str}.ogg'
])

# 4c. Eliminar AIFF temporal
os.remove(f"output/audio/briefing_{date_str}.aiff")

# 5. Enviar a Telegram
# 5a. Enviar texto
subprocess.run([
    'hermes', 'send', 'telegram',
    markdown,
    '--token', TELEGRAM_BOT_TOKEN
])

# 5b. Enviar audio (voice bubble)
subprocess.run([
    'hermes', 'send', 'telegram',
    f'MEDIA:output/audio/briefing_{date_str}.ogg',
    '--token', TELEGRAM_BOT_TOKEN
])
```

### 5.3 Salidas

- `output/markdown/briefing_YYYYMMDD.md` — Briefing en markdown
- `output/audio/briefing_YYYYMMDD.ogg` — Audio en formato OGG/Opus
- `output/audio/script_YYYYMMDD.txt` — Guión de locución
- Telegram — Mensaje enviado (texto + audio)

---

## 6. Cleanup (`cleanup_old_files.py`)

### 6.1 Entradas

- `config.yaml` — Política de retención

### 6.2 Procesamiento

```python
# 1. Definir reglas de cleanup
CLEANUP_RULES = [
    ('data/raw', 7, '*.json'),
    ('data/translated', 7, '*.json'),
    ('data/logs', 30, '*.log'),
    ('output/markdown', 30, '*.md'),
    ('output/audio', 30, '*.ogg'),
    ('output/audio', 30, '*.txt'),
]

# 2. Para cada regla, encontrar archivos viejos
for folder, days, pattern in CLEANUP_RULES:
    cutoff = datetime.now() - timedelta(days=days)
    
    for file in Path(folder).glob(pattern):
        mtime = datetime.fromtimestamp(file.stat().st_mtime)
        
        if mtime < cutoff:
            # Archivo es viejo → borrar
            age_days = (datetime.now() - mtime).days
            print(f"🗑️  {file.name} ({age_days} días)")
            file.unlink()
```

### 6.3 Salidas

- Archivos > 30 días eliminados
- Reporte de espacio liberado

---

## 7. Ejecución en Producción (Cron)

### 7.1 Configuración de Cronjobs

```bash
# Editar crontab
crontab -e

# Agregar líneas:

# Morning Briefing (Lun-Vie 8:00 AM)
0 8 * * 1-5 cd ~/hermes-morning-briefing && python3 scripts/orchestrator.py

# Cleanup semanal (Domingos 6:00 AM)
0 6 * * 0 cd ~/hermes-morning-briefing && python3 scripts/cleanup_old_files.py
```

### 7.2 Logs de Cron

Los logs se guardan automáticamente en:
- `data/logs/YYYYMMDD.log` — Log de cada ejecución diaria
- `~/.hermes/cron/output/` — Logs del scheduler de Hermes

### 7.3 Monitoreo

```bash
# Ver última ejecución
tail -20 data/logs/$(date +%Y%m%d).log

# Ver espacio usado
du -sh data/ output/

# Ver archivos próximos a borrar
python3 scripts/cleanup_old_files.py --dry-run
```

---

## 8. Debugging

### 8.1 Ejecución Paso a Paso

```bash
# Paso 1: Fetch
python3 scripts/01_fetch_news.py --date 20260528
cat data/raw/20260528.json

# Paso 2: Translate
python3 scripts/02_translate_news.py --date 20260528
cat data/translated/20260528.json

# Paso 3: Publish
python3 scripts/03_publish.py --date 20260528
cat output/markdown/briefing_20260528.md
```

### 8.2 Logs Detallados

Agregar `--verbose` a cualquier script para ver logs detallados:

```bash
python3 scripts/02_translate_news.py --date 20260528 --verbose
```

### 8.3 Errores Comunes

| Error | Causa Probable | Solución |
|-------|----------------|----------|
| `FileNotFoundError` | Paso 1 no se ejecutó | Ejecutar orchestrator.py |
| `JSONDecodeError` | LLM no devolvió JSON válido | Revisar logs, aumentar max_tokens |
| `TimeoutException` | LLM muy lento | Aumentar timeout en config |
| `hermes send: cannot read` | Archivo no existe | Verificar ruta del archivo |

---

**Documento mantenido por:** Dr. Davinson Pezo  
**Última actualización:** 28 de mayo de 2026  
**Versión:** 1.0
