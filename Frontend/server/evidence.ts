import { createHash } from 'node:crypto'
import { demoCatalog } from '../src/data/catalog'
import { CALENDAR, dateLabel, money, reasonLabels, requestSchema } from '../src/domain/selection'
import type { DemoProfile, SelectionRequest, SelectionResponse } from '../src/domain/selection'
import type { AgentFact, AgentReport, NearbyOption } from '../src/domain/agent'
import { exclusionReasons } from '../src/services/demo'

const eligibleProfiles = (r: SelectionRequest) => demoCatalog.filter((p) => p.city === r.city && p.categories.includes(r.category) && exclusionReasons(p, r).length === 0)
const display = (field: string, value: unknown) => value === null ? 'Не задано' : field === 'budget_kzt' ? money(value as number) : field === 'event_date' ? `${dateLabel(value as string)} 2026` : field === 'duration_hours' ? `${value} ч` : String(value)

/** Nearest existing profiles only; city, category and event format never expand automatically. */
export function findNearby(request: SelectionRequest): NearbyOption[] {
  const originals = new Set(eligibleProfiles(request).map((p) => p.id))
  const pool = demoCatalog.filter((p) => p.city === request.city && p.categories.includes(request.category) && p.event_formats.includes(request.event_format) && !originals.has(p.id))
  const options: NearbyOption[] = []
  for (const profile of pool) {
    const next = { ...request }
    let dateDistance = 0
    if (profile.busy_dates.includes(next.event_date)) {
      let freeDate: string | undefined
      for (let distance = 1; distance <= 14 && !freeDate; distance++) {
        for (const direction of [1, -1]) {
          const date = new Date(`${request.event_date}T12:00:00Z`)
          date.setUTCDate(date.getUTCDate() + distance * direction)
          const day = date.toISOString().slice(0, 10)
          if (day >= CALENDAR.start && day <= CALENDAR.end && !profile.busy_dates.includes(day)) { freeDate = day; dateDistance = distance; break }
        }
      }
      if (!freeDate) continue
      next.event_date = freeDate
    }
    if (profile.price_from_kzt > next.budget_kzt) next.budget_kzt = profile.price_from_kzt
    if (next.language && !profile.languages.includes(next.language)) next.language = null
    if (next.duration_hours !== null && profile.max_hours !== null && next.duration_hours > profile.max_hours) next.duration_hours = profile.max_hours
    if (!requestSchema.safeParse(next).success || exclusionReasons(profile, next).length) continue
    const fields = ['event_date', 'budget_kzt', 'language', 'duration_hours'] as const
    const labels = { event_date: 'Дата', budget_kzt: 'Бюджет', language: 'Язык', duration_hours: 'Длительность' }
    const changes = fields.filter((field) => next[field] !== request[field]).map((field) => ({ field, label: labels[field], before: display(field, request[field]), after: display(field, next[field]) }))
    if (!changes.length) continue
    const { busy_dates: _, ...contractor } = profile
    const distance = changes.length * 1000 + dateDistance * 10 + Math.min(900, (next.budget_kzt - request.budget_kzt) / Math.max(1, request.budget_kzt) * 100)
    options.push({ id: `near-${profile.id}`, contractor: { ...contractor, category: request.category }, request: next, changes, original_reasons: exclusionReasons(profile, request).map((code) => reasonLabels[code]), match_count: eligibleProfiles(next).length, distance })
  }
  return options.sort((a, b) => a.distance - b.distance || a.contractor.price_from_kzt - b.contractor.price_from_kzt || a.id.localeCompare(b.id, 'en')).slice(0, 3)
}

export function buildFacts(selection: SelectionResponse, nearby: NearbyOption[]): AgentFact[] {
  const r = selection.request
  const facts: AgentFact[] = []
  const add = (id: string, label: string, value: string, source: string) => facts.push({ id, label, value, source })
  add('request', 'Условия запроса', `${r.city}; ${r.category}; ${r.event_format}; ${dateLabel(r.event_date)} 2026; бюджет ${money(r.budget_kzt)}; язык ${r.language ?? 'не ограничен'}; длительность ${r.duration_hours === null ? 'не ограничена' : `${r.duration_hours} ч`}; пожелания: ${r.preferences || 'не указаны'}`, 'Запрос пользователя')
  add('counts', 'Сколько профилей прошло', `В городе и категории: ${selection.catalog_count}. Прошли все условия: ${selection.eligible_count}. Показаны: ${selection.recommendations.length}. Статус: ${selection.status}.`, 'Строгая фильтрация каталога')
  add('calendar', 'Границы календаря', 'Подтверждается только отсутствие занятой даты в календаре 23.09–31.12.2026. Это не бронирование.', 'Границы исходного датасета')
  add('pricing', 'Ограничение цены', 'Цена «от» — стартовая цена, итоговая смета не гарантирована.', 'Описание полей каталога')
  for (const exclusion of selection.exclusions) add(`excluded:${exclusion.code}`, reasonLabels[exclusion.code], `${exclusion.count} профилей. Каждый профиль учтён только по первой причине, в порядке: дата → формат → бюджет → язык → длительность.`, 'Сводка фильтрации без пересечений')
  const profileFacts = (p: DemoProfile, prefix: string, request: SelectionRequest) => {
    add(`${prefix}:profile`, `Профиль ${p.name}`, `${p.name}; ${p.city}; категории: ${p.categories.join(', ')}; цена от ${money(p.price_from_kzt)}; форматы: ${p.event_formats.join(', ')}; языки: ${p.languages.join(', ')}; максимум часов: ${p.max_hours ?? 'неприменимо'}.`, 'Структурированные поля CSV')
    add(`${prefix}:description`, `Описание ${p.name}`, p.description, 'Полное исходное описание; утверждения автора профиля')
    add(`${prefix}:availability`, `Календарь ${p.name}`, `${dateLabel(request.event_date)} 2026: ${p.busy_dates.includes(request.event_date) ? 'занят' : 'нет занятой даты'}.`, 'Календарь профиля')
    add(`${prefix}:provenance`, `Происхождение ${p.name}`, `Профиль ${p.origin === 'synthetic' ? 'синтетический' : 'анонимизированный'}. Цена ${p.price_is_estimated ? 'дополнена при подготовке' : 'из исходного профиля'}. Город ${p.city_is_estimated ? 'дополнен при подготовке' : 'из исходного профиля'}.`, 'Признаки происхождения CSV')
  }
  for (const card of selection.recommendations) profileFacts(demoCatalog.find((p) => p.id === card.contractor.id)!, `candidate:${card.contractor.id}`, r)
  for (const option of nearby) {
    profileFacts(demoCatalog.find((p) => p.id === option.contractor.id)!, option.id, option.request)
    add(`${option.id}:changes`, `Изменения для ${option.contractor.name}`, option.changes.map((c) => `${c.label}: ${c.before} → ${c.after}`).join('; '), 'Повторный запуск всех строгих фильтров')
    add(`${option.id}:why_excluded`, `Почему ${option.contractor.name} не в основной выдаче`, option.original_reasons.join('; '), 'Все причины исключения по исходным условиям')
    add(`${option.id}:verified`, 'Результат проверки альтернативы', `Профиль проходит все фильтры после перечисленных изменений. В городе и категории при этих условиях подходят ${option.match_count} профилей. Город, категория и формат сохранены.`, 'Контрольная фильтрация каталога')
  }
  return facts
}

/** Reject unknown references and explanations attached to the wrong profile. */
export function verifyReport(report: AgentReport, selection: SelectionResponse, nearby: NearbyOption[], facts: AgentFact[]) {
  const ids = new Set(facts.map((f) => f.id))
  const checkParagraph = (p: { evidence_ids: string[] }, subject?: string) => {
    if (p.evidence_ids.some((id) => !ids.has(id))) throw new Error('AI_UNKNOWN_EVIDENCE')
    if (subject && !p.evidence_ids.some((id) => id.startsWith(subject))) throw new Error('AI_UNGROUNDED_SUBJECT')
  }
  const expected = selection.recommendations.map((c) => c.contractor.id).sort()
  if (JSON.stringify(report.candidates.map((c) => c.contractor_id).sort()) !== JSON.stringify(expected)) throw new Error('AI_WRONG_CANDIDATES')
  if (JSON.stringify(report.nearby.map((c) => c.option_id).sort()) !== JSON.stringify(nearby.map((o) => o.id).sort())) throw new Error('AI_WRONG_ALTERNATIVES')
  report.overview.forEach((p) => checkParagraph(p))
  report.filtering.forEach((p) => checkParagraph(p.paragraph))
  report.candidates.forEach((c) => c.paragraphs.forEach((p) => checkParagraph(p, `candidate:${c.contractor_id}:`)))
  report.nearby.forEach((c) => { c.paragraphs.forEach((p) => checkParagraph(p, `${c.option_id}:`)); checkParagraph(c.tradeoff, `${c.option_id}:`) })
}

export const cacheKey = (request: SelectionRequest, model: string) => createHash('sha256').update(JSON.stringify([requestSchema.parse(request), 'hackathon-66-v1', 'keywords-price-id-v1', 'agent-evidence-v1', model])).digest('hex')
