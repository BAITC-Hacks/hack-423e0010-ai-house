import csv
import hashlib
import json
from collections import Counter
from datetime import date

from sqlalchemy import delete

from .config import CALENDAR_START, CALENDAR_END, DATASET_PATH
from .schemas import CATEGORIES, CITIES, FORMATS, LANGUAGES
from .storage import CatalogRecord


def read_catalog(path=DATASET_PATH):
    profiles, errors = [], []
    seen = set()
    with path.open(encoding='utf-8-sig', newline='') as file:
        for number, row in enumerate(csv.DictReader(file), start=2):
            try:
                profile = dict(row)
                for key in ['id', 'anon_name', 'description', 'city']:
                    if not row.get(key, '').strip():
                        raise ValueError(f'Пустое поле {key}')
                    profile[key] = row[key].strip()
                if profile['id'] in seen:
                    raise ValueError('Дублирующийся ID')
                seen.add(profile['id'])
                for key, allowed in [('categories', CATEGORIES), ('event_formats', FORMATS), ('languages', LANGUAGES)]:
                    values = sorted(set(row[key].split('|')))
                    if not values or any(v not in allowed for v in values):
                        raise ValueError(f'Некорректное поле {key}')
                    profile[key] = values
                if profile['city'] not in CITIES:
                    raise ValueError('Неизвестный город')
                for key in ['synthetic', 'city_imputed', 'price_imputed']:
                    if row[key].lower() not in ('true', 'false'):
                        raise ValueError(f'Некорректный флаг {key}')
                    profile[key] = row[key].lower() == 'true'
                profile['price_from_kzt'] = int(row['price_from_kzt'])
                if profile['price_from_kzt'] <= 0:
                    raise ValueError('Цена должна быть положительной')
                profile['max_hours'] = float(row['max_hours']) if row['max_hours'] else None
                if profile['max_hours'] is not None and profile['max_hours'] <= 0:
                    raise ValueError('Некорректная длительность')
                profile['busy_dates'] = sorted(set(filter(None, row['busy_dates'].split('|'))))
                for d in profile['busy_dates']:
                    if not date.fromisoformat(CALENDAR_START) <= date.fromisoformat(d) <= date.fromisoformat(CALENDAR_END):
                        raise ValueError('Занятая дата вне календаря')
                if profile['max_hours'] is None and not set(profile['categories']).issubset({'Флорист', 'Декоратор', 'Подарки и сувениры'}):
                    raise ValueError('Отсутствует применимая длительность')
                profiles.append(profile)
            except (ValueError, KeyError, TypeError) as exc:
                errors.append({'row': number, 'error': str(exc)})
    if not profiles and not errors:
        errors.append({'row': 1, 'error': 'Каталог пуст'})
    return profiles, errors


class Catalog:
    def __init__(self, store, path=DATASET_PATH):
        profiles, errors = read_catalog(path)
        if errors:
            raise ValueError(f'Ошибки каталога: {errors}')
        self.profiles = sorted(profiles, key=lambda p: p['id'])
        self.by_id = {p['id']: p for p in self.profiles}
        self.version = hashlib.sha256(json.dumps(self.profiles, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
        with store.session.begin() as s:
            s.execute(delete(CatalogRecord))
            s.add_all([CatalogRecord(id=p['id'], version=self.version, payload=p) for p in self.profiles])

    def options(self):
        return {
            'cities': CITIES, 'categories': CATEGORIES, 'event_formats': FORMATS, 'languages': LANGUAGES,
            'calendar_start': CALENDAR_START, 'calendar_end': CALENDAR_END, 'catalog_version': self.version,
            'total': len(self.profiles), 'synthetic_count': sum(p['synthetic'] for p in self.profiles),
            'city_counts': dict(Counter(p['city'] for p in self.profiles)),
            'category_counts': dict(Counter(c for p in self.profiles for c in p['categories'])),
        }

