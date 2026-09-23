import { demoCatalog } from '../data/catalog'
import { CALENDAR, dateLabel, money, reasonCodes, requestSchema } from '../domain/selection'
import type {
  DemoProfile,
  Recommendation,
  ReasonCode,
  SelectionRequest,
  SelectionResponse,
} from '../domain/selection'

export function exclusionReasons(profile: DemoProfile, request: SelectionRequest): ReasonCode[] {
  const reasons: ReasonCode[] = []
  if (profile.busy_dates.includes(request.event_date)) reasons.push('BUSY')
  if (!profile.event_formats.includes(request.event_format)) reasons.push('FORMAT_UNSUPPORTED')
  if (profile.price_from_kzt > request.budget_kzt) reasons.push('OVER_BUDGET')
  if (request.language && !profile.languages.includes(request.language))
    reasons.push('LANGUAGE_UNSUPPORTED')
  if (
    request.duration_hours !== null &&
    profile.max_hours !== null &&
    request.duration_hours > profile.max_hours
  )
    reasons.push('DURATION_EXCEEDED')
  return reasons
}
const inCatalog = (request: SelectionRequest) =>
  demoCatalog.filter((p) => p.city === request.city && p.categories.includes(request.category))
const eligible = (request: SelectionRequest) =>
  inCatalog(request).filter((p) => exclusionReasons(p, request).length === 0)
const preferenceFeatures = (p: DemoProfile, request: SelectionRequest) =>
  p.features.filter((feature) =>
    feature.keywords.some((word) => request.preferences.toLocaleLowerCase('ru').includes(word)),
  )

function makeRecommendation(p: DemoProfile, r: SelectionRequest): Recommendation {
  const { busy_dates: _, ...contractor } = p
  const relevant = preferenceFeatures(p, r)
  const feature = relevant[0] ?? p.features[0]
  const explanation = `Цена от ${money(p.price_from_kzt)} при бюджете ${money(r.budget_kzt)}; формат «${r.event_format}» есть в профиле${r.language ? `, язык — ${r.language}` : ''}. ${feature ? `В описании: «${feature.quote}»${relevant.length ? ' — это совпадает с ключевыми словами в ваших пожеланиях' : ''}.` : `По календарю свободен ${dateLabel(r.event_date)}.`}`
  return {
    contractor: { ...contractor, category: r.category },
    explanation,
    available_on: r.event_date,
    matched_preferences: relevant.map((f) => f.label),
    evidence: [
      {
        label: 'Дата',
        value: `${dateLabel(r.event_date)} 2026 — нет занятой даты`,
        source: 'Календарь профиля · 23.09–31.12.2026',
      },
      { label: 'Формат', value: r.event_format, source: 'Структурированное поле event_formats' },
      {
        label: 'Цена «от»',
        value: `${money(p.price_from_kzt)} ≤ ${money(r.budget_kzt)}`,
        source: 'Поле price_from_kzt · итоговая смета уточняется',
      },
      ...(r.language
        ? [{ label: 'Язык', value: r.language, source: 'Структурированное поле languages' }]
        : []),
      ...(r.duration_hours !== null
        ? [
            {
              label: 'Длительность',
              value:
                p.max_hours === null
                  ? 'Неприменима к этой услуге'
                  : `${r.duration_hours} ч ≤ ${p.max_hours} ч`,
              source: 'Структурированное поле max_hours',
            },
          ]
        : []),
      ...(feature
        ? [{ label: 'Из описания', value: feature.quote, source: 'Описание профиля' }]
        : []),
    ],
  }
}

function alternatives(r: SelectionRequest): SelectionResponse['alternatives'] {
  const result: SelectionResponse['alternatives'] = []
  const add = (label: string, patch: Partial<SelectionRequest>) => {
    const matchCount = eligible({ ...r, ...patch }).length
    if (matchCount) result.push({ label, patch, match_count: matchCount })
  }
  const prices = inCatalog(r)
    .filter((p) => exclusionReasons(p, { ...r, budget_kzt: 1_000_000_000 }).length === 0)
    .map((p) => p.price_from_kzt)
  if (prices.length && Math.min(...prices) > r.budget_kzt)
    add(`Бюджет ${money(Math.min(...prices))}`, { budget_kzt: Math.min(...prices) })
  if (r.duration_hours !== null) add('Без ограничения по часам', { duration_hours: null })
  if (r.language !== null) add('Без ограничения по языку', { language: null })
  for (let offset = 1; offset <= 14 && !result.some((item) => item.patch.event_date); offset++) {
    const day = new Date(`${r.event_date}T12:00:00Z`)
    day.setUTCDate(day.getUTCDate() + offset)
    const date = day.toISOString().slice(0, 10)
    if (date > CALENDAR.end) break
    add(`На ${dateLabel(date)}`, { event_date: date })
  }
  return result.slice(0, 3)
}

export function selectDemo(input: SelectionRequest): SelectionResponse {
  const request = requestSchema.parse(input)
  const catalog = inCatalog(request)
  // Only the first failed condition contributes to the summary; counts never overlap.
  const firstFailures = catalog.map((p) => exclusionReasons(p, request)[0]).filter(Boolean)
  const passed = eligible(request).sort(
    (a, b) =>
      preferenceFeatures(b, request).length - preferenceFeatures(a, request).length ||
      a.price_from_kzt - b.price_from_kzt ||
      a.id.localeCompare(b.id, 'en'),
  )
  return {
    status: !catalog.length ? 'CATEGORY_ABSENT' : !passed.length ? 'NO_MATCH' : 'MATCHED',
    request,
    catalog_count: catalog.length,
    eligible_count: passed.length,
    recommendations: passed.slice(0, 3).map((p) => makeRecommendation(p, request)),
    exclusions: reasonCodes
      .map((code) => ({ code, count: firstFailures.filter((value) => value === code).length }))
      .filter((item) => item.count > 0),
    alternatives: catalog.length && !passed.length ? alternatives(request) : [],
    catalog_version: 'hackathon-66-v1',
    ranking_version: 'keywords-price-id-v1',
  }
}
