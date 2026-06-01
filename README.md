# 🎙️ Hermes Morning Briefing

**Workflow automatizado para generar briefings matutinos con noticias, clima y audio tipo locutor de radio.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-production-green)](https://github.com/davinson-pezo/hermes-morning-briefing)
[![Telegram](https://img.shields.io/badge/delivery-Telegram-26A5E4?logo=telegram)](https://telegram.org)

---

## 📋 Descripción

Sistema automatizado que cada mañana (Lun-Vie, 8:00 AM):

1. **Obtiene noticias** de 7 categorías vía RSS feeds
2. **Traduce con IA** (Qwen 3.5 Cloud / Gemini)
3. **Genera audio** tipo locutor de radio (macOS TTS / Edge TTS)
4. **Envía a Telegram** (texto formateado + voice bubble con barra de progreso)

**Tiempo total:** ~30-40 segundos  
**Formato de salida:** Markdown + Audio OGG/Opus 48kHz  
**Entrega:** Telegram (texto + audio)

---

## 🎯 Características Principales

- ✅ **Arquitectura modular** — 4 scripts independientes (fetch, translate, publish, orchestrator)
- ✅ **Estado persistente** — JSONs intermedios permiten recovery si algo falla
- ✅ **Cleanup automático** — Borra archivos > 30 días (semanal, domingos 6 AM)
- ✅ **Sin dependencias complejas** — Python stdlib + feedparser + httpx
- ✅ **Fácil de extender** — Agregar nuevas categorías o fuentes es trivial
- ✅ **100% automatizable** — Diseñado para cronjobs (Hermes Agent / cron)
- ✅ **Doble entrega** — Texto formateado + audio voice bubble (barra de progreso)

---

## 💡 Motivación: ¿Por qué este proyecto?

Este sistema nació de un problema real: **durante 2 semanas intentamos configurar un cronjob simple que enviara noticias y audio a Telegram, y siempre fallaba**.

### Los Problemas que Enfrentamos

| Intento | Problema | Resultado |
|---------|----------|-----------|
| **Cronjob directo con LLM** | El agente del cronjob resumía las noticias en lugar de enviar el contenido completo | ❌ Llegaba un resumen genérico, no las noticias |
| **Cronjob con script + deliver** | El output del script no se capturaba correctamente | ❌ Telegram recibía solo "✅ Workflow completado" |
| **Audio TTS en cronjob** | El audio se generaba pero no se enviaba como voice bubble | ❌ Llegaba como archivo adjunto, no como nota de voz |
| **Scripts acoplados** | Todo en un solo script — si fallaba algo, había que reiniciar desde cero | ❌ Sin recovery, sin debugging posible |
| **Sin estado persistente** | No había forma de saber en qué paso falló | ❌ Imposible de debuggear |

### La Solución: Arquitectura Modular con Orquestador

En lugar de luchar contra el sistema de cronjobs, **separamos el workflow en 3 pasos independientes + 1 orquestador**:

```
Cronjob → orchestrator.py → [01_fetch → 02_translate → 03_publish]
                                    ↓
                            Cada paso escribe a disco
                                    ↓
                            03_publish envía directo a Telegram
```

**Resultado:**
- ✅ **Cronjob simple** — Solo ejecuta el orchestrator (sin entrega a Telegram)
- ✅ **03_publish.py envía directo** — Usa `hermes send` directamente (voice bubble perfecto)
- ✅ **Estado persistente** — Cada paso guarda su output en disco (JSONs intermedios)
- ✅ **Recovery posible** — Si el paso 2 falla, el paso 1 ya está guardado
- ✅ **Debugging fácil** — Logs por paso, sabés exactamente dónde falló
- ✅ **30-40 segundos** — Workflow completo, sin timeouts

### Lección Aprendida

> **No uses un agente de cronjob para tareas complejas con side-effects (enviar a Telegram, generar audio).**
>
> **En su lugar:**
> 1. El cronjob ejecuta un orchestrator (sin entrega)
> 2. El último paso del workflow envía directamente (con `hermes send` o API nativa)
> 3. Cada paso escribe a disco para recovery y debugging

Esta arquitectura lleva **producción desde Junio 2026** y funciona perfectamente todos los días.

---

## 🚀 Quick Start

### Requisitos

| Requisito | Versión | Notas |
|-----------|---------|-------|
| Python | 3.11+ | macOS / Linux / Windows |
| macOS | — | Para TTS nativo (`say`) o usar Edge TTS / Piper |
| Ollama | — | Opcional, para LLM cloud (Qwen, Gemini, Kimi) |
| Telegram Bot | — | Token para envío automático |

### Instalación

```bash
# 1. Clonar repositorio
git clone https://github.com/davinson-pezo/hermes-morning-briefing.git
cd hermes-morning-briefing

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar
cp config.example.yaml config.yaml
# Editar config.yaml con tus RSS feeds y preferencias

# 4. Probar workflow completo
python3 scripts/orchestrator.py
```

### Ejecución Manual

```bash
# Workflow completo (hoy)
python3 scripts/orchestrator.py

# Workflow completo (fecha específica)
python3 scripts/orchestrator.py --date 20260601

# O pasos individuales
python3 scripts/01_fetch_news.py --date 20260601
python3 scripts/02_translate_news.py --date 20260601
python3 scripts/03_publish.py --date 20260601

# Limpieza manual (dry-run)
python3 scripts/cleanup_old_files.py --dry-run

# Limpieza manual (real)
python3 scripts/cleanup_old_files.py
```

### Automatizar con Hermes Cron

```bash
# Morning Briefing (Lun-Vie 8:00 AM)
hermes cron add morning_briefing \
  --schedule "0 8 * * 1-5" \
  --script ~/path/to/news/scripts/orchestrator.py \
  --deliver local

# Cleanup semanal (Domingos 6:00 AM)
hermes cron add news_cleanup \
  --schedule "0 6 * * 0" \
  --script ~/path/to/news/scripts/cleanup_old_files.py \
  --deliver local
```

**Nota:** El envío a Telegram lo hace el script `03_publish.py` directamente (no el cronjob).

---

## 📁 Estructura del Proyecto

```
hermes-morning-briefing/
├── config.yaml                  # Configuración central
├── requirements.txt             # Dependencias Python
├── README.md                    # Este archivo
│
├── scripts/
│   ├── orchestrator.py          # Orquestador principal (ejecuta secuencia)
│   ├── 01_fetch_news.py         # Fetch RSS feeds + clima (Open-Meteo)
│   ├── 02_translate_news.py     # Traducción con LLM (Qwen/Gemini)
│   ├── 03_publish.py            # Generar audio + enviar a Telegram
│   └── cleanup_old_files.py     # Limpieza semanal (retención)
│
├── data/                        # Estado intermedio (auto-limpiable)
│   ├── raw/                     # JSON crudo (retención: 7 días)
│   ├── translated/              # JSON traducido + audio script (7 días)
│   └── logs/                    # Logs de ejecución (30 días)
│
└── output/                      # Resultados finales
    ├── markdown/                # Briefings .md (30 días)
    └── audio/                   # Audios .ogg + guiones .txt (30 días)
```

---

## ⚙️ Configuración

### RSS Feeds (`config.yaml`)

```yaml
rss_feeds:
  INTERNACIONALES:
    - https://feeds.bbci.co.uk/news/world/rss.xml
    - https://rss.nytimes.com/services/xml/rss/nyt/World.xml
  
  ALEMANIA:
    - https://www.spiegel.de/schlagzeilen/index.rss
    - https://www.handelsblatt.com/contentexport/feed/top-themen
  
  CIENCIA:
    - https://rss.sciencedaily.com/all.xml
    - https://www.nature.com/nature.rss
  
  BIOTECNOLOGÍA:
    - https://rss.sciencedaily.com/mostpopular.xml
  
  TECNOLOGÍA:
    - https://www.xataka.com/rss
    - https://es.gizmodo.com/rss
  
  IA / MACHINE LEARNING:
    - https://arxiv.org/rss/cs.AI
    - https://huggingface.co/blog/feed.xml
  
  DESARROLLO:
    - https://github.blog/feed/
    - https://stackoverflow.blog/feed/
```

### Modelo LLM

Por defecto usa **Qwen 3.5 Cloud** vía Ollama:

```yaml
llm:
  provider: "qwen3.5:cloud"
  temperature: 0.3  # Bajo para traducciones consistentes
  max_tokens: 2000
  timeout_seconds: 90
```

**Alternativas:**
- `gemini-3-flash-preview:latest` (Ollama Cloud)
- `kimi-k2.6:cloud` (Ollama Cloud)
- `gemini-2.0-flash` (Google API directa)

### Audio TTS

Por defecto usa macOS `say` con voz `Monica`:

```yaml
tts:
  provider: "macos_say"  # macos_say, edge, openai, piper
  voice: "Monica"        # macOS: Monica, Diego, Paulina
  output_format: "ogg"   # ogg para Telegram voice bubble
  audio_params:
    codec: "libopus"
    bitrate: "32k"
    sample_rate: 48000   # 48kHz para Telegram
    channels: 1          # mono
```

**Alternativas:**
- `edge-tts` — Gratis, múltiples voces (ej: `es-MX-DaliaNeural`)
- `openai-tts` — Pago, alta calidad
- `piper-tts` — Local, open source

### Telegram

```yaml
telegram:
  enabled: true
  target: "telegram"  # o "telegram:-1001234567890" para canal
  send_text: true
  send_audio: true
  audio_as_voice: true  # true = voice bubble con barra de progreso
```

### Cleanup (Limpieza Automática)

```yaml
cleanup:
  enabled: true
  schedule: "weekly"  # weekly o daily
  retention_days:
    data_raw: 7
    data_translated: 7
    data_logs: 30
    output_markdown: 30
    output_audio: 30
    output_audio_scripts: 30
```

---

## 📊 Rendimiento

| Métrica | Valor |
|---------|-------|
| **Tiempo total** | ~30-40 segundos |
| **Noticias procesadas** | ~60 originales → ~18 traducidas |
| **Audio generado** | ~350-400 KB (2-3 minutos) |
| **Categorías** | 7 (configurables) |
| **Retención** | 7 días (datos), 30 días (output) |

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR.PY                          │
│              (ejecuta en secuencia + maneja errores)        │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  01_fetch     │     │  02_translate │     │   03_publish  │
│  news.py      │────▶│  news.py      │────▶│   .py         │
│               │     │               │     │               │
│ RSS + Clima   │     │ LLM traducción│     │ Audio + Send  │
│ → JSON raw    │     │ JSON → JSON   │     │ → Telegram    │
└───────────────┘     └───────────────┘     └───────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
   data/raw/           data/translated/      output/
   20260601.json       20260601.json         briefing_20260601.ogg
                                               briefing_20260601.md
```

**Clave:** Cada paso es independiente y escribe su output a disco. Si el paso 2 falla, el paso 1 ya está guardado y podés debuggear sin reiniciar todo.

---

## 🧪 Ejemplo de Output

### Markdown (Telegram)

```markdown
🎙️ **Hermes Morning Briefing**

Lunes, 1 de junio de 2026 | Jülich, Alemania

☀️ **Clima:** 17.3°C, despejado
- Máxima: 24.8°C
- Mínima: 13.6°C

---

**INTERNACIONALES**:

1. **Colombia definirá su presidencia entre un senador de izquierda y un rival pro-Trump**
   El senador Iván Cepeda se enfrentará al abogado Abelardo de la Espriella en la segunda vuelta electoral el próximo 21 de junio.
   [Más info](https://www.bbc.com/news/articles/c1w2xvwq8g9o?at_medium=RSS&at_campaign=rss)

2. **Trump busca modificar el acuerdo entre Estados Unidos e Irán**
   Los cambios solicitados por el exmandatario se centran en la seguridad del Estrecho de Ormuz y la eliminación del uranio altamente enriquecido.
   [Más info](https://www.bbc.com/news/articles/c1w2xve315do?at_medium=RSS&at_campaign=rss)

**ALEMANIA**:

1. **Guerra en Ucrania: Numerosos heridos tras ataques rusos**
   Impactos de drones y misiles dejaron una docena de heridos, mientras el presidente Zelenski propone iniciar diálogos de paz antes del invierno.
   [Más info](https://www.spiegel.de/politik/ukraine-krieg-viele-menschen-nach-russischen-angriffen-verletzt-a-bf726c70-2d38-488a-a4a7-149e0f528560#ref=rss)

...

---
🎧 *Nota de voz con el resumen completo a continuación*
```

### Audio Script (texto plano para TTS)

```
Buenos días. Es lunes, 1 de junio de 2026.
En Jülich tenemos diecisiete coma tres grados y el cielo está despejado.

En el panorama internacional, Colombia definirá su presidencia entre
un senador de izquierda y un rival pro-Trump...

Esto ha sido todo. Que tengas un gran día.
```

---

## 🐛 Troubleshooting

### El LLM no responde

```bash
# Verificar que Ollama está corriendo
ollama list

# Probar modelo directamente
ollama run qwen3.5:cloud "Decí hola"

# Si usás Ollama Cloud, verificar API key
echo $OLLAMA_API_KEY
```

### El audio no se genera

```bash
# Probar TTS manualmente
say -v Monica "Hola, esto es una prueba" -o test.aiff

# Verificar ffmpeg está instalado
ffmpeg -version
```

### Telegram no envía

```bash
# Probar Hermes send manualmente
hermes send telegram "Test"
```

### Error: `tcsetattr: Inappropriate ioctl for device`

**Causa:** Ejecutar en background/cron sin PTY.  
**Solución:** Los scripts usan API directa, no llaman `hermes chat` directamente.

### Error: `No such file or directory: data/raw/YYYYMMDD.json`

**Causa:** El paso 1 no se ejecutó o falló.  
**Solución:** Ejecutar `python3 scripts/01_fetch_news.py --date YYYYMMDD` manualmente.

### Audio no se reproduce como voice bubble en Telegram

**Causa:** Formato incorrecto.  
**Solución:** Verificar que `tts.output_format = "ogg"` y `sample_rate = 48000` en config.yaml.

---

## 📈 Logs

Los logs se guardan en `data/logs/YYYYMMDD.log`:

```bash
# Ver último log
cat data/logs/$(date +%Y%m%d).log

# Ver todos los logs de la semana
ls -la data/logs/
```

**Formato del log:**

```
[2026-06-01 09:12:42] [INFO] Inicio del workflow - 20260601
[2026-06-01 09:12:42] [STEP] Paso 1/3: fetch
[2026-06-01 09:12:47] [SUCCESS] Paso fetch completado
[2026-06-01 09:12:47] [STEP] Paso 2/3: translate
[2026-06-01 09:13:08] [SUCCESS] Paso translate completado
[2026-06-01 09:13:08] [STEP] Paso 3/3: publish
[2026-06-01 09:13:24] [SUCCESS] Paso publish completado
[2026-06-01 09:13:24] [SUCCESS] Workflow completado en 42.5s
```

---

## 📝 Versiones

| Versión | Fecha | Cambios |
|---------|-------|---------|
| **v1.0.0** | 2026-05-28 | Versión inicial, arquitectura modular con orquestador |
| **v1.1.0** | 2026-06-01 | Corrección: output completo a Telegram, deliver: local en cronjob |

---

## 🤝 Contribuciones

¡Las contribuciones son bienvenidas!

1. Fork el repositorio
2. Crear branch (`git checkout -b feature/nueva-funcionalidad`)
3. Commit (`git commit -m 'Agregar nueva funcionalidad'`)
4. Push (`git push origin feature/nueva-funcionalidad`)
5. Abrir Pull Request

---

## 📄 Licencia

MIT License — ver [LICENSE](LICENSE) para detalles.

---

## 🙏 Agradecimientos

- **Hermes Agent** — Framework base para automatización
- **Ollama** — Acceso a modelos LLM cloud
- **Qwen / Gemini** — Traducciones de alta calidad
- **Open-Meteo** — API de clima gratis y sin API key
- **Telegram** — Entrega de briefings (texto + voice bubble)

---

## 📬 Contacto

| | |
|---|---|
| **Autor** | Dr. Davinson Pezo |
| **Rol** | Scientific Consultant |
| **GitHub** | [@davinson-pezo](https://github.com/davinson-pezo) |
| **Email** | info@dataquorum.net |
| **Website** | [dataquorum.net](https://dataquorum.net) |
| **ORCID** | [0000-0001-8978-9498](https://orcid.org/0000-0001-8978-9498) |

---

## ☕ ¿Te gusta este proyecto?

Si este workflow te ahorra tiempo cada mañana y querés apoyar el desarrollo, podés invitarme un café:

[![PayPal](https://img.shields.io/badge/Donate-PayPal-blue.svg)](https://paypal.me/dpezo)

**PayPal:** `davinson@gmail.com`

---

## 🔭 Otros Proyectos del Autor

Mirá mis otros repositorios en GitHub:

| Proyecto | Descripción |
|----------|-------------|
| **[mcp-scientific-rag](https://github.com/davinson-pezo/mcp-scientific-rag)** | RAG 100% local para procesar literatura científica con MCP |
| **[hermes-pixel-ui](https://github.com/davinson-pezo/hermes-pixel-ui)** | Dashboard pixel-art para visualizar sesiones de Hermes Agent |
| **[jarvis](https://github.com/davinson-pezo/jarvis)** | Asistente de voz AI multi-plataforma inspirado en Iron Man |
| **[watch-says-privacy](https://github.com/davinson-pezo/watch-says-privacy)** | App watchOS — Privacy policy documentation |
| **[capibara-adventure-privacy](https://github.com/davinson-pezo/capibara-adventure-privacy)** | App watchOS — Privacy policy documentation |

---

**Hecho con ❤️ en Jülich, Alemania**

*Última actualización: 2026-06-01*
