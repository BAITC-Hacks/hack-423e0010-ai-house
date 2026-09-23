import {useEffect, useRef, useState, type FormEvent, type ReactNode} from 'react';
import {ArrowRight, CalendarDays, Check, CheckCheck, ChevronDown, Compass, ExternalLink, GitCompareArrows, History, Info, Layers3, MapPin, MessageCircle, Plus, RotateCcw, Search, ShieldCheck, SlidersHorizontal, Sparkles, WandSparkles, X} from 'lucide-react';
import {api, ApiError} from './api';
import ChatSelectionContext from './ChatSelectionContext';
import type {Alternative, Card, Draft, Message, Options, Profile, Result, SavedRequest} from './types';

const DEFAULT: Draft = {city:'Алматы', event_date:'2026-10-10', event_format:'корпоратив', category:'Ведущий', budget_kzt:1000000, duration_hours:null, language:null, preferences:''};
const BLANK: Draft = {city:null,event_date:null,event_format:null,category:null,budget_kzt:null,duration_hours:null,language:null,preferences:''};
const formatMoney = (n: number) => new Intl.NumberFormat('ru-RU').format(n) + ' ₸';
const formatDate = (d: string | null) => d ? new Date(d + 'T12:00:00').toLocaleDateString('ru-RU', {day:'numeric',month:'long'}) : 'Дата не указана';
const initials = (name: string) => name.split(' ').slice(0,2).map(s=>s[0]).join('');
const statusLabel = (s: Result['status']) => s === 'MATCHED' ? 'Подобрали' : s === 'CATEGORY_ABSENT' ? 'Категории нет' : 'Нет совпадений';

function Modal({title, onClose, children, wide=false}: {title:string; onClose:()=>void; children:ReactNode; wide?:boolean}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(()=>{
    const previous = document.activeElement as HTMLElement;
    ref.current?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow='hidden';
    const handler=(e:KeyboardEvent)=>{
      if(e.key==='Escape') onClose();
      if(e.key==='Tab') {
        const nodes=ref.current?.querySelectorAll<HTMLElement>('button:not(:disabled),a[href],input,select,textarea,[tabindex="0"]');
        if(!nodes?.length) return;
        const first=nodes[0],last=nodes[nodes.length-1];
        if(e.shiftKey && (document.activeElement===first || document.activeElement===ref.current)) {e.preventDefault();last.focus();}
        else if(!e.shiftKey && document.activeElement===last) {e.preventDefault();first.focus();}
      }
    };
    document.addEventListener('keydown',handler);
    return()=>{document.body.style.overflow=overflow;document.removeEventListener('keydown',handler);previous?.focus();};
  },[onClose]);
  return <div className="modal-backdrop" onMouseDown={e=>{if(e.target===e.currentTarget)onClose();}}><div ref={ref} tabIndex={-1} className={`modal ${wide?'wide':''}`} role="dialog" aria-modal="true" aria-label={title}><div className="modal-title"><h2>{title}</h2><button className="icon-button" onClick={onClose} aria-label="Закрыть окно"><X size={20}/></button></div>{children}</div></div>;
}

function Provenance({profile}: {profile:Profile}) {
  return <div className="provenance"><span className={profile.synthetic?'tag amber':'tag subtle'} title={profile.synthetic?'Профиль полностью создан при подготовке датасета':'Анонимизированный профиль из исходного каталога'}>{profile.synthetic?'Синтетический профиль':'Исходный профиль'}</span>{profile.price_imputed&&<span className="tag amber" title="Цена проставлена при подготовке датасета">Цена из датасета*</span>}{profile.city_imputed&&<span className="tag amber" title="Город проставлен при подготовке датасета">Город из датасета*</span>}</div>;
}

function ContractorCard({card,index,selected,onSelect,onOpen}: {card:Card;index:number;selected:boolean;onSelect:()=>void;onOpen:()=>void}) {
  return <article className="contractor-card" data-testid="contractor-card"><div className="card-top"><div className={`avatar avatar-${index}`}>{initials(card.anon_name)}<span>{index+1}</span></div><div className="identity"><div className="eyebrow">{card.categories.join(' · ')}</div><button className="name-button" onClick={onOpen}>{card.anon_name}<ExternalLink size={13}/></button><div className="meta"><MapPin size={13}/>{card.city}<span>·</span>{card.max_hours===null?'Без почасового лимита':`до ${card.max_hours} часов`}</div></div><div className="card-price"><small>за мероприятие</small><strong>от {formatMoney(card.price_from_kzt)}</strong></div></div><div className="match-badges">{card.badges.map(b=><span key={b}><Check size={12}/>{b}</span>)}</div><div className="explanation"><Sparkles size={16}/><div><strong>Почему подходит</strong><p>{card.explanation}</p></div></div><details className="evidence"><summary>На чём основан выбор <ChevronDown size={14}/></summary><blockquote>«{card.evidence.quote}»</blockquote><p>Источник: описание профиля {card.id}. {card.evidence.matched_features.length>0?`Совпадения с пожеланиями: ${card.evidence.matched_features.join(', ')}.`:'Проверены условия формы; оценка качества услуг в каталоге отсутствует.'}</p><p>Стартовая цена проходит бюджет. Окончательная стоимость требует уточнения.</p></details><div className="card-bottom"><Provenance profile={card}/><label className="compare-check"><input type="checkbox" checked={selected} onChange={onSelect}/><GitCompareArrows size={14}/>Сравнить</label></div></article>;
}

export default function App() {
  const [options,setOptions]=useState<Options|null>(null);
  const [saved,setSaved]=useState<SavedRequest|null>(null);
  const [draft,setDraft]=useState<Draft>(DEFAULT);
  const [result,setResult]=useState<Result|null>(null);
  const [runs,setRuns]=useState<Result[]>([]);
  const [messages,setMessages]=useState<Message[]>([]);
  const [chatText,setChatText]=useState('');
  const [chatOpen,setChatOpen]=useState(()=>window.matchMedia('(min-width: 1051px)').matches);
  const [chatMode,setChatMode]=useState('local');
  const [pending,setPending]=useState('');
  const [error,setError]=useState('');
  const [booting,setBooting]=useState(true);
  const [tab,setTab]=useState<'selection'|'history'>('selection');
  const [selected,setSelected]=useState<string[]>([]);
  const [alternatives,setAlternatives]=useState<Alternative[]>([]);
  const [alternativesLoaded,setAlternativesLoaded]=useState(false);
  const [profile,setProfile]=useState<Profile|null>(null);
  const [comparison,setComparison]=useState<Card[]|null>(null);
  const [showHelp,setShowHelp]=useState(false);
  const chatEnd=useRef<HTMLDivElement>(null);
  const resultRef=useRef<HTMLDivElement>(null);
  const stale=!!result && JSON.stringify(result.query)!==JSON.stringify(draft);
  const busy=!!pending || booting;

  useEffect(()=>{
    let active=true;
    async function boot(){
      try {
        const opts=await api<Options>('/catalog/options');
        if(!active)return;
        setOptions(opts);setChatMode(opts.assistant_mode);
        const key=localStorage.getItem('event-request');
        let item:SavedRequest & {runs?:Result[];messages?:Message[]};
        if(key){try{item=await api(`/selection-requests/${key}`);}catch(e){if(e instanceof ApiError && e.status===404)item=await api('/selection-requests',DEFAULT);else throw e;}}
        else item=await api('/selection-requests',DEFAULT);
        if(!active)return;
        setSaved(item);setDraft(item.draft);setMessages(item.messages||[]);setRuns(item.runs||[]);setResult(item.runs?.[0]||null);localStorage.setItem('event-request',item.id);
      }catch(e){if(active)setError((e as Error).message);}finally{if(active)setBooting(false);}
    }
    void boot();return()=>{active=false;};
  },[]);
  useEffect(()=>{chatEnd.current?.scrollIntoView({behavior:'smooth',block:'nearest'});},[messages,pending]);

  function update<K extends keyof Draft>(key:K,value:Draft[K]){setDraft(d=>({...d,[key]:value}));setAlternatives([]);setAlternativesLoaded(false);setSelected([]);}
  async function persist(value:Draft){
    if(!saved)throw new Error('Сервис ещё не готов. Обновите страницу.');
    if(JSON.stringify(saved.draft)===JSON.stringify(value))return saved;
    const item=await api<SavedRequest>(`/selection-requests/${saved.id}`,{expected_revision:saved.revision,draft:value},'PATCH');setSaved(item);return item;
  }
  function acceptResult(data:Result){setResult(data);setRuns(r=>[data,...r.filter(x=>x.run_id!==data.run_id)].slice(0,20));setSelected([]);setAlternatives([]);setAlternativesLoaded(false);}
  async function search(value=draft){
    if(busy)return;
    setPending('search');setError('');setTab('selection');setDraft(value);
    try{const item=await persist(value);const data=await api<Result>(`/selection-requests/${item.id}/recommendations`,{expected_revision:item.revision});acceptResult(data);}catch(e){setError((e as Error).message);}finally{setPending('');}
  }
  async function ask(message=chatText){
    if(busy||!message.trim())return;
    setPending('chat');setError('');setChatText('');setChatOpen(true);
    const text=message.trim();
    setMessages(m=>[...m,{role:'user',content:text}]);
    try{
      const item=await persist(draft);
      const answer=await api<{message:string;mode:string;request:SavedRequest;result:Result|null;alternatives:Alternative[]}>(`/chat/messages`,{request_id:item.id,expected_revision:item.revision,message:text,displayed_run_id:result?.run_id??null});
      setSaved(answer.request);setDraft(answer.request.draft);setChatMode(answer.mode);setMessages(m=>[...m,{role:'assistant',content:answer.message}]);
      if(JSON.stringify(answer.request.draft)!==JSON.stringify(draft)){setSelected([]);setAlternatives([]);setAlternativesLoaded(false);}
      if(answer.result){acceptResult(answer.result);setTab('selection');}
      if(answer.alternatives.length){setAlternatives(answer.alternatives);setAlternativesLoaded(true);}
    }catch(e){setError((e as Error).message);setMessages(m=>[...m,{role:'assistant',content:'Не удалось выполнить запрос. Параметры сохранены; повторите сообщение или используйте форму.'}]);setChatText(text);}finally{setPending('');}
  }
  async function getAlternatives(){
    if(!saved||busy)return;setPending('alternatives');setError('');
    try{const item=await persist(draft);const data=await api<{alternatives:Alternative[]}>(`/selection-requests/${item.id}/alternatives`,{expected_revision:item.revision,kind:'all'});setAlternatives(data.alternatives);setAlternativesLoaded(true);}catch(e){setError((e as Error).message);}finally{setPending('');}
  }
  async function openProfile(id:string){try{setProfile(await api<Profile>(`/contractors/${id}`));}catch(e){setError((e as Error).message);}}
  async function compare(){if(!saved||busy)return;setPending('compare');try{const data=await api<{cards:Card[]}>(`/selection-requests/${saved.id}/compare`,{candidate_ids:selected});setComparison(data.cards);}catch(e){setError((e as Error).message);}finally{setPending('');}}
  async function newRequest(){if(busy)return;setPending('new');setError('');try{const item=await api<SavedRequest>('/selection-requests',BLANK);setSaved(item);setDraft(item.draft);setResult(null);setMessages([]);setRuns([]);setAlternatives([]);setAlternativesLoaded(false);setSelected([]);localStorage.setItem('event-request',item.id);setTab('selection');}catch(e){setError((e as Error).message);}finally{setPending('');}}
  const formSubmit=(e:FormEvent)=>{e.preventDefault();void search();};

  return <div className="app-shell">
    <header className="topbar"><a className="brand" href="/" aria-label="Событие — главная"><span className="brand-mark"><Sparkles size={24}/></span>событие<span className="brand-dot">.</span></a><nav aria-label="Основная навигация"><button className={tab==='selection'?'nav-item active':'nav-item'} onClick={()=>setTab('selection')}><Compass size={16}/>Подбор подрядчиков</button><button className={tab==='history'?'nav-item active':'nav-item'} onClick={()=>setTab('history')}><History size={16}/>История<span className="count">{runs.length}</span></button></nav><div className="topbar-end"><button className="help-button" onClick={()=>setShowHelp(true)}><Info size={16}/>Как это работает</button><span className="demo-tag">DEMO 2026</span><span className="user-avatar">Вы</span></div></header>
    <main className="page"><div className="page-intro"><div><div className="breadcrumb">Платформа мероприятий <span>/</span> {tab==='selection'?'Умный подбор':'История подбора'}</div><h1>{tab==='selection'?<>Ваше событие.<br className="mobile-break"/> Ваши люди<span>.</span></>:'История ваших подборок.'}</h1><p>Меньше поисков. Больше совпадений. До трёх вариантов, которые подходят именно вам.</p></div><div className="intro-note"><span className="stacked-avatars"><i>АК</i><i>МР</i><i><Sparkles size={16}/></i></span><span><strong>{options?.total||66} профилей</strong><small>собраны в одном месте</small></span></div></div>
      <div className="steps"><span className="step current"><b>1</b>Расскажите о событии</span><i/><span className={`step ${result&&!stale?'current':''}`}><b>2</b>Изучите совпадения</span><i/><span className={`step ${selected.length>=2?'current':''}`}><b>3</b>Сравните и выберите</span><span className="steps-note"><ShieldCheck size={14}/>Только проверяемые условия</span></div>
      {error&&<div className="error-banner" role="alert"><Info size={18}/><span>{error}</span>{!saved?<button onClick={()=>location.reload()}>Повторить</button>:null}<button className="icon-button" aria-label="Скрыть ошибку" onClick={()=>setError('')}><X size={16}/></button></div>}
      <div className={`workspace ${chatOpen?'':'chat-hidden'}`}>
        <aside className="filters"><div className="panel-heading"><span><SlidersHorizontal size={17}/>Ваше мероприятие</span><button className="icon-button" disabled={busy} onClick={()=>{setDraft(DEFAULT);setSelected([]);setAlternatives([]);setAlternativesLoaded(false);}} aria-label="Восстановить параметры примера" title="Восстановить пример"><RotateCcw size={15}/></button></div><form onSubmit={formSubmit}><fieldset disabled={busy}><div className="form-body"><label>Город <span>*</span><div className="input-wrap"><MapPin size={16}/><select aria-label="Город" required value={draft.city||''} onChange={e=>update('city',e.target.value||null)}><option value="">Выберите город</option>{options?.cities.map(c=><option key={c}>{c}</option>)}</select></div></label><label>Дата мероприятия <span>*</span><input aria-label="Дата мероприятия" type="date" required min={options?.calendar_start||'2026-09-23'} max={options?.calendar_end||'2026-12-31'} value={draft.event_date||''} onChange={e=>update('event_date',e.target.value||null)}/><small>Календарь: 23 сен — 31 дек 2026</small></label><label>Тип мероприятия <span>*</span><select aria-label="Тип мероприятия" required value={draft.event_format||''} onChange={e=>update('event_format',e.target.value||null)}><option value="">Выберите формат</option>{options?.event_formats.map(c=><option key={c} value={c}>{c[0].toUpperCase()+c.slice(1)}</option>)}</select></label><label>Кого ищем? <span>*</span><select aria-label="Категория подрядчика" required value={draft.category||''} onChange={e=>update('category',e.target.value||null)}><option value="">Выберите категорию</option>{options?.categories.map(c=><option key={c}>{c}</option>)}</select></label><label>Бюджет на подрядчика <span>*</span><div className="money-input"><input aria-label="Бюджет на подрядчика" type="number" min="1" max="1000000000" step="1" required value={draft.budget_kzt??''} onChange={e=>update('budget_kzt',e.target.value?Number(e.target.value):null)}/><span>₸</span></div><small>Сравниваем со стартовой ценой</small></label><div className="additional-title">Детали <span>необязательно</span></div><div className="two-fields"><label>Длительность<div className="money-input"><input aria-label="Длительность" type="number" min="0.5" max="100" step="0.5" placeholder="Любая" value={draft.duration_hours??''} onChange={e=>update('duration_hours',e.target.value?Number(e.target.value):null)}/><span>ч</span></div></label><label>Язык<select aria-label="Язык" value={draft.language||''} onChange={e=>update('language',e.target.value||null)}><option value="">Любой</option>{options?.languages.map(c=><option key={c}>{c}</option>)}</select></label></div><label>Что для вас важно?<textarea aria-label="Пожелания" rows={3} maxLength={2000} placeholder="Например, спокойная подача и интеллигентный юмор…" value={draft.preferences} onChange={e=>update('preferences',e.target.value)}/></label><button type="button" className="preference-chip" onClick={()=>update('preferences','Спокойная подача, интеллигентный юмор')}><Plus size={12}/>Спокойная атмосфера</button></div><div className="form-footer"><button className="primary search-button" type="submit"><Sparkles size={17}/>{pending==='search'?'Подбираем…':'Найти совпадения'}<ArrowRight size={17}/></button><p>До 3 вариантов. С объяснением каждого.</p></div></fieldset></form></aside>
        <section className="results" ref={resultRef} aria-live="polite" aria-busy={pending==='search'}>
          {tab==='history'?<><div className="results-heading"><div><div className="eyebrow">ВАШИ ЗАПРОСЫ</div><h2>Сохранённые подборки <span>{runs.length}</span></h2></div><History size={20}/></div>{runs.length===0?<div className="empty-state"><History size={35}/><h3>История начинается с события</h3><p>Результаты появятся здесь после первого подбора.</p><button className="secondary" onClick={()=>setTab('selection')}>Перейти к подбору</button></div>:<div className="history-list">{runs.map(r=><button key={r.run_id} className="history-row" disabled={busy} onClick={()=>void search(r.query)}><div className="history-icon"><CalendarDays size={21}/></div><div><strong>{r.query.category} · {r.query.city}</strong><p>{formatDate(r.query.event_date)} · {r.query.event_format} · до {formatMoney(r.query.budget_kzt!)}</p><small>{statusLabel(r.status)} · {r.cards.length} в подборке</small></div><ArrowRight size={17}/></button>)}</div>}</>:<>
            <div className="results-heading"><div><div className="eyebrow">ПОДБОР С ПОНИМАНИЕМ</div><h2>{result&&!stale?'Ваши совпадения':'Найдём тех самых'}{result&&!stale&&<span>{result.cards.length}</span>}</h2></div>{result&&!stale&&<span className={`status-pill ${result.status==='MATCHED'?'success':''}`}><span/>{statusLabel(result.status)}</span>}</div>
            {booting?<div className="empty-state"><span className="loader"/><h3>Загружаем каталог</h3></div>:pending==='search'?<div className="loading-cards">{[0,1,2].map(i=><div className="skeleton-card" key={i}><div/><span/><span/><span/></div>)}<p>Проверяем дату, условия и пожелания…</p></div>:(!result||stale)?<div className="welcome"><div className="welcome-illustration"><span className="orbit orbit-one"/><span className="orbit orbit-two"/><div className="illustration-card back"><CalendarDays size={24}/><span>ваше событие</span></div><div className="illustration-card front"><Sparkles size={30}/><span>идеальное совпадение</span><div><i/><i/><i/></div></div><span className="floating-star">✦</span><span className="floating-dot"/></div><span className="tag green">{stale?'Параметры изменились':'От идеи — к подходящим людям'}</span><h3>{stale?'Давайте обновим подборку':'Хорошее событие начинается\nс правильных людей'}</h3><p>{stale?'Нажмите «Найти совпадения», чтобы проверить новые условия. Предыдущий результат сохранён в истории.':'Расскажите о мероприятии в форме слева или напишите помощнику. Мы проверим условия и объясним каждый выбор.'}</p><div className="welcome-points"><span><CheckCheck size={16}/>Учитываем занятость</span><span><Layers3 size={16}/>Сравниваем условия</span></div><div className="demo-scenarios"><span>Попробуйте на примере</span><button disabled={busy} onClick={()=>void search(DEFAULT)}>Ведущий на корпоратив <ArrowRight size={14}/></button><button disabled={busy} onClick={()=>void search({...DEFAULT,category:'Флорист',event_format:'свадьба',budget_kzt:500000})}>Флорист на свадьбу <ArrowRight size={14}/></button><button disabled={busy} onClick={()=>void search({...DEFAULT,budget_kzt:10000})}>Если никто не подходит <ArrowRight size={14}/></button></div></div>:<>
              <p className="result-summary">{result.message}</p><div className="query-summary"><span><MapPin size={12}/>{result.query.city}</span><span><CalendarDays size={12}/>{formatDate(result.query.event_date)}</span><span>до {formatMoney(result.query.budget_kzt!)}</span></div>
              {result.warnings.map(w=><div className="notice" key={w}><Info size={16}/><p>{w}</p></div>)}
              {result.date_comparison&&<details className="date-changes" open><summary><CalendarDays size={16}/>Что изменилось с {formatDate(result.date_comparison.previous_date)}</summary>{result.date_comparison.changes.map(c=><p key={c}>{c}</p>)}</details>}
              {result.cards.length>0?<div className="cards">{result.cards.map((card,index)=><ContractorCard key={card.id} card={card} index={index} selected={selected.includes(card.id)} onSelect={()=>setSelected(s=>s.includes(card.id)?s.filter(id=>id!==card.id):[...s,card.id])} onOpen={()=>void openProfile(card.id)}/>)}</div>:<div className="empty-state no-match"><span className="empty-icon"><Search size={29}/></span><h3>{result.status==='CATEGORY_ABSENT'?'Здесь пока нет такой категории':'В этот раз условия не совпали'}</h3><p>{result.status==='CATEGORY_ABSENT'?'Попробуйте выбрать другой город или категорию. Мы не будем подменять ваш запрос.':'Это не ошибка. Мы проверили каталог, и ни один профиль не прошёл все ваши условия.'}</p></div>}
              {result.reasons.length>0&&<details className="rejection-summary" open={result.eligible_count<3}><summary>Почему подходят не все <ChevronDown size={14}/></summary><div>{result.reasons.map(r=><span key={r.code}>{r.label}<b>{r.count}</b></span>)}</div><small>Один профиль может не пройти несколько условий.</small></details>}
              {selected.length>=2&&<div className="compare-bar"><span><GitCompareArrows size={17}/>Выбрано {selected.length} варианта</span><button disabled={busy} onClick={()=>void compare()}>Сравнить <ArrowRight size={15}/></button></div>}
              {result.status!=='CATEGORY_ABSENT'&&<div className="alternatives-panel"><div><span className="soft-icon"><CalendarDays size={20}/></span><div><h3>Можно чуть иначе</h3><p>Проверим другие даты и условия</p></div><button className="icon-button" onClick={()=>void getAlternatives()} disabled={busy} aria-label="Показать альтернативы">{pending==='alternatives'?<span className="loader small"/>:<ArrowRight size={20}/>}</button></div>{alternativesLoaded&&alternatives.length===0&&<p className="alternatives-empty">Изменение одного условия не даёт новых вариантов. Попробуйте другой формат или категорию.</p>}</div>}
              <p className="price-note"><Info size={13}/>Цены указаны «от». Итоговую стоимость и детали нужно уточнить у подрядчика.</p>
              <details className="diagnostics"><summary>Как получен результат</summary><p>Каталог: {result.catalog_version}<br/>Ранжирование: {result.ranking_version}<br/>Сопоставление: {result.semantic_version}<br/>Подпись запроса: {result.signature}<br/>Расчёт: {result.elapsed_ms} мс (без сети и отрисовки)</p></details>
            </>}
          </>}
          {alternatives.length>0&&<div className="alternative-list"><p>Изменится только указанное условие:</p>{alternatives.map((a,i)=><button key={i} disabled={busy} onClick={()=>void search({...draft,...a.patch})}><span>{a.label}<small>Подходит профилей: {a.count}</small></span><ArrowRight size={16}/></button>)}</div>}
        </section>
        {chatOpen?<aside className="chat-panel"><div className="chat-header"><span className="assistant-icon"><Sparkles size={18}/></span><div><strong>Ваш помощник</strong><small><i/>{chatMode==='openai'?'ИИ · помогает с подбором':'Локальный режим'}</small></div><button className="icon-button" aria-label="Скрыть помощника" onClick={()=>setChatOpen(false)}><X size={17}/></button></div><ChatSelectionContext result={result} stale={stale} disabled={busy} onAsk={message=>void ask(message)}/><div className="chat-content">{!result&&<div className="assistant-greeting"><div className="greeting-symbol"><WandSparkles size={22}/></div><h3>Давайте найдём<br/>ваших людей.</h3><p>Расскажите о событии своими словами. Я помогу уточнить детали и разобраться в вариантах.</p></div>}{chatMode==='local'&&<div className="local-notice"><Info size={13}/><span>Без подключения ИИ: понимаю параметры, сравниваю и проверяю альтернативы. Сложные формулировки лучше внести в форму.</span></div>}<div className="chat-messages" role="log" aria-label="Сообщения помощника">{messages.map((m,i)=><div className={`message ${m.role}`} key={i}>{m.role==='assistant'&&<Sparkles size={13}/>}<p>{m.content}</p></div>)}{pending==='chat'&&<div className="typing" aria-label="Помощник готовит ответ"><i/><i/><i/></div>}<div ref={chatEnd}/></div></div><div className="chat-suggestions"><button disabled={busy} onClick={()=>void ask('Сравни варианты')}><GitCompareArrows size={12}/>Сравнить</button><button disabled={busy} onClick={()=>void ask('Покажи другие даты')}><CalendarDays size={12}/>Другие даты</button></div><form className="chat-compose" onSubmit={e=>{e.preventDefault();void ask();}}><textarea aria-label="Сообщение помощнику" placeholder="Например: а если на 17 октября?" value={chatText} onChange={e=>setChatText(e.target.value)} maxLength={4000} rows={2} disabled={busy} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();void ask();}}}/><button type="submit" disabled={busy||!chatText.trim()} aria-label="Отправить сообщение"><ArrowRight size={18}/></button></form><div className="chat-footer"><ShieldCheck size={12}/>Рекомендуем. Не бронируем.</div></aside>:<button className="chat-reopen" onClick={()=>setChatOpen(true)}><MessageCircle size={19}/>Помощник</button>}
      </div><footer className="page-footer"><span>событие<span className="brand-dot">.</span> <span>Подбор с пониманием</span></span><button disabled={busy} onClick={()=>void newRequest()}><Plus size={14}/>Новое мероприятие</button><span>AI House · Казахстан</span></footer>
    </main>
    {profile&&<Modal title={profile.anon_name} onClose={()=>setProfile(null)}><div className="profile-meta"><span><MapPin size={15}/>{profile.city}</span><strong>от {formatMoney(profile.price_from_kzt)}</strong></div><Provenance profile={profile}/><div className="profile-facts"><div><small>Категории</small><p>{profile.categories.join(', ')}</p></div><div><small>Форматы</small><p>{profile.event_formats.join(', ')}</p></div><div><small>Языки</small><p>{profile.languages.join(', ')}</p></div><div><small>Длительность</small><p>{profile.max_hours===null?'Присутствие не привязано к часам':`до ${profile.max_hours} часов`}</p></div></div><h3>О подрядчике</h3><p className="profile-description">{profile.description}</p><details className="busy-calendar"><summary>Занятые даты ({profile.busy_dates.length})</summary><div>{profile.busy_dates.map(d=><span key={d}>{new Date(d+'T12:00:00').toLocaleDateString('ru-RU')}</span>)}</div></details><p className="price-note">Данные календаря: 23.09–31.12.2026. Цена «от» не гарантирует окончательную стоимость. {profile.price_imputed?'Цена проставлена при подготовке датасета. ':''}{profile.city_imputed?'Город проставлен при подготовке датасета.':''}</p></Modal>}
    {comparison&&<Modal title="Сравним ваши варианты" onClose={()=>setComparison(null)} wide><div className="comparison-scroll"><table className="comparison-table"><thead><tr><th>Что сравниваем</th>{comparison.map(c=><th key={c.id}>{c.anon_name}</th>)}</tr></thead><tbody>{[['Цена от', (c:Card)=>formatMoney(c.price_from_kzt)],['Город',(c:Card)=>c.city],['Языки',(c:Card)=>c.languages.join(', ')],['Длительность',(c:Card)=>c.max_hours===null?'Неприменима':`до ${c.max_hours} ч`],['Форматы',(c:Card)=>c.event_formats.join(', ')],['Особенность профиля',(c:Card)=>c.evidence.quote],['Происхождение',(c:Card)=>c.synthetic?'Синтетический профиль':'Исходный профиль']].map(([label,render])=><tr key={label as string}><td>{label as string}</td>{comparison.map(c=><td key={c.id}>{(render as (c:Card)=>string)(c)}</td>)}</tr>)}</tbody></table></div><p className="price-note">Все сравниваемые профили прошли условия текущего запроса. Рейтинги качества и отзывы в исходных данных отсутствуют.</p></Modal>}
    {showHelp&&<Modal title="От условий — к совпадениям" onClose={()=>setShowHelp(false)}><div className="help-flow">{[['01','Расскажите о событии','Город, дата, формат, категория и бюджет обязательны. Язык, часы и пожелания помогают уточнить выбор.'],['02','Мы проверим условия','Занятые на дату и не проходящие строгие ограничения профили исключаются. Площадки проверяются так же, как исполнители.'],['03','Объясним каждый вариант','Покажем до трёх карточек с фактами из профилей. Если вариантов меньше — скажем почему.'],['04','Поможем сравнить','Сравнивайте карточки, меняйте условия или обсуждайте выбор с помощником. Альтернативы применяются только по вашему нажатию.']].map(([n,t,d])=><div key={n}><span>{n}</span><section><h3>{t}</h3><p>{d}</p></section></div>)}</div><div className="notice"><Info size={16}/><p>Это демонстрационный каталог: имена анонимизированы, синтетические профили отмечены. Календарь доступен с 23 сентября по 31 декабря 2026 года. Сервис не бронирует и не отправляет заявки.</p></div></Modal>}
  </div>;
}
