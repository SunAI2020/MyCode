<template>
  <div>
    <el-card>
      <div class="toolbar">
        <el-button type="primary" @click="openCreate">新增人员</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
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
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listUsers, createUser, updateUser, deleteUser, listCustomers } from '@/api'

const ROLE_OPTIONS = [
  { code: 'sys_admin', name: '系统管理员' },
  { code: 'sys_ops', name: '系统运维人员' },
  { code: 'ticket_mgr', name: '工单管理人员' },
  { code: 'cs_staff', name: '客服人员' },
  { code: 'sec_staff', name: '安服人员' },
  { code: 'cust_admin', name: '客户系统管理员' },
  { code: 'cust_service', name: '客户服务管理人员' },
  { code: 'outsource', name: '外包人员' },
]

const rows = ref<any[]>([])
const customers = ref<any[]>([])
const loading = ref(false)
const dlg = ref(false)
const editId = ref<number | null>(null)
const form = reactive<any>({ username: '', name: '', password: '', phone: '', dept: '', role_codes: [], customer_id: null })
const needsCustomer = computed(() => (form.role_codes || []).some((c: string) => ['cust_admin', 'cust_service'].includes(c)))

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
</style>
