<template>
  <div>
    <el-card>
      <div class="toolbar">
        <el-button v-if="canWrite" type="primary" @click="openCreate">新增人员</el-button>
        <el-button v-if="canEditPerm" @click="openPerm">权限设置</el-button>
      </div>
      <div v-for="sec in personnelSections" :key="sec.key" class="ps-section">
        <div class="ps-section-head">
          <span class="ps-section-title">{{ sec.title }}</span>
          <span class="ps-section-count">{{ sec.rows.length }}</span>
        </div>
        <el-table v-if="sec.rows.length" :data="sec.rows" v-loading="loading" size="small" border>
          <el-table-column prop="id" label="ID" width="60" />
          <el-table-column prop="name" label="姓名" width="120" />
          <el-table-column prop="username" label="登录名" width="130" />
          <el-table-column prop="phone" label="电话" width="130" />
          <el-table-column prop="dept" label="部门" width="130" />
          <el-table-column label="角色" show-overflow-tooltip>
            <template #default="{ row }">{{ (row.roles || []).map((r: any) => r.name).join('、') }}</template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }"><el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">{{ row.status === 'active' ? '启用' : '停用' }}</el-tag></template>
          </el-table-column>
          <el-table-column label="操作" width="140">
            <template #default="{ row }">
              <el-button v-if="canWrite" link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button v-if="canWrite" link type="danger" @click="onDelete(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-else class="ps-section-empty">暂无</div>
      </div>
    </el-card>

    <el-dialog v-model="dlg" :title="editId ? '编辑人员' : '新增人员'" width="520px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="姓名" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="登录名" required><el-input v-model="form.username" :disabled="!!editId" /></el-form-item>
        <el-form-item :label="editId ? '重置密码' : '密码'" :required="!editId">
          <el-input v-model="form.password" type="password" show-password :placeholder="editId ? '留空则不修改' : ''" />
        </el-form-item>
        <el-form-item label="电话"><el-input v-model="form.phone" /></el-form-item>
        <el-form-item label="部门"><el-input v-model="form.dept" /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role_codes" multiple style="width: 100%">
            <el-option v-for="r in ROLE_OPTIONS" :key="r.code" :label="r.name" :value="r.code" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="needsCustomer" label="所属客户" required>
          <el-select v-model="form.customer_id" style="width: 100%" placeholder="客户侧角色需绑定客户">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="dlg = false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>

    <el-drawer v-model="permDlg" title="人员权限设置（角色权限矩阵）" size="720px">
      <div class="perm-layout">
        <div class="perm-roles">
          <div v-for="r in permRoles" :key="r.code"
               :class="['perm-role', { active: r.code === activeRole }]"
               @click="selectRole(r.code)">
            <div class="perm-role-name">{{ r.name }}</div>
            <div class="perm-role-code">{{ r.code }}</div>
          </div>
        </div>
        <div class="perm-panel">
          <template v-if="activeRole">
            <div class="perm-panel-title">{{ activeRoleName }} · 权限点</div>
            <div v-for="group in permGroups" :key="group.type" class="perm-group">
              <div class="perm-group-title">{{ group.title }}</div>
              <el-checkbox-group v-model="activePerms" class="perm-checks">
                <el-checkbox v-for="p in group.items" :key="p.code" :value="p.code">{{ p.name }}</el-checkbox>
              </el-checkbox-group>
            </div>
          </template>
        </div>
      </div>
      <template #footer>
        <el-button @click="permDlg = false">取消</el-button>
        <el-button type="primary" @click="savePerm">保存</el-button>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listUsers, createUser, updateUser, deleteUser, listCustomers, listPermissions, listRoles, getRolePermissions, updateRolePermissions } from '@/api'
import { useAuthStore } from '@/stores/auth'

const ROLE_OPTIONS = [
  { code: 'sys_admin', name: '系统管理员' },
  { code: 'sys_ops', name: '系统运维人员' },
  { code: 'ticket_mgr', name: '工单管理人员' },
  { code: 'cs_staff', name: '客服人员' },
  { code: 'sec_staff', name: '工程师' },
  { code: 'cust_admin', name: '客户系统管理员' },
  { code: 'cust_service', name: '客户服务管理人员' },
  { code: 'outsource', name: '外包人员' },
  { code: 'auditor', name: '审计' },
  { code: 'bidder', name: '招标' },
  { code: 'biz_supervisor', name: '业务主管' },
]

const rows = ref<any[]>([])
const customers = ref<any[]>([])
const loading = ref(false)
const dlg = ref(false)
const editId = ref<number | null>(null)
const form = reactive<any>({ username: '', name: '', password: '', phone: '', dept: '', role_codes: [], customer_id: null })
const needsCustomer = computed(() => (form.role_codes || []).some((c: string) => ['cust_admin', 'cust_service'].includes(c)))

// ---- 竖向分栏：服务人员（我方）/ 客户人员 / 第三方人员 ----
const PERSONNEL_SECTIONS = [
  { key: 'service', title: '服务人员（我方人员）' },
  { key: 'customer', title: '客户人员' },
  { key: 'third_party', title: '第三方人员（审计、招标、业务主管）' },
]
const CUSTOMER_CODES = ['cust_admin', 'cust_service']
const THIRD_PARTY_CODES = ['auditor', 'bidder', 'biz_supervisor']
function categoryOf(row: any): string {
  const codes = (row.roles || []).map((r: any) => r.code)
  if (codes.some((c: string) => THIRD_PARTY_CODES.includes(c))) return 'third_party'
  if (codes.some((c: string) => CUSTOMER_CODES.includes(c))) return 'customer'
  return 'service'
}
const personnelSections = computed(() => {
  const buckets: Record<string, any[]> = { service: [], customer: [], third_party: [] }
  for (const r of rows.value) buckets[categoryOf(r)].push(r)
  return PERSONNEL_SECTIONS.map((sec) => ({ ...sec, rows: buckets[sec.key] }))
})

// ---- 权限矩阵 ----
const auth = useAuthStore()
const canEditPerm = computed(() => auth.hasPermission('role:write'))
const canWrite = computed(() => auth.hasPermission('user:write'))
const permDlg = ref(false)
const permRoles = ref<any[]>([])
const permList = ref<any[]>([])
const activeRole = ref('')
const activePerms = ref<string[]>([])

const permGroups = computed(() => [
  { type: 'menu', title: '菜单权限', items: permList.value.filter((p: any) => p.type === 'menu') },
  { type: 'action', title: '操作权限', items: permList.value.filter((p: any) => p.type === 'action') },
])
const activeRoleName = computed(() => permRoles.value.find((r: any) => r.code === activeRole.value)?.name || '')

async function openPerm() {
  permDlg.value = true
  try {
    const [rs, ps] = await Promise.all([listRoles(), listPermissions()])
    permRoles.value = rs.data
    permList.value = ps.data
    if (permRoles.value.length) await selectRole(permRoles.value[0].code)
  } catch { /* 加载失败不阻断 */ }
}
let permReqSeq = 0
async function selectRole(code: string) {
  activeRole.value = code
  const seq = ++permReqSeq
  try {
    const perms = (await getRolePermissions(code)).data
    if (seq === permReqSeq) activePerms.value = perms // 仅应用最新一次请求，防快速切换竞态
  } catch {
    if (seq === permReqSeq) activePerms.value = []
  }
}
async function savePerm() {
  if (!activeRole.value) return
  try {
    await updateRolePermissions(activeRole.value, { permission_codes: activePerms.value })
    ElMessage.success('已保存权限矩阵')
  } catch {
    // 后端拒绝（如 sys_admin 自锁保护）时由响应拦截器统一提示，此处仅避免未捕获异常
  }
}

async function load() {
  loading.value = true
  try {
    rows.value = (await listUsers()).data
  } finally {
    loading.value = false
  }
}
function openCreate() {
  editId.value = null
  Object.assign(form, { username: '', name: '', password: '', phone: '', dept: '', role_codes: [], customer_id: null })
  dlg.value = true
}
function openEdit(row: any) {
  editId.value = row.id
  Object.assign(form, {
    username: row.username,
    name: row.name,
    password: '',
    phone: row.phone || '',
    dept: row.dept || '',
    role_codes: (row.roles || []).map((r: any) => r.code),
    customer_id: row.customer_id ?? null,
  })
  dlg.value = true
}
async function save() {
  if (!form.name) return ElMessage.warning('请填写姓名')
  if (!form.username) return ElMessage.warning('请填写登录名')
  if (!editId.value && !form.password) return ElMessage.warning('请填写密码')
  if (needsCustomer.value && !form.customer_id) return ElMessage.warning('请选择所属客户')
  const data: any = { ...form }
  if (editId.value && !data.password) delete data.password
  if (editId.value) await updateUser(editId.value, data)
  else await createUser(data)
  ElMessage.success('已保存')
  dlg.value = false
  load()
}
async function onDelete(row: any) {
  await ElMessageBox.confirm(`确认删除人员「${row.name}」？`, '提示', { type: 'warning' })
  await deleteUser(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(async () => {
  load()
  try {
    customers.value = (await listCustomers({ page: 1, size: 100 })).data.items
  } catch {
    // 客户下拉加载失败不阻断人员列表
  }
})
</script>

<style scoped>
.toolbar { margin-bottom: 14px; }
.ps-section { margin-bottom: 16px; }
.ps-section-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.ps-section-title { font-weight: 600; color: #303133; }
.ps-section-count { color: #909399; font-size: 12px; }
.ps-section-empty { color: #c0c4cc; font-size: 13px; padding: 4px 0; }
.perm-layout { display: flex; gap: 16px; min-height: 420px; }
.perm-roles { width: 180px; flex-shrink: 0; border-right: 1px solid #e5e7eb; padding-right: 12px; }
.perm-role { padding: 8px 12px; border-radius: 6px; cursor: pointer; margin-bottom: 4px; }
.perm-role:hover { background: #f1f5f9; }
.perm-role.active { background: #0a3d91; color: #fff; }
.perm-role-name { font-size: 14px; font-weight: 600; }
.perm-role-code { font-size: 12px; opacity: 0.7; }
.perm-panel { flex: 1; }
.perm-panel-title { font-size: 15px; font-weight: 700; margin-bottom: 12px; color: #0a3d91; }
.perm-group { margin-bottom: 18px; }
.perm-group-title { font-size: 13px; font-weight: 600; color: #475569; margin-bottom: 8px; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; }
.perm-checks { display: flex; flex-wrap: wrap; gap: 4px 8px; }
.perm-checks :deep(.el-checkbox) { margin-right: 0; }
</style>
