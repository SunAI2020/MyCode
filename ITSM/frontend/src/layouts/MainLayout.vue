<template>
  <el-container class="layout">
    <el-header class="topbar">
      <span class="brand">IT运维集中管控平台</span>
      <div class="spacer" />
      <el-dropdown @command="onCommand">
        <span class="user">{{ auth.user?.name || '管理员' }}</span>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item command="switch">切换账号</el-dropdown-item>
            <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </el-header>
    <el-container>
      <el-aside width="200px" class="sidebar">
        <el-menu
          router
          :default-active="$route.path"
          background-color="#0f2440"
          text-color="#cbd5e1"
          active-text-color="#fff"
        >
          <el-menu-item v-for="m in visibleMenu" :key="m.path" :index="m.path">{{ m.label }}</el-menu-item>
        </el-menu>
      </el-aside>
      <el-main class="main"><router-view /></el-main>
    </el-container>
  </el-container>
  <div class="watermark" :style="watermarkStyle" aria-hidden="true"></div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

onMounted(() => {
  if (!auth.user) auth.fetchMe().catch(() => {})
})

// 菜单 × 权限点（menu 权限点，来自后端角色权限矩阵）；sys_admin 显示全部
const MENU_ITEMS = [
  { path: '/dashboard', label: '仪表盘', perm: 'dashboard' },
  { path: '/customers', label: '客户管理', perm: 'customers' },
  { path: '/contracts', label: '项目管理', perm: 'contracts' },
  { path: '/work-orders', label: '工单管理', perm: 'work_orders' },
  { path: '/sla', label: '工期管理', perm: 'sla' },
  { path: '/issues', label: '风险管控', perm: 'issues' },
  { path: '/compliance', label: '合规运营', perm: 'compliance' },
  { path: '/deliveries', label: '项目验收', perm: 'deliveries' },
  { path: '/personnel', label: '人员管理', perm: 'personnel' },
  { path: '/performance', label: '绩效考核', perm: 'performance' },
  { path: '/reports', label: '报告中心', perm: 'reports' },
  { path: '/portal', label: '自助门户', perm: 'portal' },
  { path: '/knowledge', label: '知识库', perm: 'knowledge' },
  { path: '/workflows', label: '工作流', perm: 'workflows' },
]

const visibleMenu = computed(() => {
  if (!auth.user) return MENU_ITEMS // 用户信息未加载时先显示全部，避免闪烁
  return MENU_ITEMS.filter((m) => auth.hasPermission(m.perm))
})

function onCommand(cmd: string) {
  if (cmd === 'switch' || cmd === 'logout') {
    auth.logout()
    router.push('/login')
  }
}

// 全屏水印：用户名 + 日期，防拍照/截图泄露（pointer-events 不拦截交互）
const watermarkStyle = computed(() => {
  const name = auth.user?.name || 'IT运维集中管控平台'
  const text = `${name} · ${new Date().toLocaleDateString('zh-CN')}`
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="300" height="160"><text x="150" y="100" font-size="14" fill="rgba(60,80,120,0.07)" transform="rotate(-25 150 100)" text-anchor="middle">${text}</text></svg>`
  return { backgroundImage: `url("data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}")` }
})
</script>

<style scoped>
.layout { height: 100vh; }
.topbar { background: #0a3d91; color: #fff; display: flex; align-items: center; }
.brand { font-weight: 700; font-size: 17px; }
.spacer { flex: 1; }
.user { color: #fff; cursor: pointer; }
.sidebar { background: #0f2440; }
.main { background: #f5f7fa; }
.watermark { position: fixed; inset: 0; pointer-events: none; z-index: 9999; }
</style>
