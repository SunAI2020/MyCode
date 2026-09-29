import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
})

request.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

request.interceptors.response.use(
  (response) => {
    const res = response.data
    if (res.code !== 0) {
      ElMessage.error(res.message || '请求失败')
      return Promise.reject(new Error(res.message || '请求失败'))
    }
    return res
  },
  (error) => {
    const status = error.response?.status
    const data = error.response?.data
    // FastAPI 统一响应用 message；未捕获异常(500)默认用 detail，两种都要能透出
    const msg = data?.message || data?.detail
    if (status === 401) {
      // 凭证无效/过期：清除本地 token 并回到登录页，避免带着失效 token 卡死在页内
      localStorage.removeItem('token')
      if (window.location.pathname !== '/login') {
        ElMessage.error(msg || '凭证无效或已过期')
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }
    if (error.response) {
      ElMessage.error(msg || `请求失败(${status})`)
    } else {
      ElMessage.error('无法连接后端服务，请确认后端已启动（端口 8000）')
    }
    return Promise.reject(error)
  },
)

export default request
