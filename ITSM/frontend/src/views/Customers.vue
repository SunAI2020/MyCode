<template>
  <div>
    <el-card>
      <div class="toolbar">
        <el-input v-model="query.name" placeholder="按名称搜索" style="width: 220px" clearable @keyup.enter="load" />
        <el-button v-if="canWrite" type="primary" @click="openCreate">新增客户</el-button>
      </div>
      <div v-loading="loading">
        <div class="lane" v-for="col in customerLanes" :key="col.key">
          <div class="lane-head">
            <span class="lane-title">{{ col.title }}</span>
            <span class="lane-count">{{ col.list.length }}</span>
          </div>
          <el-table v-if="col.list.length" :data="col.list" size="small" border>
            <el-table-column prop="id" label="ID" width="70" />
            <el-table-column prop="name" label="客户名称" />
            <el-table-column prop="short_name" label="简称" width="120" />
            <el-table-column prop="industry" label="行业" />
            <el-table-column prop="level" label="级别" width="90" />
            <el-table-column prop="contact" label="联系人" />
            <el-table-column prop="status" label="状态" width="90" />
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button v-if="canWrite" link type="primary" @click="openEdit(row)">编辑</el-button>
                <el-button v-if="canDelete" link type="danger" @click="onDelete(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="lane-empty">暂无</div>
        </div>
      </div>
    </el-card>

    <el-dialog v-model="dlg" :title="editId ? '编辑客户' : '新增客户'" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="简称"><el-input v-model="form.short_name" /></el-form-item>
        <el-form-item label="级别">
          <el-select v-model="form.level" style="width: 100%">
            <el-option v-for="l in ['金牌', '银牌', '普通', '黑名单']" :key="l" :label="l" :value="l" />
          </el-select>
        </el-form-item>
        <el-form-item label="行业"><el-input v-model="form.industry" /></el-form-item>
        <el-form-item label="联系人"><el-input v-model="form.contact" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option v-for="s in ['合作中', '已暂停', '洽谈中']" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listCustomers, createCustomer, updateCustomer, deleteCustomer } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const canWrite = computed(() => auth.hasPermission('customer:write'))
const canDelete = computed(() => auth.hasPermission('customer:delete'))

const rows = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, size: 100, name: '' })
const dlg = ref(false)
const editId = ref<number | null>(null)
const form = reactive({ name: '', short_name: '', level: '普通', industry: '', contact: '', status: '合作中' })

const CUSTOMER_STATUSES = ['合作中', '洽谈中', '已暂停']
const customerLanes = computed(() => {
  const lanes = CUSTOMER_STATUSES.map((s) => ({
    key: s,
    title: s,
    list: rows.value.filter((c: any) => c.status === s),
  }))
  const known = new Set(CUSTOMER_STATUSES)
  const others = rows.value.filter((c: any) => !known.has(c.status))
  if (others.length) lanes.push({ key: '其他', title: '其他', list: others })
  return lanes
})

async function load() {
  loading.value = true
  try {
    const res = await listCustomers(query)
    rows.value = res.data.items
    total.value = res.data.total
  } finally {
    loading.value = false
  }
}
function onPage(p: number) {
  query.page = p
  load()
}
function openCreate() {
  editId.value = null
  Object.assign(form, { name: '', short_name: '', level: '普通', industry: '', contact: '', status: '合作中' })
  dlg.value = true
}
function openEdit(row: any) {
  editId.value = row.id
  Object.assign(form, { name: row.name, short_name: row.short_name, level: row.level, industry: row.industry, contact: row.contact, status: row.status })
  dlg.value = true
}
async function save() {
  if (editId.value) {
    await updateCustomer(editId.value, form)
  } else {
    await createCustomer(form)
  }
  ElMessage.success('已保存')
  dlg.value = false
  load()
}
async function onDelete(row: any) {
  await ElMessageBox.confirm(`确认删除客户「${row.name}」？`, '提示', { type: 'warning' })
  await deleteCustomer(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
.lane { margin-bottom: 16px; }
.lane-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.lane-title { font-weight: 600; color: var(--app-text); }
.lane-count { color: var(--app-text-3); font-size: 12px; }
.lane-empty { color: var(--app-text-4); font-size: 13px; padding: 4px 0; }
</style>
