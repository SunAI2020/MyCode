<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2>IT运维集中管控平台</h2>
      <p class="sub">合同 → 子项 → 工单 全链路集中管控</p>
      <el-form :model="form" label-width="0" @keyup.enter="onLogin">
        <el-form-item>
          <el-input v-model="form.username" placeholder="用户名" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" type="password" placeholder="密码" show-password />
        </el-form-item>
        <el-button type="primary" style="width: 100%" :loading="loading" @click="onLogin">登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { login } from '@/api'

const router = useRouter()
const auth = useAuthStore()
const form = reactive({ username: 'admin', password: 'admin123' })
const loading = ref(false)

async function onLogin() {
  if (!form.username || !form.password) {
    ElMessage.warning('请输入用户名和密码')
    return
  }
  loading.value = true
  try {
    const res = await login(form)
    auth.setToken(res.data.access_token)
    auth.setUser(res.data.user)
    ElMessage.success('登录成功')
    router.push('/')
  } catch {
    // 拦截器已提示
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: radial-gradient(900px 600px at 70% -10%, #16304d 0%, #0b1220 55%);
}
.login-card { width: 360px; }
.sub { color: var(--app-text-3); font-size: 13px; margin: 4px 0 16px; }
</style>
