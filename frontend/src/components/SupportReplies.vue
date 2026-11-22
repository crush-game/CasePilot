<script setup lang="ts">
import { computed, ref } from 'vue'
import { ApiError, errorMessage, request } from '../api/client'
import { usePolling } from '../composables/usePolling'
import { useSession } from '../stores/session'
import { displayTime } from '../utils/display'
import type { TicketDetail } from '../types'
import type { components } from '../types/openapi'

type Delivery = components['schemas']['DeliveryView']
type Reply = components['schemas']['SupportAgentReply']
type Conversation = components['schemas']['SupportDetail']
const props = defineProps<{ ticket: TicketDetail }>()
const path = `/tickets/${props.ticket.id}/support-replies`
const session = useSession()
const canReply = computed(() => props.ticket.assignee_id === session.user?.id &&
  !['RESOLVED', 'CLOSED_UNRESOLVED'].includes(props.ticket.status))
const replies = ref<Delivery[]>([])
const conversation = ref<Conversation | null>(null)
const text = ref('')
const pending = ref<Reply | null>(null)
const saving = ref(false)
const message = ref('')
const labels = { queued: '等待发送', delivered: '已送达', failed: '发送失败' }
const { error, offline, refresh } = usePolling(async signal => {
  const [rows, thread] = await Promise.all([
    request<Delivery[]>(path, { signal }),
    request<Conversation>(`/tickets/${props.ticket.id}/support-conversation`, { signal }),
  ])
  if (!signal.aborted) { replies.value = rows; conversation.value = thread }
})
async function send() {
  if (!canReply.value || saving.value || offline.value || (!pending.value && !text.value.trim())) return
  pending.value ??= { action_id: crypto.randomUUID(), expected_version: props.ticket.version, text: text.value.trim() }
  saving.value = true
  message.value = ''
  try {
    await request(path, { method: 'POST', body: JSON.stringify(pending.value) })
    pending.value = null
    text.value = ''
    await refresh()
  } catch (failure) {
    message.value = errorMessage(failure)
    if (failure instanceof ApiError && [403, 404, 409, 422].includes(failure.status)) pending.value = null
  } finally { saving.value = false }
}
</script>

<template>
  <section class="panel solution-panel">
    <div class="section-title"><h2>消费者回传</h2></div>
    <p v-if="error || message" class="notice danger" role="alert">{{ message || error }}</p>
    <details v-if="conversation?.turns.length">
      <summary>查看原客服会话</summary>
      <div v-for="turn in conversation.turns" :key="turn.id">
        <p v-if="turn.request_text" class="wrap-text">客户 · {{ turn.request_text }}</p>
        <p class="wrap-text">{{ turn.reply_json.kind === 'agent_reply' ? '人工客服' : '系统' }} · {{ turn.reply_json.text }}</p>
        <p class="muted small">{{ displayTime(turn.created_at) }}</p>
      </div>
    </details>
    <p v-if="!replies.length" class="muted">暂无回传记录。</p>
    <div v-for="item in replies" :key="item.id">
      <p class="wrap-text">{{ item.text }}</p>
      <p class="muted">{{ labels[item.status] }} · {{ item.channel === 'app' ? 'App' : '模拟渠道' }}
        <span v-if="item.attempts"> · 尝试 {{ item.attempts }} 次</span></p>
    </div>
    <form v-if="canReply" @submit.prevent="send">
      <div class="field"><label for="support-reply">给消费者的回复</label>
        <el-input id="support-reply" v-model="text" type="textarea" :rows="3" :maxlength="2000" :disabled="!!pending" />
      </div>
      <el-button type="primary" native-type="submit" :loading="saving" :disabled="offline">
        {{ pending ? '重试排队' : '将回复加入发送队列' }}
      </el-button>
    </form>
    <p v-else-if="['WAITING_HUMAN', 'PENDING_CONFIRMATION'].includes(ticket.status)" class="muted">认领或审核后可回复。</p>
  </section>
</template>
