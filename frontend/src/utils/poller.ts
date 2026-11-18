export class Poller {
  private timer?: ReturnType<typeof setTimeout>
  private controller?: AbortController
  private stopped = true
  private hidden = false
  private online = true

  constructor(private load: (signal: AbortSignal) => Promise<void>, private onError: (error: unknown) => void = () => {}) {}
  start() { this.stopped = false; this.refresh() }
  stop() { this.stopped = true; clearTimeout(this.timer); this.controller?.abort() }
  visibility(hidden: boolean) { this.hidden = hidden; this.refresh() }
  connectivity(online: boolean) { this.online = online; this.refresh() }

  refresh() {
    clearTimeout(this.timer)
    this.controller?.abort()
    if (this.stopped || !this.online) return Promise.resolve()
    return this.run()
  }

  private async run() {
    const controller = new AbortController()
    this.controller = controller
    try { await this.load(controller.signal) }
    catch (error) { if (!controller.signal.aborted) this.onError(error) }
    finally {
      if (!this.stopped && this.online && this.controller === controller) {
        this.timer = setTimeout(() => void this.run(), this.hidden ? 30000 : 2000)
      }
    }
  }
}
