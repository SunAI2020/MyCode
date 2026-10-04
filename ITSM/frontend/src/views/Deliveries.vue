<template>
  <div>
    <el-card>
      <div class="toolbar">
        <el-button v-if="canWrite" type="primary" @click="openCreate">新增交付</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="title" label="标题" show-overflow-tooltip />
        <el-table-column prop="report_type" label="报告类型" width="110" />
        <el-table-column prop="customer_name" label="客户" width="130" />
        <el-table-column prop="project_name" label="项目" width="140" show-overflow-tooltip />
        <el-table-column prop="work_order_no" label="关联工单" width="120" />
        <el-table-column prop="report_id" label="报告编号" width="130" />
        <el-table-column label="签署" width="90">
          <template #default="{ row }">
            <el-tag :type="row.sign === '已签署' ? 'success' : 'info'" size="small">{{ row.sign }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column v-if="canWrite || canDelete" label="操作" width="150">
          <template #default="{ row }">
            <el-button v-if="canWrite && row.sign !== '已签署'" link type="success" @click="onSign(row)">签署</el-button>
            <el-button v-if="canWrite" link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canDelete" link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="pager" layout="total, prev, pager, next" :total="total" :page-size="query.size" :current-page="query.page" @current-change="onPage" />
    </el-card>

    <el-dialog v-model="dlg" :title="editingId ? '编辑交付' : '新增交付'" width="480px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="标题" required><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="报告类型">
          <el-select v-model="form.report_type" style="width: 100%">
            <el-option v-for="t in REPORT_TYPES" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联项目">
          <el-select v-model="form.contract_id" clearable filterable placeholder="选择项目" style="width: 100%">
            <el-option v-for="c in contracts" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="报告编号"><el-input v-model="form.report_id" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dlg = false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listDeliveries, createDelivery, updateDelivery, deleteDelivery, signDelivery, listContracts } from '@/api'
import { useAuthStore } from '@/stores/auth'

const REPORT_TYPES = ['运维报告', '履职报告', '验收报告', '安全报告', '其他']

const auth = useAuthStore()
const canWrite = computed(() => auth.roles().some((r: string) => ['sys_admin', 'sys_ops', 'ticket_mgr'].includes(r)))
const canDelete = computed(() => auth.roles().some((r: string) => ['sys_admin', 'sys_ops'].includes(r)))

const rows = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, size: 20 })
const contracts = ref<any[]>([])
const dlg = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({ title: '', report_type: '运维报告', contract_id: null as number | null, report_id: '' })

async function load() {
  loading.value = true
  try {
    const r = (await listDeliveries({ page: query.page, size: query.size })).data
    rows.value = r.items
    total.value = r.total
  } finally {
    loading.value = false
  }
}
async function loadContracts() {
  contracts.value = (await listContracts({ page: 1, size: 100 })).data.items
}
function openCreate() {
  editingId.value = null
  Object.assign(form, { title: '', report_type: '运维报告', contract_id: null, report_id: '' })
  dlg.value = true
}
function openEdit(row: any) {
  editingId.value = row.id
  Object.assign(form, { title: row.title, report_type: row.report_type, contract_id: row.contract_id, report_id: row.report_id })
  dlg.value = true
}
async function save() {
  if (!form.title.trim()) return ElMessage.warning('请填写标题')
  const payload = { title: form.title, report_type: form.report_type, contract_id: form.contract_id, report_id: form.report_id }
  if (editingId.value) await updateDelivery(editingId.value, payload)
  else await createDelivery(payload)
  ElMessage.success('已保存')
  dlg.value = false
  load()
}
async function onSign(row: any) {
  await ElMessageBox.confirm(`确认签署「${row.title}」？`, '提示', { type: 'warning' })
  await signDelivery(row.id)
  ElMessage.success('已签署')
  load()
}
async function onDelete(row: any) {
  await ElMessageBox.confirm(`确认删除「${row.title}」？`, '提示', { type: 'warning' })
  await deleteDelivery(row.id)
  ElMessage.success('已删除')
  load()
}
function onPage(p: number) {
  query.page = p
  load()
}
onMounted(() => {
  load()
  loadContracts()
})
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
