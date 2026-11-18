<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue'
import type { ActionResult, HumanTask, TicketDetail } from '../types'
import { ActionIdentity, ApiError, errorMessage, request } from '../api/client'
import { beijingISO } from '../utils/display'
import { useSession } from '../stores/session'
import Icon from './Icon.vue'

const props = defineProps<{ ticket: TicketDetail; human: HumanTask | null; offline: boolean; reload: () => Promise<boolean> }>()
const session = useSession()
const draft = reactive({ device: '', occurred: '', reply: '', reason: '', revisedDevice: '', revisedTime: '' })
const seed = ref('')
const version = ref(props.ticket.version)
const busy = ref(false)
const conflict = ref(false)
const uncertain = ref(false)
const error = ref('')
const success = ref('')
const dialog = ref(false)
const mode = ref<'close' | 'takeover' | 'contacted' | 'reinvestigate'>('close')
const outcome = ref('resolved')
const identity = new ActionIdentity()
const mine = computed(() => props.human?.assignee_id === session.user?.id)
const terminal = computed(() => ['RESOLVED', 'CLOSED_UNRESOLVED'].includes(props.ticket.status))
const dirty = computed(() => !!(draft.device || draft.occurred || draft.reason || draft.revisedDevice || draft.revisedTime || draft.reply !== seed.value))
const disabled = computed(() => busy.value || conflict.value || props.offline)
const blockedResume = computed(() => props.human && ['CHECKPOINT_MISSING', 'PAUSE_MISMATCH', 'GRAPH_VERSION_UNSUPPORTED'].includes(props.human.reason_code))
watch(() => props.ticket.version, value => { if (!dirty.value && !busy.value && !conflict.value && !dialog.value && !uncertain.value) version.value = value })
watch(() => props.ticket.solution_json.reply_draft, value => {
  if (draft.reply === seed.value) { seed.value = typeof value === 'string' ? value : ''; draft.reply = seed.value }
}, { immediate: true })

async function refreshVersion() {
  if (await props.reload()) { version.value = props.ticket.version; conflict.value = false; uncertain.value = false; identity.clear(); error.value = ''; success.value = '状态已刷新，草稿仍保留。' }
}

async function mutate(path: string, fields: object, message: string, clear: 'facts' | 'reply' | 'reason' | 'none' = 'none') {
  if (disabled.value) return
  const payload = { expected_version: version.value, ...fields }
  const body = { ...payload, action_id: identity.forPayload(path, payload) }
  busy.value = true; error.value = ''; success.value = ''
  try {
    const result = await request<ActionResult>(path, { method: 'POST', body: JSON.stringify(body) })
    version.value = result.version
    uncertain.value = false
    identity.clear()
    if (clear === 'facts') { draft.device = ''; draft.occurred = '' }
    if (clear === 'reply') seed.value = draft.reply
    if (clear === 'reason') { draft.reason = ''; draft.revisedDevice = ''; draft.revisedTime = '' }
    dialog.value = false
    success.value = message
    await props.reload()
  } catch (failure) {
    if (failure instanceof ApiError && failure.status === 409) {
      conflict.value = true
      error.value = '工单状态已更新，草稿已保留。请刷新状态后再提交。'
    } else {
      uncertain.value = failure instanceof ApiError && [0, 502, 503, 504].includes(failure.status)
      error.value = errorMessage(failure)
    }
  } finally { busy.value = false }
}

function claim() {
  if (props.human) void mutate(`/human-tasks/${props.human.id}/claim`, {}, '已认领，请核对并补充信息。')
}
function resume() {
  if (!props.human) return
  const patch: Record<string, string> = {}
  if (draft.device.trim()) patch.device_ref = draft.device.trim()
  if (draft.occurred) { patch.occurred_at = beijingISO(draft.occurred)!; patch.occurred_at_precision = 'minute' }
  if (props.human.reason_code === 'MISSING_FACTS' && !Object.keys(patch).length) { error.value = '请至少补充一项缺失信息。'; return }
  void mutate(`/human-tasks/${props.human.id}/resume`, { facts_patch: patch }, '补充信息已保存，等待继续处理。', 'facts')
}
function review(decision: 'approve' | 'revise') {
  if (!draft.reply.trim()) { error.value = '回复草稿不能为空。'; return }
  void mutate(`/tickets/${props.ticket.id}/review`, { decision, reply_draft: draft.reply }, decision === 'approve' ? '方案已审核通过，仍需确认处理结果。' : '回复修改已保存。', 'reply')
}
const dialogTitle = computed(() => ({ close: '人工结案', takeover: '请求人工接管', contacted: '记录已联系客户', reinvestigate: '重新调查' })[mode.value])
const reasonLabel = computed(() => ({ close: '结案说明', takeover: '接管原因', contacted: '联系记录', reinvestigate: '重新调查原因' })[mode.value])
const retainedDraft = computed(() => [
  draft.device && `补充设备：${draft.device}`, draft.occurred && `补充时间：${draft.occurred}`,
  draft.reply !== seed.value && `回复草稿：${draft.reply}`, draft.reason && `操作说明：${draft.reason}`,
  draft.revisedDevice && `修正设备：${draft.revisedDevice}`, draft.revisedTime && `修正时间：${draft.revisedTime}`,
].filter(Boolean).join('\n'))
function openDialog(value: typeof mode.value) { mode.value = value; dialog.value = true; error.value = ''; if (!dirty.value) version.value = props.ticket.version }
function submitDialog() {
  if (!draft.reason.trim()) { error.value = `请填写${reasonLabel.value}。`; return }
  const reason = draft.reason.trim()
  const base = `/tickets/${props.ticket.id}`
  if (mode.value === 'close') void mutate(`${base}/close`, { outcome: outcome.value, reason }, '结案结果已记录。', 'reason')
  else if (mode.value === 'takeover') void mutate(`${base}/takeover`, { reason }, '停止请求已记录，正在等待运行退出。', 'reason')
  else if (mode.value === 'contacted') void mutate(`${base}/customer-feedback`, { outcome: 'contacted', reason }, '已记录联系情况，等待客户反馈。', 'reason')
  else {
    const patch: Record<string, string> = {}
    if (draft.revisedDevice.trim()) patch.device_ref = draft.revisedDevice.trim()
    if (draft.revisedTime) { patch.occurred_at = beijingISO(draft.revisedTime)!; patch.occurred_at_precision = 'minute' }
    void mutate(`${base}/reinvestigate`, { reason, facts_patch: patch }, '已建立新的调查，原记录保留。', 'reason')
  }
}
</script>

<template>
  <section class="panel action-panel"><div class="section-title"><span class="section-icon"><Icon name="users" :size="18" /></span><h2>{{ terminal ? '处理结果' : '人工操作' }}</h2></div>
    <div v-if="error" class="notice danger" role="alert">{{ error }}</div><div v-if="success" class="notice success" role="status">{{ success }}</div><el-button v-if="conflict" class="full-width" @click="refreshVersion">刷新状态，保留草稿</el-button>
    <template v-if="terminal"><div class="result-icon"><Icon name="check" :size="26" /></div><h3>{{ ticket.status === 'RESOLVED' ? '问题已确认解决' : '工单已按未解决结案' }}</h3><p class="wrap-text">{{ ticket.result_json.reason }}</p><span class="muted small">结果来源：人工确认</span></template>
    <template v-else-if="ticket.cancel_requested"><div class="notice warning">正在停止调查。运行退出后会建立人工待办，请稍候。</div></template>
    <template v-else-if="ticket.status === 'QUEUED'"><p class="muted">工单已保存，正在等待开始处理。</p><el-button :disabled="disabled" @click="openDialog('takeover')">请求人工接管</el-button></template>
    <template v-else-if="ticket.status === 'RUNNING'"><p class="muted">系统正在调查。需要人工介入时，可以先请求停止。</p><el-button type="primary" :disabled="disabled" @click="openDialog('takeover')">请求人工接管</el-button></template>
    <template v-else-if="ticket.status === 'WAITING_HUMAN'">
      <template v-if="human?.status === 'unclaimed'"><p class="muted">此工单需要人工判断。认领后可以补充信息或明确结案。</p><el-button type="primary" class="full-width" :disabled="disabled" :loading="busy" @click="claim">认领待办</el-button></template>
      <template v-else-if="human?.status === 'claimed' && mine"><span class="owner-badge"><Icon name="check" :size="14" />我已认领</span><p v-if="blockedResume" class="muted">恢复记录不可直接使用，请重新调查或人工结案。</p><form v-else @submit.prevent="resume"><div v-if="!ticket.device_ref" class="field"><label for="supplement-device">补充设备标识</label><el-input id="supplement-device" v-model="draft.device" :maxlength="128" placeholder="输入确认的设备信息" :disabled="disabled" /></div><div v-if="!ticket.occurred_at" class="field"><label for="supplement-time">补充发生时间（北京时间）</label><input id="supplement-time" v-model="draft.occurred" type="datetime-local" class="control" :disabled="disabled" /></div><el-button type="primary" native-type="submit" class="full-width" :loading="busy" :disabled="disabled">补充并恢复</el-button></form><div class="action-divider"></div><el-button :disabled="disabled" @click="openDialog('reinvestigate')">修正信息并重新调查</el-button><el-button :disabled="disabled" @click="openDialog('close')">人工结案</el-button></template>
      <p v-else class="muted">{{ human?.status === 'resuming' ? '补充信息已保存，正在等待恢复。' : '该待办已由其他业务人员认领。' }}</p>
    </template>
    <template v-else-if="ticket.status === 'PENDING_CONFIRMATION'"><span class="owner-badge" v-if="ticket.solution_json.reviewed"><Icon name="check" :size="14" />方案已审核</span><div class="field"><label for="reply-draft">客户回复草稿</label><el-input id="reply-draft" v-model="draft.reply" type="textarea" :rows="7" :maxlength="5000" :disabled="disabled" /></div><div class="action-buttons"><el-button type="primary" :loading="busy" :disabled="disabled" @click="review('approve')">审核通过</el-button><el-button :disabled="disabled || draft.reply === seed" @click="review('revise')">保存修改</el-button></div><p class="helper">审核通过后，请联系客户并记录处理情况。</p><el-button class="full-width" :disabled="disabled || !ticket.solution_json.reviewed" @click="openDialog('contacted')">记录已联系客户</el-button><div class="action-divider"></div><el-button :disabled="disabled" @click="openDialog('reinvestigate')">重新调查</el-button><el-button :disabled="disabled" @click="openDialog('close')">人工结案</el-button></template>
    <template v-else-if="ticket.status === 'WAITING_CUSTOMER'"><p class="muted">已记录联系情况。请根据客户反馈明确处理结果。</p><el-button type="primary" class="full-width" :disabled="disabled" @click="outcome = 'resolved'; openDialog('close')">确认结果并结案</el-button><el-button class="full-width" :disabled="disabled" @click="openDialog('reinvestigate')">仍未解决，重新调查</el-button></template>
    <details v-if="dirty && (conflict || terminal || ticket.status === 'WAITING_CUSTOMER')" class="retained-draft"><summary>查看保留的本地草稿</summary><p class="wrap-text">{{ retainedDraft }}</p></details>
  </section>
  <el-dialog v-model="dialog" :title="dialogTitle" width="min(520px, calc(100vw - 32px))" :close-on-click-modal="!busy" :close-on-press-escape="!busy" :show-close="!busy">
    <form @submit.prevent="submitDialog"><div v-if="mode === 'contacted'" class="notice subtle">请确认已通过业务渠道联系客户。本操作只记录联系情况。</div><div v-if="mode === 'close'" class="field"><label for="close-outcome">结案结果</label><select id="close-outcome" v-model="outcome" class="control" :disabled="busy"><option value="resolved">已解决</option><option value="unresolved">未解决结案</option></select></div><template v-if="mode === 'reinvestigate'"><p class="muted">填写需要修正的信息，原调查记录会保留。</p><div class="field"><label for="revised-device">修正设备标识（选填）</label><el-input id="revised-device" v-model="draft.revisedDevice" :maxlength="128" :placeholder="ticket.device_ref || '设备标识'" :disabled="busy" /></div><div class="field"><label for="revised-time">修正发生时间（北京时间，选填）</label><input id="revised-time" v-model="draft.revisedTime" type="datetime-local" class="control" :disabled="busy" /></div></template><div class="field"><label for="action-reason">{{ reasonLabel }}</label><el-input id="action-reason" v-model="draft.reason" type="textarea" :rows="4" :maxlength="2000" :disabled="busy" /></div><div v-if="error" class="notice danger" role="alert">{{ error }}</div><el-button v-if="conflict" :disabled="busy" @click="refreshVersion">刷新状态，保留草稿</el-button><div class="form-footer"><el-button :disabled="busy" @click="dialog = false">暂不操作</el-button><el-button native-type="submit" type="primary" :loading="busy" :disabled="conflict || offline">{{ mode === 'close' ? '确认结案' : '确认提交' }}</el-button></div></form>
  </el-dialog>
</template>
