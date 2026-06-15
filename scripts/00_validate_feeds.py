#!/usr/bin/env python3
"""
Validador de feeds RSS para el Morning Briefing.

SOLO LECTURA. No modifica config.yaml ni ningún archivo del proyecto.
Usa la misma lista de feeds que 01_fetch_news.py (RSS_FEEDS) y además
candidatos nuevos que quieras probar.

Para cada feed reporta:
  - HTTP status
  - Tiempo de respuesta
  - ¿Parsea como XML válido?
  - Nº de items que entrega
  - Fecha del item más reciente (pubDate / dc:date / updated)
  - Antigüedad en días vs HOY
  - Veredicto: OK (≤7d) / STALE (>7d) / DEAD (>30d) / BROKEN (no parsea)

Uso:
  python3 scripts/00_validate_feeds.py                # solo feeds actuales
  python3 scripts/00_validate_feeds.py --candidates   # también candidatos nuevos
  python3 scripts/00_validate_feeds.py --days 14      # umbral personalizado
  python3 scripts/00_validate_feeds.py --json         # salida JSON
"""

import sys
import json
import argparse
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from email.utils import parsedate_to_datetime
import re

BASE_DIR = Path(__file__).parent.parent

# Misma lista que 01_fetch_news.py (copia intencional para no acoplar)
CURRENT_FEEDS = {
    'INTERNACIONALES': [
        'https://feeds.bbci.co.uk/news/world/rss.xml',
        'https://rss.nytimes.com/services/xml/rss/nyt/World.xml',
    ],
    'ALEMANIA': [
        'https://www.spiegel.de/schlagzeilen/index.rss',
        'https://www.handelsblatt.com/contentexport/feed/top-themen',
    ],
    'CIENCIA': [
        'https://phys.org/rss-feed/',
        'https://export.arxiv.org/rss/q-bio',
        'https://www.sciencedaily.com/rss/health_medicine.xml',
    ],
    'BIOTECNOLOGÍA': [
        'https://export.arxiv.org/rss/q-bio.QM',
        'https://export.arxiv.org/rss/q-bio.NC',
        'https://www.sciencedaily.com/rss/health_medicine.xml',
    ],
    'TECNOLOGÍA': [
        'https://es.gizmodo.com/rss',
        'https://www.theverge.com/rss/index.xml',
    ],
    'IA / MACHINE LEARNING': [
        'https://arxiv.org/rss/cs.AI',
        'https://huggingface.co/blog/feed.xml',
    ],
    'DESARROLLO': [
        'https://github.blog/feed/',
        'https://stackoverflow.blog/feed/',
    ],
    'GOOD_NEWS (CIENCIA extras)': [
        'https://www.goodnewsnetwork.org/feed/',
        'https://www.positive.news/feed/',
        'https://www.solutionsjournalism.org/feed/',
    ],
}

# Candidatos nuevos a evaluar (sólo si --candidates)
CANDIDATE_FEEDS = {
    'CIENCIA': [
        ('EurekAlert (AAAS)',          'https://www.eurekalert.org/rss.xml'),
        ('Phys.org',                   'https://phys.org/rss-feed/'),
        ('Science.org news',           'https://www.science.org/rss/news_current.xml'),
        ('arXiv q-bio (biología)',     'https://export.arxiv.org/rss/q-bio'),
    ],
    'BIOTECNOLOGÍA': [
        ('arXiv q-bio (todo)',         'https://export.arxiv.org/rss/q-bio'),
        ('arXiv q-bio.QM (mol)',       'https://export.arxiv.org/rss/q-bio.QM'),
        ('arXiv q-bio.NC (neuronal)',  'https://export.arxiv.org/rss/q-bio.NC'),
        ('SciDaily genetics',          'https://www.sciencedaily.com/rss/health_medicine/genetics.xml'),
        ('SciDaily biotech',           'https://www.sciencedaily.com/rss/health_medicine/biotechnology.xml'),
        ('Phys bio',                   'https://phys.org/rss-feed/biology/'),
        ('Nature biotech',             'https://www.nature.com/nbt.rss'),
        ('FierceBiotech',              'https://www.fiercebiotech.com/rss/xml'),
        ('GEN news',                   'https://www.genengnews.com/rss-feed/'),
    ],
}


def curl(url, timeout=10):
    """curl con user-agent; devuelve (status_code, body, elapsed_ms, error).

    IMPORTANTE: separar body y metadatos en dos invocaciones para evitar que
    el flag -w de curl concatene '200|0.114' al final del body (eso rompe
    xml.etree con 'junk after document element').
    """
    try:
        meta_proc = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}|%{time_total}',
             '-A', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
             '-L', '--max-time', str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        meta = meta_proc.stdout.strip()
        if '|' not in meta:
            return 0, '', 0, f'meta vacío: {meta!r}'
        code, t = meta.split('|', 1)
        body_proc = subprocess.run(
            ['curl', '-s',
             '-A', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
             '-L', '--max-time', str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 5
        )
        return int(code), body_proc.stdout, int(float(t) * 1000), None
    except Exception as e:
        return 0, '', 0, str(e)


def parse_items(xml_text):
    """Devuelve (items_count, latest_date_iso) o lanza Exception."""
    root = ET.fromstring(xml_text)
    # RSS 2.0: <channel><item>...</item></channel>
    # Atom:   <feed><entry>...</entry></feed>
    items = root.findall('.//item') or root.findall('.//{http://www.w3.org/2005/Atom}entry')
    if not items:
        return 0, None
    # Fecha más reciente
    latest = None
    date_candidates = ['pubDate', 'dc:date', 'date', 'updated',
                       '{http://purl.org/dc/elements/1.1/}date',
                       '{http://www.w3.org/2005/Atom}updated',
                       '{http://www.w3.org/2005/Atom}published']
    for it in items:
        for tag in date_candidates:
            el = it.find(tag)
            if el is not None and el.text:
                try:
                    d = parse_any_date(el.text.strip())
                    if d and (latest is None or d > latest):
                        latest = d
                    break
                except Exception:
                    continue
        if latest is not None:
            break
    return len(items), latest


def parse_any_date(s):
    """RFC 822, ISO 8601, otros → datetime aware en UTC."""
    # RFC 822 (pubDate típico)
    try:
        d = parsedate_to_datetime(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        pass
    # ISO 8601
    s2 = s.replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(s2)
    except Exception:
        return None


def verdict_for(latest_date, now, stale_days, dead_days):
    if latest_date is None:
        return 'UNKNOWN (no parseable date)'
    age = (now - latest_date).days
    if age < 0:
        return f'FUTURE (+{-age}d) ¿reloj mal?'
    if age > dead_days:
        return f'DEAD ({age}d)'
    if age > stale_days:
        return f'STALE ({age}d)'
    return f'OK ({age}d)'


def eval_feed(url, stale=7, dead=30, timeout=10):
    code, body, ms, err = curl(url, timeout=timeout)
    if err or code != 200:
        return {
            'url': url, 'http': code, 'ms': ms, 'items': 0,
            'latest': None, 'verdict': f'BROKEN ({err or "HTTP " + str(code)})',
        }
    try:
        n, latest = parse_items(body)
    except ET.ParseError as e:
        return {
            'url': url, 'http': code, 'ms': ms, 'items': 0,
            'latest': None, 'verdict': f'BROKEN (XML parse: {e})',
        }
    now = datetime.now(timezone.utc)
    v = verdict_for(latest, now, stale, dead)
    return {
        'url': url, 'http': code, 'ms': ms, 'items': n,
        'latest': latest.isoformat() if latest else None,
        'verdict': v,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--candidates', action='store_true',
                    help='Evaluar también feeds candidatos (no incorporados)')
    ap.add_argument('--days', type=int, default=7,
                    help='Días a partir del cual un feed se considera STALE (default 7)')
    ap.add_argument('--dead-days', type=int, default=30,
                    help='Días a partir del cual un feed se considera DEAD (default 30)')
    ap.add_argument('--json', action='store_true', help='Salida JSON')
    ap.add_argument('--timeout', type=int, default=10)
    args = ap.parse_args()

    sets = [{'label': 'ACTUALES', 'feeds': CURRENT_FEEDS, 'names': {}}]
    if args.candidates:
        cand = {}
        names = {}
        for cat, items in CANDIDATE_FEEDS.items():
            cand[cat] = [u for _, u in items]
            names[cat] = dict(items)
        sets.append({'label': 'CANDIDATOS', 'feeds': cand, 'names': names})

    results = {}
    for s in sets:
        label = s['label']
        feeds_dict = s['feeds']
        names_map = s['names']
        results[label] = {}
        for cat, urls in feeds_dict.items():
            results[label][cat] = []
            for u in urls:
                # Anonimizar en salida
                display_name = None
                if names_map and cat in names_map:
                    display_name = names_map[cat].get(u)
                r = eval_feed(u, stale=args.days, dead=args.dead_days,
                              timeout=args.timeout)
                r['category'] = cat
                r['name'] = display_name
                results[label][cat].append(r)

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
        return

    # Salida humana
    print(f"\n{'='*78}")
    print(f"VALIDACIÓN DE FEEDS — {datetime.now().strftime('%Y-%m-%d %H:%M %Z')}")
    print(f"Umbrales: STALE > {args.days}d, DEAD > {args.dead_days}d")
    print(f"{'='*78}\n")

    for label, cats in results.items():
        print(f"\n{'#'*78}")
        print(f"# {label}")
        print(f"{'#'*78}\n")
        for cat, items in cats.items():
            print(f"  {cat}")
            for r in items:
                tag = '[OK]' if r['verdict'].startswith('OK') else \
                      '[!!]' if 'STALE' in r['verdict'] else \
                      '[XX]' if r['verdict'].startswith(('DEAD', 'BROKEN', 'FUTURE')) else '[??]'
                name = f"  ({r['name']})" if r.get('name') else ''
                print(f"    {tag} {r['verdict']:<20} items={r['items']:<3} "
                      f"http={r['http']} {r['ms']}ms{name}")
                print(f"        {r['url']}")
                if r.get('latest'):
                    print(f"        latest = {r['latest']}")
            print()

    # Resumen ejecutivo
    print(f"\n{'='*78}")
    print("RESUMEN EJECUTIVO")
    print(f"{'='*78}")
    for label, cats in results.items():
        ok = stale = dead = broken = 0
        for items in cats.values():
            for r in items:
                v = r['verdict']
                if v.startswith('OK'): ok += 1
                elif 'STALE' in v: stale += 1
                elif v.startswith('DEAD'): dead += 1
                else: broken += 1
        total = ok + stale + dead + broken
        flag = '✅' if dead == 0 and broken == 0 else '⚠️'
        print(f"  {flag} {label}: {ok} OK, {stale} STALE, {dead} DEAD, {broken} BROKEN "
              f"(de {total} feeds)")
    print()


if __name__ == '__main__':
    main()
