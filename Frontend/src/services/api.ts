import { requestSchema, responseSchema } from '../domain/selection'
import type { SelectionRequest, SelectionResponse } from '../domain/selection'

export const API_URL = import.meta.env.VITE_RECOMMENDATIONS_URL?.trim() ?? ''
export const isDemoMode = !API_URL

export async function getRecommendations(
  request: SelectionRequest,
  signal: AbortSignal,
): Promise<SelectionResponse> {
  const payload = requestSchema.parse(request)
  if (isDemoMode) {
    const { selectDemo } = await import('./demo')
    await new Promise<void>((resolve, reject) => {
      if (signal.aborted) {
        reject(new DOMException('Aborted', 'AbortError'))
        return
      }
      const abort = () => {
        clearTimeout(timer)
        reject(new DOMException('Aborted', 'AbortError'))
      }
      const timer = setTimeout(() => {
        signal.removeEventListener('abort', abort)
        resolve()
      }, 650)
      signal.addEventListener('abort', abort, { once: true })
    })
    return responseSchema.parse(selectDemo(payload))
  }
  const controller = new AbortController()
  const abort = () => controller.abort()
  signal.addEventListener('abort', abort, { once: true })
  if (signal.aborted) controller.abort()
  const timer = setTimeout(
    () => controller.abort(new DOMException('Timeout', 'TimeoutError')),
    10000,
  )
  try {
    const response = await fetch(API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
    if (!response.ok)
      throw new Error(
        response.status === 422
          ? 'Сервер не принял параметры запроса. Проверьте условия и попробуйте ещё раз.'
          : 'Сервис подбора временно недоступен. Попробуйте ещё раз чуть позже.',
      )
    const result = responseSchema.safeParse(await response.json())
    if (!result.success)
      throw new Error('Получен некорректный ответ сервера. Попробуйте повторить подбор.')
    if (JSON.stringify(result.data.request) !== JSON.stringify(payload))
      throw new Error('Сервер вернул результат для других условий. Повторите подбор.')
    return result.data
  } catch (error) {
    if (signal.aborted) throw new DOMException('Aborted', 'AbortError')
    if (controller.signal.aborted)
      throw new Error('Подбор занял больше 10 секунд. Проверьте соединение и повторите попытку.')
    if (error instanceof TypeError)
      throw new Error('Не удалось связаться с сервером. Проверьте соединение и попробуйте ещё раз.')
    if (error instanceof SyntaxError)
      throw new Error('Сервер вернул ответ в неподдерживаемом формате.')
    throw error
  } finally {
    clearTimeout(timer)
    signal.removeEventListener('abort', abort)
  }
}
