import { describe, expect, it } from 'vitest'
import { demoCatalog } from '../src/data/catalog'
import {
  CATEGORIES,
  CITIES,
  defaultForm,
  parseForm,
  requestSchema,
  responseSchema,
} from '../src/domain/selection'
import type { SelectionRequest } from '../src/domain/selection'
import { exclusionReasons, selectDemo } from '../src/services/demo'

const base = parseForm(defaultForm).request!
const run = (patch: Partial<SelectionRequest> = {}) => selectDemo({ ...base, ...patch })

describe('Provided catalog and documented use cases', () => {
  it('preserves all 66 records and provenance flags from the source', () => {
    expect(demoCatalog).toHaveLength(66)
    expect(new Set(demoCatalog.map((p) => p.id)).size).toBe(66)
    expect(demoCatalog.filter((p) => p.origin === 'synthetic')).toHaveLength(13)
    expect(demoCatalog.filter((p) => p.price_is_estimated)).toHaveLength(18)
    expect(demoCatalog.filter((p) => p.city_is_estimated)).toHaveLength(8)
    expect(new Set(demoCatalog.flatMap((p) => p.categories)).size).toBe(17)
    for (const p of demoCatalog)
      for (const feature of p.features) expect(p.description).toContain(feature.quote)
  })
  it('UC-01 returns only three of four eligible hosts on October 10', () => {
    const result = run()
    expect(result.status).toBe('MATCHED')
    expect(result.eligible_count).toBe(4)
    expect(result.recommendations.map((c) => c.contractor.name)).toEqual([
      'Куррапика',
      'Аня Форджер',
      'Сон Гоку',
    ])
  })
  it('UC-02 ranks only eligible profiles using source-backed preference features', () => {
    const result = run({ preferences: 'Танцы и развлечения' })
    expect(result.recommendations[0].contractor.name).toBe('Аня Форджер')
    expect(result.recommendations[0].explanation).toContain('Только развлечения и танцы')
  })
  it('UC-06 repeats IDs in exactly the same order', () => {
    for (let i = 0; i < 10; i++)
      expect(run({ preferences: 'интеллигентный юмор' })).toEqual(
        run({ preferences: 'интеллигентный юмор' }),
      )
  })
  it('UC-07 changes the composition on October 17 and preserves other conditions', () => {
    const result = run({ event_date: '2026-10-17' })
    expect(result.eligible_count).toBe(3)
    expect(result.recommendations.map((c) => c.contractor.id)).not.toEqual(
      run().recommendations.map((c) => c.contractor.id),
    )
    expect(result.request.budget_kzt).toBe(base.budget_kzt)
  })
  it('UC-08 shows the single florist and does not pad results', () => {
    const first = run({ category: 'Флорист', event_format: 'свадьба', budget_kzt: 500000 })
    const second = run({
      category: 'Флорист',
      event_format: 'свадьба',
      budget_kzt: 500000,
      event_date: '2026-10-17',
    })
    expect(first.recommendations).toHaveLength(1)
    expect(first.recommendations[0].contractor.name).toBe('Тони Тони Чоппер')
    expect(second.recommendations).toHaveLength(1)
    expect(second.recommendations[0].contractor.name).toBe('Тихиро Огино')
  })
  it('UC-09 distinguishes an absent category before other filters', () => {
    const result = run({ city: 'Астана', category: 'Декоратор', budget_kzt: 1 })
    expect(result.status).toBe('CATEGORY_ABSENT')
    expect(result.catalog_count).toBe(0)
    expect(result.exclusions).toEqual([])
  })
  it('UC-10 explains a nonempty category with no eligible profiles', () => {
    const result = run({ budget_kzt: 10000 })
    expect(result.status).toBe('NO_MATCH')
    expect(result.catalog_count).toBeGreaterThan(0)
    expect(result.recommendations).toHaveLength(0)
    expect(result.exclusions.some((r) => r.code === 'OVER_BUDGET')).toBe(true)
    expect(result.exclusions.reduce((n, r) => n + r.count, 0)).toBe(result.catalog_count)
    for (const alternative of result.alternatives) {
      expect(run({ ...result.request, ...alternative.patch }).eligible_count).toBe(
        alternative.match_count,
      )
    }
  })
  it('UC-03/04/05 enforces language, duration and calendar across all categories', () => {
    for (const city of CITIES)
      for (const category of CATEGORIES)
        for (const event_date of ['2026-10-10', '2026-10-17', '2026-11-14']) {
          const result = run({
            city,
            category,
            event_date,
            budget_kzt: 10000000,
            language: 'русский',
            duration_hours: 8,
          })
          expect(responseSchema.safeParse(result).success).toBe(true)
          for (const { contractor: p } of result.recommendations) {
            const source = demoCatalog.find((item) => item.id === p.id)!
            expect(source.busy_dates).not.toContain(event_date)
            expect(p.languages).toContain('русский')
            expect(p.max_hours === null || p.max_hours >= 8).toBe(true)
            expect(p.event_formats).toContain(base.event_format)
            expect(p.categories).toContain(category)
            expect(p.city).toBe(city)
          }
        }
  })
  it('never treats a venue with a busy date as available in any of its categories', () => {
    const venue = demoCatalog.find(
      (p) => p.categories.includes('Банкетный зал') && p.busy_dates.length,
    )!
    for (const category of venue.categories) {
      const request = {
        ...base,
        city: venue.city,
        category,
        event_date: venue.busy_dates[0],
        event_format: venue.event_formats[0],
        budget_kzt: 100000000,
      }
      expect(exclusionReasons(venue, request)).toContain('BUSY')
      expect(selectDemo(request).recommendations.map((c) => c.contractor.id)).not.toContain(
        venue.id,
      )
    }
  })
  it('handles non-applicable florist duration without interpreting it as zero', () => {
    const result = run({
      category: 'Флорист',
      event_format: 'свадьба',
      budget_kzt: 500000,
      duration_hours: 24,
    })
    expect(result.recommendations).toHaveLength(1)
    expect(result.recommendations[0].contractor.max_hours).toBeNull()
  })
  it('uses structured formats even when descriptions mention other formats', () => {
    const p = demoCatalog.find((p) => p.name === 'Кики')!
    expect(p.description.toLowerCase()).toContain('конференц')
    expect(exclusionReasons(p, { ...base, event_format: 'конференция' })).toContain(
      'FORMAT_UNSUPPORTED',
    )
  })
})

describe('Form and backend contract', () => {
  it('sends one normalized object, including nullable optional fields', () => {
    const { request } = parseForm({
      ...defaultForm,
      budget_kzt: '1 000 000',
      preferences: '  Тихая атмосфера  ',
    })
    expect(request).toEqual({
      city: 'Алматы',
      event_date: '2026-10-10',
      event_format: 'корпоратив',
      category: 'Ведущий',
      budget_kzt: 1000000,
      duration_hours: null,
      language: null,
      preferences: 'Тихая атмосфера',
    })
  })
  it.each(['', '0', '-5', 'NaN', '1.5', '1000000001'])(
    'rejects invalid budget %s',
    (budget_kzt) => {
      expect(parseForm({ ...defaultForm, budget_kzt }).errors.budget_kzt).toBeTruthy()
    },
  )
  it.each(['2026-09-22', '2027-01-01', '2026-02-30', ''])(
    'rejects unsupported or invalid dates %s',
    (event_date) => {
      expect(parseForm({ ...defaultForm, event_date }).errors.event_date).toBeTruthy()
    },
  )
  it.each(['0', '-1', '25', 'abc'])('rejects invalid duration %s', (duration_hours) => {
    expect(parseForm({ ...defaultForm, duration_hours }).errors.duration_hours).toBeTruthy()
  })
  it('rejects contradictory, duplicate and oversized backend responses', () => {
    const valid = run()
    expect(responseSchema.safeParse(valid).success).toBe(true)
    expect(responseSchema.safeParse({ ...valid, status: 'NO_MATCH' }).success).toBe(false)
    expect(
      responseSchema.safeParse({
        ...valid,
        recommendations: [...valid.recommendations, valid.recommendations[0]],
      }).success,
    ).toBe(false)
    expect(
      responseSchema.safeParse({
        ...valid,
        recommendations: [
          valid.recommendations[0],
          valid.recommendations[0],
          valid.recommendations[0],
        ],
      }).success,
    ).toBe(false)
    const changed = structuredClone(valid)
    changed.recommendations[0].available_on = '2026-12-01'
    expect(responseSchema.safeParse(changed).success).toBe(false)
    const wrongCategories = structuredClone(valid)
    wrongCategories.recommendations[0].contractor.categories = ['Флорист']
    expect(responseSchema.safeParse(wrongCategories).success).toBe(false)
    expect(requestSchema.safeParse({ ...base, category: 'Неизвестная категория' }).success).toBe(
      false,
    )
  })
})
