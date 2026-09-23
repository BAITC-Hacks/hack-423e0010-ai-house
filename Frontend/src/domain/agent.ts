import { z } from 'zod'
import { CATEGORIES, CITIES, EVENT_FORMATS, LANGUAGES, profileSchema, requestSchema, responseSchema } from './selection'

export const factSchema = z.object({ id: z.string(), label: z.string(), value: z.string(), source: z.string() })
const paragraphSchema = z.object({ text: z.string().min(1).max(2200), evidence_ids: z.array(z.string()).min(1).max(12) })
export const agentReportSchema = z.object({
  title: z.string().min(1).max(160),
  overview: z.array(paragraphSchema).min(1).max(4),
  filtering: z.array(z.object({ title: z.string(), paragraph: paragraphSchema })).min(1).max(6),
  candidates: z.array(z.object({ contractor_id: z.string(), paragraphs: z.array(paragraphSchema).min(1).max(4) })).max(3),
  nearby: z.array(z.object({ option_id: z.string(), paragraphs: z.array(paragraphSchema).min(1).max(4), tradeoff: paragraphSchema })).max(3),
  limitations: z.array(z.string()).min(1).max(5),
  next_step: z.string().min(1).max(800),
})
export type AgentReport = z.infer<typeof agentReportSchema>
export type AgentParagraph = z.infer<typeof paragraphSchema>
export type AgentFact = z.infer<typeof factSchema>
export const nearbySchema = z.object({
  id: z.string(), contractor: profileSchema, request: requestSchema,
  changes: z.array(z.object({ field: z.enum(['event_date', 'budget_kzt', 'language', 'duration_hours']), label: z.string(), before: z.string(), after: z.string() })).min(1),
  original_reasons: z.array(z.string()).min(1), match_count: z.number().int().positive(),
  distance: z.number().nonnegative(),
})
export type NearbyOption = z.infer<typeof nearbySchema>
export const agentResponseSchema = z.object({
  selection: responseSchema, report: agentReportSchema.nullable(),
  nearby_options: z.array(nearbySchema).max(3), facts: z.array(factSchema),
  ai_status: z.enum(['completed', 'unavailable']), ai_error: z.string().nullable(),
  model: z.string(), cached: z.boolean(),
})
export type AgentResponse = z.infer<typeof agentResponseSchema>
export const extractedFieldsSchema = z.object({
  city: z.enum(CITIES).nullable(), event_date: z.string().nullable(), event_format: z.enum(EVENT_FORMATS).nullable(),
  category: z.enum(CATEGORIES).nullable(), budget_kzt: z.number().nullable(),
  duration_hours: z.number().nullable(), language: z.enum(LANGUAGES).nullable(), preferences: z.string(),
})
export const parseModelSchema = z.object({ fields: extractedFieldsSchema, interpretation: z.string(), questions: z.array(z.string()), unverified_requirements: z.array(z.string()) })
export const parseResponseSchema = parseModelSchema.extend({ missing_fields: z.array(z.string()), invalid_fields: z.array(z.string()), ready: z.boolean() })
export type ParsedRequest = z.infer<typeof parseResponseSchema>
