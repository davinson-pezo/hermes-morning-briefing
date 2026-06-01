#!/usr/bin/env python3
"""
Limpieza automática de archivos antiguos.

Ejecutar:
  python3 cleanup_old_files.py --dry-run   # Ver qué se borraría
  python3 cleanup_old_files.py              # Ejecutar limpieza real

Se ejecuta semanalmente (domingos 6:00 AM) vía cronjob.
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# ==================== CONFIGURACIÓN ====================

BASE_DIR = Path(__file__).parent.parent  # ~/Documents/Hermes_docs/news

# Reglas de limpieza: (carpeta_rel, días_retención, patrón_glob)
CLEANUP_RULES = [
    ('data/raw', 7, '*.json'),
    ('data/translated', 7, '*.json'),
    ('data/logs', 30, '*.log'),
    ('output/markdown', 30, '*.md'),
    ('output/audio', 30, '*.ogg'),
    ('output/audio', 30, '*.txt'),
]

# ==================== FUNCIONES ====================

def get_old_files(folder_rel, days, pattern):
    """Encuentra archivos más antiguos que X días."""
    cutoff = datetime.now() - timedelta(days=days)
    folder_path = BASE_DIR / folder_rel
    
    if not folder_path.exists():
        return []
    
    old_files = []
    for f in folder_path.glob(pattern):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            if mtime < cutoff:
                age_days = (datetime.now() - mtime).days
                old_files.append((f, age_days, f.stat().st_size))
        except (OSError, FileNotFoundError):
            continue
    
    # Ordenar por antigüedad (más viejos primero)
    old_files.sort(key=lambda x: x[1], reverse=True)
    return old_files

def format_size(size_bytes):
    """Formatea tamaño en KB/MB."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / 1024 / 1024:.2f} MB"

def cleanup(dry_run=False):
    """Ejecuta la limpieza según las reglas configuradas."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    print("=" * 70)
    print(f"🧹 Hermes Morning Briefing - Cleanup")
    print(f"   Fecha: {timestamp}")
    print(f"   Modo: {'DRY RUN (solo vista)' if dry_run else 'REAL (borrando)'}")
    print("=" * 70)
    
    total_files = 0
    total_size = 0
    stats_by_folder = {}
    
    for folder_rel, days, pattern in CLEANUP_RULES:
        old_files = get_old_files(folder_rel, days, pattern)
        
        if not old_files:
            print(f"\n✓ {folder_rel}/{pattern}")
            print(f"  Nada que borrar (retención: {days} días)")
            stats_by_folder[folder_rel] = {'files': 0, 'size': 0}
            continue
        
        folder_size = sum(size for _, _, size in old_files)
        folder_count = len(old_files)
        total_files += folder_count
        total_size += folder_size
        stats_by_folder[folder_rel] = {'files': folder_count, 'size': folder_size}
        
        print(f"\n📁 {folder_rel}/{pattern}")
        print(f"  {folder_count} archivos ({format_size(folder_size)}) - retención: {days} días")
        
        # Mostrar primeros 10 archivos
        for filepath, age_days, size in old_files[:10]:
            print(f"  - {filepath.name:40s} ({age_days:3d} días, {format_size(size):>8s})")
        
        if len(old_files) > 10:
            print(f"  ... y {len(old_files) - 10} archivos más")
        
        # Borrar archivos
        if not dry_run:
            for filepath, _, _ in old_files:
                try:
                    filepath.unlink()
                except (OSError, FileNotFoundError) as e:
                    print(f"  ⚠️  Error borrando {filepath.name}: {e}")
    
    # Resumen final
    print("\n" + "=" * 70)
    print("📊 RESUMEN")
    print("=" * 70)
    
    if total_files == 0:
        print("✅ No hay archivos antiguos que borrar.")
    else:
        print(f"Total archivos: {total_files}")
        print(f"Espacio liberado: {format_size(total_size)}")
        
        if dry_run:
            print("\n⚠️  DRY RUN - Nada se borró.")
            print("   Ejecutá sin --dry-run para aplicar la limpieza.")
        else:
            print("\n✅ Limpieza completada.")
    
    print("=" * 70)
    
    return {
        'timestamp': timestamp,
        'dry_run': dry_run,
        'total_files': total_files,
        'total_size': total_size,
        'stats_by_folder': stats_by_folder
    }

# ==================== MAIN ====================

def main():
    parser = argparse.ArgumentParser(
        description='Limpieza de archivos antiguos del Morning Briefing'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Solo mostrar archivos que se borrarían, no borrar nada'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output en formato JSON (para logging)'
    )
    args = parser.parse_args()
    
    result = cleanup(dry_run=args.dry_run)
    
    if args.json:
        import json
        print("\n" + json.dumps(result, indent=2, default=str))
    
    return 0 if result['total_files'] >= 0 else 1

if __name__ == '__main__':
    sys.exit(main())
