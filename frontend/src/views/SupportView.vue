<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError, errorMessage, request } from '../api/client'
import LoadNotice from '../components/LoadNotice.vue'
import { usePolling } from '../composables/usePolling'
import { useSession } from '../stores/session'
import type { components } from '../types/openapi'
import { statusLabels } from '../utils/display'

type Message = components['schemas']['SupportMessage']
type Conversation = components['schemas']['SupportConversationView']
type Detail = components['schemas']['SupportDetail']
type Accepted = components['schemas']['SupportAccepted']
const session = useSession()
const router = useRouter()
const storageKey = `casepilot.support.${session.user?.id}`
function restoreDraft(): { active?: string; text?: string; product?: string; firmware?: string; pending?: Message } {
  try { return JSON.parse(sessionStorage.getItem(storageKey) ?? '{}') ?? {} }
  catch { return {} }
}
const stored = restoreDraft()
const active = ref(stored.active || '')
const text = ref(stored.text || '')
const product = ref(stored.product || '')
const firmware = ref(stored.firmware || '')
const pending = ref<Message | null>(stored.pending || null)
const history = ref<Conversation[]>([])
const current = ref<Detail | null>(null)
const sending = ref(false)
const actionError = ref('')
watch([active, text, product, firmware, pending], () => {
  sessionStorage.setItem(storageKey, JSON.stringify({
    active: active.value, text: text.value, product: product.value, firmware: firmware.value, pending: pending.value,
  }))
}, { flush: 'sync' })
const { loading, error, offline, refresh } = usePolling(async signal => {
  const selected = active.value
  const [rows, detail] = await Promise.all([
    request<Conversation[]>('/support/conversations', { signal }),
    selected ? request<Detail>(`/support/conversations/${selected}`, { signal }) : Promise.resolve(null),
  ])
  if (!signal.aborted && selected === active.value) { history.value = rows; current.value = detail }
})
const lastReply = computed(() => current.value?.turns.at(-1)?.reply_json.kind)
const closed = computed(() => ['RESOLVED', 'CLOSED_UNRESOLVED'].includes(current.value?.ticket_status ?? ''))
async function selectConversation(id: string) {
  active.value = id
  current.value = null
  text.value = product.value = firmware.value = actionError.value = ''
  await refresh()
}
async function submit(action: NonNullable<Message['action']> = 'message') {
  if (sending.value || offline.value || closed.value) return
  if (!pending.value) {
    if (action === 'message' && !text.value.trim()) { actionError.value = '请填写问题。'; return }
    if (action === 'clarify' && (!product.value.trim() || !firmware.value.trim())) {
      actionError.value = '请填写设备型号和固件版本，或转人工。'; return
    }
    pending.value = { action_id: crypto.randomUUID(), action, conversation_id: active.value || null,
      text: text.value.trim(), product_ref: product.value.trim() || null, firmware_version: firmware.value.trim() || null }
  }
  sending.value = true
  actionError.value = ''
  try {
    const result = await request<Accepted>('/support/turns', { method: 'POST', body: JSON.stringify(pending.value) })
    const previous = current.value?.id === result.id ? current.value.turns : []
    current.value = { ...result, turns: [...previous.filter(turn => turn.id !== result.turn.id), result.turn] }
    active.value = result.id
    pending.value = null
    text.value = product.value = firmware.value = ''
    await refresh()
  } catch (failure) {
    actionError.value = errorMessage(failure)
    if (failure instanceof ApiError && [400, 403, 404, 409, 422].includes(failure.status)) pending.value = null
  } finally { sending.value = false }
}
async function logout() {
  try { await session.logout(); sessionStorage.removeItem(storageKey); await router.replace('/login') }
  catch (failure) { actionError.value = errorMessage(failure) }
}
</script>

<template>
  <main class="support-view">
    <header class="page-heading">
      <div><h1>售后客服</h1><p>提问、补充设备信息或查看人工处理进度。</p></div>
      <el-button :disabled="sending" @click="logout">退出登录</el-button>
    </header>
    <LoadNotice :error="error" :offline="offline" @retry="refresh" />
    <div v-if="actionError" class="notice danger" role="alert">{{ actionError }}</div>
    <section class="panel support-panel">
      <div class="action-buttons support-history">
        <label for="support-history">会话</label>
        <select id="support-history" :value="active" class="control" :disabled="sending || !!pending"
          @change="selectConversation(($event.target as HTMLSelectElement).value)">
          <option value="">新会话</option>
          <option v-for="(row, index) in history" :key="row.id" :value="row.id">{{ row.ticket_no || `会话 ${history.length - index}` }}</option>
        </select>
        <el-button :disabled="!active || sending || !!pending" @click="selectConversation('')">新会话</el-button>
      </div>
      <p v-if="current?.ticket_no && current.ticket_status" class="notice subtle" role="status">
        工单 {{ current.ticket_no }} · {{ statusLabels[current.ticket_status] }}
      </p>
      <p v-if="loading && !current" class="muted">正在读取会话。</p>
      <div aria-live="polite" class="support-messages">
        <article v-for="turn in current?.turns" :key="turn.id">
          <p v-if="turn.request_text" class="support-request wrap-text">{{ turn.request_text }}</p>
          <p class="wrap-text">{{ turn.reply_json.text }}</p>
          <p v-if="turn.reply_json.service_window" class="muted">{{ turn.reply_json.service_window }}</p>
          <p v-if="turn.reply_json.evidence_title" class="muted small">来源：{{ turn.reply_json.evidence_title }}</p>
        </article>
      </div>
      <p v-if="closed" class="muted">此工单已结案。如需继续，请开启新会话。</p>
      <form v-else @submit.prevent="submit(lastReply === 'clarify' ? 'clarify' : 'message')">
        <div v-if="lastReply === 'clarify'" class="support-scope">
          <div class="field"><label for="support-product">设备型号</label>
            <el-input id="support-product" v-model="product" :maxlength="120" :disabled="!!pending" /></div>
          <div class="field"><label for="support-firmware">固件版本</label>
            <el-input id="support-firmware" v-model="firmware" :maxlength="120" :disabled="!!pending" /></div>
        </div>
        <div v-else class="field"><label for="support-question">{{ current?.ticket_no ? '补充信息' : '问题' }}</label>
          <el-input id="support-question" v-model="text" type="textarea" :rows="3" :maxlength="2000" :disabled="!!pending" /></div>
        <div class="action-buttons">
          <el-button type="primary" native-type="submit" :loading="sending" :disabled="offline">
            {{ pending ? '重试提交' : lastReply === 'clarify' ? '提交设备信息' : '发送' }}
          </el-button>
          <el-button v-if="!current?.ticket_no" :disabled="offline || sending || !!pending" @click="submit('handoff')">转人工</el-button>
          <el-button v-if="lastReply === 'answer'" :disabled="offline || sending || !!pending" @click="submit('solved')">已解决</el-button>
        </div>
        <p v-if="offline" class="muted">离线期间输入保留在当前标签页，联网后可以提交。</p>
        <p v-else-if="pending && !sending" class="muted">提交结果待确认。重试沿用原请求。</p>
      </form>
    </section>
  </main>
</template>

<style scoped>
.support-view { max-width: 760px; margin: 0 auto; padding: 24px 16px; }
.support-panel { padding: 20px; }
.support-history { align-items: center; margin-bottom: 16px; }
.support-history select { min-width: 0; max-width: 100%; }
.support-messages article { padding: 12px 0; border-bottom: 1px solid var(--line); }
.support-request { margin: 0; font-weight: 650; }
.support-panel form { margin-top: 20px; }
.support-scope { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
</style>
