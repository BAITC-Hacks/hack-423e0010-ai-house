"""Administrative tasks, without exposing unauthenticated mutation endpoints."""
import argparse
import json
import sys
import time
from pathlib import Path
from statistics import median

from . import config
from .catalog import Catalog, read_catalog
from .engine import RecommendationEngine
from .schemas import Draft
from .semantic import SemanticIndex, evidence
from .storage import RunRecord, Store


def main():
    parser=argparse.ArgumentParser(description='Событие: проверка каталога, индексы, диагностика')
    parser.add_argument('command', choices=['validate','prepare','features','benchmark','inspect-run'])
    parser.add_argument('--dataset',type=Path,default=config.DATASET_PATH)
    parser.add_argument('--run-id')
    args=parser.parse_args()
    if args.command=='validate':
        profiles,errors=read_catalog(args.dataset)
        print(json.dumps({'valid_profiles':len(profiles),'errors':errors},ensure_ascii=False,indent=2))
        return 1 if errors else 0
    store=Store()
    if args.command=='inspect-run':
        with store.session() as session:
            run=session.get(RunRecord,args.run_id)
            if not run:
                print('Запуск не найден');return 1
            print(json.dumps(run.payload,ensure_ascii=False,indent=2))
        return 0
    catalog=Catalog(store,args.dataset)
    if args.command=='features':
        print(json.dumps([{'id':p['id'],'name':p['anon_name'],**evidence(p)} for p in catalog.profiles],ensure_ascii=False,indent=2))
        return 0
    semantic=SemanticIndex(catalog,store)
    if args.command=='prepare':
        print(json.dumps({'profiles':len(catalog.profiles),'catalog_version':catalog.version,'semantic_version':semantic.version},ensure_ascii=False,indent=2))
        return 0
    engine=RecommendationEngine(catalog,semantic)
    cases=[Draft(city='Алматы',event_date='2026-10-10',event_format='корпоратив',category='Ведущий',budget_kzt=1000000),Draft(city='Алматы',event_date='2026-10-17',event_format='корпоратив',category='Ведущий',budget_kzt=1000000),Draft(city='Алматы',event_date='2026-10-10',event_format='свадьба',category='Флорист',budget_kzt=500000),Draft(city='Алматы',event_date='2026-10-10',event_format='корпоратив',category='Ведущий',budget_kzt=10000),Draft(city='Астана',event_date='2026-10-10',event_format='свадьба',category='Декоратор',budget_kzt=3000000)]
    times=[]
    for case in cases:
        start=time.perf_counter();result=engine.recommend(case);times.append((time.perf_counter()-start)*1000)
        again=engine.recommend(case)
        assert [p['id'] for p in result['cards']]==[p['id'] for p in again['cards']]
        print(json.dumps({'query':case.model_dump(mode='json'),'status':result['status'],'eligible':result['eligible_count'],'cards':[p['anon_name'] for p in result['cards']]},ensure_ascii=False))
    print(json.dumps({'median_engine_ms':round(median(times),2),'max_engine_ms':round(max(times),2),'scope':'engine only, no HTTP or browser'}))
    return 0


if __name__=='__main__':
    sys.exit(main())

