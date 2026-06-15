# 💡 Lecciones Aprendidas — Hermes Morning Briefing

**De 2 semanas fallando a 2 horas funcionando: Lo que aprendimos en el camino**

---

## 1. El Problema Inicial

### 1.1 Contexto

**Objetivo:** Briefing matutino automático con noticias, clima y audio tipo locutor.

**Intentos previos:** 2 semanas de pruebas fallidas

**Síntomas:**
- Scripts se colgaban sin error claro
- TTY conflicts en background
- `hermes chat` no funcionaba en cronjobs
- Pérdida total de progreso si algo fallaba

### 1.2 Root Cause Analysis

**Problema raíz:** Arquitectura monolítica

```python
# ❌ ANTES: Un solo script haciendo todo
def main():
    news = fetch_news()      # 5s
    translated = llm(news)   # 15s → ACÁ SE COLGABA
    audio = tts(translated)  # 5s
    send(audio)             # 2s
    
# Si fallaba en llm():
# - Perdías todo el progreso
# - No había logs de qué falló
# - Imposible debuggear
```

**Errores de diseño:**
1. Todo en un solo proceso
2. Sin estado persistente entre pasos
3. Mezclar interactivo (`hermes chat`) con background
4. Sin manejo de errores granular

---

## 2. La Solución

### 2.1 Insight Clave

> **"El problema no era el código, era la arquitectura."**

**Cambio de paradigma:**
- ❌ Un script que hace todo
- ✅ 4 scripts que hacen UNA cosa cada uno

### 2.2 Nueva Arquitectura

```python
# ✅ AHORA: Scripts separados con estado persistente

# 01_fetch_news.py
news = fetch_news()
save_json('data/raw/today.json', news)  # ← Persiste

# 02_translate_news.py
news = load_json('data/raw/today.json')  # ← Recupera
translated = llm(news)
save_json('data/translated/today.json', translated)  # ← Persiste

# 03_publish.py
translated = load_json('data/translated/today.json')  # ← Recupera
audio = tts(translated)
send(audio)

# orchestrator.py
run('01_fetch_news.py')   # Si falla, pará acá
run('02_translate_news.py')  # Si falla, paso 1 ya está guardado
run('03_publish.py')  # Si falla, pasos 1-2 ya están guardados
```

**Beneficios:**
- ✅ Cada paso es independiente
- ✅ Estado persiste en disco
- ✅ Podés re-ejecutar solo el paso que falló
- ✅ Debugging trivial (mirá el JSON intermedio)

---

## 3. Lecciones Técnicas

### 3.1 Arquitectura > Código

**Lección:** Una buena arquitectura salva código mediocre. Código perfecto no salva arquitectura mala.

**Antes:**
- 500 líneas de código "perfecto"
- 2 semanas sin funcionar

**Después:**
- 4 scripts de 100 líneas cada uno
- 2 horas funcionando

**Acción:** Siempre empezar con arquitectura en papel antes de codificar.

---

### 3.2 Estado Persistente es Oro

**Lección:** Guardar estado intermedio en disco permite:
- Recovery después de fallos
- Debugging sin re-ejecutar todo
- Testing de pasos individuales
- Idempotencia (re-ejecutar sin efectos secundarios)

**Formato elegido:** JSON
- ✅ Legible por humanos
- ✅ Legible por máquinas
- ✅ Auto-descriptivo
- ✅ Fácil de validar

**Alternativas descartadas:**
- ❌ Pickle (binario, no legible)
- ❌ CSV (no soporta estructuras anidadas)
- ❌ SQLite (overkill para este caso)

---

### 3.3 No Mezclar Interactivo con Background

**Lección:** Herramientas interactivas (`hermes chat`, `vim`, `python REPL`) NO funcionan en background/cron.

**Problema:**
```bash
# ❌ Esto NO funciona en cron
hermes chat -p "Traducí estas noticias" < input.txt

# Error: tcsetattr: Inappropriate ioctl for device
```

**Solución:**
```bash
# ✅ Usar API directa (sin TTY)
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model": "gemini", "messages": [...]}'
```

**Regla de oro:** Si va a correr en background/cron, usar APIs HTTP, no herramientas interactivas.

---

### 3.4 Fail Fast con Validación Temprana

**Lección:** Validar inputs temprano evita fallos en cascada.

**Antes:**
```python
# ❌ Validar al final
result = step1()
result = step2(result)
result = step3(result)  # ← ACÁ FALLA
validate(result)  # ¿Ahora qué?
```

**Después:**
```python
# ✅ Validar antes de cada paso
data = load_json('raw.json')
validate_structure(data, required=['date', 'weather', 'categories'])

result = translate(data)
validate_structure(result, required=['date_es', 'audio_script'])

publish(result)
```

**Beneficios:**
- Error messages más claros
- Más fácil identificar root cause
- Menos tiempo debugging

---

### 3.5 Elegir Herramientas con Credenciales Disponibles

**Lección:** No asumir que tenés API keys. Verificar antes de diseñar.

**Historia:**
- Diseñamos con `qwen3.5:cloud`
- 2 semanas después descubrimos: requiere API key que no teníamos
- Hermes interactivo funcionaba (credenciales en gateway)
- Scripts NO funcionaban (sin acceso a esas credenciales)

**Solución:**
- Usar `gemini-3-flash-preview:latest` (ya configurado en Ollama)
- Sin API keys nuevas
- Funcionó en 10 minutos

**Regla:** Siempre verificar credenciales disponibles ANTES de elegir tecnología.

---

### 3.6 Cleanup desde el Día 1

**Lección:** Si no planificás cleanup desde el inicio, vas a acumular basura para siempre.

**Diseño inicial:**
```yaml
cleanup:
  retention_days: 30
  run_schedule: "0 6 * * 0"  # Domingos 6 AM
```

**Beneficios:**
- ✅ Sin gestión manual de archivos viejos
- ✅ Espacio en disco predecible
- ✅ Logs históricos suficientes (30 días)
- ✅ Datos intermedios efímeros (7 días)

**Fórmula mágica:**
```python
# cleanup_old_files.py
for folder, days, pattern in CLEANUP_RULES:
    cutoff = datetime.now() - timedelta(days=days)
    for file in Path(folder).glob(pattern):
        if file.stat().st_mtime < cutoff:
            file.unlink()  # ← Adiós basura
```

---

## 4. Lecciones de Proceso

### 4.1 Documentar ANTES de Codificar

**Lección:** Escribir README y docs de arquitectura ANTES de codificar clarifica el diseño.

**Qué hicimos:**
1. Escribir `GITHUB_README.md` (qué hace el sistema)
2. Escribir `ARQUITECTURA.md` (cómo lo hace)
3. Escribir `WORKFLOW.md` (flujo paso a paso)
4. Recién ahí codificar

**Beneficios:**
- ✅ Pensás la interfaz antes de la implementación
- ✅ Identificás edge cases temprano
- ✅ Tenés docs listos cuando terminás
- ✅ Más fácil obtener feedback

**Regla:** Docs primero, código después.

---

### 4.2 Probar en Aislamiento

**Lección:** Probar cada paso por separado antes de integrar.

**Nuestro proceso:**
```bash
# Día 1: Probar solo fetch
python3 scripts/01_fetch_news.py
# ✅ Funciona → 59 noticias

# Día 2: Probar solo traducción
python3 scripts/02_translate_news.py
# ❌ Falla → Debuggear → ✅ Funciona

# Día 3: Probar solo publish
python3 scripts/03_publish.py
# ⚠️ Casi funciona → Arreglar race condition → ✅ Funciona

# Día 4: Integrar con orchestrator
python3 scripts/orchestrator.py
# ✅ Funciona todo junto
```

**Beneficios:**
- ✅ Si falla, sabés exactamente dónde
- ✅ Podés debuggear sin reiniciar todo
- ✅ Más fácil identificar dependencias

---

### 4.3 Logs Son Tu Mejor Amigo

**Lección:** Logs detallados salvan horas de debugging.

**Nuestro formato:**
```
[2026-05-28 08:00:00] [INFO] Inicio del workflow
[2026-05-28 08:00:05] [INFO] Paso 1: 59 noticias obtenidas
[2026-05-28 08:00:10] [INFO] Paso 2: Enviando prompt (5378 chars)
[2026-05-28 08:00:25] [INFO] Paso 2: Respuesta recibida (7271 chars)
[2026-05-28 08:00:26] [INFO] Paso 2: JSON parseado exitosamente
[2026-05-28 08:00:28] [INFO] Paso 3: Audio generado (259 KB)
[2026-05-28 08:00:30] [INFO] Workflow completado en 28.5s
```

**Qué loguear:**
- ✅ Timestamps (para medir performance)
- ✅ Tamaño de datos (para identificar cuellos de botella)
- ✅ Exit codes (para saber qué falló)
- ✅ Errores con contexto (no solo "falló")

**Qué NO loguear:**
- ❌ Contenido completo de datos (muy verboso)
- ❌ API keys o tokens (seguridad)
- ❌ Mensajes repetitivos (ruido)

---

### 4.4 Métricas Temprano

**Lección:** Medir performance desde el inicio identifica optimizaciones.

**Nuestras métricas:**
```python
# orchestrator.py
start = time.time()
run_step_1()
run_step_2()
run_step_3()
duration = time.time() - start

log(f"Workflow completado en {duration:.1f}s")
# → 28.5s
```

**Desglose:**
| Paso | Tiempo | % del total |
|------|--------|-------------|
| Fetch | 5s | 18% |
| Translate | 15s | 53% |
| Publish | 8s | 29% |
| **Total** | **28s** | **100%** |

**Insights:**
- LLM es el cuello de botella (53%)
- Fetch es rápido (paralelización funciona)
- Publish podría optimizarse (TTS es lento)

**Acciones:**
- ✅ Aumentar `max_tokens` para LLM (evita timeouts)
- ✅ Parallelizar RSS feeds (ya hecho)
- ⏳ Considerar TTS más rápido (opcional)

---

## 5. Lecciones Humanas

### 5.1 La Persistencia Paga

**Lección:** 2 semanas fallando → 2 horas funcionando. No aflojar.

**Momento crítico:**
- Día 10: "¿Y si esto no tiene solución?"
- Día 12: "Probemos una arquitectura diferente"
- Día 14: "¡FUNCIONA!"

**Reflexión:** El problema tenía solución. Solo necesitábamos cambiar de perspectiva.

---

### 5.2 Pedir Ayuda (a Vos Mismo)

**Lección:** A veces la mejor ayuda es escribir el problema en papel.

**Técnica que usamos:**
1. Escribir problema en una hoja
2. Dibujar arquitectura actual
3. Preguntar: "¿Qué asunciones estoy haciendo?"
4. Identificar asunción falsa: "Un script puede hacer todo"
5. Diseñar nueva arquitectura
6. Implementar

**Beneficio:** Escribir fuerza claridad mental.

---

### 5.3 Celebrar Pequeñas Victorias

**Lección:** Cada paso funcionando es un win. Celebrar.

**Nuestras victorias:**
- ✅ Día 1: Fetch funciona (59 noticias!)
- ✅ Día 2: LLM responde (aunque no JSON válido)
- ✅ Día 3: JSON parsea (aunque falta audio_script)
- ✅ Día 4: Audio se genera (aunque no envía)
- ✅ Día 5: Telegram funciona
- ✅ Día 6: Workflow completo

**Reflexión:** Cada "casi funciona" es progreso, no fracaso.

---

## 6. Checklist para Próximos Proyectos

### 6.1 Antes de Empezar

- [ ] Definir arquitectura en papel
- [ ] Identificar credenciales necesarias
- [ ] Verificar credenciales disponibles
- [ ] Diseñar formato de estado persistente
- [ ] Planear cleanup desde el inicio
- [ ] Escribir README (aunque sea borrador)

### 6.2 Durante Desarrollo

- [ ] Probar cada componente en aislamiento
- [ ] Loguear timestamps y tamaños
- [ ] Validar inputs temprano
- [ ] Guardar estado intermedio en disco
- [ ] Documentar decisiones de diseño
- [ ] Medir performance de cada paso

### 6.3 Antes de Deploy

- [ ] Probar workflow completo manualmente
- [ ] Configurar cronjobs
- [ ] Verificar cleanup automático
- [ ] Probar recovery después de fallo
- [ ] Documentar troubleshooting común
- [ ] Crear script de monitoreo

---

## 7. Patrones Reutilizables

### 7.1 Patrón: Pipeline con Estado Persistente

```python
# pipeline.py
import json
from pathlib import Path

def run_pipeline():
    # Paso 1
    data1 = step1()
    Path('data/step1.json').write_text(json.dumps(data1))
    
    # Paso 2
    data1 = json.loads(Path('data/step1.json').read_text())
    data2 = step2(data1)
    Path('data/step2.json').write_text(json.dumps(data2))
    
    # Paso 3
    data2 = json.loads(Path('data/step2.json').read_text())
    result = step3(data2)
    
    return result
```

**Cuándo usar:**
- ✅ Múltiples pasos secuenciales
- ✅ Pasos costosos (no querés re-ejecutar)
- ✅ Posibles fallos en pasos intermedios

---

### 7.2 Patrón: Orquestador con Validación

```python
# orchestrator.py
import subprocess
import sys

def run_step(name, script):
    print(f"▶️ {name}")
    result = subprocess.run(script, shell=True)
    if result.returncode != 0:
        print(f"❌ {name} falló")
        sys.exit(1)
    print(f"✅ {name} completado\n")
    return True

def main():
    run_step("Paso 1: Fetch", "python3 scripts/01_fetch.py")
    run_step("Paso 2: Translate", "python3 scripts/02_translate.py")
    run_step("Paso 3: Publish", "python3 scripts/03_publish.py")
    print("🎉 Pipeline completado")
```

**Cuándo usar:**
- ✅ Scripts independientes
- ✅ Querés fail-fast
- ✅ Necesitás logs centralizados

---

### 7.3 Patrón: Cleanup Automático

```python
# cleanup.py
from pathlib import Path
from datetime import datetime, timedelta

def cleanup(folder, days, pattern):
    cutoff = datetime.now() - timedelta(days=days)
    for file in Path(folder).glob(pattern):
        mtime = datetime.fromtimestamp(file.stat().st_mtime)
        if mtime < cutoff:
            print(f"🗑️  {file.name} ({(datetime.now() - mtime).days} días)")
            file.unlink()

# Uso
cleanup('data/raw', 7, '*.json')
cleanup('output/audio', 30, '*.ogg')
```

**Cuándo usar:**
- ✅ Archivos temporales
- ✅ Logs que crecen indefinidamente
- ✅ Outputs de pipelines automáticos

---

## 8. Conclusión

### 8.1 Resumen Ejecutivo

**Problema:** 2 semanas sin poder automatizar briefing matutino.

**Causa raíz:** Arquitectura monolítica + mezclar interactivo con background.

**Solución:** 4 scripts separados + estado persistente + APIs HTTP.

**Resultado:** 28 segundos de ejecución, 100% automatizado, 0 intervención manual.

### 8.2 Lección Principal

> **"La arquitectura correcta con código simple gana siempre a la arquitectura incorrecta con código perfecto."**

### 8.3 Próximos Pasos

1. ✅ Workflow operativo (28 de mayo de 2026)
2. ⏳ Configurar cronjob (primera semana de junio)
3. ⏳ Monitorear 1 semana (estabilidad)
4. ⏳ Publicar en GitHub (documentación completa)
5. ⏳ Próximo workflow automatizado (¿reportes semanales?)

---

**Documento mantenido por:** Dr. Davinson Pezo  
**Fecha:** 28 de mayo de 2026  
**Versión:** 1.0  
**Estado:** ✅ Completado

---

*"Dos semanas de debugging te enseñan más que dos años de tutoriales."*
