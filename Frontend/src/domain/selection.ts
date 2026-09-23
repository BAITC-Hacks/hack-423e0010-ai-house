import { z } from 'zod'

export const CITIES = ['Алматы', 'Астана', 'Зарубежье'] as const
export const CATEGORIES = [
  'Ведущий',
  'Фотограф',
  'Видеограф',
  'Банкетный зал',
  'Загородная площадка',
  'Ресторан',
  'Отель',
  'Флорист',
  'Декоратор',
  'Ведущий церемонии',
  'Инструменталист',
  'Лайв-бэнд',
  'Национальный ансамбль',
  'Танцевальный коллектив',
  'Шоу-программа',
  'Фото и видеобудки',
  'Подарки и сувениры',
] as const
export const EVENT_FORMATS = [
  'корпоратив',
  'свадьба',
  'той',
  'конференция',
  'юбилей',
  'день рождения',
] as const
export const LANGUAGES = ['русский', 'казахский', 'английский'] as const
export const CALENDAR = { start: '2026-09-23', end: '2026-12-31' }

export const requestSchema = z.object({
  city: z.enum(CITIES),
  event_date: z.iso
    .date()
    .refine(
      (date) => date >= CALENDAR.start && date <= CALENDAR.end,
      'Выберите дату с 23 сентября по 31 декабря 2026 года.',
    ),
  event_format: z.enum(EVENT_FORMATS),
  category: z.enum(CATEGORIES),
  budget_kzt: z.number().int().positive().max(1_000_000_000),
  duration_hours: z.number().positive().max(24).nullable(),
  language: z.enum(LANGUAGES).nullable(),
  preferences: z.string().max(500),
})
export type SelectionRequest = z.infer<typeof requestSchema>
export type Category = SelectionRequest['category']
export type FormValues = Omit<SelectionRequest, 'budget_kzt' | 'duration_hours'> & {
  budget_kzt: string
  duration_hours: string
}
export type FieldErrors = Partial<Record<keyof FormValues, string>>

export const defaultForm: FormValues = {
  city: 'Алматы',
  event_date: '2026-10-10',
  event_format: 'корпоратив',
  category: 'Ведущий',
  budget_kzt: '1000000',
  duration_hours: '',
  language: null,
  preferences: '',
}

export function parseForm(form: FormValues): { request?: SelectionRequest; errors: FieldErrors } {
  const result = requestSchema.safeParse({
    ...form,
    budget_kzt: Number(form.budget_kzt.replace(/\s/g, '')),
    duration_hours: form.duration_hours.trim() ? Number(form.duration_hours) : null,
    preferences: form.preferences.trim(),
  })
  if (result.success) return { request: result.data, errors: {} }
  const errors: FieldErrors = {}
  for (const issue of result.error.issues) {
    const field = issue.path[0] as keyof FormValues
    errors[field] =
      field === 'budget_kzt'
        ? 'Укажите бюджет от 1 до 1 000 000 000 ₸.'
        : field === 'duration_hours'
          ? 'Укажите длительность больше 0 и не больше 24 часов.'
          : field === 'event_date'
            ? 'Выберите дату с 23 сентября по 31 декабря 2026 года.'
            : 'Проверьте значение поля.'
  }
  return { errors }
}
export function requestToForm(request: SelectionRequest): FormValues {
  return {
    ...request,
    budget_kzt: String(request.budget_kzt),
    duration_hours: request.duration_hours === null ? '' : String(request.duration_hours),
  }
}
export const money = (amount: number) => `${new Intl.NumberFormat('ru-KZ').format(amount)} ₸`
export const dateLabel = (date: string) =>
  new Intl.DateTimeFormat('ru-RU', { day: 'numeric', month: 'long' }).format(
    new Date(`${date}T12:00:00`),
  )
export const plural = (n: number, forms: [string, string, string]) =>
  forms[n % 100 >= 11 && n % 100 <= 14 ? 2 : n % 10 === 1 ? 0 : n % 10 >= 2 && n % 10 <= 4 ? 1 : 2]

export const profileSchema = z.object({
  id: z.string().min(1),
  name: z.string().min(1),
  category: z.enum(CATEGORIES),
  categories: z.array(z.enum(CATEGORIES)).min(1),
  city: z.enum(CITIES),
  price_from_kzt: z.number().nonnegative(),
  event_formats: z.array(z.enum(EVENT_FORMATS)),
  languages: z.array(z.enum(LANGUAGES)),
  max_hours: z.number().positive().nullable(),
  description: z.string().min(1),
  specialty: z.string().min(1),
  features: z.array(
    z.object({ label: z.string(), quote: z.string(), keywords: z.array(z.string()) }),
  ),
  origin: z.enum(['demo', 'catalog', 'synthetic']),
  price_is_estimated: z.boolean(),
  city_is_estimated: z.boolean(),
  artwork: z.enum(['sage', 'clay', 'blue', 'rose', 'sand', 'forest']),
})
export type Profile = z.infer<typeof profileSchema>
export type DemoProfile = Profile & { busy_dates: string[] }
export const reasonCodes = [
  'BUSY',
  'FORMAT_UNSUPPORTED',
  'OVER_BUDGET',
  'LANGUAGE_UNSUPPORTED',
  'DURATION_EXCEEDED',
] as const
export type ReasonCode = (typeof reasonCodes)[number]
export const reasonLabels: Record<ReasonCode, string> = {
  BUSY: 'Заняты на выбранную дату',
  FORMAT_UNSUPPORTED: 'Не работают с этим форматом',
  OVER_BUDGET: 'Цена «от» выше бюджета',
  LANGUAGE_UNSUPPORTED: 'Не работают на выбранном языке',
  DURATION_EXCEEDED: 'Не подходят по длительности',
}
export const recommendationSchema = z.object({
  contractor: profileSchema,
  explanation: z.string().min(1),
  available_on: z.iso.date(),
  matched_preferences: z.array(z.string()),
  evidence: z.array(z.object({ label: z.string(), value: z.string(), source: z.string() })).min(1),
})
export type Recommendation = z.infer<typeof recommendationSchema>
export const responseSchema = z
  .object({
    status: z.enum(['MATCHED', 'CATEGORY_ABSENT', 'NO_MATCH']),
    request: requestSchema,
    catalog_count: z.number().int().nonnegative(),
    eligible_count: z.number().int().nonnegative(),
    recommendations: z.array(recommendationSchema).max(3),
    exclusions: z.array(
      z.object({ code: z.enum(reasonCodes), count: z.number().int().positive() }),
    ),
    alternatives: z.array(
      z.object({
        label: z.string(),
        patch: requestSchema.partial(),
        match_count: z.number().int().positive(),
      }),
    ),
    catalog_version: z.string().min(1),
    ranking_version: z.string().min(1),
  })
  .superRefine((data, ctx) => {
    const fail = (message: string) => ctx.addIssue({ code: 'custom', message })
    if (data.eligible_count > data.catalog_count) fail('Invalid candidate count')
    if (
      data.status === 'MATCHED' &&
      (data.eligible_count < 1 || data.recommendations.length !== Math.min(3, data.eligible_count))
    )
      fail('Invalid matched result')
    if (
      data.status === 'CATEGORY_ABSENT' &&
      (data.catalog_count !== 0 || data.eligible_count !== 0)
    )
      fail('Invalid absent result')
    if (data.status === 'NO_MATCH' && (data.catalog_count < 1 || data.eligible_count !== 0))
      fail('Invalid empty result')
    if (data.status !== 'MATCHED' && data.recommendations.length !== 0) fail('Unexpected cards')
    if (
      new Set(data.recommendations.map((card) => card.contractor.id)).size !==
      data.recommendations.length
    )
      fail('Duplicate profiles')
    if (new Set(data.exclusions.map((item) => item.code)).size !== data.exclusions.length)
      fail('Duplicate reasons')
    if (
      data.exclusions.reduce((sum, item) => sum + item.count, 0) !==
      data.catalog_count - data.eligible_count
    )
      fail('Exclusions must count first failure only')
    for (const card of data.recommendations) {
      const p = card.contractor,
        r = data.request
      if (
        card.available_on !== r.event_date ||
        p.city !== r.city ||
        p.category !== r.category ||
        !p.categories.includes(r.category) ||
        p.price_from_kzt > r.budget_kzt ||
        !p.event_formats.includes(r.event_format) ||
        (r.language && !p.languages.includes(r.language)) ||
        (r.duration_hours !== null && p.max_hours !== null && p.max_hours < r.duration_hours)
      )
        fail('Profile contradicts request')
    }
  })
export type SelectionResponse = z.infer<typeof responseSchema>
