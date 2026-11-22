<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { errorMessage, request } from '../api/client'
import LoadNotice from '../components/LoadNotice.vue'
import { usePolling } from '../composables/usePolling'
import { useSession } from '../stores/session'
import type { components } from '../types/openapi'
import { displayTime } from '../utils/display'

type List = components['schemas']['QualityList']
type Detail = components['schemas']['QualityDetail']
type Decision = components['schemas']['QualityDecision']
type Finding = components['schemas']['QualityFinding'] & { label: string; deduction: number }
type Batch = components['schemas']['QualityBatchView']
type RuleVersion = components['schemas']['QualityRuleSetInput']
type Message = { id: string; role: 'customer' | 'human' | 'assistant'; text: string; at: string }

const route = useRoute()
const session = useSession()
const ticketId = typeof route.query.ticket_id === 'string' ? route.query.ticket_id : ''
const search = ticketId ? `?ticket_id=${encodeURIComponent(ticketId)}` : ''
const list = ref<List | null>(null)
const cursor = ref('')
const detail = ref<Detail | null>(null)
const ruleVersions = ref<RuleVersion[]>([])
const included = ref<string[]>([])
const evidenceId = ref('')
const reason = ref('')
const gapStatement = ref('')
const gapNotice = ref('')
const newVersion = ref('')
const busy = ref(false)
const actionError = ref('')
const batch = ref<Batch | null>(null)
const batchKey = ref(crypto.randomUUID())
const randomPct = ref(10)
const maxCalls = ref(20)
const labels = { queued: '待初筛', screened: '已初筛', ai_queued: '待精检', pending_review: '待复核',
  finalized: '已确认', appealed: '待申诉复核', insufficient: '资料不足' }
const roles = { customer: '客户', human: '人工客服', assistant: '智能助手' }
const messages = computed(() => (detail.value?.snapshot.messages ?? []) as Message[])
const evidence = computed(() => messages.value.find(row => row.id === evidenceId.value))
const findings = computed(() => (detail.value?.result_json.findings ?? []) as Finding[])
const missing = computed(() => (detail.value?.result_json.missing ?? []) as string[])
const mine = computed(() => detail.value?.subject_id === session.user?.id)
const reviewable = computed(() => !mine.value && detail.value !== null &&
  ['screened', 'pending_review', 'appealed', 'insufficient'].includes(detail.value.status))
const { error, offline, refresh } = usePolling(async signal => {
  const suffix = cursor.value ? `${search ? '&' : '?'}cursor=${encodeURIComponent(cursor.value)}` : ''
  const value = await request<List>(`/quality/assessments${search}${suffix}`, { signal })
  if (!signal.aborted) list.value = value
})

function show(row: Detail) {
  detail.value = row
  included.value = ((row.result_json.findings ?? []) as Finding[]).map(item => item.rule_id)
  evidenceId.value = ''
  newVersion.value = ''
  gapStatement.value = ''
  gapNotice.value = ''
}

async function open(id: string) {
  actionError.value = ''
  reason.value = ''
  try {
    const [row, rules] = await Promise.all([
      request<Detail>(`/quality/assessments/${id}`), request<RuleVersion[]>('/quality/rules'),
    ])
    show(row)
    ruleVersions.value = rules
  } catch (failure) { actionError.value = errorMessage(failure) }
}

async function submitBatch() {
  actionError.value = ''
  busy.value = true
  try {
    batch.value = await request<Batch>('/quality/batches', { method: 'POST', body: JSON.stringify({
      batch_key: batchKey.value, random_pct: randomPct.value, max_calls: maxCalls.value, ticket_id: ticketId || null,
    }) })
    await refresh()
  } catch (failure) { actionError.value = errorMessage(failure) }
  finally { busy.value = false }
}

async function decide(decision: Decision['decision']) {
  if (!detail.value || busy.value || !reason.value.trim()) return
  actionError.value = ''
  busy.value = true
  const body: Decision = { action_id: crypto.randomUUID(), expected_version: detail.value.version,
    decision, reason: reason.value.trim() }
  if (decision === 'adjust') body.findings = findings.value.filter(item => included.value.includes(item.rule_id))
    .map(({ rule_id, evidence }) => ({ rule_id, evidence }))
  if (decision === 'rescore') body.rule_version = newVersion.value
  try {
    const row = await request<Detail>(`/quality/assessments/${detail.value.id}/decision`, {
      method: 'POST', body: JSON.stringify(body),
    })
    show(row)
    reason.value = ''
    await refresh()
  } catch (failure) { actionError.value = errorMessage(failure) }
  finally { busy.value = false }
}

async function submitGap(ruleId: Finding['rule_id']) {
  if (!detail.value || busy.value || !gapStatement.value.trim()) return
  actionError.value = ''
  busy.value = true
  try {
    await request(`/quality/assessments/${detail.value.id}/knowledge-gap`, {
      method: 'POST', body: JSON.stringify({ rule_id: ruleId, statement: gapStatement.value.trim() }),
    })
    gapNotice.value = '知识缺口已提交，等待知识管理员核对。'
    gapStatement.value = ''
  } catch (failure) { actionError.value = errorMessage(failure) }
  finally { busy.value = false }
}
</script>

<template>
  <div class="page-heading"><div><h1>服务质检</h1><p>查看结案会话、规则判定与复核记录。</p></div></div>
  <LoadNotice :error="error" :offline="offline" @retry="refresh" />
  <p v-if="actionError" class="notice danger" role="alert">{{ actionError }}</p>
  <section class="panel quality-panel">
    <h2>精检批次</h2>
    <form class="batch-fields" @submit.prevent="submitBatch">
      <label>批次键<input v-model="batchKey" class="control" required maxlength="80" /></label>
      <label>普通单抽样百分比<input v-model.number="randomPct" class="control" type="number" min="0" max="100" required /></label>
      <label>调用预算<input v-model.number="maxCalls" class="control" type="number" min="0" max="200" required /></label>
      <el-button type="primary" native-type="submit" :disabled="offline || busy">安排精检</el-button>
    </form>
    <p v-if="batch" class="muted" role="status">入样 {{ batch.selection_json.length }} 条 · 调用预算 {{ batch.max_calls }} 次</p>
  </section>
  <section class="panel quality-panel">
    <h2>质检记录</h2>
    <p v-if="list?.snapshot_missing.length" class="notice warning">{{ list.snapshot_missing.join('、') }}</p>
    <p v-if="!list?.items.length" class="muted">暂无可查看的质检记录。</p>
    <div v-for="row in list?.items" :key="row.id" class="quality-row">
      <span>{{ row.subject_name }} · {{ row.rule_version }} · {{ labels[row.status] }}</span>
      <span>{{ row.result_json.score ?? '待判定' }}</span>
      <el-button text @click="open(row.id)">查看质检证据</el-button>
    </div>
    <el-button v-if="cursor" text @click="cursor = ''; refresh()">回到首页</el-button>
    <el-button v-if="list?.next_cursor" text @click="cursor = list.next_cursor; refresh()">下一页</el-button>
  </section>
  <section v-if="detail" class="panel quality-panel">
    <h2>质检证据</h2>
    <p>{{ detail.subject_name }} · {{ detail.rule_version }} · {{ labels[detail.status] }} · {{ detail.result_json.score ?? '待判定' }}</p>
    <p v-if="missing.length" class="notice warning">{{ missing.join('、') }}</p>
    <router-link :to="`/tickets/${detail.ticket_id}`">打开来源工单</router-link>
    <p v-if="!findings.length" class="muted">当前没有扣分项。</p>
    <div v-if="!mine && detail.status === 'finalized' && findings.length" class="field"><label for="gap-statement">知识缺口说明</label>
      <el-input id="gap-statement" v-model="gapStatement" :maxlength="1000" />
    </div>
    <p v-if="gapNotice" class="notice success" role="status">{{ gapNotice }}</p>
    <div v-for="item in findings" :key="item.rule_id" class="quality-row">
      <label>
        <input v-if="reviewable" v-model="included" type="checkbox" :value="item.rule_id" />
        {{ item.label }}{{ item.deduction ? ` · ${item.deduction} 分` : '' }}
      </label>
      <el-button v-for="id in item.evidence" :key="id" text @click="evidenceId = id">
        {{ id.startsWith('fact:') ? '查看字段' : '查看原消息' }}
      </el-button>
      <el-button v-if="!mine && detail.status === 'finalized'" text :disabled="busy || !gapStatement.trim()"
        @click="submitGap(item.rule_id)">提交知识缺口</el-button>
    </div>
    <div v-if="evidence" class="notice subtle" role="status">
      <p>{{ roles[evidence.role] }} · {{ displayTime(evidence.at) }}</p><p class="wrap-text">{{ evidence.text }}</p>
    </div>
    <p v-else-if="evidenceId === 'fact:product_ref'" class="notice subtle" role="status">结案时工单产品型号为空。</p>
    <details>
      <summary>查看快照会话</summary>
      <p v-for="message in messages" :key="message.id" class="wrap-text">{{ roles[message.role] }} · {{ message.text }}</p>
    </details>
    <details v-if="detail.history_json.length">
      <summary>查看历史复核</summary>
      <p v-for="(entry, index) in detail.history_json" :key="index" class="wrap-text">{{ entry.reason }}</p>
    </details>
    <div class="field"><label for="quality-reason">操作依据</label>
      <el-input id="quality-reason" v-model="reason" type="textarea" :maxlength="1000" />
    </div>
    <div class="action-buttons">
      <el-button v-if="reviewable" type="primary" :disabled="busy || !reason.trim()" @click="decide('confirm')">确认评分</el-button>
      <el-button v-if="reviewable" :disabled="busy || !reason.trim()" @click="decide('adjust')">按选中项改判</el-button>
      <el-button v-if="mine && detail.status === 'finalized'" :disabled="busy || !reason.trim()" @click="decide('appeal')">提交申诉</el-button>
    </div>
    <div v-if="!mine && ruleVersions.some(rule => rule.version !== detail?.rule_version)" class="action-buttons">
      <label for="quality-version">复评规则版本</label>
      <select id="quality-version" v-model="newVersion" class="control">
        <option value="">请选择版本</option>
        <option v-for="rule in ruleVersions.filter(item => item.version !== detail?.rule_version)" :key="rule.version">{{ rule.version }}</option>
      </select>
      <el-button :disabled="busy || !reason.trim() || !newVersion" @click="decide('rescore')">按新版本复评</el-button>
    </div>
  </section>
</template>

<style scoped>
.quality-panel { padding: 18px; margin-block: 12px; }
.batch-fields { display: grid; gap: 12px; align-items: end; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
.batch-fields input { width: 100%; }
.quality-row { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; padding-block: 8px; border-bottom: 1px solid var(--line); }
.quality-panel details, .quality-panel .field { margin-block: 12px; }
</style>
