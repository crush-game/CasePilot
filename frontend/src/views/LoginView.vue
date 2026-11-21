<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { router, safeRedirect } from '../router'
import { useSession } from '../stores/session'
import { errorMessage } from '../api/client'
import Icon from '../components/Icon.vue'
const route = useRoute()
const login = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')
async function submit() {
  if (busy.value) return
  if (!login.value.trim() || !password.value) { error.value = '请填写账号和密码。'; return }
  busy.value = true; error.value = ''
  try { await useSession().login(login.value.trim(), password.value); password.value = ''; await router.replace(safeRedirect(route.query.redirect)) }
  catch (failure) { error.value = errorMessage(failure) }
  finally { busy.value = false }
}
</script>
<template>
  <div class="login-page"><section class="login-intro"><div class="brand light"><span class="brand-mark"><Icon name="layers" /></span>CasePilot<span class="brand-dot">.</span></div><div class="intro-copy"><div class="eyebrow">售后处理工作台</div><h1>每一条反馈，<br>都有清晰的下一步。</h1><p>汇集问题、调查进展与人工判断，<br>让处理过程有据可查。</p><div class="intro-flow"><span><Icon name="inbox" />接收问题</span><i></i><span><Icon name="file" />调查处理</span><i></i><span><Icon name="check" />人工确认</span></div></div><div class="intro-foot">清晰记录 · 有序协作 · 结果确认</div></section>
    <section class="login-form-area"><form class="login-form" @submit.prevent="submit"><el-tag type="info" effect="plain" round>模拟数据环境</el-tag><h2>登录工作台</h2><p class="muted">使用本地账号登录售后工作台或客服。</p><div v-if="route.query.expired" class="notice warning">登录已过期，请重新登录后继续。</div><div v-if="route.query.reconnect" class="notice warning">暂时无法恢复登录，请检查连接后重试。</div><div v-if="error" class="notice danger" role="alert">{{ error }}</div><div class="field"><label for="login-name">账号</label><el-input id="login-name" v-model="login" autocomplete="username" placeholder="输入账号" size="large" :disabled="busy" /></div><div class="field"><label for="login-password">密码</label><el-input id="login-password" v-model="password" type="password" show-password autocomplete="current-password" placeholder="输入密码" size="large" :disabled="busy" /></div><el-button native-type="submit" type="primary" size="large" :loading="busy" class="login-submit">登录工作台<Icon name="arrow" :size="18" /></el-button><p class="login-note"><Icon name="shield" :size="16" />登录后可创建工单、跟踪进度与处理人工待办。</p></form></section>
  </div>
</template>
