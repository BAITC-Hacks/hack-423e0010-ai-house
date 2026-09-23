import { useEffect, useRef, useState } from 'react'
import { ArrowRight, Check, MessageSquareText, Sparkles } from 'lucide-react'
import { parseNaturalRequest } from '../services/agent'
import type { ParsedRequest } from '../domain/agent'
import { money } from '../domain/selection'

export const fieldNames: Record<string, string> = { city: 'Город', event_date: 'Дата с годом', event_format: 'Формат', category: 'Категория', budget_kzt: 'Бюджет', duration_hours: 'Длительность', language: 'Язык', preferences: 'Пожелания' }
export function NaturalRequest({ onApply }: { onApply: (parsed: ParsedRequest) => void }) {
  const [message, setMessage] = useState('')
  const [parsed, setParsed] = useState<ParsedRequest | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const controller = useRef<AbortController | null>(null)
  useEffect(() => () => controller.current?.abort(), [])
  const change = (text: string) => { controller.current?.abort(); setMessage(text); setParsed(null); setError(''); setLoading(false) }
  const parse = async () => {
    if (message.trim().length < 10) { setError('Расскажите немного подробнее: хотя бы 10 символов.'); return }
    controller.current?.abort(); const abort = new AbortController(); controller.current = abort
    setLoading(true); setParsed(null); setError('')
    try { const result = await parseNaturalRequest(message, abort.signal); if (!abort.signal.aborted) setParsed(result) }
    catch (cause) { if (!abort.signal.aborted) setError(cause instanceof Error ? cause.message : 'Не удалось разобрать запрос.') }
    finally { if (!abort.signal.aborted) setLoading(false) }
  }
  return <section className="natural-request" aria-labelledby="natural-title">
    <div className="natural-heading"><span className="agent-orb"><Sparkles size={22} /></span><div><span className="section-eyebrow">НАЧНИТЕ С ИДЕИ</span><h2 id="natural-title">Опишите событие — агент разберётся в деталях</h2><p>Напишите своими словами. ИИ выделит условия, уточнит недостающее и подготовит обоснованный подбор.</p></div><span className="real-ai-badge">С помощью ИИ</span></div>
    <form onSubmit={(event) => { event.preventDefault(); void parse() }}>
      <label className="sr-only" htmlFor="natural-message">Запрос для ИИ-агента</label>
      <textarea id="natural-message" rows={2} maxLength={2000} value={message} onChange={(event) => change(event.target.value)} placeholder="Нужен флорист в Алматы на свадьбу 10 октября 2026, до 500 тысяч тенге. Хочу нежные сезонные цветы…" aria-describedby="natural-hint" />
      <div className="natural-actions"><span id="natural-hint"><MessageSquareText size={14} />Город, дата с годом, формат, категория и бюджет</span><button className="primary-button" disabled={loading || !message.trim()}>{loading ? <><span className="spinner" />Разбираем запрос…</> : <><Sparkles size={15} />Разобрать с ИИ<ArrowRight size={15} /></>}</button></div>
    </form>
    <div className="natural-examples"><span>Например:</span><button onClick={() => change('Нужен флорист в Алматы на свадьбу 10 октября 2026 года, до 500 тысяч тенге. Нежные сезонные цветы.')}>Флорист на свадьбу</button><button onClick={() => change('Ищу ведущего в Алматы на корпоратив 10 октября 2026 года. Бюджет 10 тысяч тенге, русский язык, 6 часов. Спокойная подача и интеллигентный юмор.')}>Ведущий с небольшим бюджетом</button></div>
    {error && <div className="agent-error" role="alert">{error}</div>}
    {parsed && <div className="parsed-request" aria-live="polite"><div className="parsed-title"><Check size={17} /><strong>Вот как агент понял ваш запрос</strong></div><p>{parsed.interpretation}</p><dl>{Object.entries(parsed.fields).filter(([, value]) => value !== null && value !== '').map(([key, value]) => <div key={key}><dt>{fieldNames[key]}</dt><dd>{key === 'budget_kzt' ? money(value as number) : key === 'duration_hours' ? `${value} ч` : String(value)}</dd></div>)}</dl>
      {parsed.missing_fields.length > 0 && <p className="parse-missing"><strong>Нужно уточнить:</strong> {parsed.missing_fields.map((field) => fieldNames[field]).join(', ')}. Дополните текст или заполните эти поля в форме.</p>}
      {parsed.invalid_fields.length > 0 && <p className="parse-missing"><strong>Не проходят проверку:</strong> {parsed.invalid_fields.map((field) => fieldNames[field]).join(', ')}. Календарь доступен с 23 сентября по 31 декабря 2026 года.</p>}
      {parsed.questions.length > 0 && <ul className="agent-questions">{parsed.questions.map((question, index) => <li key={index}>{question}</li>)}</ul>}
      {parsed.unverified_requirements.length > 0 && <div className="unverified-note"><strong>Требует отдельного уточнения</strong><ul>{parsed.unverified_requirements.map((item, index) => <li key={index}>{item}</li>)}</ul></div>}
      <div className="parsed-footer"><span>Проверьте параметры перед применением.</span><button className="primary-button" onClick={() => onApply(parsed)}>{parsed.ready ? 'Подобрать и объяснить' : 'Перенести в форму'}<ArrowRight size={15} /></button></div>
    </div>}
    <div className="or-form"><span>или задайте условия в форме ниже</span></div>
  </section>
}
