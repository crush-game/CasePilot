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
import SupportReplies from '../components/SupportReplies.vue'
import ExperienceHints from '../components/ExperienceHints.vue'
import type { components } from '../types/openapi'
const id = String(useRoute().params.id)
const ticket = ref<TicketDetail | null>(null)
const human = ref<HumanTask | null>(null)
const run = ref<Run | null>(null)
const events = ref<TicketEvent[]>([])
const eventCursor = ref(0)
const visibleEvents = ref(20)
const drawer = ref(false)
const citations = ref<Record<string, { title: string; text: string; document_version?: number; source_type?: string; occurred_at?: string; start_line: number; end_line: number; usable: boolean }>>({})
const sourceError = ref('')
const scopeFields = [{ key: 'product_ref', label: '产品型号' }, { key: 'firmware_version', label: '固件版本' }, { key: 'region', label: '适用地区' }, { key: 'channel', label: '业务渠道' }, { key: 'platform', label: '设备平台' }, { key: 'app_version', label: 'App版本' }] as const
function factValue(field: string) { const value = [...(ticket.value?.facts || [])].sort((a, b) => b.fact_version - a.fact_version).find(row => row.field === field)?.value_json.value; return typeof value === 'string' ? value : '' }
const recallScope = computed<components['schemas']['RecallQuery'] | null>(() => {
  const product = factValue('product_ref')
  const version = factValue('firmware_version')
  if (!ticket.value || !product || !version) return null
  const platform = factValue('platform')
  return {
    query: ticket.value.feedback_text.slice(0, 500), product_ref: product, firmware_version: version,
    region: factValue('region') || null, channel: factValue('channel') || null,
    app_version: factValue('app_version') || null, platform: platform === 'android' || platform === 'ios' ? platform : null,
  }
})
async function openSources() {
  drawer.value = true; sourceError.value = ''; citations.value = {}
  const scope = new URLSearchParams(scopeFields.filter(field => !['platform', 'app_version'].includes(field.key)).flatMap(field => factValue(field.key) ? [[field.key, factValue(field.key)]] : []))
  await Promise.all(evidence.value.filter(ref => ref.startsWith('kb:') || ref.startsWith('logev:')).map(async ref => {
    try { citations.value[ref] = await request(ref.startsWith('kb:') ? `/knowledge/chunks/${ref.slice(3)}?${scope}` : `/tickets/${id}/evidence/${ref.slice(6)}`) }
    catch { sourceError.value = '部分引用暂时无法读取，请稍后重试。' }
  }))
}
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
  const value = ticket.value?.solution_json.evidence_refs || human.value?.payload_json.evidence_refs
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
})
type FaultReport = { inspected_domains: string[]; source_kind: string; viewed_range: { start?: string; end?: string }; findings: { point: string; applicability: string }[]; candidate_causes: { hypothesis: string; required_verification: string }[]; limitations: string[] }
const faultReport = computed(() => {
  const value = ticket.value?.solution_json.fault_report || human.value?.payload_json.fault_report
  return value && typeof value === 'object' && 'findings' in value && Array.isArray(value.findings) ? value as FaultReport : null
})
const solutionFacts = computed(() => {
  const facts = ticket.value?.solution_json.confirmed_facts
  return facts && typeof facts === 'object' ? scopeFields.filter(field => field.key in facts).map(field => ({
    label: field.label, value: String((facts as Record<string, unknown>)[field.key]),
  })) : []
})
const solutionObservations = computed(() => {
  const rows = ticket.value?.solution_json.observations
  return Array.isArray(rows) ? rows as { point: string; applicability: string }[] : []
})
function provenance(field: string) {
  const fact = [...(ticket.value?.facts || [])].sort((a, b) => b.fact_version - a.fact_version).find(item => item.field === field)
  return fact?.source_type === 'human' ? '人工补充' : fact ? '建单录入' : ''
}
const eventNames: Record<string, string> = {
  'ticket.created': '工单已创建', 'ticket.updated': '工单信息已更新', 'run.started': '调查已开始',
  'run.paused': '等待人工处理', 'human.claimed': '人工待办已认领', 'human.resume_queued': '补充信息已保存',
  'run.requeued': '调查已重新排队', 'run.completed': '处理方案已生成', 'run.stop_requested': '已请求人工接管',
  'solution.reviewed': '方案审核已记录', 'customer.contacted': '已记录联系客户', 'ticket.closed': '结案结果已记录',
  'support.reply_queued': '消费者回复已排队',
  'support.message_received': '消费者补充信息',
  'run.reinvestigation_queued': '新的调查已建立',
}
function eventTitle(event: TicketEvent) {
  return event.event_type === 'node.completed' ? nodeLabels[String(event.payload_json.node_name)] || '调查步骤已完成' : eventNames[event.event_type] || '处理记录已更新'
}
</script>
<template>
  <router-link to="/tickets" class="back-link"><Icon name="back" :size="16" />返回工单队列</router-link><LoadNotice :error="error" :offline="offline" @retry="refresh" /><el-skeleton v-if="loading && !ticket" :rows="8" animated class="panel detail-skeleton" /><section v-else-if="!ticket" class="panel empty-state"><Icon name="file" :size="36" /><h1>暂时无法读取工单</h1><p>请检查工单是否存在，或稍后重试。</p><el-button @click="refresh">重新读取</el-button></section>
  <template v-else><div class="page-heading detail-heading"><div><div class="eyebrow" :title="ticket.ticket_no">{{ shortTicket(ticket.ticket_no) }}</div><h1>工单详情</h1><p>创建于 {{ displayTime(ticket.created_at) }} · 最近更新 {{ displayTime(ticket.updated_at) }}</p></div><StatusTag :status="ticket.status" /></div><div class="detail-layout"><div class="detail-main"><section class="panel summary-panel"><div class="section-title"><span class="section-icon"><Icon name="inbox" :size="18" /></span><h2>问题摘要</h2><span class="priority" :class="ticket.priority">{{ priorityLabels[ticket.priority] }}</span></div><p class="feedback-text wrap-text">{{ ticket.feedback_text }}</p><div class="facts-grid"><div><span class="fact-label">客户邮箱</span><strong>{{ ticket.customer_email }}</strong><span class="source-label">{{ provenance('customer_email') }}</span></div><div><span class="fact-label">设备型号 / 标识</span><strong :class="{ missing: !ticket.device_ref }">{{ ticket.device_ref || '待补充' }}</strong><span class="source-label">{{ provenance('device_ref') }}</span></div><div><span class="fact-label">发生时间（北京时间）</span><strong :class="{ missing: !ticket.occurred_at }">{{ ticket.occurred_at ? displayTime(ticket.occurred_at) : '待补充' }}</strong><span class="source-label">{{ provenance('occurred_at') }}</span></div></div><div class="facts-grid"><div v-for="field in scopeFields.filter(field => factValue(field.key))" :key="field.key"><span class="fact-label">{{ field.label }}</span><strong>{{ factValue(field.key) }}</strong><span class="source-label">{{ provenance(field.key) }}</span></div></div><div v-if="human && ['unclaimed','claimed'].includes(human.status)" class="notice warning"><Icon name="users" :size="18" /><span>{{ reasonLabels[human.reason_code] || '需要人工核查' }}，请在人工操作区域处理。</span></div></section>
      <section v-if="ticket.solution_json.internal_plan" class="panel solution-panel"><div class="section-title"><span class="section-icon"><Icon name="file" :size="18" /></span><h2>内部处理方案</h2><el-tag type="info" size="small">{{ ticket.solution_json.inference_mode === 'real' ? '模型草稿 · 模拟业务资料' : '模拟方案' }}</el-tag></div><template v-if="solutionFacts.length">
        <h3>已确认的调查范围</h3>
        <p class="wrap-text">{{ solutionFacts.map(fact => `${fact.label}：${fact.value}`).join(' · ') }}</p>
      </template>
      <template v-if="solutionObservations.length">
        <h3>有引用的调查观察</h3>
        <p v-for="(finding, index) in solutionObservations" :key="index" class="wrap-text">
          {{ finding.point }}<br /><span class="muted">{{ finding.applicability }}</span>
        </p>
      </template>
      <h3>建议操作</h3>
      <p class="wrap-text plan-text">{{ ticket.solution_json.internal_plan }}</p><el-button text @click="openSources">查看来源说明（{{ evidence.length }}）<Icon name="arrow" :size="16" /></el-button></section>
      <section v-if="faultReport" class="panel solution-panel"><div class="section-title"><h2>故障调查记录</h2><el-tag type="info" size="small">模拟业务资料</el-tag></div><p class="muted">已查看领域：{{ faultReport.inspected_domains.join('、') || '尚无足够资料' }} · {{ faultReport.source_kind === 'telemetry' ? '仅WiFi埋点，详细日志缺失' : faultReport.source_kind === 'detailed_log' ? '详细日志' : '尚未读取日志' }}</p><p v-if="faultReport.viewed_range.start" class="muted">查看范围：{{ displayTime(faultReport.viewed_range.start) }} 至 {{ displayTime(faultReport.viewed_range.end) }}</p><p v-for="(finding, index) in faultReport.findings" :key="index" class="wrap-text">{{ finding.point }}<br /><span class="muted small">{{ finding.applicability }}</span></p><div v-for="(cause, index) in faultReport.candidate_causes" :key="index" class="notice subtle"><strong>未确认的候选原因</strong><p class="wrap-text">{{ cause.hypothesis }}</p><p class="wrap-text">需验证：{{ cause.required_verification }}</p></div><p v-for="(limit, index) in faultReport.limitations" :key="index" class="muted wrap-text">{{ limit }}</p><el-button text @click="openSources">查看来源说明（{{ evidence.length }}）</el-button></section>
      <ExperienceHints v-if="recallScope" :key="JSON.stringify(recallScope)" :scope="recallScope" :offline="offline" />
      <SupportReplies v-if="['app_support', 'mock_channel'].includes(ticket.source)" :ticket="ticket" />
      <section class="panel timeline-panel"><div class="section-title"><span class="section-icon"><Icon name="clock" :size="18" /></span><h2>处理时间线</h2><span class="muted small">仅显示操作与完成步骤</span></div><div v-if="!events.length" class="muted">暂无处理记录。</div><el-button v-if="events.length > visibleEvents" text @click="visibleEvents += 20">查看更早记录</el-button><ol class="timeline"><li v-for="event in events.slice(-visibleEvents).reverse()" :key="event.id"><span class="timeline-dot"></span><div><strong>{{ eventTitle(event) }}</strong><p v-if="event.payload_json.reason_code" class="muted">{{ reasonLabels[String(event.payload_json.reason_code)] || '请人工核查' }}</p><p v-if="event.payload_json.reason" class="muted wrap-text">{{ event.payload_json.reason }}</p><p v-if="event.event_type === 'support.message_received'" class="wrap-text">{{ event.payload_json.message }}</p><time>{{ displayTime(event.created_at) }}</time></div></li></ol><div v-if="run" class="timeline-foot">{{ run.status === 'succeeded' ? '本次自动调查已结束，处理结果以人工确认为准。' : '进展会自动更新。' }}</div></section>
    </div><aside class="detail-side"><ActionPanel :ticket="ticket" :human="human" :offline="offline" :reload="reload" /><div class="notice subtle"><Icon name="shield" :size="18" /><span>方案仅供处理参考，结案需要明确确认。</span></div></aside></div></template>
  <el-drawer v-model="drawer" title="来源说明" size="min(460px, 100vw)"><div v-if="['supervisor-v1', 'supervisor-v2'].includes(run?.graph_version || '')" class="notice subtle">引用来自模拟业务资料；日志只展示脱敏片段。请核对平台、版本、时间范围及当前适用状态。</div><div v-else class="notice subtle">当前使用固定模拟来源，不包含真实文档原文或客户日志。</div><div v-if="sourceError" class="notice danger" role="alert">{{ sourceError }}</div><div v-for="reference in evidence" :key="reference" class="evidence-item"><Icon name="file" /><div><strong>{{ citations[reference]?.title || (reference.startsWith('kb:') ? '知识文档引用' : reference.includes('knowledge') ? '模拟知识调查记录' : '模拟故障调查记录') }}</strong><p class="muted wrap-text">{{ reference }}</p><template v-if="citations[reference]"><p class="wrap-text">{{ citations[reference].text }}</p><p class="muted"><span v-if="citations[reference].document_version">版本 {{ citations[reference].document_version }} · </span><span v-if="citations[reference].occurred_at">{{ displayTime(citations[reference].occurred_at) }} · </span>第 {{ citations[reference].start_line }}—{{ citations[reference].end_line }} 行</p><el-tag :type="citations[reference].usable ? 'success' : 'warning'" size="small">{{ citations[reference].usable ? '当前适用' : '当前不可用，请核对范围或有效期' }}</el-tag></template><el-tag v-else type="info" size="small">{{ reference.startsWith('kb:') ? '模拟知识资料' : '模拟来源' }}</el-tag></div></div><p v-if="!evidence.length" class="muted">尚未生成来源引用。</p></el-drawer>
</template>
