<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ActionIdentity, ApiError, errorMessage, request } from '../api/client'
import { usePolling } from '../composables/usePolling'
import LoadNotice from '../components/LoadNotice.vue'
import type { components } from '../types/openapi'

type Experience = components['schemas']['ExperienceView']
type ExperienceList = components['schemas']['ExperienceList']
const route = useRoute()
const ticket = computed(() => typeof route.query.ticket_id === 'string' ? route.query.ticket_id : '')
const statusLabels = { candidate: '待审阅', reviewed: '已审阅', archived: '已归档' }
const conditionLabels: Record<string, string> = {
  product_ref: '产品型号', firmware_version: '固件版本', platform: '平台',
  app_version: 'App版本', region: '地区', channel: '渠道',
}
const status = ref<Experience['status'] | ''>(ticket.value ? '' : 'candidate')
const items = ref<Experience[]>([])
const cursor = ref<string | null>(null)
const previous = ref<(string | null)[]>([])
const next = ref<string | null>(null)
const selected = ref<Experience | null>(null)
const decision = ref<'review' | 'archive'>('review')
const reason = ref('')
const saving = ref(false)
const conflict = ref(false)
const formError = ref('')
const identity = new ActionIdentity()

const { loading, error, offline, refresh } = usePolling(async signal => {
  const params = new URLSearchParams()
  if (ticket.value) params.set('ticket_id', ticket.value)
  if (status.value) params.set('status', status.value)
  if (cursor.value) params.set('cursor', cursor.value)
  const result = await request<ExperienceList>(`/experiences?${params}`, { signal })
  if (!signal.aborted) {
    items.value = result.items
    next.value = result.next_cursor
  }
})
watch([ticket, status], () => {
  cursor.value = null
  previous.value = []
  void refresh()
})
function paginate(forward: boolean) {
  if (forward && next.value) {
    previous.value.push(cursor.value)
    cursor.value = next.value
  } else if (!forward && previous.value.length) cursor.value = previous.value.pop() ?? null
  void refresh()
}
function openReview(item: Experience, action: typeof decision.value) {
  if (selected.value?.id !== item.id) reason.value = ''
  selected.value = item
  decision.value = action
  conflict.value = false
  formError.value = ''
  identity.clear()
}
async function submit() {
  if (!selected.value || saving.value || offline.value || conflict.value) return
  if (!reason.value.trim()) { formError.value = '请填写审阅或归档说明。'; return }
  const path = `/experiences/${selected.value.id}/review`
  const body = { decision: decision.value, expected_version: selected.value.version, reason: reason.value.trim() }
  saving.value = true
  formError.value = ''
  try {
    await request(path, { method: 'POST', body: JSON.stringify({ ...body, action_id: identity.forPayload(path, body) }) })
    selected.value = null
    reason.value = ''
    await refresh()
  } catch (failure) {
    formError.value = errorMessage(failure)
    conflict.value = failure instanceof ApiError && failure.status === 409
    if (conflict.value) await refresh()
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="page-heading"><div><h1>经验候选</h1><p>复核已确认解决的工单，记录可供后续验证的处理经验。</p></div>
    <el-button @click="refresh">刷新候选</el-button>
  </div>
  <LoadNotice :error="error" :offline="offline" @retry="refresh" />
  <section class="panel">
    <div class="panel-toolbar">
      <div class="filter-group">
        <label for="experience-status">审阅状态</label>
        <select id="experience-status" v-model="status" class="control">
          <option value="">全部</option>
          <option v-for="(label, value) in statusLabels" :key="value" :value="value">{{ label }}</option>
        </select>
        <router-link v-if="ticket" to="/experiences" class="table-text-link">查看全部工单</router-link>
      </div>
    </div>
    <el-skeleton v-if="loading && !items.length" :rows="4" animated class="table-skeleton" />
    <p v-else-if="!items.length" class="empty-state muted">当前没有匹配的经验候选。</p>
    <article v-for="item in items" :key="item.id" class="experience-item">
      <div class="section-title"><h2 class="wrap-text">{{ item.content_json.problem }}</h2>
        <el-tag type="info">{{ statusLabels[item.status] }}</el-tag>
      </div>
      <p class="wrap-text"><strong>结果确认</strong><br />{{ item.content_json.result_note }}</p>
      <p class="muted">{{ item.content_json.confirmation === 'customer_confirmed' ? '客户确认（人工记录）' : '人工核验' }}</p>
      <p v-if="item.content_json.verified_steps" class="wrap-text"><strong>已核验有效的操作</strong><br />{{ item.content_json.verified_steps }}</p>
      <p v-for="limit in item.content_json.limitations" :key="limit" class="muted">{{ limit }}</p>
      <p v-if="Object.keys(item.content_json.conditions).length" class="wrap-text">
        {{ Object.entries(item.content_json.conditions).map(([key, value]) => `${conditionLabels[key] ?? key}：${value}`).join(' · ') }}
      </p>
      <p v-if="item.review_json.reason" class="wrap-text">审阅记录：{{ item.review_json.reason }}</p>
      <div class="action-buttons">
        <router-link :to="`/tickets/${item.source_ticket_id}`" class="table-text-link">查看来源工单与证据（{{ item.content_json.evidence_refs.length }}）</router-link>
        <el-button v-if="item.status === 'candidate'" :disabled="offline || saving" @click="openReview(item, 'review')">标记已审阅</el-button>
        <el-button v-if="item.status !== 'archived'" :disabled="offline || saving" @click="openReview(item, 'archive')">归档候选</el-button>
      </div>
      <form v-if="selected?.id === item.id" @submit.prevent="submit">
        <div class="field">
          <label :for="`review-${item.id}`">{{ decision === 'review' ? '审阅说明' : '归档说明' }}</label>
          <el-input :id="`review-${item.id}`" v-model="reason" type="textarea" :maxlength="2000" :disabled="saving" />
        </div>
        <p v-if="formError" class="notice danger" role="alert">{{ formError }}</p>
        <el-button v-if="conflict && item.status !== 'archived' && (decision === 'archive' || item.status === 'candidate')"
          @click="openReview(item, decision)">使用当前版本</el-button>
        <el-button type="primary" native-type="submit" :loading="saving" :disabled="offline || conflict">确认提交</el-button>
        <el-button :disabled="saving" @click="selected = null">取消</el-button>
      </form>
    </article>
    <div class="pagination"><span></span><div>
      <el-button :disabled="!previous.length" @click="paginate(false)">上一页</el-button>
      <el-button :disabled="!next" @click="paginate(true)">下一页</el-button>
    </div></div>
  </section>
</template>

<style scoped>
.experience-item { padding: 20px 24px; border-bottom: 1px solid var(--line); overflow-wrap: anywhere; }
.experience-item form { margin-top: 16px; max-width: 620px; }
.experience-item h2 { min-width: 0; }
</style>
