import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defaultForm, parseForm } from '../src/domain/selection'
import { selectDemo } from '../src/services/demo'
const request = parseForm(defaultForm).request!

beforeEach(() => {
  vi.resetModules()
  vi.stubEnv('VITE_RECOMMENDATIONS_URL', 'https://backend.example/api/recommendations')
})
afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('Single endpoint adapter', () => {
  it('POSTs the exact JSON payload and returns backend results', async () => {
    const response = selectDemo(request)
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(response)))
    vi.stubGlobal('fetch', fetchMock)
    const { getRecommendations, isDemoMode } = await import('../src/services/api')
    expect(isDemoMode).toBe(false)
    expect(await getRecommendations(request, new AbortController().signal)).toEqual(response)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('https://backend.example/api/recommendations')
    expect(init.method).toBe('POST')
    expect(init.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(init.body)).toEqual(request)
  })
  it('does not replace a backend error with demo cards or an empty result', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('Failed', { status: 503 })))
    const { getRecommendations } = await import('../src/services/api')
    await expect(getRecommendations(request, new AbortController().signal)).rejects.toThrow(
      'временно недоступен',
    )
  })
  it('rejects malformed response data and mismatched echoed requests', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ status: 'MATCHED' })))
      .mockResolvedValueOnce(
        new Response(JSON.stringify(selectDemo({ ...request, budget_kzt: 1500000 }))),
      )
    vi.stubGlobal('fetch', fetchMock)
    const { getRecommendations } = await import('../src/services/api')
    await expect(getRecommendations(request, new AbortController().signal)).rejects.toThrow(
      'некорректный ответ',
    )
    await expect(getRecommendations(request, new AbortController().signal)).rejects.toThrow(
      'других условий',
    )
  })
  it('handles cancellation and a ten-second timeout distinctly', async () => {
    vi.useFakeTimers()
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_url, { signal }) =>
          new Promise((_resolve, reject) => {
            if (signal.aborted) reject(signal.reason)
            else signal.addEventListener('abort', () => reject(signal.reason), { once: true })
          }),
      ),
    )
    const { getRecommendations } = await import('../src/services/api')
    const controller = new AbortController()
    const cancelled = expect(getRecommendations(request, controller.signal)).rejects.toMatchObject({
      name: 'AbortError',
    })
    controller.abort()
    await cancelled
    const timedOut = expect(
      getRecommendations(request, new AbortController().signal),
    ).rejects.toThrow('больше 10 секунд')
    await vi.advanceTimersByTimeAsync(10001)
    await timedOut
  })
})
