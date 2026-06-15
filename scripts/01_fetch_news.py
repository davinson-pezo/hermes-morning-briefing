#!/usr/bin/env python3
"""
Paso 1: Obtener noticias RSS + clima.

Entrada: --date YYYYMMDD (o fecha actual por defecto)
Salida: data/raw/YYYYMMDD.json

Ejecutar:
  python3 scripts/01_fetch_news.py --date 20260528
  python3 scripts/01_fetch_news.py  # usa fecha actual
"""

import os
import sys
import json
import re
import argparse
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

# ==================== CONFIGURACIÓN ====================

BASE_DIR = Path(__file__).parent.parent

# Frescura máxima de items (en días). Si un item tiene pubDate más viejo,
# se descarta para que el briefing NO publique noticias añejas cuando
# un feed quede congelado. Default 7d.
MAX_ITEM_AGE_DAYS = 7

# Feeds RSS por categoría (desde config.yaml)
# Estructura: {'category': {'feeds': [...], 'sentiment': 'mixed' | 'positive' | 'negative'}}
RSS_FEEDS = {
    'INTERNACIONALES': {
        'feeds': [
            'https://feeds.bbci.co.uk/news/world/rss.xml',
            'https://rss.nytimes.com/services/xml/rss/nyt/World.xml',
        ],
        'sentiment': 'mixed',  # Balance 50/50
    },
    'ALEMANIA': {
        'feeds': [
            'https://www.spiegel.de/schlagzeilen/index.rss',
            'https://www.handelsblatt.com/contentexport/feed/top-themen',
        ],
        'sentiment': 'mixed',
    },
    'CIENCIA': {
        'feeds': [
            # Phys.org - noticias generales de ciencia (fresco, 30 items/día)
            'https://phys.org/rss-feed/',
            # arXiv q-bio - preprints biología/molecular
            'https://export.arxiv.org/rss/q-bio',
            # ScienceDaily health/medicine (verificado OK 2026-06-15)
            'https://www.sciencedaily.com/rss/health_medicine.xml',
        ],
        'sentiment': 'positive',  # La ciencia suele ser positiva (descubrimientos, avances)
    },
    'BIOTECNOLOGÍA': {
        # Feeds dedicados biotech + arXiv sub-categorías biológicas
        # (los 3 son OK, verificado 2026-06-15 con 00_validate_feeds.py)
        'feeds': [
            'https://export.arxiv.org/rss/q-bio.QM',  # Quantitative Biology - molecular
            'https://export.arxiv.org/rss/q-bio.NC',  # Quantitative Biology - neurons/cognition
            'https://www.sciencedaily.com/rss/health_medicine.xml',
        ],
        'sentiment': 'positive',
        'filter_keywords': [  # al menos 1 debe matchear (case-insensitive)
            'biotecnología', 'biotechnology', 'genoma', 'genome', 'genomic',
            'crispr', 'células madre', 'stem cell', 'stem-cell',
            'proteína', 'protein', 'proteomic', 'proteómica',
            'arn', 'adn', 'rna', 'dna', 'mrna', 'sirna',
            'microbioma', 'microbiome', 'fármaco', 'farmaco', 'pharmaceutical',
            'vacuna', 'vaccine', 'anticuerpo', 'antibody', 'monoclonal',
            'biología molecular', 'molecular biology', 'biomolecular',
            'terapia génica', 'gene therapy', 'genetic',
            'biología sintética', 'synthetic biology',
            'cultivo celular', 'cell culture', 'cell biology',
            'bioproces', 'bioreactor', 'biomarker', 'biomarcador',
            'cell', 'cellular', 'tissue', 'tejido',
            'organoid', 'órgano', 'organ',
            'enzyme', 'enzima', 'metabol', 'fermentat',
        ],
    },
    'TECNOLOGÍA': {
        'feeds': [
            'https://es.gizmodo.com/rss',
            'https://www.theverge.com/rss/index.xml',
        ],
        'sentiment': 'mixed',
    },
    'IA / MACHINE LEARNING': {
        'feeds': [
            'https://arxiv.org/rss/cs.AI',
            'https://huggingface.co/blog/feed.xml',
        ],
        'sentiment': 'positive',  # Avances técnicos, no noticias negativas
    },
    'DESARROLLO': {
        'feeds': [
            'https://github.blog/feed/',
            'https://stackoverflow.blog/feed/',
        ],
        'sentiment': 'positive',  # Herramientas, tutoriales, lanzamientos
    },
}

# ==================== BALANCE 50/50 ====================

# Fuentes EXCLUSIVAS de noticias positivas (Good News)
# Verificado OK 2026-06-15:
#   - goodnewsnetwork.org  → 50 items/día, fresco
#   - positive.news        → 10 items, 2d
# Eliminado: solutionsjournalism.org/feed/ (404 desde 2026-06-15)
POSITIVE_NEWS_SOURCES = [
    # Good News Network - noticias positivas verificadas
    'https://www.goodnewsnetwork.org/feed/',
    # Positive News - periodismo constructivo
    'https://www.positive.news/feed/',
]

# Palabras clave para excluir (ruido, no noticias relevantes)
EXCLUDE_KEYWORDS = [
    'celebrity', 'sport', 'fußball', 'bundesliga',
    'mord', 'unfall', 'wetter', 'lotto',
    # Deportes/streaming en vivo (detectado en Gizmodo ES, 2026-06-15)
    'dónde ver', 'donde ver', 'en directo', 'en vivo',
    'premier league', 'la liga', 'champions league',
    # Entretenimiento puro
    'reality show', 'reality', 'telenovela',
]

# Palabras clave para detectar noticias POSITIVAS
POSITIVE_KEYWORDS = [
    # Logros y avances
    'descubre', 'descubren', 'descubrimiento', 'breakthrough', 'advance', 'advances',
    'innovación', 'innovation', 'innovative', 'nuevo método', 'new method',
    'mejora', 'improves', 'improvement', 'optimiza', 'optimizes',
    # Éxitos y soluciones
    'éxito', 'success', 'successful', 'logra', 'achieves', 'achievement',
    'solución', 'solution', 'resuelve', 'solves', 'resolve',
    'cura', 'cure', 'treatment', 'therapy', 'vacuna', 'vaccine',
    # Impacto positivo
    'beneficio', 'benefit', 'beneficial', 'ayuda', 'helps', 'helpful',
    'protege', 'protects', 'conserva', 'conserves', 'sostenible', 'sustainable',
    'reduce', 'reduces', 'disminuye', 'decreases', 'eficiente', 'efficient',
    # Colaboración y progreso
    'colaboración', 'collaboration', 'partnership', 'alianza', 'alliance',
    'inversión', 'investment', 'funding', 'financia', 'funds',
    'lanza', 'launches', 'lanzamiento', 'launch', 'inaugura', 'inaugurates',
    # Emociones positivas
    'esperanza', 'hope', 'hopeful', 'optimista', 'optimistic', 'inspirador', 'inspiring',
    'récord', 'record', 'histórico', 'historic', 'sin precedentes', 'unprecedented',
]

# Palabras clave para detectar noticias NEGATIVAS
NEGATIVE_KEYWORDS = [
    # Conflictos y violencia
    'guerra', 'war', 'conflicto', 'conflict', 'violencia', 'violence',
    'ataque', 'attack', 'bombardeo', 'bombing', 'tiroteo', 'shooting',
    'muerte', 'death', 'muerto', 'dead', 'víctima', 'victim', 'fatal',
    'asesinato', 'murder', 'homicidio', 'homicide', 'crimen', 'crime',
    # Desastres y accidentes
    'desastre', 'disaster', 'terremoto', 'earthquake', 'huracán', 'hurricane',
    'inundación', 'flood', 'incendio', 'fire', 'accidente', 'accident',
    'choque', 'crash', 'colisión', 'collision', 'derrumbe', 'collapse',
    # Crisis y problemas
    'crisis', 'crac', 'colapso', 'collapse', 'quiebra', 'bankruptcy',
    'escasez', 'shortage', 'hambruna', 'famine', 'pobreza', 'poverty',
    'corrupción', 'corruption', 'fraude', 'fraud', 'escándalo', 'scandal',
    # Enfermedades y salud negativa
    'epidemia', 'epidemic', 'pandemia', 'pandemic', 'brote', 'outbreak',
    'cáncer', 'cancer', 'tumor', 'enfermedad', 'disease', 'virus',
    # Política negativa
    'demanda', 'lawsuit', 'demanda judicial', 'sanción', 'sanction',
    'prohibición', 'ban', 'prohibe', 'bans', 'condena', 'condemns', 'condena', 'conviction',
    'renuncia', 'resignation', 'dimisión', 'resigns', 'despido', 'fired',
]

# ==================== FUNCIONES ====================

def get_weather():
    """Obtiene clima actual de Jülich vía Open-Meteo API."""
    try:
        result = subprocess.run(
            [
                'curl', '-s',
                'https://api.open-meteo.com/v1/forecast?'
                'latitude=50.9236&longitude=6.3628'
                '&current=temperature_2m,weather_code'
                '&daily=temperature_2m_max,temperature_2m_min'
                '&timezone=auto&forecast_days=1'
            ],
            capture_output=True, text=True, timeout=15
        )
        
        if result.returncode != 0:
            raise Exception(f"curl failed: {result.stderr}")
        
        data = json.loads(result.stdout)
        current = data.get('current', {})
        daily = data.get('daily', {})
        
        # Mapear weather_code a descripción
        weather_codes = {
            0: "despejado",
            1: "parcialmente nublado",
            2: "nublado",
            3: "muy nublado",
            45: "con niebla",
            48: "con niebla helada",
            51: "con llovizna ligera",
            53: "con llovizna moderada",
            55: "con llovizna densa",
            61: "con lluvia ligera",
            63: "con lluvia moderada",
            65: "con lluvia fuerte",
            71: "con nieve ligera",
            73: "con nieve moderada",
            75: "con nieve fuerte",
            80: "con chubascos ligeros",
            81: "con chubascos moderados",
            82: "con chubascos fuertes",
            95: "con tormenta",
            96: "con tormenta y granizo",
        }
        
        weather_code = current.get('weather_code', 0)
        condition = weather_codes.get(weather_code, "variable")
        
        return {
            'temp': round(current.get('temperature_2m', 0), 1),
            'temp_max': round(daily.get('temperature_2m_max', [0])[0], 1),
            'temp_min': round(daily.get('temperature_2m_min', [0])[0], 1),
            'condition': condition,
            'weather_code': weather_code,
        }
    
    except Exception as e:
        print(f"⚠️  Error obteniendo clima: {e}")
        return {
            'temp': 0,
            'temp_max': 0,
            'temp_min': 0,
            'condition': 'no disponible',
            'weather_code': -1,
        }

def fetch_rss_feed(url):
    """Descarga y parsea un feed RSS."""
    try:
        result = subprocess.run(
            [
                'curl', '-s', '-L',
                '-A', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                '--connect-timeout', '10',
                '--max-time', '15',
                url
            ],
            capture_output=True, text=True, timeout=20
        )
        
        if result.returncode != 0:
            return None
        
        return result.stdout
    
    except Exception as e:
        print(f"⚠️  Error fetching {url}: {e}")
        return None

def parse_rss(xml_content, limit=10):
    """Extrae items de un feed RSS."""
    items = []
    
    try:
        root = ET.fromstring(xml_content.strip())
        
        # Encontrar el channel (puede estar en root o anidado)
        channel = root.find('channel')
        if channel is None:
            channel = root
        
        for item in channel.findall('item')[:limit]:
            title_elem = item.find('title')
            link_elem = item.find('link')
            desc_elem = item.find('description')
            # Intentar varios tags de fecha (RSS 2.0, Dublin Core, Atom)
            pub_date = None
            for date_tag in ('pubDate', 'dc:date', 'date',
                             '{http://purl.org/dc/elements/1.1/}date'):
                el = item.find(date_tag)
                if el is not None and el.text:
                    pub_date = el.text.strip()
                    break

            if title_elem is not None and link_elem is not None:
                title = (title_elem.text or '').strip()
                link = (link_elem.text or '').strip()
                description = (desc_elem.text or '') if desc_elem is not None else ''

                # Limpiar HTML del description
                description = clean_html(description)

                items.append({
                    'title': title,
                    'description': description[:500],  # Truncar a 500 chars
                    'url': link,
                    'pub_date': pub_date,  # None si no hay fecha
                })
    
    except ET.ParseError as e:
        print(f"⚠️  Error parseando XML: {e}")
    except Exception as e:
        print(f"⚠️  Error procesando RSS: {e}")
    
    return items

def clean_html(text):
    """Limpia tags HTML básicos de un texto."""
    if not text:
        return ''
    
    # Reemplazar tags comunes
    replacements = [
        ('<p>', ''), ('</p>', '\n'),
        ('<br>', '\n'), ('<br/>', '\n'), ('<br />', '\n'),
        ('<strong>', ''), ('</strong>', ''),
        ('<b>', ''), ('</b>', ''),
        ('<em>', ''), ('</em>', ''),
        ('<i>', ''), ('</i>', ''),
        ('<a href="[^"]*">', ''), ('</a>', ''),
    ]
    
    import re
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    
    # Eliminar tags restantes
    text = re.sub(r'<[^>]+>', '', text)
    
    # Decodir entidades HTML
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    text = text.replace('&#39;', "'")
    
    # Limpiar espacios múltiples
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def is_fresh(item, max_age_days=MAX_ITEM_AGE_DAYS):
    """
    Devuelve True si el item es más reciente que max_age_days días,
    o si no se puede parsear su fecha (asumimos fresco: no descartar
    un item por no tener pubDate — sólo descartamos si sabemos que es viejo).
    """
    pub = item.get('pub_date')
    if not pub:
        return True  # sin fecha -> asumir fresco, no penalizar
    try:
        # RFC 822 (pubDate típico)
        d = parsedate_to_datetime(pub)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        d = d.astimezone(timezone.utc)
    except Exception:
        try:
            # ISO 8601 fallback
            d = datetime.fromisoformat(pub.replace('Z', '+00:00'))
        except Exception:
            return True  # fecha no parseable -> asumir fresco
    age_days = (datetime.now(timezone.utc) - d).days
    return age_days <= max_age_days


def matches_keywords(item, keywords):
    """Devuelve True si item.title+description contiene al menos 1 keyword (case-insensitive)."""
    if not keywords:
        return True
    text = (item.get('title', '') + ' ' + item.get('description', '')).lower()
    return any(kw.lower() in text for kw in keywords)


def is_relevant(title, description, category):
    """Filtra noticias irrelevantes o spam."""
    text = (title + ' ' + description).lower()
    
    # Excluir por palabras clave
    for keyword in EXCLUDE_KEYWORDS:
        if keyword.lower() in text:
            return False
    
    # Excluir títulos muy cortos o muy largos
    if len(title) < 10 or len(title) > 200:
        return False
    
    return True

def classify_sentiment(title, description):
    """
    Clasifica una noticia como POSITIVA, NEGATIVA o NEUTRA.
    
    Retorna: 'positive', 'negative', o 'neutral'
    """
    text = (title + ' ' + description).lower()
    
    positive_score = 0
    negative_score = 0
    
    # Contar coincidencias con palabras positivas
    for keyword in POSITIVE_KEYWORDS:
        if keyword.lower() in text:
            positive_score += 1
    
    # Contar coincidencias con palabras negativas
    for keyword in NEGATIVE_KEYWORDS:
        if keyword.lower() in text:
            negative_score += 1
    
    # Clasificar
    if positive_score > 0 and negative_score == 0:
        return 'positive'
    elif negative_score > 0 and positive_score == 0:
        return 'negative'
    elif positive_score > negative_score:
        return 'positive'
    elif negative_score > positive_score:
        return 'negative'
    else:
        return 'neutral'


def fetch_all_news():
    """
    Obtiene noticias de todas las categorías con balance 50/50.
    
    Para categorías 'mixed': 50% positivas, 50% negativas
    Para categorías 'positive': prioriza positivas (80%+)
    Para categorías 'negative': prioriza negativas (noticias de última hora)
    """
    all_news = {}
    
    for category, config in RSS_FEEDS.items():
        feeds = config.get('feeds', [])
        sentiment_preference = config.get('sentiment', 'mixed')
        
        print(f"   📌 {category} (balance: {sentiment_preference})...")
        
        all_items = []
        positive_items = []
        negative_items = []
        neutral_items = []
        
        for feed_url in feeds:
            xml_content = fetch_rss_feed(feed_url)

            if xml_content:
                items = parse_rss(xml_content, limit=15)  # Obtener más para filtrar

                # Filtro de frescura: descarta items más viejos que MAX_ITEM_AGE_DAYS
                fresh_items = [it for it in items if is_fresh(it)]
                stale_count = len(items) - len(fresh_items)
                if stale_count > 0:
                    print(f"      ⏰ {feed_url.split('/')[2]}: {stale_count}/{len(items)} items descartados (> {MAX_ITEM_AGE_DAYS}d)")

                # Filtro de keywords (sólo si la categoría las define)
                filter_kw = config.get('filter_keywords')
                if filter_kw:
                    kw_items = [it for it in fresh_items if matches_keywords(it, filter_kw)]
                    # Si ninguna matchea, fallback a los fresh sin filtrar (no dejar sección vacía)
                    items_after_kw = kw_items if kw_items else fresh_items
                    if not kw_items and fresh_items:
                        print(f"      🔬 {category}: 0/{len(fresh_items)} matchean keywords biotech, fallback")
                else:
                    items_after_kw = fresh_items

                # Clasificar cada noticia
                for item in items_after_kw:
                    if is_relevant(item['title'], item['description'], category):
                        sentiment = classify_sentiment(item['title'], item['description'])
                        item['sentiment'] = sentiment

                        if sentiment == 'positive':
                            positive_items.append(item)
                        elif sentiment == 'negative':
                            negative_items.append(item)
                        else:
                            neutral_items.append(item)
        
        # Aplicar balance según preferencia de la categoría
        if sentiment_preference == 'mixed':
            # Balance 50/50: mitad positivas, mitad negativas
            # Si no hay suficientes de un tipo, usar neutrales como comodín
            target_per_sentiment = 5  # 5 positivas + 5 negativas = 10 total
            
            selected_positive = positive_items[:target_per_sentiment]
            selected_negative = negative_items[:target_per_sentiment]
            
            # Si faltan positivas, rellenar con neutrales
            if len(selected_positive) < target_per_sentiment:
                needed = target_per_sentiment - len(selected_positive)
                selected_positive.extend(neutral_items[:needed])
            
            # Si faltan negativas, rellenar con neutrales
            if len(selected_negative) < target_per_sentiment:
                needed = target_per_sentiment - len(selected_negative)
                selected_negative.extend(neutral_items[:needed])
            
            all_items = selected_positive + selected_negative
            
        elif sentiment_preference == 'positive':
            # Priorizar positivas (80%), resto neutrales
            target_positive = int(10 * 0.8)  # 8 positivas
            selected_positive = positive_items[:target_positive]
            selected_neutral = neutral_items[:10 - len(selected_positive)]
            all_items = selected_positive + selected_neutral
            
        else:  # negative
            # Para categorías negativas (última hora), priorizar negativas
            target_negative = int(10 * 0.7)  # 7 negativas
            selected_negative = negative_items[:target_negative]
            selected_neutral = neutral_items[:10 - len(selected_negative)]
            all_items = selected_negative + selected_neutral
        
        # Limitar a 10 noticias por categoría
        all_items = all_items[:10]

        # Deduplicación final: por URL normalizada y por título normalizado
        # (algunos feeds repiten el mismo item con URL ligeramente distinta)
        seen_urls = set()
        seen_titles = set()
        unique_items = []
        for it in all_items:
            url = (it.get('url') or '').split('?')[0].split('#')[0].rstrip('/').lower()
            title_key = re.sub(r'\s+', ' ', (it.get('title') or '').lower()).strip()[:80]
            if url in seen_urls or title_key in seen_titles:
                continue
            seen_urls.add(url)
            seen_titles.add(title_key)
            unique_items.append(it)
        if len(unique_items) < len(all_items):
            print(f"      🧹 {len(all_items) - len(unique_items)} duplicados eliminados")
        all_items = unique_items

        # Contar por sentimiento para el reporte
        pos_count = sum(1 for item in all_items if item.get('sentiment') == 'positive')
        neg_count = sum(1 for item in all_items if item.get('sentiment') == 'negative')
        neu_count = sum(1 for item in all_items if item.get('sentiment') == 'neutral')
        
        all_news[category] = all_items
        print(f"      ✓ {len(all_items)} noticias (🟢{pos_count} 🔴{neg_count} ⚪{neu_count})")
    
    # Agregar noticias EXCLUSIVAS de fuentes positivas (Good News)
    # Estas se distribuyen en categorías existentes o crean una nueva
    print(f"   📰 Obteniendo buenas noticias adicionales...")
    good_news_items = []
    
    for feed_url in POSITIVE_NEWS_SOURCES:  # sólo 2 fuentes (2026-06-15)
        xml_content = fetch_rss_feed(feed_url)
        if xml_content:
            items = parse_rss(xml_content, limit=5)
            for item in items:
                item['sentiment'] = 'positive'
                good_news_items.append(item)
    
    # Si hay buenas noticias, agregarlas a la categoría más apropiada
    if good_news_items:
        # Preferentemente a CIENCIA o TECNOLOGÍA
        if 'CIENCIA' in all_news:
            all_news['CIENCIA'].extend(good_news_items[:3])
            all_news['CIENCIA'] = all_news['CIENCIA'][:10]  # Mantener límite
            print(f"      + Buenas noticias agregadas a CIENCIA")
    
    return all_news

# ==================== MAIN ====================

def main():
    parser = argparse.ArgumentParser(description='Paso 1: Fetch RSS + clima')
    parser.add_argument(
        '--date',
        type=str,
        default=datetime.now().strftime('%Y%m%d'),
        help='Fecha para el output (YYYYMMDD). Default: hoy'
    )
    parser.add_argument(
        '--output-dir',
        type=Path,
        default=BASE_DIR / 'data' / 'raw',
        help='Directorio de output'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Mostrar output detallado'
    )
    args = parser.parse_args()
    
    date_str = args.date
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    print("=" * 70)
    print(f"📰 Hermes Morning Briefing - Paso 1: Fetch RSS + Clima")
    print(f"   Fecha: {date_str}")
    print(f"   Hora: {timestamp}")
    print("=" * 70)
    
    # 1. Obtener clima
    print("\n🌤️  Obteniendo clima...")
    weather = get_weather()
    print(f"   {weather['temp']}°C, {weather['condition']}")
    print(f"   Máx: {weather['temp_max']}°C | Mín: {weather['temp_min']}°C")
    
    # 2. Obtener noticias RSS
    print("\n📰 Obteniendo noticias RSS...")
    news = fetch_all_news()
    
    total_news = sum(len(items) for items in news.values())
    print(f"\n   TOTAL: {total_news} noticias obtenidas")
    
    # 3. Guardar JSON
    output_data = {
        'date': date_str,
        'generated_at': timestamp,
        'weather': weather,
        'categories': news,
    }
    
    output_file = output_dir / f"{date_str}.json"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Guardado en: {output_file}")
    print(f"   Tamaño: {output_file.stat().st_size / 1024:.1f} KB")
    
    # 4. Validar output
    if output_file.stat().st_size < 100:
        print("\n❌ Error: Archivo output demasiado pequeño")
        return 1
    
    print("\n✅ Paso 1 completado exitosamente")
    print("=" * 70)
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
