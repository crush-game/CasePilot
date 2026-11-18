import { defineStore } from 'pinia'
import { ref } from 'vue'
import { csrfToken, request, setCsrf, ApiError } from '../api/client'
import type { LoginResult, User } from '../types'

export const useSession = defineStore('session', () => {
  const user = ref<User | null>(null)
  const initialized = ref(false)
  const expired = ref(false)
  let restoring: Promise<void> | null = null

  async function restore() {
    if (initialized.value) return
    if (!restoring) restoring = (async () => {
      if (!csrfToken()) { initialized.value = true; return }
      try { user.value = await request<User>('/auth/me') }
      catch (error) {
        if (!(error instanceof ApiError) || error.status !== 401) throw error
        expired.value = true
        setCsrf('')
      }
      initialized.value = true
    })().finally(() => { restoring = null })
    return restoring
  }

  async function login(login: string, password: string) {
    const result = await request<LoginResult>('/auth/login', { method: 'POST', body: JSON.stringify({ login, password }) })
    setCsrf(result.csrf_token)
    user.value = result.user
    expired.value = false
    initialized.value = true
  }

  function expire() { user.value = null; setCsrf(''); initialized.value = true; expired.value = true }
  async function logout() {
    await request<void>('/auth/logout', { method: 'POST' })
    expire()
    expired.value = false
  }
  return { user, initialized, expired, restore, login, logout, expire }
})
