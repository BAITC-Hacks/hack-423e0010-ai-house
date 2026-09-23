import { createServer } from 'node:http'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { z } from 'zod'
import { requestSchema } from '../src/domain/selection'
import { analyze, MODEL, parseText, publicAIError } from './openai'

const port = Number(process.env.AGENT_PORT || 8787)
const limits = new Map<string, { count: number; reset: number }>()
let active = 0
const send = (res: ServerResponse, status: number, value: unknown) => { res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' }); res.end(JSON.stringify(value)) }
async function readBody(req: IncomingMessage): Promise<unknown> {
  const parts: Buffer[] = []; let bytes = 0
  for await (const part of req) {
    bytes += part.length
    if (bytes > 16000) throw new Error('BODY_LIMIT')
    parts.push(part)
  }
  return JSON.parse(Buffer.concat(parts).toString('utf8'))
}
const server = createServer(async (req, res) => {
  if (req.url === '/api/agent/health' && req.method === 'GET') {
    send(res, 200, { configured: !!process.env.OPENAI_API_KEY, model: MODEL }); return
  }
  if (req.method !== 'POST' || !['/api/agent/analyze', '/api/agent/parse'].includes(req.url ?? '')) { send(res, 404, { error: 'Маршрут не найден.' }); return }
  const origin = req.headers.origin
  if (origin && origin !== process.env.FRONTEND_ORIGIN && !/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin)) { send(res, 403, { error: 'Этот origin не разрешён.' }); return }
  if (!req.headers['content-type']?.startsWith('application/json')) { send(res, 415, { error: 'Ожидается JSON.' }); return }
  const ip = req.socket.remoteAddress || 'local'
  const now = Date.now()
  for (const [key, value] of limits) if (value.reset <= now) limits.delete(key)
  const limit = limits.get(ip) || { count: 0, reset: now + 60000 }
  if (limit.count >= 20 || active >= 3) { send(res, 429, { error: 'Слишком много запросов. Подождите немного и попробуйте ещё раз.' }); return }
  limit.count++; limits.set(ip, limit)
  const controller = new AbortController()
  res.on('close', () => { if (!res.writableEnded) controller.abort() })
  try {
    const body = await readBody(req)
    if (req.url === '/api/agent/analyze') {
      const request = requestSchema.strict().safeParse(body)
      if (!request.success) { send(res, 422, { error: 'Проверьте обязательные поля и диапазон календаря.' }); return }
      active++
      try { send(res, 200, await analyze(request.data, controller.signal)) } finally { active-- }
    } else {
      const parsed = z.object({ message: z.string().trim().min(10).max(2000) }).strict().safeParse(body)
      if (!parsed.success) { send(res, 422, { error: 'Опишите мероприятие: от 10 до 2000 символов.' }); return }
      active++
      try { send(res, 200, await parseText(parsed.data.message, controller.signal)) } finally { active-- }
    }
  } catch (error) {
    if (controller.signal.aborted) return
    if (error instanceof SyntaxError || error instanceof Error && error.message === 'BODY_LIMIT') send(res, 400, { error: 'Не удалось прочитать запрос. Проверьте формат и размер JSON.' })
    else send(res, 502, { error: publicAIError(error) })
  }
})
server.listen(port, '127.0.0.1', () => console.log(`Tandau agent: http://127.0.0.1:${port} (${process.env.OPENAI_API_KEY ? 'key configured' : 'key missing'})`))
server.on('error', (error: NodeJS.ErrnoException) => { console.error(error.code === 'EADDRINUSE' ? `Port ${port} is already in use. Stop the previous agent server.` : 'Agent server could not start.'); process.exit(1) })
