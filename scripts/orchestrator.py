#!/usr/bin/env python3
"""
Orquestador del Morning Briefing.

Ejecuta los 3 pasos en secuencia:
  1. 01_fetch_news.py     → Obtener RSS + clima
  2. 02_translate_news.py → Traducir con LLM
  3. 03_publish.py        → Generar audio + enviar Telegram

Manejo de errores:
  - Si paso 1 falla → abortar, notificar
  - Si paso 2 falla → enviar solo markdown (sin audio)
  - Si paso 3 falla → reintentar 2 veces, luego notificar

Ejecutar:
  python3 scripts/orchestrator.py
  python3 scripts/orchestrator.py --date 20260528
  python3 scripts/orchestrator.py --dry-run  # Solo validar, no ejecutar
"""

import os
import sys
import argparse
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# ==================== CONFIGURACIÓN ====================

BASE_DIR = Path(__file__).parent.parent
SCRIPTS_DIR = BASE_DIR / 'scripts'
LOGS_DIR = BASE_DIR / 'data' / 'logs'

# Pasos del workflow
STEPS = [
    {
        'name': 'fetch',
        'script': '01_fetch_news.py',
        'timeout': 60,
        'critical': True,  # Si falla, abortar todo
    },
    {
        'name': 'translate',
        'script': '02_translate_news.py',
        'timeout': 120,
        'critical': True,  # Si falla, no hay audio ni texto
    },
    {
        'name': 'publish',
        'script': '03_publish.py',
        'timeout': 90,
        'critical': False,  # Si falla, al menos los archivos están generados
        'retry': 2,  # Reintentar 2 veces si falla
    },
]

# ==================== FUNCIONES ====================

def setup_logging(date_str):
    """Configura archivo de log para esta ejecución."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"{date_str}.log"
    return log_file

def log_message(log_file, message, level='INFO'):
    """Escribe un mensaje en el log."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Escribir al archivo si existe
    if log_file:
        line = f"[{timestamp}] [{level}] {message}\n"
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(line)
    
    # También imprimir a stdout
    prefix = {
        'INFO': 'ℹ️',
        'SUCCESS': '✅',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'STEP': '▶️',
    }.get(level, '•')
    
    print(f"{prefix} {message}")

def run_step(step, date_str, dry_run=False):
    """
    Ejecuta un paso del workflow.
    
    Retorna: (success: bool, error_msg: str|None)
    """
    
    script_name = step['script']
    script_path = SCRIPTS_DIR / script_name
    timeout = step.get('timeout', 60)
    retry_count = step.get('retry', 0)
    
    if not script_path.exists():
        return False, f"Script no encontrado: {script_path}"
    
    # Comando base
    cmd = [
        'python3', str(script_path),
        '--date', date_str,
    ]
    
    # Intentar con reintentos si está configurado
    attempts = 1 + retry_count
    last_error = None
    
    for attempt in range(1, attempts + 1):
        if attempt > 1:
            log_message(None, f"Reintento {attempt}/{attempts} para {step['name']}...", 'WARNING')
        
        if dry_run:
            log_message(None, f"[DRY RUN] Ejecutaría: {' '.join(cmd)}", 'INFO')
            return True, None
        
        try:
            log_message(None, f"Ejecutando {script_name} (timeout: {timeout}s)...", 'STEP')
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(BASE_DIR)
            )
            
            if result.returncode == 0:
                return True, None
            
            last_error = f"Exit code {result.returncode}: {result.stderr[:200]}"
            log_message(None, f"Falló: {last_error}", 'ERROR')
        
        except subprocess.TimeoutExpired:
            last_error = f"Timeout después de {timeout}s"
            log_message(None, f"Timeout: {step['name']} excedió {timeout}s", 'ERROR')
        
        except Exception as e:
            last_error = str(e)
            log_message(None, f"Error: {e}", 'ERROR')
    
    return False, last_error

def send_error_notification(error_msg, step_name, date_str):
    """Envía notificación de error a Telegram."""
    
    try:
        from hermes_tools import send_message
        
        message = (
            f"❌ **Morning Briefing - Error**\n\n"
            f"Fecha: {date_str}\n"
            f"Paso fallido: **{step_name}**\n\n"
            f"Error:\n```\n{error_msg[:500]}\n```\n\n"
            f"Revisá logs: `data/logs/{date_str}.log`"
        )
        
        send_message(action='send', target='telegram', message=message)
        print("📬 Notificación de error enviada a Telegram")
    
    except Exception as e:
        print(f"⚠️  No se pudo enviar notificación: {e}")

def cleanup_partial_outputs(date_str):
    """Limpia archivos parciales si el workflow falla a la mitad."""
    
    # Si falla el paso 1, no hay nada que limpiar
    # Si falla el paso 2, limpiar raw (ya no sirve)
    # Si falla el paso 3, mantener todo (al menos hay archivos)
    
    pass  # Por ahora no hacemos cleanup automático

# ==================== MAIN ====================

def main():
    parser = argparse.ArgumentParser(description='Orquestador del Morning Briefing')
    parser.add_argument(
        '--date',
        type=str,
        default=datetime.now().strftime('%Y%m%d'),
        help='Fecha para procesar (YYYYMMDD). Default: hoy'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Solo validar, no ejecutar scripts'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Mostrar output detallado de cada script'
    )
    args = parser.parse_args()
    
    date_str = args.date
    dry_run = args.dry_run
    
    # Setup logging
    log_file = setup_logging(date_str)
    
    # Header
    print("=" * 70)
    print(f"🎙️ Hermes Morning Briefing - Orquestador")
    print(f"   Fecha: {date_str}")
    print(f"   Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Modo: {'DRY RUN' if dry_run else 'NORMAL'}")
    print("=" * 70)
    
    log_message(log_file, "=" * 50, 'INFO')
    log_message(log_file, f"Inicio del workflow - {date_str}", 'INFO')
    
    start_time = datetime.now()
    failed_step = None
    failed_error = None
    
    # Ejecutar pasos en secuencia
    for i, step in enumerate(STEPS, 1):
        step_name = step['name']
        log_message(log_file, f"Paso {i}/{len(STEPS)}: {step_name}", 'STEP')
        
        success, error = run_step(step, date_str, dry_run)
        
        if success:
            log_message(log_file, f"Paso {step_name} completado", 'SUCCESS')
        else:
            log_message(log_file, f"Paso {step_name} FALLÓ: {error}", 'ERROR')
            failed_step = step_name
            failed_error = error
            
            if step.get('critical', True):
                log_message(log_file, "Paso crítico falló - abortando workflow", 'ERROR')
                break
            else:
                log_message(log_file, "Paso no crítico - continuando", 'WARNING')
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Resumen final
    print("\n" + "=" * 70)
    print("📊 RESUMEN")
    print("=" * 70)
    
    if dry_run:
        print("✅ DRY RUN completado - sin errores")
        log_message(log_file, "DRY RUN completado", 'SUCCESS')
    
    elif failed_step is None:
        print(f"✅ Workflow completado exitosamente")
        print(f"   Duración: {duration:.1f}s")
        log_message(log_file, f"Workflow completado en {duration:.1f}s", 'SUCCESS')
    
    else:
        print(f"❌ Workflow falló en paso: {failed_step}")
        print(f"   Error: {failed_error[:200]}")
        print(f"   Duración: {duration:.1f}s (parcial)")
        log_message(log_file, f"Workflow falló en {failed_step}: {failed_error}", 'ERROR')
        
        # Enviar notificación de error
        if not dry_run:
            send_error_notification(failed_error, failed_step, date_str)
    
    print("=" * 70)
    log_message(log_file, "=" * 50, 'INFO')
    
    # Imprimir el contenido del briefing para que el cronjob lo envíe a Telegram
    if not dry_run and failed_step is None:
        md_path = BASE_DIR / 'output' / 'markdown' / f"briefing_{date_str}.md"
        if md_path.exists():
            print("\n" + "=" * 70)
            print("🎙️ HERMES MORNING BRIEFING")
            print("=" * 70 + "\n")
            with open(md_path, 'r', encoding='utf-8') as f:
                print(f.read())
    
    # Retornar código de exit
    if failed_step and any(s['name'] == failed_step and s.get('critical', True) for s in STEPS):
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
