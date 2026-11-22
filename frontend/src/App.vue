<script setup lang="ts">
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { useSession } from './stores/session'
import { router } from './router'
import { errorMessage } from './api/client'
import Icon from './components/Icon.vue'

const route = useRoute()
const session = useSession()
const logoutError = ref('')
const loggingOut = ref(false)
async function logout() {
  loggingOut.value = true
  try { await session.logout(); await router.replace('/login') }
  catch (error) { logoutError.value = errorMessage(error) }
  finally { loggingOut.value = false }
}
</script>

<template>
  <router-view v-if="route.path === '/login' || route.path === '/support'" />
  <div v-else class="app-shell">
    <a class="skip-link" href="#main-content">跳转到主要内容</a>
    <aside class="sidebar">
      <router-link to="/tickets" class="brand"><span class="brand-mark"><Icon name="layers" /></span>CasePilot<span class="brand-dot">.</span></router-link>
      <div class="workspace-label">售后处理工作台</div>
      <nav aria-label="主导航">
        <div class="nav-caption">工作空间</div>
        <router-link to="/tickets" :class="{ active: route.path.startsWith('/tickets') }"><Icon name="inbox" />工单队列</router-link>
        <router-link to="/human-tasks" :class="{ active: route.path === '/human-tasks' }"><Icon name="users" />人工待办</router-link>
        <router-link to="/experiences" :class="{ active: route.path === '/experiences' }"><Icon name="file" />经验候选</router-link>
        <router-link to="/quality" :class="{ active: route.path === '/quality' }"><Icon name="check" />服务质检</router-link>
      </nav>
      <div class="sidebar-bottom"><span class="environment-dot"></span>模拟数据环境<p>处理过程保留，关键结果由人工确认。</p></div>
    </aside>
    <div class="workspace"><header class="topbar"><span class="topbar-label">客户服务 / {{ route.path === '/human-tasks' ? '人工待办' : route.path === '/experiences' ? '经验候选' : route.path === '/quality' ? '服务质检' : '工单管理' }}</span><div class="account"><el-tag type="info" effect="plain" round>模拟数据</el-tag><span class="avatar">{{ session.user?.login.slice(0, 1).toUpperCase() }}</span><span class="account-name">{{ session.user?.login }}</span><el-button text :loading="loggingOut" @click="logout">退出登录</el-button></div></header>
      <main id="main-content" class="main-content"><el-alert v-if="logoutError" :title="logoutError" type="error" :closable="false" /><section v-if="session.user?.role !== 'business'" class="panel permission-panel"><Icon name="shield" /><h1>当前账号没有工单处理权限</h1><p>请使用业务处理账号登录。</p><el-button @click="logout">切换账号</el-button></section><router-view v-else :key="route.path" /></main>
    </div>
  </div>
</template>
