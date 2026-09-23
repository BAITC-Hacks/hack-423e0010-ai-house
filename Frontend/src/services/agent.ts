import { z } from 'zod'
import { agentResponseSchema, parseResponseSchema } from '../domain/agent'
import type { SelectionRequest, SelectionResponse } from '../domain/selection'

const base = (import.meta.env.VITE_AGENT_API_URL?.trim() || '/api/agent').replace(/\/$/, '')
async function post<T>(route: string, body: unknown, schema: z.ZodType<T>, signal: AbortSignal): Promise<T> {
  const timeout = AbortSignal.timeout(65000)
  try {
    const response = await fetch(`${base}/${route}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal: AbortSignal.any([signal, timeout]) })
    const data = await response.json().catch(() => null)
    if (!response.ok) throw new Error(data?.error || 'Сервис агента временно недоступен. Подбор по каталогу сохранён.')
    const parsed = schema.safeParse(data)
    if (!parsed.success) throw new Error('Агент вернул неподтверждённый ответ. Повторите разбор.')
    return parsed.data
  } catch (error) {
    if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
    if (timeout.aborted) throw new Error('Агент не успел завершить разбор. Попробуйте повторить запрос.')
    if (error instanceof TypeError) throw new Error('Не удалось подключиться к агенту. Основной подбор остаётся доступен.')
    throw error
  }
}
export const parseNaturalRequest = (message: string, signal: AbortSignal) => post('parse', { message }, parseResponseSchema, signal)
export async function explainSelection(request: SelectionRequest, expected: SelectionResponse, signal: AbortSignal) {
  const data = await post('analyze', request, agentResponseSchema, signal)
  const fingerprint = (r: SelectionResponse) => JSON.stringify([r.request, r.catalog_version, r.ranking_version, r.status, r.catalog_count, r.eligible_count, r.recommendations.map((c) => c.contractor.id)])
  if (fingerprint(data.selection) !== fingerprint(expected)) throw new Error('Каталог агента отличается от каталога подбора. Для объяснения нужно синхронизировать данные сервисов.')
  return data
}
