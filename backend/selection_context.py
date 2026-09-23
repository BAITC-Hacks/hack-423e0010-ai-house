"""Read-only questions about the exact recommendation snapshot shown in the UI."""
import re

from .engine import money

TOPICS = ['overview', 'price', 'language', 'duration', 'format', 'availability', 'style', 'recommendation', 'comparison', 'unknown']


def selection_context(run, draft):
    if run is None:
        return None
    fields = ('id', 'anon_name', 'categories', 'city', 'price_from_kzt', 'max_hours', 'languages', 'event_formats', 'description', 'explanation', 'evidence', 'score', 'synthetic', 'city_imputed', 'price_imputed')
    return {
        'run_id': run['run_id'], 'query': run['query'], 'status': run['status'],
        'message': run['message'], 'is_stale': run['query'] != draft.model_dump(mode='json'),
        'catalog_version': run['catalog_version'], 'eligible_count': run['eligible_count'],
        'reasons': run['reasons'], 'warnings': run.get('warnings', []),
        'cards': [{'position': position, **{k: p[k] for k in fields}, 'available_on': run['query']['event_date']} for position, p in enumerate(run['cards'], 1)],
    }


def local_selection_plan(message, run, history=None):
    """Recognize questions before the draft parser mistakes them for new filters."""
    text = message.lower().replace('ё', 'е')
    # Explicit search/changes retain the existing draft-editing path.
    if re.search(r'\b(?:измени|поменяй|перенеси|ищи|подбери|найди|укажи|добавь|убери|выбери|давай|теперь|нужен|нужна|нужны|хочется)\b|бюджет\s*(?:до|:)', text):
        return None
    cards = (run or {}).get('cards', [])
    ids = [p['id'] for p in cards if p['anon_name'].lower().replace('ё', 'е') in text or p['id'].lower() in text]
    positions = []
    for pattern, index in [(r'\bперв\w*', 0), (r'\bвтор\w*', 1), (r'\bтрет\w*', 2), (r'\bчетверт\w*', 3)]:
        if re.search(pattern, text):
            positions.append(index)
    positions.extend(int(n) - 1 for n in re.findall(r'(?:кандидат\w*|вариант\w*|номер|№)\s*([1-9])\b', text))
    question = re.search(r'кто из|кто (?:лучше|дешевле|подходит)|кого (?:выбрать|посовету)|расскажи|подробнее|сравни|чем.*отлич|почему|какие языки|на каких языках|сколько.*стоит|какая цена|что.*уме[ею]т|подборк|кандидат|вариант', text)
    question = question or re.search(r'\b(?:цена|язык|часов|длительность)\s*\??$', text) or re.search(r'\b(?:он|она|они|них|него|неё|ее|его)\b', text)
    if not (ids or positions or question):
        return None
    if positions and any(n >= len(cards) for n in positions):
        return 'clarify', {'question': f'В обсуждаемой подборке {len(cards)} кандидатов. Укажите имя или номер показанной карточки.' if cards else 'Сначала выполните подбор через фильтры, чтобы я мог рассказать о показанных кандидатах.'}
    for n in positions:
        if cards[n]['id'] not in ids:
            ids.append(cards[n]['id'])
    # A follow-up such as "а на каких языках он работает?" uses the last
    # unambiguous named answer, never an arbitrary ordinal from old history.
    if not ids and re.search(r'\b(?:он|она|него|нее|его|ее)\b', text):
        for entry in reversed(history or []):
            if entry['role'] != 'assistant':
                continue
            found = [p['id'] for p in cards if p['anon_name'] in entry['content']]
            if len(found) == 1:
                ids = found
            break
        if not ids:
            return 'clarify', {'question': 'О каком кандидате вы спрашиваете? Укажите имя или номер карточки.'}
    topic = 'overview'
    if re.search(r'отзыв|рейтинг|контакт|телефон|опыт.*лет|вместим|гостей|оборудован|скидк', text):
        topic = 'unknown'
    elif re.search(r'сравни|чем.*отлич', text):
        topic = 'comparison'
    elif re.search(r'лучше|кого.*выбрать|посовету|больше подход', text):
        topic = 'recommendation'
    elif re.search(r'цен|стоим|стоит|дешев|дороже|бюджет', text):
        topic = 'price'
    elif re.search(r'язык|русск|казахск|английск', text):
        topic = 'language'
    elif re.search(r'час|длитель', text):
        topic = 'duration'
    elif re.search(r'свобод|занят|доступен|дат', text):
        topic = 'availability'
    elif re.search(r'формат|свадьб|корпоратив|конференц', text):
        topic = 'format'
    elif re.search(r'стиль|юмор|конкурс|спокой|танц', text):
        topic = 'style'
    return 'answer_candidates', {'candidate_ids': ids, 'topic': topic, 'evidence_quotes': []}


def answer_candidates(run, draft, args):
    """All names, numbers and quotations are taken from the stored snapshot."""
    if run is None:
        return 'Пока нет подборки для обсуждения. Нажмите «Найти совпадения» в форме — после этого я увижу кандидатов и смогу ответить по каждому.'
    prefix = ''
    if run['query'] != draft.model_dump(mode='json'):
        prefix = 'Фильтры изменены. Отвечаю по предыдущей подборке на ' + run['query']['event_date'] + '; для новых условий нажмите «Найти совпадения».\n\n'
    if not run['cards']:
        text = run['message']
        if run['reasons']:
            text += '\nПричины (могут пересекаться): ' + '; '.join(f'{r["label"]}: {r["count"]}' for r in run['reasons']) + '.'
        return prefix + text + '\nМогу проверить альтернативные даты и условия.'
    requested = args.get('candidate_ids', [])
    if not isinstance(requested, list) or any(key not in {p['id'] for p in run['cards']} for key in requested):
        return prefix + 'Указанный кандидат не входит в эту подборку. Уточните имя или номер одной из показанных карточек.'
    cards = [p for p in run['cards'] if not requested or p['id'] in requested]
    topic = args.get('topic', 'overview')
    lines = []
    if topic == 'recommendation':
        first = cards[0]
        explanation = 'Учитываем совпадения с пожеланиями, затем стартовую цену.' if run['query'].get('preferences') else 'Пожелания не заданы, поэтому порядок определяется стартовой ценой и ID при равенстве.'
        return prefix + f'По правилам подбора из этих вариантов первым идёт {first["anon_name"]}. {explanation}\n\n{first["explanation"]}\n\nЭто соответствие условиям, а не рейтинг качества услуг. Отзывов и проверенных оценок качества в каталоге нет.'
    if topic == 'unknown' or topic not in TOPICS:
        return prefix + 'По этой подборке не могу надёжно подтвердить запрошенную деталь. В каталоге есть описания, стартовые цены, языки, форматы и длительность; отсутствующие сведения нужно уточнить у подрядчика.'
    quotes = {}
    for item in args.get('evidence_quotes', []):
        if not isinstance(item, dict):
            continue
        card = next((p for p in cards if p['id'] == item.get('contractor_id')), None)
        quote = item.get('quote', '')
        if card and isinstance(quote, str) and 12 <= len(quote) <= 700 and quote in card['description']:
            quotes[card['id']] = quote
    if topic == 'price':
        cards = sorted(cards, key=lambda p: (p['price_from_kzt'], p['id']))
    for p in cards:
        label = f'{next(n for n, c in enumerate(run["cards"], 1) if c["id"] == p["id"])}. {p["anon_name"]}'
        if topic == 'price':
            info = f'от {money(p["price_from_kzt"])} за мероприятие'
            if p['price_imputed']:
                info += ' (цена проставлена при подготовке датасета)'
        elif topic == 'language':
            info = 'языки работы: ' + ', '.join(p['languages'])
        elif topic == 'duration':
            info = f'до {p["max_hours"]:g} часов на площадке' if p['max_hours'] is not None else 'ограничение по часам присутствия неприменимо'
        elif topic == 'format':
            info = 'форматы: ' + ', '.join(p['event_formats'])
        elif topic == 'availability':
            info = f'по календарю свободен на {run["query"]["event_date"]}; для другой даты нужен новый подбор'
        elif topic == 'style':
            info = 'в описании: «' + quotes.get(p['id'], p['evidence']['quote']) + '»'
        elif topic == 'comparison':
            duration = f'до {p["max_hours"]:g} ч' if p['max_hours'] is not None else 'длительность неприменима'
            info = f'от {money(p["price_from_kzt"])}, языки: {", ".join(p["languages"])}; {duration}. В профиле: «{quotes.get(p["id"], p["evidence"]["quote"])}»'
        else:
            info = p['explanation']
            if p['id'] in quotes:
                info += '\nИз описания: «' + quotes[p['id']] + '»'
        lines.append(f'{label} — {info}.')
    text = '\n\n'.join(lines)
    if topic in ('price', 'comparison'):
        text += '\n\nЭто стартовые цены; окончательная стоимость требует уточнения.'
    return prefix + text

