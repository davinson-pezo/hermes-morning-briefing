# 🏗️ Arquitectura — Hermes Morning Briefing

**Documento de diseño técnico y decisiones de arquitectura**

---

## 1. Visión General

Sistema automatizado de briefing matutino con arquitectura modular basada en **pipeline secuencial con estado persistente**.

### 1.1 Principios de Diseño

1. **Separación de responsabilidades** — Cada script hace UNA cosa bien
2. **Estado persistente** — JSONs intermedios permiten recovery
3. **Fail-fast** — Validar temprano, fallar rápido
4. **Idempotencia** — Se puede re-ejecutar sin efectos secundarios
5. **Cleanup automático** — Sin gestión manual de archivos

---

## 2. Arquitectura del Sistema

### 2.1 Diagrama de Flujo

```
┌──────────────────────────────────────────────────────────────────┐
│                     ORQUESTADOR (orchestrator.py)                │
│  - Valida fecha                                                  │
│  - Ejecuta pasos en secuencia                                    │
│  - Verifica exit codes                                           │
│  - Escribe logs                                                  │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  PASO 1: 01_fetch_news.py                                        │
│  ─────────────────────                                           │
│  Entradas:                                                       │
│    - RSS feeds (config.yaml)                                     │
│    - Open-Meteo API (clima)                                      │
│  Salidas:                                                        │
│    - data/raw/YYYYMMDD.json                                      │
│                                                                  │
│  Procesamiento:                                                  │
│    1. Parsear RSS feeds (feedparser)                             │
│    2. Filtrar noticias duplicadas                                │
│    3. Obtener clima (Open-Meteo API)                             │
│    4. Guardar JSON crudo                                         │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  PASO 2: 02_translate_news.py                                    │
│  ────────────────────────────                                    │
│  Entradas:                                                       │
│    - data/raw/YYYYMMDD.json                                      │
│  Salidas:                                                        │
│    - data/translated/YYYYMMDD.json                               │
│                                                                  │
│  Procesamiento:                                                  │
│    1. Construir prompt (máx 3 noticias por categoría)            │
│    2. Llamar LLM (Gemini vía Ollama Cloud)                       │
│    3. Parsear respuesta JSON                                     │
│    4. Validar estructura                                         │
│    5. Guardar JSON traducido                                     │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  PASO 3: 03_publish.py                                           │
│  ───────────────────                                             │
│  Entradas:                                                       │
│    - data/translated/YYYYMMDD.json                               │
│  Salidas:                                                        │
│    - output/markdown/briefing_YYYYMMDD.md                        │
│    - output/audio/briefing_YYYYMMDD.ogg                          │
│    - output/audio/script_YYYYMMDD.txt                            │
│    - Telegram (texto + audio)                                    │
│                                                                  │
│  Procesamiento:                                                  │
│    1. Generar markdown (formato Telegram)                        │
│    2. Extraer audio_script del JSON                              │
│    3. Generar audio (macOS say + ffmpeg)                         │
│    4. Enviar a Telegram                                          │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  CLEANUP: cleanup_old_files.py (semanal)                         │
│  ──────────────────────────────────                              │
│  Entradas:                                                       │
│    - config.yaml (cleanup policy)                                │
│  Salidas:                                                        │
│    - Archivos > 30 días eliminados                               │
│                                                                  │
│  Procesamiento:                                                  │
│    1. Escanear carpetas data/ y output/                          │
│    2. Calcular antigüedad de archivos                            │
│    3. Eliminar archivos > 30 días                                │
│    4. Reportar espacio liberado                                  │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. Decisiones de Diseño Clave

### 3.1 ¿Por qué 3 scripts separados en vez de uno solo?

**Problema inicial (2 semanas fallando):**
- Script monolítico hacía todo
- Si fallaba el paso 2, perdías todo
- Debugging imposible (¿dónde falló?)
- TTY conflicts al mezclar interactivo + background

**Solución (2 horas funcionando):**
- Cada script es independiente
- Estado persistente entre pasos (JSONs en disco)
- Podés re-ejecutar solo el paso que falló
- Cada script corre en su propio proceso (sin TTY conflicts)

**Lección:** La arquitectura importa más que el código.

---

### 3.2 ¿Por qué JSON como formato intermedio?

**Ventajas:**
- ✅ Legible por humanos (debugging fácil)
- ✅ Legible por máquinas (parsing trivial)
- ✅ Auto-descriptivo (keys explican el contenido)
- ✅ Fácil de validar (schema simple)
- ✅ Fácil de transformar (Python json module)

**Alternativas consideradas:**
- ❌ Pickle: Binario, no legible, Python-specific
- ❌ CSV: No soporta estructuras anidadas
- ❌ XML: Verboso, parsing más complejo

---

### 3.3 ¿Por qué Ollama Cloud en vez de API directa?

**Contexto:**
- Hermes ya tiene Ollama configurado
- Gemini está disponible vía Ollama Cloud
- No requiere API keys adicionales

**Ventajas:**
- ✅ Sin configuración extra de API keys
- ✅ Mismo interface para todos los modelos
- ✅ Fácil cambiar de modelo (solo cambiar nombre)
- ✅ Ollama maneja rate limiting, retries, etc.

**Desventajas:**
- ❌ Requiere Ollama corriendo localmente
- ❌ Un layer más de abstracción

**Alternativas:**
- API directa de Google Gemini (requiere API key)
- API directa de OpenAI (requiere API key + pago)

---

### 3.4 ¿Por qué macOS TTS en vez de cloud TTS?

**Ventajas de macOS TTS:**
- ✅ Gratis (ya viene con el sistema)
- ✅ Sin API keys
- ✅ Sin límites de uso
- ✅ Funciona offline
- ✅ Alta calidad (voces neuronales)

**Desventajas:**
- ❌ Solo macOS
- ❌ Menos voces que cloud providers

**Alternativas:**
- Edge TTS (gratis, multiplataforma, requiere internet)
- OpenAI TTS (pago, alta calidad)
- Piper TTS (open source, local, requiere instalación)

---

### 3.5 ¿Por qué cleanup semanal en vez de diario?

**Razones:**
1. **Menos overhead** — Una vez por semana es suficiente
2. **Horario tranquilo** — Domingos 6 AM (sin competencia por recursos)
3. **Debugging más fácil** — Si algo falla el martes, los archivos del lunes aún están
4. **Retención suficiente** — 30 días da margen para recuperar briefings antiguos

**Cleanup policy:**

| Carpeta | Retención | Frecuencia |
|---------|-----------|------------|
| `data/raw/` | 7 días | Semanal |
| `data/translated/` | 7 días | Semanal |
| `data/logs/` | 30 días | Semanal |
| `output/markdown/` | 30 días | Semanal |
| `output/audio/` | 30 días | Semanal |

---

## 4. Estructura de Datos

### 4.1 JSON Crudo (`data/raw/YYYYMMDD.json`)

```json
{
  "date": "20260528",
  "fetched_at": "2026-05-28 08:00:00",
  "weather": {
    "temp": 21.7,
    "temp_max": 27.0,
    "temp_min": 13.8,
    "condition": "despejado",
    "location": "Jülich, Alemania"
  },
  "categories": {
    "INTERNACIONALES": [
      {
        "title": "Iran attacks US base after new airstrikes",
        "description": "The hostilities come during a fragile ceasefire...",
        "url": "https://www.bbc.com/news/...",
        "published": "2026-05-28T06:30:00Z",
        "source": "BBC"
      }
    ],
    "ALEMANIA": [...],
    "CIENCIA": [...],
    "TECNOLOGÍA": [...],
    "IA / MACHINE LEARNING": [...],
    "DESARROLLO": [...]
  }
}
```

### 4.2 JSON Traducido (`data/translated/YYYYMMDD.json`)

```json
{
  "date": "20260528",
  "date_es": "Jueves, 28 de mayo de 2026",
  "translated_at": "2026-05-28 08:00:15",
  "weather": {...},
  "categories": {
    "INTERNACIONALES": [
      {
        "title_es": "Irán ataca base estadounidense tras nuevos bombardeos",
        "summary_es": "Las hostilidades ocurren durante un frágil alto el fuego...",
        "url": "https://www.bbc.com/news/..."
      }
    ],
    ...
  },
  "audio_script": "Buenos días. Es jueves, 28 de mayo de 2026..."
}
```

**Diferencias clave:**
- `title` → `title_es` (traducido)
- `description` → `summary_es` (resumido + traducido)
- Se agrega `audio_script` (texto plano para TTS)
- Se eliminan `published` y `source` (no necesarios para output)

---

## 5. Manejo de Errores

### 5.1 Estrategia General

```python
try:
    # Intentar operación
    result = do_something()
except SpecificError as e:
    # Error conocido → manejar graceful
    log_error(e)
    return fallback_value()
except Exception as e:
    # Error desconocido → fail fast
    log_error(e)
    sys.exit(1)
```

### 5.2 Errores Comunes y Manejo

| Error | Causa | Manejo |
|-------|-------|--------|
| RSS feed no responde | Timeout de red | Reintentar 2 veces, luego saltar categoría |
| LLM timeout | Prompt muy largo | Reducir noticias por categoría |
| LLM JSON inválido | Modelo no sigue formato | Reintentar con prompt más estricto |
| TTS falla | Voz no disponible | Fallback a voz predeterminada |
| Telegram falla | Bot token inválido | Log error, continuar sin envío |

---

## 6. Rendimiento y Optimización

### 6.1 Tiempos Típicos

| Paso | Tiempo | Cuello de botella |
|------|--------|-------------------|
| Fetch RSS | ~5s | Red (7 feeds paralelos) |
| Fetch clima | ~1s | Red (1 API call) |
| Traducción LLM | ~15s | LLM inference |
| Generar markdown | ~0.5s | CPU (trivial) |
| Generar audio | ~5s | CPU (TTS + encoding) |
| Enviar Telegram | ~2s | Red (API call) |
| **TOTAL** | **~28s** | — |

### 6.2 Optimizaciones Posibles

1. **Paralelizar RSS feeds** — Ya implementado (concurrent.futures)
2. **Cache de clima** — No implementado (cambia poco en el día)
3. **Batch LLM** — No implementado (Gemini es rápido suficiente)
4. **Streaming Telegram** — No implementado (envío es rápido)

---

## 7. Seguridad

### 7.1 Credenciales

- ✅ **No hardcoded** — API keys en variables de entorno o config.yaml
- ✅ **No commit** — config.yaml en .gitignore
- ✅ **Telegram bot token** — Solo permisos de envío (no lectura)

### 7.2 Datos

- ✅ **No PII** — Solo noticias públicas
- ✅ **Cleanup automático** — Archivos viejos se borran
- ✅ **Sin logging de contenido** — Solo logs de ejecución

---

## 8. Escalabilidad

### 8.1 Límites Actuales

| Recurso | Límite | Uso actual |
|---------|--------|------------|
| RSS feeds | Ilimitado | 7 feeds |
| Categorías | Ilimitado | 6 categorías |
| Noticias por categoría | Ilimitado | 3 (configurable) |
| Audio length | Ilimitado | ~2-3 minutos |
| Retención | Configurada | 30 días |

### 8.2 Cómo Escalar

**Más noticias:**
```yaml
# config.yaml
max_news_per_category: 5  # Aumentar de 3 a 5
```

**Más categorías:**
```yaml
# config.yaml
rss_feeds:
  DEPORTES:
    - https://...
  ECONOMÍA:
    - https://...
```

**Más retención:**
```yaml
# config.yaml
cleanup:
  retention_days: 90  # Aumentar de 30 a 90
```

---

## 9. Monitoreo

### 9.1 Logs

Ubicación: `data/logs/YYYYMMDD.log`

Formato:
```
[2026-05-28 08:00:00] [INFO] Inicio del workflow
[2026-05-28 08:00:05] [INFO] Paso 1 completado: 59 noticias
[2026-05-28 08:00:20] [INFO] Paso 2 completado: 18 noticias traducidas
[2026-05-28 08:00:28] [INFO] Paso 3 completado: Audio enviado
[2026-05-28 08:00:28] [INFO] Workflow completado en 28.5s
```

### 9.2 Métricas a Monitorear

- ✅ Tiempo total de ejecución
- ✅ Número de noticias por categoría
- ✅ Tamaño de audio generado
- ✅ Éxito/fallo de envío a Telegram
- ✅ Espacio liberado por cleanup

---

## 10. Futuras Mejoras

### 10.1 Corto Plazo

- [ ] Notificación Telegram si algún paso falla
- [ ] Reintentos automáticos para fallos transitorios
- [ ] Dashboard web para ver briefings históricos

### 10.2 Largo Plazo

- [ ] Detección de temas trending (agrupar noticias similares)
- [ ] Resúmenes semanales/mensuales automáticos
- [ ] Soporte para múltiples idiomas
- [ ] Integración con email

---

**Documento mantenido por:** Dr. Davinson Pezo  
**Última actualización:** 28 de mayo de 2026  
**Versión:** 1.0
