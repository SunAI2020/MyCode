import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getMe } from '@/api'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem('token') || '')
  const user = ref<any>(null)

  function setToken(t: string) {
    token.value = t
    localStorage.setItem('token', t)
  }
  function setUser(u: any) {
    user.value = u
  }
  function roles(): string[] {
    return (user.value?.roles || []).map((r: any) => r.code)
  }
  async function fetchMe() {
    const res = await getMe()
    setUser(res.data)
    return res.data
  }
  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
  }

  return { token, user, setToken, setUser, roles, fetchMe, logout }
})
