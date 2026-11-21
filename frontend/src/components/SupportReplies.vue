<script setup lang="ts">
import { computed, ref } from 'vue'
import { ApiError, errorMessage, request } from '../api/client'
import { usePolling } from '../composables/usePolling'
import { useSession } from '../stores/session'
import type { TicketDetail } from '../types'
import type { components } from '../types/openapi'

type Delivery = components['schemas']['DeliveryView']
type Reply = components['schemas']['SupportAgentReply']
const props = defineProps<{ ticket: TicketDetail }>()
const path = `/tickets/${props.ticket.id}/support-replies`
const session = useSession()
const canReply = computed(() => props.ticket.assignee_id === session.user?.id)
const replies = ref<Delivery[]>([])
const text = ref('')
const pending = ref<Reply | null>(null)
const saving = ref(false)
const message = ref('')
const labels = { queued: '等待发送', delivered: '已送达', failed: '发送失败' }
const { error, offline, refresh } = usePolling(async signal => {
  const rows = await request<Delivery[]>(path, { signal })
  if (!signal.aborted) replies.value = rows
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
    <p v-else class="muted">认领后可回复。</p>
  </section>
</template>
