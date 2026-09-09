export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

// pydantic adds this prefix to custom validation errors; it means nothing to users
const VALUE_ERROR = /^Value error,\s*/

function messageOf(item: unknown): string {
  if (typeof item === 'string') return item.trim()
  if (!item || typeof item !== 'object') return ''
  const { msg, message } = item as { msg?: unknown; message?: unknown }
  return messageOf(msg ?? message).replace(VALUE_ERROR, '')
}

/** When FastAPI validation fails, detail is a `{loc, msg, type}` array; rendered as-is it would show [object Object]. */
function formatDetail(detail: unknown, fallback: string): string {
  if (Array.isArray(detail)) {
    return detail.map(messageOf).filter(Boolean).join('; ') || fallback
  }
  return messageOf(detail) || fallback
}

/** Uploads and downloads use native fetch; their errors are all built here so messages match JSON requests. */
export async function apiError(response: Response, fallback: string): Promise<ApiError> {
  const body = await response.json().catch(() => null)
  return new ApiError(response.status, formatDetail(body?.detail, fallback))
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })

  if (!response.ok) throw await apiError(response, response.statusText)
  return response.status === 204 ? (undefined as T) : response.json()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
