import { createRouter, createWebHistory } from 'vue-router'
import { useSession } from '../stores/session'

export function safeRedirect(value: unknown): string {
  return typeof value === 'string' && /^\/(tickets(?:\/[a-zA-Z0-9-]+)?|human-tasks|experiences)(?:\?.*)?$/.test(value) ? value : '/tickets'
}

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/tickets' },
    { path: '/login', component: () => import('../views/LoginView.vue') },
    { path: '/tickets', component: () => import('../views/TicketListView.vue') },
    { path: '/tickets/new', component: () => import('../views/TicketCreateView.vue') },
    { path: '/tickets/:id', component: () => import('../views/TicketDetailView.vue') },
    { path: '/human-tasks', component: () => import('../views/HumanTasksView.vue') },
    { path: '/experiences', component: () => import('../views/ExperiencesView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/tickets' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach(async to => {
  const session = useSession()
  // 网络异常时留在登录入口，给出可操作的错误，不把异常当成账号无权限。
  try { await session.restore() } catch { return to.path === '/login' ? true : { path: '/login', query: { redirect: to.fullPath, reconnect: '1' } } }
  if (!session.user && to.path !== '/login') return { path: '/login', query: { redirect: to.fullPath, ...(session.expired ? { expired: '1' } : {}) } }
  if (session.user && to.path === '/login') return safeRedirect(to.query.redirect)
})
