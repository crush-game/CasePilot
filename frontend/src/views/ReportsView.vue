<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { errorMessage, request } from '../api/client'
import LoadNotice from '../components/LoadNotice.vue'
import { usePolling } from '../composables/usePolling'
import { useSession } from '../stores/session'
import type { components } from '../types/openapi'
import { displayTime } from '../utils/display'

type Report = components['schemas']['WeeklyReportView']
type Ratio = components['schemas']['MetricRatio']
type Gap = components['schemas']['KnowledgeGapView']
type GapDecision = components['schemas']['KnowledgeGapDecision']
type Excerpt = { ref: string; role: string; text: string }

const route = useRoute()
const session = useSession()
const isAdmin = session.user?.role === 'knowledge_admin'
const reports = ref<Report[]>([])
const report = ref<Report | null>(null)
const gaps = ref<Gap[]>([])
const gapNotes = ref<Record<string, string>>({})
const busy = ref(false)
const actionError = ref('')
const week = ref('')
const selected = ref(typeof route.query.report_id === 'string' ? route.query.report_id : '')
const metrics = computed(() => report.value?.metrics_json)
const deliveryStates = { queued: '等待发送', sending: '发送中', sent: '已接收', failed: '失败', unknown: '结果待核对' }
const gapStates = { pending: '待核对', confirmed: '已确认', dismissed: '已驳回' }
const { error, offline, refresh } = usePolling(async signal => {
  if (isAdmin) {
    const value = await request<Gap[]>('/knowledge-gaps', { signal })
    if (!signal.aborted) gaps.value = value
    return
  }
  const value = await request<Report[]>('/reports/weekly', { signal })
  const id = selected.value
  const detail = id && !value.some(item => item.id === id)
    ? await request<Report>(`/reports/weekly/${id}`, { signal })
    : value.find(item => item.id === id) ?? value[0]
  if (!signal.aborted && selected.value === id) { reports.value = value; report.value = detail ?? null }
})

function ratio(value: Ratio) {
  return `${value.count}/${value.total}${value.total ? `（${(100 * value.count / value.total).toFixed(1)}%）` : ''}`
}

async function act(operation: () => Promise<void>) {
  busy.value = true
  actionError.value = ''
  try { await operation(); await refresh() }
  catch (failure) { actionError.value = errorMessage(failure) }
  finally { busy.value = false }
}

function generate() {
  void act(async () => {
    const value = await request<Report>('/reports/weekly', {
      method: 'POST', body: JSON.stringify({ week_start: week.value || null }),
    })
    selected.value = value.id
    report.value = value
  })
}

function send() {
  if (!report.value) return
  const id = report.value.id
  void act(async () => { await request(`/reports/weekly/${id}/delivery`, { method: 'POST' }) })
}

function decide(gap: Gap, decision: GapDecision['decision']) {
  const reason = gapNotes.value[gap.id]?.trim()
  if (!reason) return
  void act(async () => {
    await request(`/knowledge-gaps/${gap.id}/decision`, { method: 'POST', body: JSON.stringify({ decision, reason }) })
  })
}

function excerpts(gap: Gap) { return (gap.evidence_json.excerpts ?? []) as Excerpt[] }
</script>

<template>
  <div class="page-heading"><div><h1>{{ isAdmin ? '知识缺口' : '售后周报' }}</h1>
    <p>{{ isAdmin ? '核对由质检复核提交的知识缺口。' : '按北京时间查看自有网页客服的服务和质检记录。' }}</p></div></div>
  <LoadNotice :error="error" :offline="offline" @retry="refresh" />
  <p v-if="actionError" class="notice danger" role="alert">{{ actionError }}</p>
  <template v-if="isAdmin">
    <p v-if="!gaps.length" class="muted">暂无待核对的知识缺口。</p>
    <section v-for="gap in gaps" :key="gap.id" class="panel report-panel">
      <h2>{{ gapStates[gap.status] }}</h2>
      <p class="wrap-text">{{ gap.evidence_json.statement }}</p>
      <p class="muted wrap-text">来源工单 {{ gap.evidence_json.ticket_id }} · {{ gap.rule_id }}</p>
      <p class="muted wrap-text">会话证据 {{ gap.evidence_json.refs }}</p>
      <details v-if="excerpts(gap).length"><summary>查看相关会话摘录</summary>
        <p v-for="excerpt in excerpts(gap)" :key="excerpt.ref" class="wrap-text">{{ excerpt.text }}</p>
      </details>
      <div v-if="gap.status === 'pending'" class="action-buttons">
        <label :for="`gap-reason-${gap.id}`">核对依据</label>
        <input :id="`gap-reason-${gap.id}`" v-model="gapNotes[gap.id]" class="control" maxlength="1000" />
        <el-button type="primary" :disabled="busy || !gapNotes[gap.id]?.trim()" @click="decide(gap, 'confirmed')">确认缺口</el-button>
        <el-button :disabled="busy || !gapNotes[gap.id]?.trim()" @click="decide(gap, 'dismissed')">驳回</el-button>
      </div>
      <p v-else class="wrap-text">{{ gap.resolution_json.reason }}</p>
    </section>
  </template>
  <template v-else>
    <section class="panel report-panel">
      <form class="action-buttons" @submit.prevent="generate">
        <label for="report-week">统计周的周一</label>
        <input id="report-week" v-model="week" class="control" type="date" />
        <el-button type="primary" native-type="submit" :disabled="busy || offline">生成或重算周报</el-button>
        <span class="muted">留空生成上周</span>
      </form>
      <div v-if="reports.length" class="action-buttons">
        <label for="report-version">周报版本</label>
        <select id="report-version" v-model="selected" class="control" @change="refresh">
          <option value="">最新周报</option>
          <option v-for="row in reports" :key="row.id" :value="row.id">{{ row.week_start }} · 第 {{ row.revision }} 版</option>
        </select>
      </div>
    </section>
    <p v-if="!report" class="muted">暂无周报。</p>
    <template v-else-if="metrics">
      <section class="panel report-panel">
        <h2>{{ report.week_start }} · 第 {{ report.revision }} 版</h2>
        <p class="muted">统计截至 {{ displayTime(report.observed_at) }} · {{ report.definition_version }}</p>
        <dl class="report-metrics">
          <div><dt>客服会话</dt><dd>{{ metrics.conversations }}</dd></div>
          <div><dt>新增工单</dt><dd>{{ metrics.new_tickets }}</dd></div>
          <div><dt>待人工</dt><dd>{{ metrics.pending_human_at_cutoff }}</dd></div>
          <div><dt>自助解决率</dt><dd>{{ ratio(metrics.self_resolved) }}</dd></div>
          <div><dt>转人工率</dt><dd>{{ ratio(metrics.handoff) }}</dd></div>
          <div><dt>连接故障</dt><dd>{{ metrics.faults.wifi }}</dd></div>
        </dl>
        <h3>质检覆盖</h3>
        <p>结案快照 {{ metrics.quality.total }} · 资料不足 {{ metrics.quality.insufficient }} ·
          完成初筛 {{ metrics.quality.screened }} · 完成精检 {{ metrics.quality.ai_checked }} · 完成人工复核 {{ metrics.quality.reviewed }}</p>
        <p v-for="row in metrics.deductions" :key="row.rule_id">{{ row.label }} · {{ row.count }} 次</p>
      </section>
      <section class="panel report-panel">
        <h2>群报投递</h2>
        <el-button type="primary" :disabled="busy || offline" @click="send">安排群报投递</el-button>
        <p v-for="delivery in report.deliveries" :key="delivery.id">
          {{ delivery.group_key }} · {{ delivery.mode === 'mock' ? '模拟' : '飞书' }} ·
          {{ deliveryStates[delivery.status] }} · 尝试 {{ delivery.attempts }} 次
        </p>
      </section>
    </template>
  </template>
</template>

<style scoped>
.report-panel { padding: 18px; margin-block: 12px; }
.report-panel .action-buttons { margin-block: 12px; align-items: center; flex-wrap: wrap; }
.report-panel .control { width: auto; max-width: 100%; }
.report-metrics { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); }
.report-metrics div { padding: 12px; border: 1px solid var(--line); border-radius: 8px; }
.report-metrics dt { font-size: 0.9rem; }
.report-metrics dd { font-size: 1.2rem; font-weight: 650; margin: 5px 0 0; }
</style>
