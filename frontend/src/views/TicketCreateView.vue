<script setup lang="ts">
import { reactive, ref } from 'vue'
import { router } from '../router'
import { ActionIdentity, errorMessage, request } from '../api/client'
import type { TicketCreate, TicketCreated, Priority } from '../types'
import { beijingISO, priorityLabels } from '../utils/display'
import Icon from '../components/Icon.vue'
const form = reactive({ feedback: '', email: '', device: '', occurred: '', priority: 'normal' as Priority })
const fields = reactive<Record<string, string>>({})
const busy = ref(false)
const error = ref('')
const identity = new ActionIdentity()
async function submit() {
  if (busy.value) return
  for (const key of Object.keys(fields)) delete fields[key]
  if (!form.feedback.trim()) fields.feedback = '请填写客户遇到的问题。'
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(form.email.trim())) fields.email = '请填写有效的客户邮箱。'
  if (Object.keys(fields).length) return
  const body: TicketCreate = { feedback_text: form.feedback.trim(), customer_email: form.email.trim(), priority: form.priority }
  if (form.device.trim()) body.device_ref = form.device.trim()
  if (form.occurred) { body.occurred_at = beijingISO(form.occurred); body.occurred_at_precision = 'minute' }
  busy.value = true; error.value = ''
  try {
    const created = await request<TicketCreated>('/tickets', { method: 'POST', body: JSON.stringify(body), headers: { 'Idempotency-Key': identity.forPayload('create', body) } })
    identity.clear()
    await router.push(`/tickets/${created.ticket_id}`)
  } catch (failure) { error.value = errorMessage(failure) }
  finally { busy.value = false }
}
</script>
<template>
  <router-link to="/tickets" class="back-link"><Icon name="back" :size="16" />返回工单队列</router-link><div class="page-heading"><div><div class="eyebrow">接收问题</div><h1>新建工单</h1><p>记录客户反馈，开始一次有迹可循的处理。</p></div></div>
  <div class="create-layout"><form class="panel create-form" @submit.prevent="submit"><div v-if="error" class="notice danger" role="alert">{{ error }}<span class="muted">输入内容已保留，可直接重试。</span></div><h2>问题信息</h2><div class="field"><label for="feedback">问题描述 <span class="required">*</span></label><el-input id="feedback" v-model="form.feedback" type="textarea" :rows="5" :maxlength="20000" placeholder="描述客户遇到的现象、已尝试的操作等" :disabled="busy" :aria-invalid="!!fields.feedback" /><span v-if="fields.feedback" class="field-error" role="alert">{{ fields.feedback }}</span></div><div class="field"><label for="customer-email">客户邮箱 <span class="required">*</span></label><el-input id="customer-email" v-model="form.email" type="email" :maxlength="254" placeholder="customer@example.com" :disabled="busy" :aria-invalid="!!fields.email" /><span v-if="fields.email" class="field-error" role="alert">{{ fields.email }}</span></div><div class="form-divider"></div><h2>补充信息 <span class="heading-note">选填</span></h2><div class="form-grid"><div class="field"><label for="device">设备型号 / 标识</label><el-input id="device" v-model="form.device" :maxlength="128" placeholder="例如 DEMO-01" :disabled="busy" /></div><div class="field"><label for="occurred">发生时间（北京时间）</label><input id="occurred" v-model="form.occurred" type="datetime-local" class="control" :disabled="busy" /></div></div><div class="field narrow-field"><label for="priority">优先级</label><select id="priority" v-model="form.priority" class="control" :disabled="busy"><option v-for="(label, value) in priorityLabels" :key="value" :value="value">{{ label }}</option></select></div><div class="form-footer"><router-link to="/tickets" class="button-link secondary">取消</router-link><el-button type="primary" native-type="submit" :loading="busy">创建工单<Icon name="arrow" :size="17" /></el-button></div></form>
    <aside class="create-aside"><span class="aside-icon"><Icon name="file" :size="26" /></span><h2>信息越清晰，处理越顺畅</h2><p>设备和时间暂不确定也可以提交。需要补充的信息会在人工待办中明确展示。</p><div class="aside-separator"></div><span class="mini-label">接下来</span><ol><li>工单保存并进入队列</li><li>系统进行模拟调查</li><li>人工补充或确认结果</li></ol><div class="notice subtle">当前使用模拟数据，方案由人工审核。</div></aside></div>
</template>
