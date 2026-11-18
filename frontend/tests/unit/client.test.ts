import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { ActionIdentity, request, setCsrf } from '../../src/api/client'

beforeEach(() => {
  const data = new Map<string, string>()
  vi.stubGlobal('sessionStorage', { getItem: (key: string) => data.get(key), setItem: (key: string, value: string) => data.set(key, value), removeItem: (key: string) => data.delete(key) })
  vi.stubGlobal('window', new EventTarget())
})
afterEach(() => { vi.unstubAllGlobals(); vi.useRealTimers() })

it('丢失响应后重试同一操作沿用标识，修改输入才创建新标识', () => {
  const identity = new ActionIdentity()
  const first = identity.forPayload('resume', { expected_version: 3, device: 'D' })
  expect(identity.forPayload('resume', { expected_version: 3, device: 'D' })).toBe(first)
  expect(identity.forPayload('resume', { expected_version: 4, device: 'D' })).not.toBe(first)
})

it('写请求附带 CSRF 与同源 Cookie，GET 不附带写令牌', async () => {
  const fetcher = vi.fn(async (_url: string, _options: RequestInit) => new Response('{}', { status: 200 }))
  vi.stubGlobal('fetch', fetcher)
  setCsrf('test-only-csrf')
  await request('/tickets', { method: 'POST', body: '{}' })
  expect(fetcher.mock.calls[0][1].credentials).toBe('same-origin')
  expect(new Headers(fetcher.mock.calls[0][1].headers).get('X-CSRF-Token')).toBe('test-only-csrf')
  await request('/tickets')
  expect(new Headers(fetcher.mock.calls[1][1].headers).has('X-CSRF-Token')).toBe(false)
})

it('会话失效通知应用，登录失败保持在登录表单', async () => {
  const expired = vi.fn()
  window.addEventListener('casepilot:auth-expired', expired)
  vi.stubGlobal('fetch', async () => new Response('{}', { status: 401 }))
  await expect(request('/auth/login', { method: 'POST' })).rejects.toMatchObject({ status: 401 })
  expect(expired).not.toHaveBeenCalled()
  await expect(request('/auth/me')).rejects.toMatchObject({ status: 401 })
  expect(expired).toHaveBeenCalledTimes(1)
})

it('请求超时可重试，页面取消保持 AbortError', async () => {
  vi.useFakeTimers()
  vi.stubGlobal('fetch', (_url: string, options: RequestInit) => new Promise((_resolve, reject) => {
    options.signal?.addEventListener('abort', () => reject(new DOMException('cancelled', 'AbortError')))
  }))
  const timeout = expect(request('/tickets', { method: 'POST', body: '{}' })).rejects.toMatchObject({ status: 0, code: 'TIMEOUT' })
  await vi.advanceTimersByTimeAsync(15000)
  await timeout
  const controller = new AbortController()
  const cancelled = expect(request('/tickets', { signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' })
  controller.abort()
  await cancelled
})
