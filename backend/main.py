import logging
import mimetypes
import os
import secrets
import threading
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .assistant import Assistant
from .catalog import Catalog
from .engine import RecommendationEngine, compare_dates
from .schemas import AlternativeInput, ChatInput, CompareInput, Draft, RequestUpdate, RunInput
from .semantic import SemanticIndex
from .storage import Store

logger = logging.getLogger('platform')


def create_app(database_url=None, dataset_path=None, semantic_provider=None):
    # Windows registry may associate .js with text/plain. Module scripts require
    # the correct MIME type, especially with X-Content-Type-Options: nosniff.
    mimetypes.add_type('text/javascript', '.js')
    mimetypes.add_type('text/css', '.css')
    mimetypes.add_type('image/svg+xml', '.svg')
    @asynccontextmanager
    async def lifespan(app):
        store = Store(database_url or config.DATABASE_URL)
        catalog = Catalog(store, dataset_path or config.DATASET_PATH)
        semantic = SemanticIndex(catalog, store, semantic_provider)
        app.state.store = store
        app.state.catalog = catalog
        app.state.engine = RecommendationEngine(catalog, semantic)
        app.state.assistant = Assistant(catalog, app.state.engine, store)
        app.state.locks = [threading.Lock() for _ in range(64)]
        yield
        store.engine.dispose()

    app = FastAPI(title='Событие — API подбора подрядчиков', version='1.0.0', lifespan=lifespan)

    @app.middleware('http')
    async def session_cookie(request: Request, call_next):
        session = request.cookies.get('event_session')
        fresh = not session or len(session) != 43
        if fresh:
            session = secrets.token_urlsafe(32)
        request.state.owner = session
        response = await call_next(request)
        if fresh:
            response.set_cookie('event_session', session, httponly=True, samesite='strict', secure=os.getenv('COOKIE_SECURE', 'false').lower() == 'true', max_age=60 * 60 * 24 * 30)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        errors = [{'field': '.'.join(str(v) for v in e['loc'][1:]), 'message': e['msg']} for e in exc.errors()]
        return JSONResponse(status_code=422, content={'detail': 'Проверьте параметры запроса', 'errors': errors})

    @app.exception_handler(httpx.HTTPError)
    async def external_error(request, exc):
        logger.warning('Embedding provider unavailable: %s', type(exc).__name__)
        return JSONResponse(status_code=503, content={'detail': 'Смысловой поиск временно недоступен. Повторите запрос. Порядок рекомендаций не заменён другим алгоритмом.'})

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logger.error('Request failed: %s', type(exc).__name__)
        return JSONResponse(status_code=500, content={'detail': 'Техническая ошибка сервиса. Параметры сохранены; повторите действие.'})

    def get_item(request, key, revision=None, complete=False):
        item = app.state.store.get_request(key, request.state.owner)
        if not item:
            raise HTTPException(404, 'Запрос не найден в вашей сессии')
        if revision is not None and item['revision'] != revision:
            raise HTTPException(409, 'Параметры уже изменились. Обновите запрос и повторите действие.')
        draft = Draft.model_validate(item['draft'])
        if complete and draft.missing():
            raise HTTPException(422, {'message': 'Заполните обязательные поля', 'missing': draft.missing()})
        return item, draft

    def lock_for(key):
        return app.state.locks[sum(key.encode()) % len(app.state.locks)]

    @app.get('/api/health')
    def health():
        return {'status': 'ok', 'catalog_version': app.state.catalog.version, 'profiles': len(app.state.catalog.profiles)}

    @app.get('/api/catalog/options')
    def options():
        return {**app.state.catalog.options(), 'assistant_mode': 'openai' if config.API_KEY else 'local', 'semantic_mode': app.state.engine.semantic.provider}

    @app.post('/api/selection-requests', status_code=201)
    def create_request(draft: Draft, request: Request):
        return app.state.store.create_request(request.state.owner, draft.model_dump(mode='json'))

    @app.get('/api/selection-requests/{key}')
    def get_request(key: str, request: Request):
        item, _ = get_item(request, key)
        return {**item, 'messages': app.state.store.messages(key), 'runs': app.state.store.runs(key, request.state.owner)}

    @app.patch('/api/selection-requests/{key}')
    def update_request(key: str, body: RequestUpdate, request: Request):
        with lock_for(key):
            get_item(request, key, body.expected_revision)
            item = app.state.store.update_request(key, request.state.owner, body.expected_revision, body.draft.model_dump(mode='json'))
            if not item:
                raise HTTPException(409, 'Запрос уже изменён')
            return item

    @app.post('/api/selection-requests/{key}/recommendations')
    def recommend(key: str, body: RunInput, request: Request):
        with lock_for(key):
            item, draft = get_item(request, key, body.expected_revision, complete=True)
            previous = app.state.store.runs(key, request.state.owner, 1)
            result = app.state.engine.recommend(draft, item['revision'])
            result['date_comparison'] = compare_dates(previous[0] if previous else None, result, app.state.catalog)
            return app.state.store.save_run(key, request.state.owner, result)

    @app.post('/api/selection-requests/{key}/alternatives')
    def alternatives(key: str, body: AlternativeInput, request: Request):
        _, draft = get_item(request, key, body.expected_revision, complete=True)
        return {'alternatives': app.state.engine.alternatives(draft, body.kind)}

    @app.get('/api/contractors/{key}')
    def profile(key: str):
        p = app.state.catalog.by_id.get(key)
        if not p:
            raise HTTPException(404, 'Профиль не найден')
        return p

    @app.post('/api/selection-requests/{key}/compare')
    def compare(key: str, body: CompareInput, request: Request):
        _, draft = get_item(request, key, complete=True)
        if len(set(body.candidate_ids)) != len(body.candidate_ids):
            raise HTTPException(422, 'Выберите разные профили')
        current = app.state.engine.recommend(draft)
        selected = [p for p in current['cards'] if p['id'] in body.candidate_ids]
        if len(selected) != len(body.candidate_ids):
            raise HTTPException(422, 'Сравнивать можно профили из текущей подборки')
        return {'cards': selected}

    @app.post('/api/chat/messages')
    def chat(body: ChatInput, request: Request):
        with lock_for(body.request_id):
            item, _ = get_item(request, body.request_id, body.expected_revision)
            return app.state.assistant.reply(item, request.state.owner, body.message.strip())

    dist = config.ROOT / 'frontend' / 'dist'
    if dist.exists():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

        @app.get('/favicon.svg', include_in_schema=False)
        def favicon():
            return FileResponse(dist / 'favicon.svg')

        @app.get('/', include_in_schema=False)
        def index():
            return FileResponse(dist / 'index.html')
    return app


app = create_app()

