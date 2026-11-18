<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { request } from '../api/client'
import type { Events, HumanTask, Run, TicketDetail, TicketEvent } from '../types'
import { usePolling } from '../composables/usePolling'
import { displayTime, nodeLabels, priorityLabels, reasonLabels, shortTicket } from '../utils/display'
import Icon from '../components/Icon.vue'
import StatusTag from '../components/StatusTag.vue'
import LoadNotice from '../components/LoadNotice.vue'
import ActionPanel from '../components/ActionPanel.vue'
const id = String(useRoute().params.id)
const ticket = ref<TicketDetail | null>(null)
const human = ref<HumanTask | null>(null)
const run = ref<Run | null>(null)
const events = ref<TicketEvent[]>([])
const eventCursor = ref(0)
const visibleEvents = ref(20)
const drawer = ref(false)
const { error, loading, offline, refresh } = usePolling(async signal => {
  const value = await request<TicketDetail>(`/tickets/${id}`, { signal })
  const [task, investigation] = await Promise.all([
    value.human_task_id ? request<HumanTask>(`/human-tasks/${value.human_task_id}`, { signal }) : Promise.resolve(null),
    value.latest_run_id ? request<Run>(`/runs/${value.latest_run_id}`, { signal }) : Promise.resolve(null),
  ])
  let cursor = eventCursor.value
  const added: TicketEvent[] = []
  for (let page = 0; page < 5; page++) {
    const batch = await request<Events>(`/tickets/${id}/events?after_id=${cursor}&limit=100`, { signal })
    added.push(...batch.items)
    cursor = batch.next_after_id
    if (!batch.has_more) break
  }
  if (signal.aborted) return
  ticket.value = value; human.value = task; run.value = investigation
  events.value = [...new Map([...events.value, ...added].map(event => [event.id, event])).values()].sort((a, b) => a.id - b.id)
  eventCursor.value = cursor
})
async function reload() { await refresh(); return !error.value && !offline.value }
const evidence = computed(() => {
  const value = ticket.value?.solution_json.evidence_refs
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
})
function provenance(field: string) {
  const fact = ticket.value?.facts.find(item => item.field === field)
  return fact?.source_type === 'human' ? '人工补充' : fact ? '建单录入' : ''
}
const eventNames: Record<string, string> = {
  'ticket.created': '工单已创建', 'ticket.updated': '工单信息已更新', 'run.started': '调查已开始',
  'run.paused': '等待人工处理', 'human.claimed': '人工待办已认领', 'human.resume_queued': '补充信息已保存',
  'run.requeued': '调查已重新排队', 'run.completed': '处理方案已生成', 'run.stop_requested': '已请求人工接管',
  'solution.reviewed': '方案审核已记录', 'customer.contacted': '已记录联系客户', 'ticket.closed': '结案结果已记录',
  'run.reinvestigation_queued': '新的调查已建立',
}
function eventTitle(event: TicketEvent) {
  return event.event_type === 'node.completed' ? nodeLabels[String(event.payload_json.node_name)] || '调查步骤已完成' : eventNames[event.event_type] || '处理记录已更新'
}
</script>
<template>
  <router-link to="/tickets" class="back-link"><Icon name="back" :size="16" />返回工单队列</router-link><LoadNotice :error="error" :offline="offline" @retry="refresh" /><el-skeleton v-if="loading && !ticket" :rows="8" animated class="panel detail-skeleton" /><section v-else-if="!ticket" class="panel empty-state"><Icon name="file" :size="36" /><h1>暂时无法读取工单</h1><p>请检查工单是否存在，或稍后重试。</p><el-button @click="refresh">重新读取</el-button></section>
  <template v-else><div class="page-heading detail-heading"><div><div class="eyebrow" :title="ticket.ticket_no">{{ shortTicket(ticket.ticket_no) }}</div><h1>工单详情</h1><p>创建于 {{ displayTime(ticket.created_at) }} · 最近更新 {{ displayTime(ticket.updated_at) }}</p></div><StatusTag :status="ticket.status" /></div><div class="detail-layout"><div class="detail-main"><section class="panel summary-panel"><div class="section-title"><span class="section-icon"><Icon name="inbox" :size="18" /></span><h2>问题摘要</h2><span class="priority" :class="ticket.priority">{{ priorityLabels[ticket.priority] }}</span></div><p class="feedback-text wrap-text">{{ ticket.feedback_text }}</p><div class="facts-grid"><div><span class="fact-label">客户邮箱</span><strong>{{ ticket.customer_email }}</strong><span class="source-label">{{ provenance('customer_email') }}</span></div><div><span class="fact-label">设备型号 / 标识</span><strong :class="{ missing: !ticket.device_ref }">{{ ticket.device_ref || '待补充' }}</strong><span class="source-label">{{ provenance('device_ref') }}</span></div><div><span class="fact-label">发生时间（北京时间）</span><strong :class="{ missing: !ticket.occurred_at }">{{ ticket.occurred_at ? displayTime(ticket.occurred_at) : '待补充' }}</strong><span class="source-label">{{ provenance('occurred_at') }}</span></div></div><div v-if="human && ['unclaimed','claimed'].includes(human.status)" class="notice warning"><Icon name="users" :size="18" /><span>{{ reasonLabels[human.reason_code] || '需要人工核查' }}，请在人工操作区域处理。</span></div></section>
      <section v-if="ticket.solution_json.internal_plan" class="panel solution-panel"><div class="section-title"><span class="section-icon"><Icon name="file" :size="18" /></span><h2>内部处理方案</h2><el-tag type="info" size="small">模拟方案</el-tag></div><p class="wrap-text plan-text">{{ ticket.solution_json.internal_plan }}</p><el-button text @click="drawer = true">查看来源说明（{{ evidence.length }}）<Icon name="arrow" :size="16" /></el-button></section>
      <section class="panel timeline-panel"><div class="section-title"><span class="section-icon"><Icon name="clock" :size="18" /></span><h2>处理时间线</h2><span class="muted small">仅显示操作与完成步骤</span></div><div v-if="!events.length" class="muted">暂无处理记录。</div><el-button v-if="events.length > visibleEvents" text @click="visibleEvents += 20">查看更早记录</el-button><ol class="timeline"><li v-for="event in events.slice(-visibleEvents).reverse()" :key="event.id"><span class="timeline-dot"></span><div><strong>{{ eventTitle(event) }}</strong><p v-if="event.payload_json.reason_code" class="muted">{{ reasonLabels[String(event.payload_json.reason_code)] || '请人工核查' }}</p><p v-if="event.payload_json.reason" class="muted wrap-text">{{ event.payload_json.reason }}</p><time>{{ displayTime(event.created_at) }}</time></div></li></ol><div v-if="run" class="timeline-foot">{{ run.status === 'succeeded' ? '本次自动调查已结束，处理结果以人工确认为准。' : '进展会自动更新。' }}</div></section>
    </div><aside class="detail-side"><ActionPanel :ticket="ticket" :human="human" :offline="offline" :reload="reload" /><div class="notice subtle"><Icon name="shield" :size="18" /><span>方案仅供处理参考，结案需要明确确认。</span></div></aside></div></template>
  <el-drawer v-model="drawer" title="来源说明" size="min(460px, 100vw)"><div class="notice subtle">当前使用固定模拟来源，不包含真实文档原文或客户日志。</div><div v-for="reference in evidence" :key="reference" class="evidence-item"><Icon name="file" /><div><strong>{{ reference.includes('knowledge') ? '模拟知识调查记录' : '模拟故障调查记录' }}</strong><p class="muted wrap-text">{{ reference }}</p><el-tag type="info" size="small">模拟来源</el-tag></div></div><p v-if="!evidence.length" class="muted">尚未生成来源引用。</p></el-drawer>
</template>
