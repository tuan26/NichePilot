// API client (T053 – FR-061): gửi CSRF header cho thao tác thay đổi dữ liệu, chuẩn hóa lỗi problem+json theo `code`.
const UNSAFE = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly params: Record<string, string>

  constructor(status: number, code: string, params: Record<string, string> = {}) {
    super(code)
    this.status = status
    this.code = code
    this.params = params
  }
}

function readCookie(name: string): string | undefined {
  return document.cookie
    .split('; ')
    .find((c) => c.startsWith(`${name}=`))
    ?.slice(name.length + 1)
}

export async function api<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  const method = init.method ?? 'GET'
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (init.body !== undefined) headers['Content-Type'] = 'application/json'
  if (UNSAFE.has(method)) {
    const csrf = readCookie('np_csrf')
    if (csrf) headers['X-CSRF-Token'] = csrf
  }
  let res: Response
  try {
    res = await fetch(path, {
      method,
      headers,
      credentials: 'same-origin',
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    })
  } catch {
    throw new ApiError(0, 'NETWORK')
  }
  if (res.status === 204) return undefined as T
  const data: unknown = await res.json().catch(() => ({}))
  if (!res.ok) {
    const problem = data as { code?: string; params?: Record<string, string> }
    throw new ApiError(res.status, problem.code ?? 'INTERNAL_ERROR', problem.params ?? {})
  }
  return data as T
}

/** Khóa i18n cho một lỗi bất kỳ. */
export function errorKey(err: unknown): string {
  if (err instanceof ApiError) return err.code === 'NETWORK' ? 'errors.network' : `errors.${err.code}`
  return 'errors.generic'
}
