<template>
  <el-container class="layout">
    <el-aside width="224px" class="sidebar">
      <div class="logo">
        <img class="glyph-img" src="/logo.jpg" alt="有信网安 LOGO" />
        <div class="logo-txt">
          <b>IT运维集中管控</b>
          <span class="logo-sub">SECURITY OPS CONSOLE</span>
        </div>
      </div>

      <nav class="nav">
        <template v-for="g in visibleGroups" :key="g.title">
          <div class="nav-title">{{ g.title }}</div>
          <el-menu
            router
            :default-active="$route.path"
            background-color="transparent"
            text-color="#8b96ab"
            active-text-color="#dff6ff"
            class="nav-menu"
          >
            <el-menu-item v-for="m in g.items" :key="m.path" :index="m.path">
              <el-icon><component :is="m.icon" /></el-icon>
              <span>{{ m.label }}</span>
            </el-menu-item>
          </el-menu>
        </template>
      </nav>

      <div class="foot">
        <span class="dot"></span>
        <span>数据同步正常</span>
      </div>
    </el-aside>

    <el-container class="body">
      <el-header class="topbar">
        <span class="crumb">工作台 <span class="sep">/</span> <b>{{ currentLabel }}</b></span>
        <div class="spacer" />
        <el-dropdown @command="onCommand">
          <span class="user">
            <span class="av">{{ initial }}</span>
            <span class="nm">{{ auth.user?.name || '管理员' }}</span>
            <span v-if="roleName" class="rl">{{ roleName }}</span>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="switch">切换账号</el-dropdown-item>
              <el-dropdown-item command="logout" divided>退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main class="main"><router-view /></el-main>
    </el-container>
  </el-container>
  <div class="watermark" :style="watermarkStyle" aria-hidden="true"></div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

onMounted(() => {
  if (!auth.user) auth.fetchMe().catch(() => {})
})

// 菜单 × 权限点（menu 权限点，来自后端角色权限矩阵）；sys_admin 显示全部
const MENU_GROUPS = [
  {
    title: '运营',
    items: [
      { path: '/dashboard', label: '仪表盘', perm: 'dashboard', icon: 'Odometer' },
      { path: '/customers', label: '客户管理', perm: 'customers', icon: 'OfficeBuilding' },
      { path: '/contracts', label: '项目管理', perm: 'contracts', icon: 'Folder' },
      { path: '/work-orders', label: '工单管理', perm: 'work_orders', icon: 'Tickets' },
      { path: '/sla', label: '工期管理', perm: 'sla', icon: 'Timer' },
    ],
  },
  {
    title: '安全',
    items: [
      { path: '/issues', label: '风险管控', perm: 'issues', icon: 'Warning' },
      { path: '/compliance', label: '合规运营', perm: 'compliance', icon: 'CircleCheck' },
      { path: '/deliveries', label: '项目验收', perm: 'deliveries', icon: 'Checked' },
    ],
  },
  {
    title: '组织',
    items: [
      { path: '/personnel', label: '人员管理', perm: 'personnel', icon: 'Avatar' },
      { path: '/performance', label: '绩效考核', perm: 'performance', icon: 'DataLine' },
      { path: '/reports', label: '报告中心', perm: 'reports', icon: 'Document' },
      { path: '/portal', label: '自助门户', perm: 'portal', icon: 'Monitor' },
      { path: '/knowledge', label: '知识库', perm: 'knowledge', icon: 'Collection' },
      { path: '/workflows', label: '工作流', perm: 'workflows', icon: 'Share' },
    ],
  },
]

const visibleGroups = computed(() => {
  if (!auth.user) return MENU_GROUPS // 用户信息未加载时先显示全部，避免闪烁
  return MENU_GROUPS.map((g) => ({ ...g, items: g.items.filter((m) => auth.hasPermission(m.perm)) })).filter(
    (g) => g.items.length,
  )
})

const currentLabel = computed(() => {
  for (const g of MENU_GROUPS) {
    const m = g.items.find((x) => x.path === route.path)
    if (m) return m.label
  }
  return '仪表盘'
})

const initial = computed(() => (auth.user?.name || '管理员').slice(0, 1))
const roleName = computed(() => auth.user?.roles?.[0]?.name || '')

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
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="300" height="160"><text x="150" y="100" font-size="14" fill="rgba(140,160,200,0.05)" transform="rotate(-25 150 100)" text-anchor="middle">${text}</text></svg>`
  return { backgroundImage: `url("data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}")` }
})
</script>

<style scoped>
.layout { height: 100vh; }

/* —— 侧栏 —— */
.sidebar {
  background: linear-gradient(180deg, #0d1728, #0a1120);
  border-right: 1px solid var(--app-line);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.logo {
  display: flex; align-items: center; gap: 11px; height: 60px; padding: 0 18px;
  border-bottom: 1px solid var(--app-line); flex: none;
}
.logo .glyph-img {
  width: 30px; height: 30px; border-radius: 7px; flex: none;
  object-fit: contain; background: #fff; padding: 2px; box-sizing: border-box;
}
.logo-txt { display: flex; flex-direction: column; line-height: 1.25; }
.logo-txt b { font-size: 13.5px; font-weight: 700; letter-spacing: .2px; color: var(--app-text); }
.logo-sub { font-size: 9px; color: var(--app-text-4); font-weight: 500; letter-spacing: 1px; }

.nav { flex: 1; overflow-y: auto; padding: 8px 10px 12px; }
.nav-title {
  font-size: 10px; color: var(--app-text-4); letter-spacing: 1.5px;
  padding: 14px 10px 6px; text-transform: uppercase;
}
.nav-menu { border-right: none !important; }
.nav-menu :deep(.el-menu-item) {
  height: 36px; line-height: 36px; margin: 1px 0; border-radius: 7px;
  border: 1px solid transparent; color: var(--app-text-3); font-size: 13px;
}
.nav-menu :deep(.el-menu-item .el-icon) { color: var(--app-text-4); margin-right: 10px; }
.nav-menu :deep(.el-menu-item:hover) { background: rgba(255, 255, 255, .03); color: var(--app-text); }
.nav-menu :deep(.el-menu-item.is-active) {
  background: linear-gradient(90deg, rgba(53, 200, 240, .16), rgba(53, 200, 240, .04));
  border-color: rgba(53, 200, 240, .25); color: #dff6ff;
}
.nav-menu :deep(.el-menu-item.is-active .el-icon) { color: var(--app-accent); }

.foot {
  flex: none; margin: 10px; padding: 10px 12px; border: 1px solid var(--app-line);
  border-radius: 7px; font-size: 11px; color: var(--app-text-4);
  display: flex; align-items: center; gap: 8px;
}
.foot .dot { width: 7px; height: 7px; border-radius: 50%; background: var(--app-ok); box-shadow: 0 0 0 3px rgba(45, 212, 191, .15); }

/* —— 顶栏 —— */
.body { display: flex; flex-direction: column; }
.topbar {
  background: rgba(14, 22, 38, .8); backdrop-filter: blur(8px);
  color: #fff; display: flex; align-items: center; gap: 14px;
  padding: 0 22px; border-bottom: 1px solid var(--app-line);
}
.crumb { font-size: 13px; color: var(--app-text-4); }
.crumb .sep { margin: 0 6px; color: var(--app-text-4); }
.crumb b { color: var(--app-text); font-weight: 600; }
.spacer { flex: 1; }
.user { display: flex; align-items: center; gap: 9px; cursor: pointer; color: var(--app-text); }
.user .av {
  width: 28px; height: 28px; border-radius: 50%; flex: none;
  background: linear-gradient(135deg, #1d3a5f, #0f1f33); border: 1px solid var(--app-line-2);
  display: grid; place-items: center; font-size: 12px; color: #a8c8ee; font-weight: 600;
}
.user .nm { font-size: 12.5px; font-weight: 550; }
.user .rl { font-size: 10.5px; color: var(--app-text-4); }

.main { background: var(--app-bg); }
.watermark { position: fixed; inset: 0; pointer-events: none; z-index: 9999; }
</style>
