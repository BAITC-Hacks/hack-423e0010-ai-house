import hashlib
import json
import re
import time
from collections import Counter
from datetime import date, timedelta

from .config import CALENDAR_START, CALENDAR_END
from .schemas import Draft
from .semantic import evidence

REASONS = {
    'BUSY': 'заняты на дату', 'FORMAT_UNSUPPORTED': 'не работают с этим форматом',
    'OVER_BUDGET': 'стартовая цена выше бюджета', 'LANGUAGE_UNSUPPORTED': 'нет выбранного языка',
    'DURATION_EXCEEDED': 'недостаточно часов работы',
}
RANKING_VERSION = 'rules-v1'


def money(value):
    return f'{value:,}'.replace(',', ' ') + ' ₸'


def reject_reasons(profile, draft):
    reasons = []
    if draft.event_date.isoformat() in profile['busy_dates']:
        reasons.append('BUSY')
    if draft.event_format not in profile['event_formats']:
        reasons.append('FORMAT_UNSUPPORTED')
    if profile['price_from_kzt'] > draft.budget_kzt:
        reasons.append('OVER_BUDGET')
    if draft.language and draft.language not in profile['languages']:
        reasons.append('LANGUAGE_UNSUPPORTED')
    if draft.duration_hours and profile['max_hours'] is not None and profile['max_hours'] < draft.duration_hours:
        reasons.append('DURATION_EXCEEDED')
    return reasons


def unsupported_warnings(preferences):
    warnings = []
    if re.search(r'\d+\s*(?:гост|человек|мест)|вместим|парков|кейтер|веган|халал|оборудован|обязательно', preferences.lower()):
        warnings.append('В пожеланиях есть условия, которые не представлены надёжными полями каталога. Вместимость, оснащение и специальные требования нужно уточнить у подрядчика; подбор их не подтверждает.')
    return warnings


class RecommendationEngine:
    def __init__(self, catalog, semantic):
        self.catalog, self.semantic = catalog, semantic

    def base(self, draft):
        return [p for p in self.catalog.profiles if p['city'] == draft.city and draft.category in p['categories']]

    def eligible(self, draft):
        return [p for p in self.base(draft) if not reject_reasons(p, draft)]

    def card(self, profile, draft, score):
        proof = evidence(profile, draft.preferences)
        conditions = [f'По календарю свободен {draft.event_date.strftime("%d.%m.%Y")}', f'формат — {draft.event_format}', f'цена от {money(profile["price_from_kzt"])} при бюджете {money(draft.budget_kzt)}']
        badges = ['Дата свободна', draft.event_format]
        if draft.language:
            conditions.append(f'язык — {draft.language}')
            badges.append(draft.language)
        if draft.duration_hours:
            if profile['max_hours'] is None:
                badges.append('Длительность неприменима')
            else:
                conditions.append(f'до {profile["max_hours"]:g} ч при запросе {draft.duration_hours:g} ч')
                badges.append(f'{draft.duration_hours:g} ч')
        text = '; '.join(conditions) + '. В профиле: «' + proof['quote'].rstrip('. ') + '».'
        return {**profile, 'explanation': text, 'badges': badges, 'evidence': proof, 'score': {'features': score[0], 'similarity': score[1]}}

    def recommend(self, draft, revision=1):
        started = time.perf_counter()
        if draft.missing():
            raise ValueError('Не заполнены обязательные поля')
        base = self.base(draft)
        rejected = {p['id']: reject_reasons(p, draft) for p in base}
        eligible = [p for p in base if not rejected[p['id']]]
        scores = self.semantic.scores(draft.preferences, eligible) if eligible else {}
        eligible.sort(key=lambda p: (-scores[p['id']][0], -scores[p['id']][1], p['price_from_kzt'], p['id']))
        summary = Counter(reason for reasons in rejected.values() for reason in reasons)
        status = 'CATEGORY_ABSENT' if not base else 'MATCHED' if eligible else 'NO_MATCH'
        if not base:
            message = f'В городе {draft.city} в каталоге пока нет категории «{draft.category}».'
        elif not eligible:
            message = f'В категории есть {len(base)} профилей, но ни один не проходит все условия.'
        elif len(eligible) < 3:
            message = f'Подходит {len(eligible)} из {len(base)} профилей. Показываем все подходящие варианты.'
        else:
            message = f'Подходит {len(eligible)} из {len(base)} профилей. Показываем {min(3, len(eligible))} варианта.'
        payload = draft.model_dump(mode='json')
        signature = hashlib.sha256(json.dumps({'query': payload, 'catalog': self.catalog.version, 'ranking': RANKING_VERSION, 'semantic': self.semantic.version}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]
        return {
            'status': status, 'message': message, 'cards': [self.card(p, draft, scores[p['id']]) for p in eligible[:3]],
            'eligible_count': len(eligible), 'base_count': len(base), 'query': payload, 'revision': revision,
            'reasons': [{'code': code, 'label': REASONS[code], 'count': summary[code]} for code in REASONS if summary[code]],
            'reasons_overlap': True, 'exclusions': {k: v for k, v in rejected.items() if v},
            'catalog_version': self.catalog.version, 'ranking_version': RANKING_VERSION, 'semantic_version': self.semantic.version,
            'signature': signature, 'warnings': unsupported_warnings(draft.preferences),
            'elapsed_ms': round((time.perf_counter() - started) * 1000, 2),
        }

    def alternatives(self, draft, kind='all'):
        result = []
        original = draft.model_dump(mode='json')
        if not self.base(draft):
            return []
        baseline_ids = {p['id'] for p in self.eligible(draft)}

        def add(patch, label, change_kind):
            changed = Draft.model_validate({**original, **patch})
            profiles = self.eligible(changed)
            if profiles and (change_kind == 'date' or {p['id'] for p in profiles} - baseline_ids):
                result.append({'kind': change_kind, 'label': label, 'patch': patch, 'count': len(profiles), 'candidate_ids': [p['id'] for p in profiles]})

        if kind in ('all', 'date'):
            start, end = date.fromisoformat(CALENDAR_START), date.fromisoformat(CALENDAR_END)
            dates = [start + timedelta(days=n) for n in range((end - start).days + 1)]
            dates.sort(key=lambda d: (abs((d - draft.event_date).days), d))
            found = 0
            for day in dates:
                if day == draft.event_date:
                    continue
                before = len(result)
                add({'event_date': day.isoformat()}, f'Дата {day.strftime("%d.%m.%Y")}', 'date')
                if len(result) > before:
                    found += 1
                if found == 3:
                    break
        if kind in ('all', 'budget'):
            relaxed = Draft.model_validate({**original, 'budget_kzt': 1_000_000_000})
            candidates = [p for p in self.eligible(relaxed) if p['price_from_kzt'] > draft.budget_kzt]
            if candidates:
                price = min(p['price_from_kzt'] for p in candidates)
                add({'budget_kzt': price}, f'Бюджет от {money(price)}', 'budget')
        if kind in ('all', 'language') and draft.language:
            add({'language': None}, 'Без ограничения по языку', 'language')
        if kind in ('all', 'duration') and draft.duration_hours:
            add({'duration_hours': None}, 'Без ограничения по длительности', 'duration')
        return result

    def explain_exclusion(self, contractor_id, draft):
        p = self.catalog.by_id.get(contractor_id)
        if not p:
            return 'Профиль не найден.'
        if p['city'] != draft.city or draft.category not in p['categories']:
            return f'{p["anon_name"]}: другой город или категория.'
        reasons = reject_reasons(p, draft)
        if reasons:
            return f'{p["anon_name"]}: ' + ', '.join(REASONS[r] for r in reasons) + '.'
        return f'{p["anon_name"]} проходит строгие условия; в выдаче отображаются только первые три по ранжированию.'


def compare_dates(previous, current, catalog):
    if not previous or previous['query']['event_date'] == current['query']['event_date']:
        return None
    old = {p['id']: p for p in previous['cards']}
    new = {p['id']: p for p in current['cards']}
    changes = []
    for key in old.keys() - new.keys():
        p = catalog.by_id.get(key)
        busy = p and current['query']['event_date'] in p['busy_dates']
        changes.append(f'{old[key]["anon_name"]}: ' + ('занят на новую дату' if busy else 'не вошёл в новую тройку; изменились условия или порядок'))
    for key in new.keys() - old.keys():
        p = catalog.by_id.get(key)
        was_busy = p and previous['query']['event_date'] in p['busy_dates']
        changes.append(f'{new[key]["anon_name"]}: ' + ('на прежнюю дату был занят, на новую свободен' if was_busy else 'появился в новой подборке'))
    return {'previous_date': previous['query']['event_date'], 'current_date': current['query']['event_date'], 'changes': sorted(changes) or ['Состав тройки не изменился; все показанные профили свободны на обе даты.']}

