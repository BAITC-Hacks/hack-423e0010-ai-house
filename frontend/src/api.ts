export class ApiError extends Error {
  constructor(message: string, public status: number) {super(message);}
}
export async function api<T>(path: string, body?: unknown, method?: string): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`/api${path}`, {method: method || (body === undefined ? 'GET' : 'POST'), credentials: 'same-origin', headers: body === undefined ? {} : {'Content-Type': 'application/json'}, body: body === undefined ? undefined : JSON.stringify(body), signal: controller.signal});
    const data = await response.json();
    if (!response.ok) {
      const details = data.errors?.map((e: {field: string; message: string}) => `${e.field}: ${e.message}`).join('; ');
      throw new ApiError(details || (typeof data.detail === 'string' ? data.detail : data.detail?.message) || 'Не удалось выполнить запрос', response.status);
    }
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new Error('Нет ответа от сервиса. Проверьте соединение и повторите действие.');
  } finally {clearTimeout(timeout);}
}

