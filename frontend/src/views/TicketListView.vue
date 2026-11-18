<script setup lang="ts">
import { ref, watch } from 'vue'
import { request } from '../api/client'
import type { Ticket, TicketList, TicketStatus, Priority } from '../types'
import { usePolling } from '../composables/usePolling'
import { useSession } from '../stores/session'
import { statusLabels, priorityLabels, displayTime, shortTicket } from '../utils/display'
import Icon from '../components/Icon.vue'
import StatusTag from '../components/StatusTag.vue'
import LoadNotice from '../components/LoadNotice.vue'
const items = ref<Ticket[]>([])
const status = ref<TicketStatus | ''>('')
const priority = ref<Priority | ''>('')
const mine = ref(false)
const cursor = ref<string | null>(null)
const next = ref<string | null>(null)
const previous = ref<(string | null)[]>([])
const session = useSession()
const { loading, error, offline, refresh } = usePolling(async signal => {
  const params = new URLSearchParams({ limit: '20' })
  if (status.value) params.set('status', status.value)
  if (priority.value) params.set('priority', priority.value)
  if (mine.value && session.user) params.set('assignee_id', session.user.id)
  if (cursor.value) params.set('cursor', cursor.value)
  const result = await request<TicketList>(`/tickets?${params}`, { signal })
  if (!signal.aborted) { items.value = result.items; next.value = result.next_cursor ?? null }
})
watch([status, priority, mine], () => { cursor.value = null; previous.value = []; refresh() })
function paginate(forward: boolean) {
  if (forward && next.value) { previous.value.push(cursor.value); cursor.value = next.value }
  else if (!forward && previous.value.length) cursor.value = previous.value.pop() ?? null
  refresh()
}
</script>
<template>
  <div class="page-heading"><div><div class="eyebrow">工单管理</div><h1>工单队列</h1><p>跟踪每一次处理，在需要时及时介入。</p></div><router-link to="/tickets/new" class="button-link primary"><Icon name="plus" :size="18" />新建工单</router-link></div>
  <LoadNotice :error="error" :offline="offline" @retry="refresh" />
  <section class="panel"><div class="panel-toolbar"><div class="filter-group"><label for="ticket-status" class="sr-only">工单状态</label><select id="ticket-status" v-model="status" class="control"><option value="">全部状态</option><option v-for="(label, value) in statusLabels" :key="value" :value="value">{{ label }}</option></select><label for="ticket-priority" class="sr-only">优先级筛选</label><select id="ticket-priority" v-model="priority" class="control"><option value="">全部优先级</option><option v-for="(label, value) in priorityLabels" :key="value" :value="value">{{ label }}</option></select><el-checkbox v-model="mine">只看分配给我</el-checkbox></div><el-button text @click="refresh"><Icon name="refresh" :size="16" />刷新</el-button></div>
    <el-skeleton v-if="loading" :rows="5" animated class="table-skeleton" /><div v-else-if="!items.length" class="empty-state"><Icon name="inbox" :size="38" /><h2>这里还没有工单</h2><p>试试调整筛选条件，或创建一张新工单。</p><router-link to="/tickets/new" class="button-link secondary">新建工单</router-link></div>
    <div v-else class="table-wrap"><table class="data-table"><thead><tr><th>工单 / 问题</th><th class="optional-column">客户邮箱</th><th>处理状态</th><th class="optional-column">优先级</th><th class="optional-column">创建时间</th><th><span class="sr-only">操作</span></th></tr></thead><tbody><tr v-for="ticket in items" :key="ticket.id"><td class="feedback-cell"><router-link :to="`/tickets/${ticket.id}`" class="ticket-title">{{ ticket.feedback_text }}</router-link><span class="ticket-number" :title="ticket.ticket_no">{{ shortTicket(ticket.ticket_no) }}</span></td><td class="optional-column">{{ ticket.customer_email }}</td><td><StatusTag :status="ticket.status" /></td><td class="optional-column"><span class="priority" :class="ticket.priority">{{ priorityLabels[ticket.priority] }}</span></td><td class="optional-column muted">{{ displayTime(ticket.created_at) }}</td><td><router-link :to="`/tickets/${ticket.id}`" class="table-action" :aria-label="`查看工单：${ticket.feedback_text}`"><Icon name="arrow" :size="18" /></router-link></td></tr></tbody></table></div>
    <div class="pagination"><span class="muted">本页 {{ items.length }} 条 · 自动更新</span><div><el-button :disabled="!previous.length" @click="paginate(false)">上一页</el-button><el-button :disabled="!next" @click="paginate(true)">下一页</el-button></div></div>
  </section>
</template>
