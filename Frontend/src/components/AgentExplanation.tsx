import { ArrowRight, Check, ChevronDown, CircleHelp, RefreshCw, Sparkles } from 'lucide-react'
import type { AgentFact, AgentParagraph, AgentResponse, NearbyOption } from '../domain/agent'
import { dateLabel, money, reasonLabels } from '../domain/selection'
import type { SelectionResponse } from '../domain/selection'
import { Artwork } from './Artwork'

type Props = { data: AgentResponse | null; loading: boolean; error: string; selection: SelectionResponse; onRetry: () => void; onApply: (option: NearbyOption) => void; stale: boolean }
function GroundedParagraph({ paragraph, facts }: { paragraph: AgentParagraph; facts: AgentFact[] }) {
  const selected = paragraph.evidence_ids.map((id) => facts.find((f) => f.id === id)).filter((item): item is AgentFact => !!item)
  return <div className="grounded-paragraph"><p>{paragraph.text}</p><details className="agent-sources"><summary>Основания этого вывода <span>{selected.length}</span><ChevronDown size={12} /></summary>{selected.map((fact) => <div key={fact.id}><strong>{fact.label}</strong><p>{fact.value}</p><small>{fact.source}</small></div>)}</details></div>
}
export function NearbySuggestions({ data, onApply, stale }: Pick<Props, 'onApply' | 'stale'> & { data: AgentResponse }) {
  if (!data.nearby_options.length) return null
  return <section className="nearby-section" aria-label="Ближайшие варианты"><div className="nearby-heading"><Sparkles size={20} /><div><h3>Ближайшие варианты, если изменить условия</h3><p>Эти подрядчики не проходят исходный запрос. Все необходимые изменения указаны ниже.</p></div></div>
    <div className="nearby-list">{data.nearby_options.map((option) => {
      const reasoning = data.report?.nearby.find((entry) => entry.option_id === option.id)
      return <article className="nearby-card" key={option.id}><div className="nearby-profile"><Artwork palette={option.contractor.artwork} category={option.contractor.category} name={option.contractor.name} compact /><div><span className="conditional-badge">При изменении условий</span><h4>{option.contractor.name}</h4><p>{option.contractor.category} · {option.contractor.city}</p><strong>от {money(option.contractor.price_from_kzt)}</strong></div></div>
        <div className="why-not-original"><strong>Почему не в основной подборке</strong><p>{option.original_reasons.join(' · ')}</p></div>
        <div className="condition-changes">{option.changes.map((change) => <div key={change.field}><span>{change.label}</span><div><del>{change.before}</del><ArrowRight size={13} /><strong>{change.after}</strong></div></div>)}</div>
        {reasoning ? <><div className="nearby-reasoning">{reasoning.paragraphs.map((paragraph, index) => <GroundedParagraph key={index} paragraph={paragraph} facts={data.facts} />)}</div><div className="tradeoff"><CircleHelp size={17} /><div><strong>Что придётся изменить</strong><GroundedParagraph paragraph={reasoning.tradeoff} facts={data.facts} /></div></div></> : <p className="nearby-no-ai">Вариант проверен фильтрами. Развёрнутое объяснение ИИ пока недоступно.</p>}
        <div className="nearby-footer"><span><Check size={14} />Проверен на {dateLabel(option.request.event_date)}<small>Цена «от»; итоговая смета требует уточнения.</small></span><button className="secondary-button" onClick={() => onApply(option)} disabled={stale}>Применить условия <ArrowRight size={15} /></button></div>
      </article>
    })}</div>
  </section>
}
export function AgentExplanation({ data, loading, error, selection, onRetry, onApply, stale }: Props) {
  const report = data?.report
  return <div className="agent-explanation" aria-busy={loading}>
    <div className="agent-intro"><span className="agent-orb"><Sparkles size={25} /></span><div><span className="section-eyebrow">TANDAU · ВАШ АГЕНТ</span><h3>{loading ? 'Разбираем ваш выбор по деталям' : report?.title || 'Что показал подбор'}</h3><p>{selection.request.city} · {selection.request.category} · {dateLabel(selection.request.event_date)} · до {money(selection.request.budget_kzt)}</p></div></div>
    {stale && <div className="agent-error">Вы изменили форму. Этот разбор относится к показанным выше условиям. Обновите подбор перед применением альтернатив.</div>}
    <div className="agent-funnel"><div><strong>{selection.catalog_count}</strong><span>в городе и категории</span></div><ArrowRight size={17} /><div><strong>{selection.eligible_count}</strong><span>прошли все условия</span></div><ArrowRight size={17} /><div><strong>{selection.recommendations.length}</strong><span>в вашей подборке</span></div></div>
    {loading && <div className="agent-thinking" role="status"><span className="spinner" /><div><strong>ИИ изучает подтверждённые факты</strong><p>Объясняет результат, сопоставляет пожелания и разбирает компромиссы ближайших вариантов. Обычно это занимает до минуты.</p></div></div>}
    {(error || data?.ai_error) && <div className="agent-error" role="alert"><strong>ИИ-разбор сейчас недоступен</strong><p>{error || data?.ai_error}</p><button className="secondary-button" onClick={onRetry} disabled={loading}><RefreshCw size={14} />Повторить разбор</button></div>}
    {!report && !loading && <div className="agent-factual-summary"><h4>Подтверждено каталогом</h4><p>{selection.status === 'CATEGORY_ABSENT' ? 'В этом городе нет профилей выбранной категории. Изменение бюджета, даты или языка не создаст отсутствующую категорию.' : `Под все условия проходят ${selection.eligible_count} из ${selection.catalog_count} профилей. ${selection.eligible_count < 3 ? 'Подборка не дополняется неподходящими кандидатами.' : 'В основной выдаче показаны не более трёх вариантов.'}`}</p>{selection.exclusions.length > 0 && <ul>{selection.exclusions.map((item) => <li key={item.code}><span>{reasonLabels[item.code]}</span><strong>{item.count}</strong></li>)}</ul>}<small>Каждый исключённый профиль учтён по первому неподходящему условию. Это сводка фильтров, не ответ ИИ.</small></div>}
    {report && <>
      <div className="agent-overview">{report.overview.map((paragraph, index) => <GroundedParagraph key={index} paragraph={paragraph} facts={data.facts} />)}</div>
      <section className="agent-report-section"><h3>Почему получился именно такой результат</h3>{report.filtering.map((section, index) => <div className="filter-explanation" key={index}><h4>{section.title}</h4><GroundedParagraph paragraph={section.paragraph} facts={data.facts} /></div>)}</section>
      {report.candidates.length > 0 && <section className="agent-report-section"><h3>Разбираем каждого кандидата</h3>{selection.recommendations.map((card) => { const entry = report.candidates.find((item) => item.contractor_id === card.contractor.id); return entry && <article className="agent-candidate" key={entry.contractor_id}><div><Artwork palette={card.contractor.artwork} category={card.contractor.category} name={card.contractor.name} compact /><div><h4>{card.contractor.name}</h4><p>{card.contractor.category} · от {money(card.contractor.price_from_kzt)}</p></div></div>{entry.paragraphs.map((paragraph, index) => <GroundedParagraph key={index} paragraph={paragraph} facts={data.facts} />)}</article> })}</section>}
    </>}
    {data && <NearbySuggestions data={data} onApply={onApply} stale={stale} />}
    {data && selection.eligible_count < 3 && !data.nearby_options.length && <p className="no-nearby">Ближайших дополнительных вариантов в этой категории, городе и формате не найдено: проверены соседние даты в пределах 14 дней, бюджет, язык и длительность. Город, категория и формат автоматически не меняются.</p>}
    {report && <><section className="agent-limitations"><h3>Что важно уточнить</h3><ul>{report.limitations.map((item, index) => <li key={index}>{item}</li>)}</ul></section><div className="agent-next-step"><Sparkles size={19} /><div><h3>Мой совет</h3><p>{report.next_step}</p></div></div><p className="agent-footer-note">ИИ-разбор основан на каталоге и календарях. У каждого вывода можно открыть использованные факты.{data.cached ? ' Показан сохранённый разбор того же запроса.' : ''}</p></>}
  </div>
}
export function AgentSummary({ data, loading, error, onOpen, onApply, stale }: Omit<Props, 'selection' | 'onRetry'> & { onOpen: () => void }) {
  return <div className="agent-results-panel"><div className="agent-summary"><span className="agent-orb"><Sparkles size={23} /></span><div><span className="section-eyebrow">ВЫБОР С ОБОСНОВАНИЕМ</span><h3>{loading ? 'Агент готовит подробный разбор' : data?.report ? 'Агент объяснил вашу подборку' : 'Разберём результат вместе с агентом'}</h3><p>{loading ? 'Проверенные факты, отличия кандидатов и ближайшие альтернативы.' : error || data?.ai_error ? 'ИИ-разбор не получен. Подтверждённая подборка остаётся доступна.' : 'Почему эти кандидаты, почему вариантов столько и какие изменения дадут больше выбора.'}</p></div><button className="secondary-button" onClick={onOpen}>{loading ? 'Открыть окно' : data?.report ? 'Читать разбор' : 'Открыть агента'}<ArrowRight size={15} /></button></div>{data && <NearbySuggestions data={data} onApply={onApply} stale={stale} />}</div>
}
