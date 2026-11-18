import { onMounted, onUnmounted, ref } from 'vue'
import { errorMessage } from '../api/client'
import { Poller } from '../utils/poller'

export function usePolling(load: (signal: AbortSignal) => Promise<void>) {
  const error = ref('')
  const offline = ref(!navigator.onLine)
  const loading = ref(true)
  const poller = new Poller(async signal => {
    try { await load(signal); if (!signal.aborted) error.value = '' }
    finally { if (!signal.aborted) loading.value = false }
  }, failure => { error.value = errorMessage(failure); loading.value = false })
  const visibility = () => poller.visibility(document.hidden)
  const network = () => { offline.value = !navigator.onLine; poller.connectivity(navigator.onLine) }
  onMounted(() => {
    poller.visibility(document.hidden)
    poller.connectivity(navigator.onLine)
    poller.start()
    document.addEventListener('visibilitychange', visibility)
    window.addEventListener('online', network)
    window.addEventListener('offline', network)
  })
  onUnmounted(() => {
    poller.stop()
    document.removeEventListener('visibilitychange', visibility)
    window.removeEventListener('online', network)
    window.removeEventListener('offline', network)
  })
  return { error, offline, loading, refresh: () => poller.refresh() }
}
