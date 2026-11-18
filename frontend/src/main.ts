import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { ElAlert, ElButton, ElInput, ElTag, ElDialog, ElDrawer, ElCheckbox, ElSkeleton } from 'element-plus'
import 'element-plus/dist/index.css'
import './style.css'
import App from './App.vue'
import { router } from './router'
import { useSession } from './stores/session'

const app = createApp(App).use(createPinia())
for (const component of [ElAlert, ElButton, ElInput, ElTag, ElDialog, ElDrawer, ElCheckbox, ElSkeleton]) app.use(component)
window.addEventListener('casepilot:auth-expired', () => {
  useSession().expire()
  const route = router.currentRoute.value
  if (route.path !== '/login' && route.matched.length) void router.replace({ path: '/login', query: { redirect: route.fullPath, expired: '1' } })
})
app.use(router).mount('#app')
