# 🛠️ Setup — Hermes Morning Briefing

**Guía de instalación y configuración paso a paso**

---

## 1. Requisitos Previos

### 1.1 Sistema Operativo

- ✅ **macOS** (recomendado — TTS nativo incluido)
- ⚠️ **Linux** (requiere configurar TTS alternativo)
- ❌ **Windows** (no probado, requiere WSL)

### 1.2 Software Requerido

```bash
# Python 3.11+
python3 --version  # Debe ser >= 3.11

# ffmpeg (para convertir audio)
ffmpeg -version

# Ollama (para LLM)
ollama --version
```

### 1.3 Cuentas y API Keys

| Servicio | Requerido | Costo | Obtener en |
|----------|-----------|-------|------------|
| **Ollama Cloud** | ✅ (para LLM) | Gratis | https://ollama.com/settings |
| **Telegram Bot** | ✅ (para envío) | Gratis | https://t.me/BotFather |
| **Open-Meteo** | ❌ (clima) | Gratis | Sin API key |

---

## 2. Instalación Paso a Paso

### 2.1 Clonar Repositorio

```bash
# Crear directorio para proyectos
mkdir -p ~/projects
cd ~/projects

# Clonar repositorio
git clone https://github.com/davinson-pezo/hermes-morning-briefing.git
cd hermes-morning-briefing
```

### 2.2 Crear Entorno Virtual (Opcional pero Recomendado)

```bash
# Crear venv
python3 -m venv venv

# Activar venv
source venv/bin/activate

# Verificar
which python3  # Debe apuntar a ~/projects/hermes-morning-briefing/venv/bin/python3
```

### 2.3 Instalar Dependencias

```bash
pip install -r requirements.txt
```

**Contenido de `requirements.txt`:**

```txt
feedparser>=6.0.10
httpx>=0.27.0
pyyaml>=6.0.1
```

### 2.4 Verificar Ollama

```bash
# Listar modelos disponibles
ollama list

# Deberías ver algo como:
# NAME                           ID              SIZE      MODIFIED
# gemini-3-flash-preview:latest  abc123          -         2 days ago
# qwen3.5:cloud                  def456          -         1 week ago
```

**Si no tenés modelos cloud:**

```bash
# Configurar Ollama Cloud (requiere API key)
ollama pull gemini-3-flash-preview:latest
```

### 2.5 Configurar Telegram Bot

```bash
# 1. Abrir Telegram y buscar @BotFather
# 2. Enviar /newbot
# 3. Seguir instrucciones:
#    - Nombre: Hermes Morning Briefing
#    - Username: hermes_morning_bot (debe terminar en 'bot')
# 4. Copiar token (ej: 123456789:ABCdefGHIjklMNOpqrsTUVwxyz)

# 5. Agregar bot a tu chat/canal
#    - Buscar @hermes_morning_bot en Telegram
#    - Iniciar chat con /start

# 6. Obtener tu chat ID
#    - Enviar mensaje al bot
#    - Visitar: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
#    - Buscar "chat":{"id":123456789}
```

---

## 3. Configuración

### 3.1 Crear Archivo de Configuración

```bash
# Copiar plantilla
cp config.example.yaml config.yaml

# Editar configuración
nano config.yaml
```

### 3.2 Configurar RSS Feeds

```yaml
# config.yaml
rss_feeds:
  INTERNACIONALES:
    - https://feeds.bbci.co.uk/news/world/rss.xml
    - https://www.theguardian.com/world/rss
    - https://rss.nytimes.com/services/xml/rss/nyt/World.xml
  
  ALEMANIA:
    - https://www.spiegel.de/schlagzeilen/index.rss
    - https://www.zeit.de/news/index.xml
  
  CIENCIA:
    - https://rss.sciencedaily.com/all.xml
    - https://www.nature.com/subjects/physics.rss
  
  TECNOLOGÍA:
    - https://www.xataka.com/index.xml
    - https://arstechnica.com/feed/
  
  IA / MACHINE LEARNING:
    - https://arxiv.org/rss/cs.AI
    - https://arxiv.org/rss/cs.LG
  
  DESARROLLO:
    - https://github.blog/feed/
    - https://stackoverflow.com/blogs/feed/
```

**Fuentes recomendadas por categoría:**

| Categoría | Fuentes Sugeridas |
|-----------|-------------------|
| Internacionales | BBC, Guardian, NYT, Reuters |
| Alemania | Spiegel, Zeit, FAZ, Tagesschau |
| Ciencia | ScienceDaily, Nature, Phys.org |
| Tecnología | Xataka, Ars Technica, The Verge |
| IA/ML | arXiv cs.AI, cs.LG, Hugging Face blog |
| Desarrollo | GitHub blog, Stack Overflow, Dev.to |

### 3.3 Configurar LLM

```yaml
# config.yaml
llm:
  provider: ollama  # o 'openai', 'google', 'anthropic'
  model: gemini-3-flash-preview:latest
  timeout: 120  # segundos
  max_tokens: 8000
  temperature: 0.3  # 0.0 = determinista, 1.0 = creativo
```

**Modelos soportados:**

| Proveedor | Modelos | API Key |
|-----------|---------|---------|
| **Ollama Cloud** | `gemini-3-flash-preview:latest`, `qwen3.5:cloud`, `kimi-k2.6:cloud` | OLLAMA_API_KEY |
| **Google** | `gemini-2.0-flash`, `gemini-2.5-pro` | GOOGLE_API_KEY |
| **OpenAI** | `gpt-4o`, `gpt-4o-mini` | OPENAI_API_KEY |
| **Anthropic** | `claude-sonnet-4`, `claude-opus-4` | ANTHROPIC_API_KEY |

### 3.4 Configurar TTS (Text-to-Speech)

```yaml
# config.yaml
tts:
  provider: macos_say  # o 'edge-tts', 'openai-tts', 'piper-tts'
  voice: Monica  # macOS: Monica, Alex, Samantha; Edge: es-ES-AlvaroNeural
  format: ogg  # ogg, mp3, wav
  speed: 1.0  # 0.5 = lento, 2.0 = rápido
```

**Proveedores TTS:**

| Proveedor | Voces | Costo | Calidad |
|-----------|-------|-------|---------|
| **macOS say** | ~50 voces | Gratis | Muy buena |
| **Edge TTS** | ~100 voces | Gratis | Excelente |
| **OpenAI TTS** | 6 voces | $0.015/1K chars | Excelente |
| **Piper TTS** | ~50 voces | Gratis | Buena |

### 3.5 Configurar Telegram

```yaml
# config.yaml
telegram:
  enabled: true
  bot_token: ${TELEGRAM_BOT_TOKEN}  # Usar variable de entorno
  chat_id: 123456789  # Tu chat ID o ID de canal
  send_text: true
  send_audio: true
```

**Variables de entorno (recomendado para API keys):**

```bash
# ~/.hermes/.env o .env local
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
OLLAMA_API_KEY=sk-...
```

### 3.6 Configurar Cleanup

```yaml
# config.yaml
cleanup:
  enabled: true
  retention_days: 30  # Días de retención para output
  data_retention_days: 7  # Días de retención para datos intermedios
  run_schedule: "0 6 * * 0"  # Domingos 6:00 AM
```

---

## 4. Primeras Pruebas

### 4.1 Probar Paso 1 (Fetch)

```bash
cd ~/projects/hermes-morning-briefing

# Ejecutar fetch
python3 scripts/01_fetch_news.py

# Verificar output
ls -lh data/raw/
cat data/raw/$(date +%Y%m%d).json | head -50
```

**Output esperado:**
- ✅ JSON creado en `data/raw/YYYYMMDD.json`
- ✅ 6-7 categorías con noticias
- ✅ Clima incluido

### 4.2 Probar Paso 2 (Translate)

```bash
# Ejecutar traducción
python3 scripts/02_translate_news.py

# Verificar output
ls -lh data/translated/
cat data/translated/$(date +%Y%m%d).json | head -80
```

**Output esperado:**
- ✅ JSON traducido en `data/translated/YYYYMMDD.json`
- ✅ Títulos en español
- ✅ `audio_script` generado

### 4.3 Probar Paso 3 (Publish)

```bash
# Ejecutar publish (sin envío a Telegram primero)
python3 scripts/03_publish.py --no-send

# Verificar output
ls -lh output/markdown/
ls -lh output/audio/
cat output/markdown/briefing_$(date +%Y%m%d).md
```

**Output esperado:**
- ✅ Markdown en `output/markdown/briefing_YYYYMMDD.md`
- ✅ Audio en `output/audio/briefing_YYYYMMDD.ogg`
- ✅ Guión en `output/audio/script_YYYYMMDD.txt`

### 4.4 Probar Envío a Telegram

```bash
# Ejecutar con envío
python3 scripts/03_publish.py

# Verificar Telegram
# → Deberías recibir mensaje en tu chat/canal
```

### 4.5 Probar Workflow Completo

```bash
# Ejecutar orchestrator
python3 scripts/orchestrator.py

# Ver logs
tail -30 data/logs/$(date +%Y%m%d).log
```

**Output esperado:**
```
======================================================================
🎙️ Hermes Morning Briefing - Orquestador
   Fecha: 20260528
   Hora: 2026-05-28 08:00:00
======================================================================
▶️ Paso 1/3: fetch
✅ Paso fetch completado
▶️ Paso 2/3: translate
✅ Paso translate completado
▶️ Paso 3/3: publish
✅ Paso publish completado

📊 RESUMEN
✅ Workflow completado en 28.5s
======================================================================
```

---

## 5. Automatizar con Cron

### 5.1 Verificar Cronjob

```bash
# Ver cronjobs actuales
crontab -l

# Deberías ver algo como:
# 0 8 * * 1-5 cd ~/projects/hermes-morning-briefing && python3 scripts/orchestrator.py
# 0 6 * * 0 cd ~/projects/hermes-morning-briefing && python3 scripts/cleanup_old_files.py
```

### 5.2 Agregar Cronjob

```bash
# Editar crontab
crontab -e

# Agregar líneas (ajustar ruta):

# Morning Briefing (Lun-Vie 8:00 AM)
0 8 * * 1-5 cd ~/projects/hermes-morning-briefing && python3 scripts/orchestrator.py >> ~/.hermes/cron/output/morning-briefing.log 2>&1

# Cleanup semanal (Domingos 6:00 AM)
0 6 * * 0 cd ~/projects/hermes-morning-briefing && python3 scripts/cleanup_old_files.py >> ~/.hermes/cron/output/cleanup.log 2>&1
```

### 5.3 Verificar Cronjob

```bash
# Forzar ejecución manual para test
python3 scripts/orchestrator.py

# Ver logs de cron
tail -20 ~/.hermes/cron/output/morning-briefing.log

# Ver logs del workflow
tail -20 data/logs/$(date +%Y%m%d).log
```

---

## 6. Troubleshooting

### 6.1 Problemas Comunes

#### Error: `ModuleNotFoundError: No module named 'feedparser'`

```bash
# Solución: Instalar dependencias
pip install -r requirements.txt

# Si usás venv, verificar que está activado
source venv/bin/activate
```

#### Error: `ollama: command not found`

```bash
# Solución: Instalar Ollama
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Verificar instalación
ollama --version
```

#### Error: `No models available`

```bash
# Solución: Pull modelo cloud
ollama pull gemini-3-flash-preview:latest

# O configurar API key de Ollama
export OLLAMA_API_KEY=sk-...
```

#### Error: `Telegram bot no envía`

```bash
# Verificar token
echo $TELEGRAM_BOT_TOKEN

# Probar manualmente
curl -X POST https://api.telegram.org/bot<TOKEN>/sendMessage \
  -d chat_id=<CHAT_ID> \
  -d text="Test"

# Si falla, regenerar token con @BotFather
```

#### Error: `say: command not found` (Linux)

```bash
# Solución: Usar Edge TTS en vez de macOS say
# 1. Instalar edge-tts
pip install edge-tts

# 2. Cambiar config.yaml
tts:
  provider: edge-tts
  voice: es-ES-AlvaroNeural
```

### 6.2 Debugging

```bash
# Ejecutar con verbose
python3 scripts/02_translate_news.py --verbose

# Ver logs detallados
cat data/logs/$(date +%Y%m%d).log

# Probar LLM directamente
ollama run gemini-3-flash-preview:latest "Decí hola"

# Probar RSS feed
python3 -c "import feedparser; print(feedparser.parse('https://feeds.bbci.co.uk/news/world/rss.xml'))"
```

---

## 7. Actualización

### 7.1 Actualizar desde GitHub

```bash
cd ~/projects/hermes-morning-briefing

# Hacer backup de config
cp config.yaml config.yaml.backup

# Pull cambios
git pull origin main

# Restaurar config
cp config.yaml.backup config.yaml

# Verificar cambios en requirements
pip install -r requirements.txt --upgrade
```

### 7.2 Migrar Versión Anterior

Si venís de una versión anterior sin orquestador:

```bash
# 1. Backup
cp -r hermes-morning-briefing hermes-morning-briefing.backup

# 2. Descargar nueva versión
git clone https://github.com/davinson-pezo/hermes-morning-briefing.git new-version

# 3. Migrar config
cp hermes-morning-briefing.backup/config.yaml new-version/config.yaml

# 4. Reemplazar
rm -rf hermes-morning-briefing
mv new-version hermes-morning-briefing

# 5. Probar
cd hermes-morning-briefing
python3 scripts/orchestrator.py
```

---

## 8. Soporte

### 8.1 Recursos

- **GitHub Issues:** https://github.com/davinson-pezo/hermes-morning-briefing/issues
- **Documentación:** `/docs` en el repositorio
- **Email:** info@dataquorum.net

### 8.2 Reportar Bugs

Incluir en el report:

1. Versión de Python (`python3 --version`)
2. Versión de Ollama (`ollama --version`)
3. Sistema operativo (`uname -a`)
4. Logs del error (`data/logs/YYYYMMDD.log`)
5. Pasos para reproducir

---

**Documento mantenido por:** Dr. Davinson Pezo  
**Última actualización:** 28 de mayo de 2026  
**Versión:** 1.0
