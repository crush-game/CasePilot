import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Poller } from '../../src/utils/poller'

describe('页面轮询生命周期', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('前台每两秒更新，隐藏后退避，离开页面停止', async () => {
    const load = vi.fn(async () => {})
    const poller = new Poller(load)
    poller.start()
    await vi.advanceTimersByTimeAsync(4000)
    expect(load).toHaveBeenCalledTimes(3)
    poller.visibility(true)
    await vi.advanceTimersByTimeAsync(29999)
    expect(load).toHaveBeenCalledTimes(4)
    await vi.advanceTimersByTimeAsync(1)
    expect(load).toHaveBeenCalledTimes(5)
    poller.stop()
    await vi.advanceTimersByTimeAsync(60000)
    expect(load).toHaveBeenCalledTimes(5)
  })

  it('断网取消请求，恢复连接立即补取，旧请求不会重建定时器', async () => {
    const signals: AbortSignal[] = []
    const load = vi.fn((signal: AbortSignal) => new Promise<void>(resolve => {
      signals.push(signal)
      signal.addEventListener('abort', () => resolve())
    }))
    const poller = new Poller(load)
    poller.start()
    poller.connectivity(false)
    expect(signals[0].aborted).toBe(true)
    await vi.advanceTimersByTimeAsync(10000)
    expect(load).toHaveBeenCalledTimes(1)
    poller.connectivity(true)
    expect(load).toHaveBeenCalledTimes(2)
    poller.stop()
    await vi.advanceTimersByTimeAsync(60000)
    expect(load).toHaveBeenCalledTimes(2)
  })

  it('请求耗时超过间隔时不叠加请求，失败后继续尝试', async () => {
    const onError = vi.fn()
    let complete: () => void = () => {}
    const load = vi.fn(() => new Promise<void>(resolve => { complete = resolve }))
    const poller = new Poller(load, onError)
    poller.start()
    await vi.advanceTimersByTimeAsync(8000)
    expect(load).toHaveBeenCalledTimes(1)
    complete()
    load.mockRejectedValueOnce(new Error('temporary'))
    await vi.advanceTimersByTimeAsync(2000)
    expect(onError).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(2000)
    expect(load).toHaveBeenCalledTimes(3)
    poller.stop()
  })
})
