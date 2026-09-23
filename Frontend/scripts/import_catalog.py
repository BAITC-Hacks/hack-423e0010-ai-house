"""Import the anonymized hackathon CSV. Usage: python3 scripts/import_catalog.py /path/to/catalog.csv"""
import csv
import json
import re
import sys
from pathlib import Path

GROUPS = [
    ('Интеллигентный юмор', ['интеллигент', 'тонкий юмор', 'тонким юмор', 'тактич']),
    ('Спокойная подача', ['спокойн', 'ненавязчив', 'лампов']),
    ('Лаконичная программа', ['без долгих речей']),
    ('Деловые события', ['делов', 'бизнес', 'конференц']),
    ('Танцы и развлечения', ['танц', 'развлечен', 'энергич', 'интерактив']),
    ('Традиции', ['традиц', 'национальн']),
    ('Камерный формат', ['камерн', 'уютн']),
    ('Живые эмоции', ['репортаж', 'естествен', 'эмоци']),
    ('Оформление события', ['цветоч', 'флорист', 'оформлен', 'декор']),
    ('Музыкальная программа', ['музык', 'вокал', 'инструмент']),
]
PALETTES = ['sage', 'clay', 'blue', 'rose', 'sand', 'forest']

def features(description):
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', description) if s.strip()]
    found = []
    for label, keywords in GROUPS:
        sentence = next((s for s in sentences if any(k in s.lower() for k in keywords)), None)
        if sentence:
            # Exact substrings of the source only. No inferred services or capabilities.
            quote = sentence.rstrip('.!?')
            if len(quote) > 240:
                keyword_pos = min((quote.lower().find(k) for k in keywords if k in quote.lower()), default=0)
                start = max(0, keyword_pos - 50)
                if start: start = quote.find(' ', start) + 1
                end = quote.rfind(' ', start, start + 235)
                quote = quote[start:end if end > start else start + 235]
            found.append({'label': label, 'quote': quote, 'keywords': keywords})
    if not found:
        quote = (sentences[0] if sentences else description).rstrip('.!?')
        if len(quote) > 220: quote = quote[:220].rsplit(' ', 1)[0]
        found.append({'label': 'Из описания профиля', 'quote': quote, 'keywords': []})
    return found

source = Path(sys.argv[1])
with source.open(encoding='utf-8-sig', newline='') as file:
    rows = list(csv.DictReader(file))
profiles = []
for i, row in enumerate(rows):
    categories = row['categories'].split('|')
    feats = features(row['description'])
    profiles.append({
        'id': row['id'], 'name': row['anon_name'], 'category': categories[0], 'categories': categories,
        'city': row['city'], 'price_from_kzt': int(row['price_from_kzt']),
        'event_formats': row['event_formats'].split('|'), 'languages': row['languages'].split('|'),
        'max_hours': int(row['max_hours']) if row['max_hours'] else None,
        'description': row['description'], 'specialty': feats[0]['label'], 'features': feats,
        'origin': 'synthetic' if row['synthetic'].lower() == 'true' else 'catalog',
        'price_is_estimated': row['price_imputed'].lower() == 'true',
        'city_is_estimated': row['city_imputed'].lower() == 'true',
        'artwork': PALETTES[i % len(PALETTES)], 'busy_dates': row['busy_dates'].split('|') if row['busy_dates'] else [],
    })
assert len({p['id'] for p in profiles}) == len(profiles), 'Duplicate IDs'
assert all(f['quote'] in p['description'] for p in profiles for f in p['features']), 'Unverifiable quote'
output = Path(__file__).resolve().parents[1] / 'src/data/catalog.json'
output.write_text(json.dumps(profiles, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'Imported {len(profiles)} profiles into {output.name}')
