import csv
import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend import config
from backend.assistant import local_plan
from backend.catalog import Catalog, read_catalog
from backend.engine import RecommendationEngine, reject_reasons
from backend.main import create_app
from backend.schemas import Draft
from backend.semantic import SemanticIndex
from backend.storage import Store


@pytest.fixture
def engine(tmp_path):
    store = Store(f'sqlite:///{(tmp_path / "engine.db").as_posix()}')
    catalog = Catalog(store)
    engine = RecommendationEngine(catalog, SemanticIndex(catalog, store, 'local'))
    yield engine
    store.engine.dispose()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'API_KEY', '')
    app = create_app(f'sqlite:///{(tmp_path / "api.db").as_posix()}', semantic_provider='local')
    with TestClient(app) as client:
        yield client


def query(**patch):
    return Draft(city='Алматы', event_date='2026-10-10', event_format='корпоратив', category='Ведущий', budget_kzt=1_000_000, **patch)


def create(client, payload=None):
    response = client.post('/api/selection-requests', json=payload if payload is not None else query().model_dump(mode='json'))
    assert response.status_code == 201, response.text
    return response.json()


def run(client, item):
    response = client.post(f'/api/selection-requests/{item["id"]}/recommendations', json={'expected_revision': item['revision']})
    assert response.status_code == 200, response.text
    return response.json()


def test_catalog_integrity(engine):
    assert len(engine.catalog.profiles) == 66
    assert sum(p['synthetic'] for p in engine.catalog.profiles) == 13
    assert sum(p['max_hours'] is None for p in engine.catalog.profiles) == 9
    assert len(engine.catalog.by_id) == 66


def test_built_javascript_has_module_mime_type(client):
    dist=config.ROOT/'frontend'/'dist'/'assets'
    if not dist.exists():
        pytest.skip('Build the frontend first')
    filename=next(dist.glob('*.js')).name
    response=client.get('/assets/'+filename)
    assert response.status_code==200
    assert response.headers['content-type'].startswith('text/javascript')


def test_baseline_determinism_and_concrete_explanations(engine):
    request = query()
    result = engine.recommend(request)
    assert result['status'] == 'MATCHED'
    assert result['base_count'] == 10
    assert result['eligible_count'] == 4
    assert [p['anon_name'] for p in result['cards'][:2]] == ['Куррапика', 'Аня Форджер']
    assert len(result['cards']) == 3
    assert len(set(p['explanation'] for p in result['cards'])) == 3
    assert result['signature'] == engine.recommend(request)['signature']
    assert [p['id'] for p in result['cards']] == [p['id'] for p in engine.recommend(request)['cards']]
    for p in result['cards']:
        assert p['evidence']['quote'].rstrip('…') in p['description']
        assert '10.10.2026' in p['explanation']
        assert 'от ' in p['explanation']


@pytest.mark.parametrize('language,duration', [(None, None), ('русский', 6), ('английский', 8), ('казахский', 10)])
def test_hard_filter_invariant_for_every_calendar_day(engine, language, duration):
    day = date(2026, 9, 23)
    while day <= date(2026, 12, 31):
        draft = Draft.model_validate({**query().model_dump(), 'event_date': day, 'language': language, 'duration_hours': duration})
        for p in engine.recommend(draft)['cards']:
            assert not reject_reasons(p, draft)
            assert p['city'] == draft.city
            assert draft.category in p['categories']
        day += timedelta(days=1)


def test_semantic_preferences_affect_order_without_relaxing_filters(engine):
    request = query(preferences='Развлечения, танцы, без долгих речей')
    result = engine.recommend(request)
    assert result['cards'][0]['anon_name'] == 'Аня Форджер'
    assert all(not reject_reasons(p, request) for p in result['cards'])


def test_dates_change_results(engine):
    first = engine.recommend(query())
    other = engine.recommend(Draft.model_validate({**query().model_dump(), 'event_date': '2026-10-17'}))
    assert first['eligible_count'] == 4
    assert other['eligible_count'] == 3
    assert {p['id'] for p in first['cards']} != {p['id'] for p in other['cards']}


def test_rare_and_not_applicable_duration(engine):
    draft = Draft(city='Алматы', event_date='2026-10-10', event_format='свадьба', category='Флорист', budget_kzt=500000, duration_hours=24)
    result = engine.recommend(draft)
    assert result['eligible_count'] == 1
    assert result['cards'][0]['anon_name'] == 'Тони Тони Чоппер'
    assert result['cards'][0]['max_hours'] is None


def test_no_match_is_different_from_absent_category(engine):
    cheap = Draft.model_validate({**query().model_dump(), 'budget_kzt': 10000})
    absent = Draft.model_validate({**query().model_dump(), 'city': 'Астана', 'category': 'Декоратор'})
    assert engine.recommend(cheap)['status'] == 'NO_MATCH'
    assert engine.recommend(absent)['status'] == 'CATEGORY_ABSENT'
    assert engine.recommend(cheap)['reasons']


def test_venues_respect_calendar(engine):
    for p in engine.catalog.profiles:
        if 'Банкетный зал' not in p['categories']:
            continue
        d = Draft(city=p['city'], category='Банкетный зал', event_format=p['event_formats'][0], event_date=p['busy_dates'][0], budget_kzt=99999999)
        assert p['id'] not in [c['id'] for c in engine.recommend(d)['cards']]


def test_alternatives_are_real_and_preserve_other_fields(engine):
    d = Draft.model_validate({**query().model_dump(), 'budget_kzt': 10000})
    alts = engine.alternatives(d)
    assert alts
    assert any(a['kind'] == 'budget' for a in alts)
    for alt in alts:
        assert len(alt['patch']) == 1
        changed = Draft.model_validate({**d.model_dump(), **alt['patch']})
        eligible = engine.eligible(changed)
        assert len(eligible) == alt['count']
        assert {p['id'] for p in eligible} == set(alt['candidate_ids'])


@pytest.mark.parametrize('patch', [{'event_date':'2027-01-01'}, {'budget_kzt':-1}, {'duration_hours':0}, {'language':'китайский'}, {'city':'Москва'}])
def test_api_validation(client, patch):
    r = client.post('/api/selection-requests', json={**query().model_dump(mode='json'), **patch})
    assert r.status_code == 422
    assert r.json()['errors']


def test_api_revisions_history_and_ownership(client):
    item = create(client)
    result = run(client, item)
    assert result['status'] == 'MATCHED'
    path = f'/api/selection-requests/{item["id"]}'
    changed = {**item['draft'], 'event_date':'2026-10-17'}
    r = client.patch(path, json={'expected_revision': 1, 'draft': changed})
    assert r.status_code == 200
    assert client.patch(path, json={'expected_revision': 1, 'draft': changed}).status_code == 409
    assert client.post(path+'/recommendations', json={'expected_revision':1}).status_code == 409
    second = run(client, r.json())
    assert second['date_comparison']['changes']
    assert len(client.get(path).json()['runs']) == 2
    client.cookies.clear()
    assert client.get(path).status_code == 404


def test_profile_comparison_validation(client):
    item = create(client)
    result = run(client, item)
    assert client.get('/api/contractors/'+result['cards'][0]['id']).status_code == 200
    path=f'/api/selection-requests/{item["id"]}/compare'
    assert client.post(path, json={'candidate_ids':[c['id'] for c in result['cards'][:2]]}).status_code == 200
    assert client.post(path, json={'candidate_ids':['HK-does-not-exist',result['cards'][0]['id']]}).status_code == 422


def test_chat_extracts_request_and_preserves_context(client):
    item = create(client, {})
    r = client.post('/api/chat/messages', json={'request_id':item['id'], 'expected_revision':1, 'message':'Нужен ведущий в Алматы на корпоратив 10 октября 2026, до миллиона, на русском, на 6 часов. Хочется интеллигентного юмора.'})
    assert r.status_code == 200, r.text
    answer=r.json()
    assert answer['result']['status']=='MATCHED'
    assert answer['request']['draft']['duration_hours']==6
    assert answer['request']['draft']['budget_kzt']==1000000
    assert answer['mode']=='local'
    second=client.post('/api/chat/messages', json={'request_id':item['id'],'expected_revision':answer['request']['revision'],'message':'А теперь на 17 октября'})
    assert second.status_code==200,second.text
    body=second.json()
    assert body['request']['draft']['event_date']=='2026-10-17'
    assert body['request']['draft']['budget_kzt']==1000000
    assert body['result']['date_comparison']
    assert len(client.get(f'/api/selection-requests/{item["id"]}').json()['messages'])==4


def test_chat_missing_fields_and_booking(client):
    item=create(client,{})
    r=client.post('/api/chat/messages',json={'request_id':item['id'],'expected_revision':1,'message':'Нужен фотограф в Алматы'})
    answer=r.json()
    assert answer['result'] is None
    assert 'бюджет' in answer['message']
    r=client.post('/api/chat/messages',json={'request_id':item['id'],'expected_revision':answer['request']['revision'],'message':'Забронируй фотографа'})
    assert 'не выполняются' in r.json()['message']


def test_chat_provider_failure_keeps_core_working(client, monkeypatch):
    import httpx
    from backend import assistant
    monkeypatch.setattr(config,'API_KEY','test-not-real')
    def fail(*args,**kwargs):
        raise httpx.ConnectError('offline')
    monkeypatch.setattr(assistant,'model_plan',fail)
    item=create(client)
    r=client.post('/api/chat/messages',json={'request_id':item['id'],'expected_revision':1,'message':'Подбери варианты'})
    assert r.status_code==200
    assert r.json()['mode']=='local'
    assert r.json()['result']['cards']
    assert 'временно недоступен' in r.json()['message']


def test_chat_asks_year_and_retains_partial_fields(client):
    item=create(client,{})
    r=client.post('/api/chat/messages',json={'request_id':item['id'],'expected_revision':1,'message':'Нужен ведущий в Алматы на корпоратив 10 октября, до миллиона'})
    answer=r.json()
    assert 'год' in answer['message']
    assert answer['request']['draft']['city']=='Алматы'
    assert answer['request']['draft']['event_date'] is None
    r=client.post('/api/chat/messages',json={'request_id':item['id'],'expected_revision':answer['request']['revision'],'message':'2026'})
    assert r.json()['request']['draft']['event_date']=='2026-10-10'


def test_decimal_budget_is_not_interpreted_as_a_date(engine):
    action,args=local_plan('Бюджет до 1.5 млн',query(),engine.catalog)
    assert action=='update_request'
    assert args['patch']['budget_kzt']==1500000
    assert 'event_date' not in args['patch']


def test_openai_tool_contract_drives_same_engine(client,monkeypatch):
    import httpx
    from backend import assistant
    real_client=httpx.Client
    captured=[]
    def transport(request):
        payload=json.loads(request.content)
        captured.append(payload)
        assert payload['tool_choice']=='required'
        assert payload['parallel_tool_calls'] is False
        assert all(t['function']['strict'] for t in payload['tools'])
        fields={name:None for name in Draft.model_fields}
        fields['event_date']='2026-10-17'
        return httpx.Response(200,json={'choices':[{'message':{'tool_calls':[{'function':{'name':'update_request','arguments':json.dumps({'fields':fields,'clear_fields':[],'question':None})}}]}}]})
    def mocked_client(*args,**kwargs):
        return real_client(transport=httpx.MockTransport(transport),**kwargs)
    monkeypatch.setattr(config,'API_KEY','test-not-real')
    monkeypatch.setattr(assistant.httpx,'Client',mocked_client)
    item=create(client)
    response=client.post('/api/chat/messages',json={'request_id':item['id'],'expected_revision':1,'message':'Перенеси на 17 октября'})
    assert response.status_code==200,response.text
    body=response.json()
    assert body['mode']=='openai'
    assert body['request']['draft']['event_date']=='2026-10-17'
    assert body['request']['draft']['budget_kzt']==1000000
    assert len(body['result']['cards'])==3
    assert len(captured)==1


def test_remote_embeddings_are_cached_and_have_stable_order(engine,monkeypatch):
    calls=[]
    def fake_encode(self,texts,timeout=5):
        calls.append(texts)
        return [[float(len(t)%7+1),1.0,2.0] for t in texts]
    monkeypatch.setattr(SemanticIndex,'encode',fake_encode)
    index=SemanticIndex(engine.catalog,engine.semantic.store,'openai')
    remote=RecommendationEngine(engine.catalog,index)
    request=query(preferences='Спокойная подача')
    first=remote.recommend(request)
    second=remote.recommend(request)
    assert len(calls)==2  # one catalog batch, one query; repeated query from DB cache
    assert [c['id'] for c in first['cards']]==[c['id'] for c in second['cards']]
    SemanticIndex(engine.catalog,engine.semantic.store,'openai')
    assert len(calls)==2  # catalog cache survives index reconstruction


def test_catalog_reports_bad_rows_without_partial_import(tmp_path):
    with config.DATASET_PATH.open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f))
    rows[1]['id']=rows[0]['id']
    rows[2]['busy_dates']='2027-01-01'
    target=tmp_path/'bad.csv'
    with target.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys());w.writeheader();w.writerows(rows)
    _, errors=read_catalog(target)
    assert len(errors)==2


def test_unknown_requirement_is_not_claimed_as_verified(engine):
    result=engine.recommend(query(preferences='Обязательно 400 гостей, парковка и кейтеринг'))
    assert result['warnings']


def test_source_fields_override_marketing_description(engine):
    kiki=next(p for p in engine.catalog.profiles if p['anon_name']=='Кики')
    assert 'конференц' in kiki['description'].lower()
    request=Draft.model_validate({**query().model_dump(), 'event_date':'2026-10-17','event_format':'конференция'})
    assert kiki['id'] not in [p['id'] for p in engine.recommend(request)['cards']]


def chat_about(client, item, result, message):
    response = client.post('/api/chat/messages', json={
        'request_id': item['id'], 'expected_revision': item['revision'],
        'message': message, 'displayed_run_id': result['run_id'] if result else None,
    })
    assert response.status_code == 200, response.text
    return response.json()


def test_form_selection_is_chat_context_without_repeating_search(client, monkeypatch):
    item = create(client)
    result = run(client, item)
    def no_search(*args, **kwargs):
        raise AssertionError('Reading a selection must not rerun recommendations')
    monkeypatch.setattr(client.app.state.engine, 'recommend', no_search)
    answer = chat_about(client, item, result, 'Второй говорит на английском?')
    assert answer['context_run_id'] == result['run_id']
    assert 'Аня Форджер' in answer['message']
    assert 'языки работы: русский' in answer['message']
    assert 'Куррапика' not in answer['message']
    assert answer['request']['draft'] == item['draft']
    assert answer['request']['revision'] == item['revision']
    assert answer['result'] is None
    assert len(client.get(f'/api/selection-requests/{item["id"]}').json()['runs']) == 1
    comparison = chat_about(client, item, result, 'Сравни первого и третьего')
    assert 'Куррапика' in comparison['message']
    assert result['cards'][2]['anon_name'] in comparison['message']
    assert 'Аня Форджер' not in comparison['message']


def test_follow_up_uses_previously_named_candidate(client):
    item = create(client)
    result = run(client, item)
    chat_about(client, item, result, 'Расскажи про второго')
    answer = chat_about(client, item, result, 'Сколько часов он работает?')
    assert 'Аня Форджер' in answer['message']
    assert 'до 6 часов' in answer['message']
    assert 'Куррапика' not in answer['message']


def test_selection_snapshot_is_not_replaced_by_newer_run(client):
    item = create(client)
    old = run(client, item)
    item = client.patch(f'/api/selection-requests/{item["id"]}', json={
        'expected_revision': item['revision'], 'draft': {**item['draft'], 'event_date': '2026-10-17'},
    }).json()
    new = run(client, item)
    answer = chat_about(client, item, old, 'Расскажи про второго')
    assert 'Аня Форджер' in answer['message']
    assert 'Фильтры изменены' in answer['message']
    assert '2026-10-10' in answer['message']
    assert answer['context_run_id'] == old['run_id']
    answer = chat_about(client, item, new, 'Расскажи про второго')
    assert 'Буллма' in answer['message']
    assert 'Аня Форджер' not in answer['message']
    assert 'Фильтры изменены' not in answer['message']


def test_stale_selection_can_be_discussed_with_incomplete_draft(client):
    item = create(client)
    result = run(client, item)
    item = client.patch(f'/api/selection-requests/{item["id"]}', json={
        'expected_revision': 1, 'draft': {**item['draft'], 'budget_kzt': None},
    }).json()
    answer = chat_about(client, item, result, 'Сколько стоит второй?')
    assert 'Аня Форджер' in answer['message']
    assert '700 000' in answer['message']
    assert 'Фильтры изменены' in answer['message']
    assert answer['request']['draft']['budget_kzt'] is None


def test_empty_selection_does_not_resurrect_previous_candidates(client):
    item = create(client)
    old = run(client, item)
    chat_about(client, item, old, 'Кто из них лучше?')
    item = client.patch(f'/api/selection-requests/{item["id"]}', json={
        'expected_revision': 1, 'draft': {**item['draft'], 'budget_kzt': 10000},
    }).json()
    empty = run(client, item)
    answer = chat_about(client, item, empty, 'Кто из них лучше?')
    assert 'ни один не проходит' in answer['message']
    assert 'Куррапика' not in answer['message']
    assert answer['context_run_id'] == empty['run_id']


def test_no_selection_requires_search_even_if_history_exists(client):
    item = create(client)
    run(client, item)
    answer = chat_about(client, item, None, 'Сравни варианты')
    assert 'Пока нет подборки' in answer['message']
    assert answer['context_run_id'] is None


def test_chat_rejects_selection_from_another_request(client):
    first = create(client)
    other = create(client)
    result = run(client, other)
    response = client.post('/api/chat/messages', json={
        'request_id': first['id'], 'expected_revision': first['revision'],
        'displayed_run_id': result['run_id'], 'message': 'Расскажи про второго',
    })
    assert response.status_code == 404
    client.cookies.clear()
    third = create(client)
    response = client.post('/api/chat/messages', json={
        'request_id': third['id'], 'expected_revision': 1,
        'displayed_run_id': result['run_id'], 'message': 'Расскажи про второго',
    })
    assert response.status_code == 404


def test_model_receives_full_selection_and_verified_evidence(client, monkeypatch):
    import httpx
    from backend import assistant
    item = create(client)
    result = run(client, item)
    candidate = result['cards'][1]
    real_client = httpx.Client
    def transport(request):
        payload = json.loads(request.content)
        context = json.loads(payload['messages'][0]['content'].split('Текущий контекст: ', 1)[1])
        selected = context['selection']
        assert selected['run_id'] == result['run_id']
        assert selected['query'] == item['draft']
        assert selected['is_stale'] is False
        assert selected['cards'][1]['position'] == 2
        for field in ('description', 'price_from_kzt', 'languages', 'max_hours', 'explanation', 'evidence', 'synthetic'):
            assert selected['cards'][1][field] == candidate[field]
        args = {'candidate_ids': [candidate['id']], 'topic': 'style', 'evidence_quotes': [{'contractor_id': candidate['id'], 'quote': candidate['evidence']['quote']}, {'contractor_id': candidate['id'], 'quote': 'ВЫДУМАННОЕ ПРЕИМУЩЕСТВО'}]}
        return httpx.Response(200, json={'choices': [{'message': {'tool_calls': [{'function': {'name': 'answer_candidates', 'arguments': json.dumps(args)}}]}}]})
    monkeypatch.setattr(config, 'API_KEY', 'test-not-real')
    monkeypatch.setattr(assistant.httpx, 'Client', lambda *args, **kwargs: real_client(transport=httpx.MockTransport(transport), **kwargs))
    answer = chat_about(client, item, result, 'Какой стиль у второго?')
    assert answer['mode'] == 'openai'
    assert candidate['anon_name'] in answer['message']
    assert candidate['evidence']['quote'] in answer['message']
    assert 'ВЫДУМАННОЕ' not in answer['message']
    assert answer['result'] is None


def test_model_cannot_answer_for_candidate_outside_selection(client, monkeypatch):
    from backend import assistant
    item = create(client)
    result = run(client, item)
    monkeypatch.setattr(config, 'API_KEY', 'test-not-real')
    monkeypatch.setattr(assistant, 'model_plan', lambda *args: ('answer_candidates', {'candidate_ids': ['HK-unknown'], 'topic': 'overview'}))
    answer = chat_about(client, item, result, 'Расскажи о кандидате')
    assert 'не входит в эту подборку' in answer['message']

