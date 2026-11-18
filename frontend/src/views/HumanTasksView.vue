<script setup lang="ts">
import { ref, watch } from 'vue'
import { request } from '../api/client'
import type { HumanTask, HumanTaskList } from '../types'
import { usePolling } from '../composables/usePolling'
import { useSession } from '../stores/session'
import { reasonLabels, displayTime, priorityLabels } from '../utils/display'
import Icon from '../components/Icon.vue'
import LoadNotice from '../components/LoadNotice.vue'
const session = useSession()
const mine = ref(false)
const status = ref('')
const cursor = ref<string | null>(null)
const previous = ref<(string | null)[]>([])
const next = ref<string | null>(null)
const tasks = ref<HumanTask[]>([])
const taskLabels: Record<string, string> = { unclaimed: '未认领', claimed: '已认领', resuming: '正在恢复', completed: '已完成', cancelled: '已取消' }
const { error, offline, loading, refresh } = usePolling(async signal => {
  const params = new URLSearchParams({ limit: '20' })
  if (mine.value && session.user) params.set('assignee_id', session.user.id)
  if (status.value) params.set('status', status.value)
  if (cursor.value) params.set('cursor', cursor.value)
  const result = await request<HumanTaskList>(`/human-tasks?${params}`, { signal })
  if (!signal.aborted) { tasks.value = result.items; next.value = result.next_cursor ?? null }
})
watch([mine, status], () => { cursor.value = null; previous.value = []; refresh() })
function paginate(forward: boolean) {
  if (forward && next.value) { previous.value.push(cursor.value); cursor.value = next.value }
  else if (!forward && previous.value.length) cursor.value = previous.value.pop() ?? null
  refresh()
}
</script>
<template>
  <div class="page-heading"><div><div class="eyebrow">人工协作</div><h1>人工待办</h1><p>集中处理需要补充信息、核查或接管的工单。</p></div><el-button @click="refresh"><Icon name="refresh" :size="16" />刷新待办</el-button></div><LoadNotice :error="error" :offline="offline" @retry="refresh" />
  <section class="panel"><div class="panel-toolbar"><div class="filter-group"><label for="human-status" class="sr-only">待办状态</label><select id="human-status" v-model="status" class="control"><option value="">开放的待办</option><option v-for="(label, value) in taskLabels" :key="value" :value="value">{{ label }}</option></select><el-checkbox v-model="mine">只看我认领的</el-checkbox></div><span class="muted">认领后可补充信息并恢复处理</span></div><el-skeleton v-if="loading" :rows="4" animated class="table-skeleton" /><div v-else-if="!tasks.length" class="empty-state"><Icon name="check" :size="38" /><h2>当前没有待办</h2><p>需要人工判断的工单会出现在这里。</p><router-link to="/tickets" class="button-link secondary">查看工单队列</router-link></div><div v-else class="table-wrap"><table class="data-table"><thead><tr><th>需要处理</th><th>待办状态</th><th class="optional-column">优先级</th><th class="optional-column">认领人</th><th class="optional-column">进入时间</th><th>操作</th></tr></thead><tbody><tr v-for="task in tasks" :key="task.id"><td><strong>{{ reasonLabels[task.reason_code] || '待人工核查' }}</strong><div class="muted small">{{ task.payload_json.missing_fields && (task.payload_json.missing_fields as string[]).length ? '请查看缺失信息并补充' : '请查看调查过程后决定下一步' }}</div></td><td><span class="task-label" :class="task.status">{{ taskLabels[task.status] }}</span></td><td class="optional-column"><span class="priority" :class="task.priority">{{ priorityLabels[task.priority] }}</span></td><td class="optional-column">{{ task.assignee_id === session.user?.id ? '我' : task.assignee_id ? '其他业务人员' : '尚未认领' }}</td><td class="optional-column muted">{{ displayTime(task.created_at) }}</td><td><router-link :to="`/tickets/${task.ticket_id}`" class="table-text-link">查看工单<Icon name="arrow" :size="15" /></router-link></td></tr></tbody></table></div><div class="pagination"><span class="muted">本页 {{ tasks.length }} 条 · 自动更新</span><div><el-button :disabled="!previous.length" @click="paginate(false)">上一页</el-button><el-button :disabled="!next" @click="paginate(true)">下一页</el-button></div></div></section>
</template>
