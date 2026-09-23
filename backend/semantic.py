"""Versioned matching: deterministic local concepts or pretrained embeddings.

The local mode is deliberately labelled as a vocabulary fallback, not an LLM.
External embeddings never silently fall back and change the order of a query.
"""
import hashlib
import math
import re
from collections import Counter

import httpx

from . import config

CONCEPTS = {
    'спокойная подача': ['спокойн', 'ненавязчив', 'не напряж', 'интеллигент', 'деликатн', 'без спешки', 'без пошл', 'без пафос'],
    'юмор и импровизация': ['юмор', 'импровизац', 'квн', 'stand-up', 'стендап'],
    'активная программа': ['танц', 'динамич', 'развлечен', 'энерги', 'интерактив'],
    'индивидуальный сценарий': ['сценари', 'индивидуальн', 'персональн', 'авторск'],
    'естественные эмоции': ['естествен', 'живые кадр', 'искренн', 'эмоц', 'репортаж', 'документальн'],
    'эстетика и детали': ['эстетик', 'детал', 'красив', 'стиль', 'свет'],
    'деловые мероприятия': ['делов', 'бизнес', 'форум', 'конференц', 'презентац'],
    'традиции': ['традиц', 'национальн', 'казахск', 'этно'],
    'камерный формат': ['камерн', 'уют', 'лампов', 'небольш', 'тепл', 'тёпл'],
    'масштабные события': ['масштаб', 'крупн', '3000', '1000', 'больших'],
    'музыка и вокал': ['музык', 'вокал', 'саксофон', 'скрипк', 'кавер', 'репертуар'],
    'оформление и декор': ['оформлен', 'флорист', 'цветоч', 'декор', 'концепци'],
    'печать и персонализация': ['печать', 'печат', 'брендирован', 'логотип', 'надпис', 'сувенир'],
}
LOCAL_VERSION = 'concepts-v2'


def normalize(text):
    return ' '.join(text.lower().replace('ё', 'е').split())


def concepts(text):
    value = normalize(text)
    return {label for label, words in CONCEPTS.items() if any(normalize(w) in value for w in words)}


def tokens(text):
    return Counter(t[:6] for t in re.findall(r'[а-яa-z]{4,}', normalize(text)))


def cosine(a, b):
    den = math.sqrt(sum(v * v for v in a)) * math.sqrt(sum(v * v for v in b))
    return sum(x * y for x, y in zip(a, b)) / den if den else 0.0


def evidence(profile, preferences=''):
    description = profile['description']
    wanted = concepts(preferences)
    spans = [s.strip() for s in re.split(r'(?<=[.!?])\s+|\n+', description) if len(s.strip()) > 18]
    spans = spans or [description]
    query_tokens = set(tokens(preferences))
    indexed = list(enumerate(spans))
    # Prefer an actual specialty/style over a generic introduction even when
    # the request has no free-text preferences.
    indexed.sort(key=lambda item: (-len(concepts(item[1]) & wanted), -len(set(tokens(item[1])) & query_tokens), -len(concepts(item[1])), item[0]))
    snippet = indexed[0][1]
    if len(snippet) > 260:
        snippet = snippet[:257].rsplit(' ', 1)[0] + '…'
    return {'quote': snippet, 'field': 'description', 'matched_features': sorted(concepts(description) & wanted)}


class SemanticIndex:
    def __init__(self, catalog, store, provider=None):
        self.catalog, self.store = catalog, store
        self.provider = provider or config.EMBEDDING_PROVIDER
        if self.provider not in ('local', 'openai', 'sentence-transformers'):
            raise ValueError('Неизвестный EMBEDDING_PROVIDER')
        model = config.EMBEDDING_MODEL if self.provider == 'openai' else config.SENTENCE_MODEL
        self.version = LOCAL_VERSION if self.provider == 'local' else f'{self.provider}:{model}:{LOCAL_VERSION}'
        self.model = None
        self.vectors = {}
        if self.provider != 'local':
            missing = []
            for p in catalog.profiles:
                vector = store.vector(self.key(p['description']))
                if vector is not None:
                    self.vectors[p['id']] = vector
                else:
                    missing.append(p)
            if missing:
                vectors = self.encode([p['description'] for p in missing], timeout=45)
                for p, vector in zip(missing, vectors):
                    self.vectors[p['id']] = vector
                    store.put_vector(self.key(p['description']), vector)

    def key(self, text):
        return hashlib.sha256(f'{self.version}|{normalize(text)}'.encode()).hexdigest()

    def encode(self, texts, timeout=5):
        if self.provider == 'openai':
            if not config.API_KEY:
                raise RuntimeError('Для OpenAI embeddings требуется OPENAI_API_KEY')
            with httpx.Client(timeout=timeout) as client:
                response = client.post(f'{config.API_BASE}/embeddings', headers={'Authorization': f'Bearer {config.API_KEY}'}, json={'model': config.EMBEDDING_MODEL, 'input': texts})
                response.raise_for_status()
                data = sorted(response.json()['data'], key=lambda row: row['index'])
                if len(data) != len(texts):
                    raise ValueError('Неполный ответ embeddings')
                vectors = [row['embedding'] for row in data]
                dimensions = {len(v) for v in vectors}
                if len(dimensions) != 1 or 0 in dimensions or not all(isinstance(x, (int, float)) and math.isfinite(x) for v in vectors for x in v):
                    raise ValueError('Некорректные embedding-векторы')
                return vectors
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(config.SENTENCE_MODEL)
        return self.model.encode(texts, normalize_embeddings=True).tolist()

    def scores(self, preferences, profiles):
        if not preferences.strip():
            return {p['id']: (0, 0.0) for p in profiles}
        wanted = concepts(preferences)
        query = tokens(preferences)
        query_vector = None
        if self.provider != 'local':
            key = self.key(preferences)
            query_vector = self.store.vector(key)
            if query_vector is None:
                query_vector = self.encode([preferences])[0]
                self.store.put_vector(key, query_vector)
        scores = {}
        for profile in profiles:
            matched = len(wanted & concepts(profile['description']))
            if query_vector is not None:
                similarity = cosine(query_vector, self.vectors[profile['id']])
            else:
                document = tokens(profile['description'])
                keys = sorted(query.keys() | document.keys())
                similarity = cosine([query[k] for k in keys], [document[k] for k in keys])
            scores[profile['id']] = (matched, round(similarity, 6))
        return scores

