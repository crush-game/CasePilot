const CSRF_KEY = 'casepilot.csrf'

export function csrfToken(): string {
  return sessionStorage.getItem(CSRF_KEY) || ''
}

export function setCsrf(token: string) {
  if (token) sessionStorage.setItem(CSRF_KEY, token)
  else sessionStorage.removeItem(CSRF_KEY)
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code = '',
    public requestId = '',
  ) { super(message) }
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body) headers.set('Content-Type', 'application/json')
  if (options.method && !['GET', 'HEAD'].includes(options.method)) {
    headers.set('X-CSRF-Token', csrfToken())
  }
  let response: Response
  const controller = new AbortController()
  let timedOut = false
  const abort = () => controller.abort()
  options.signal?.addEventListener('abort', abort, { once: true })
  if (options.signal?.aborted) controller.abort()
  const timeout = setTimeout(() => { timedOut = true; controller.abort() }, 15000)
  try {
    response = await fetch(`/api/v1${path}`, { ...options, headers, credentials: 'same-origin', signal: controller.signal })
    if (!response.ok) {
      const value = await response.json().catch(() => ({}))
      if (response.status === 401 && path !== '/auth/login') window.dispatchEvent(new Event('casepilot:auth-expired'))
      throw new ApiError(response.status, value.error?.message || '服务暂不可用，请稍后重试。', value.error?.code, value.request_id)
    }
    if (response.status === 204) return undefined as T
    return await response.json()
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (options.signal?.aborted) throw new DOMException('页面请求已取消', 'AbortError')
    if (timedOut) throw new ApiError(0, '请求超时，结果尚未确认，请刷新状态或重试。', 'TIMEOUT')
    if (error instanceof SyntaxError) throw new ApiError(502, '服务响应异常，请稍后重试。', 'INVALID_RESPONSE')
    throw new ApiError(0, '网络连接中断，请检查网络后重试。')
  } finally {
    clearTimeout(timeout)
    options.signal?.removeEventListener('abort', abort)
  }
}

export function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : '操作失败，请稍后重试。'
}

export class ActionIdentity {
  private fingerprint = ''
  private value = ''

  forPayload(operation: string, payload: unknown): string {
    const fingerprint = JSON.stringify([operation, payload])
    if (fingerprint !== this.fingerprint) {
      this.fingerprint = fingerprint
      this.value = crypto.randomUUID()
    }
    return this.value
  }

  clear() { this.fingerprint = ''; this.value = '' }
}
