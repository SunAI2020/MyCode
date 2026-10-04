<template>
  <div>
    <el-card>
      <div class="toolbar">
        <el-button v-if="canWrite" type="primary" @click="openCreate">新增绩效</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="user_name" label="人员" width="110" />
        <el-table-column prop="work_order_no" label="工单" width="130" />
        <el-table-column prop="workload" label="工作量(工时)" width="110" />
        <el-table-column prop="dispatch_price" label="派单价格" width="100" />
        <el-table-column prop="ratio" label="分摊%" width="80" />
        <el-table-column prop="quality_score" label="质量评分" width="90" />
        <el-table-column prop="customer_score" label="客户评分" width="90" />
        <el-table-column prop="perf_score" label="绩效分" width="100" />
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column v-if="canWrite || canDelete" label="操作" width="120">
          <template #default="{ row }">
            <el-button v-if="canWrite" link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canDelete" link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="pager" layout="total, prev, pager, next" :total="total" :page-size="query.size" :current-page="query.page" @current-change="onPage" />
    </el-card>

    <el-dialog v-model="dlg" :title="editingId ? '编辑绩效' : '新增绩效'" width="480px">
      <el-form :model="form" label-width="100px">
        <el-form-item label="人员" required>
          <el-select v-model="form.user_id" filterable placeholder="选择人员" style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="工单" required>
          <el-select v-model="form.work_order_id" filterable placeholder="选择工单" style="width: 100%">
            <el-option v-for="w in workOrders" :key="w.id" :label="w.no" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="工作量(工时)"><el-input-number v-model="form.workload" :min="0" style="width: 100%" /></el-form-item>
        <el-form-item label="派单价格"><el-input-number v-model="form.dispatch_price" :min="0" :precision="2" style="width: 100%" /></el-form-item>
        <el-form-item label="分摊比例%"><el-input-number v-model="form.ratio" :min="0" :max="100" style="width: 100%" /></el-form-item>
        <el-form-item label="质量评分"><el-input-number v-model="form.quality_score" :min="0" :max="2" :step="0.1" style="width: 100%" /></el-form-item>
        <el-form-item label="客户评分"><el-input-number v-model="form.customer_score" :min="0" :max="2" :step="0.1" style="width: 100%" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dlg = false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listPerformance, createPerformance, updatePerformance, deletePerformance, listUsers, listWorkOrders } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const canWrite = computed(() => auth.roles().some((r: string) => ['sys_admin', 'sys_ops', 'ticket_mgr'].includes(r)))
const canDelete = computed(() => auth.roles().some((r: string) => ['sys_admin', 'sys_ops'].includes(r)))

const rows = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, size: 20 })
const users = ref<any[]>([])
const workOrders = ref<any[]>([])
const dlg = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({ user_id: null as number | null, work_order_id: null as number | null, workload: 0, dispatch_price: 0, ratio: 100, quality_score: 1.0, customer_score: 1.0 })

async function load() {
  loading.value = true
  try {
    const r = (await listPerformance({ page: query.page, size: query.size })).data
    rows.value = r.items
    total.value = r.total
  } finally {
    loading.value = false
  }
}
async function loadRefs() {
  users.value = (await listUsers()).data
  workOrders.value = (await listWorkOrders({ page: 1, size: 100 })).data.items
}
function openCreate() {
  editingId.value = null
  Object.assign(form, { user_id: null, work_order_id: null, workload: 0, dispatch_price: 0, ratio: 100, quality_score: 1.0, customer_score: 1.0 })
  dlg.value = true
}
function openEdit(row: any) {
  editingId.value = row.id
  Object.assign(form, { user_id: row.user_id, work_order_id: row.work_order_id, workload: row.workload, dispatch_price: row.dispatch_price, ratio: row.ratio, quality_score: row.quality_score, customer_score: row.customer_score })
  dlg.value = true
}
async function save() {
  if (!form.user_id || !form.work_order_id) return ElMessage.warning('请选择人员与工单')
  const payload = { user_id: form.user_id, work_order_id: form.work_order_id, workload: form.workload, dispatch_price: form.dispatch_price, ratio: form.ratio, quality_score: form.quality_score, customer_score: form.customer_score }
  if (editingId.value) await updatePerformance(editingId.value, payload)
  else await createPerformance(payload)
  ElMessage.success('已保存')
  dlg.value = false
  load()
}
async function onDelete(row: any) {
  await ElMessageBox.confirm('确认删除该绩效记录？', '提示', { type: 'warning' })
  await deletePerformance(row.id)
  ElMessage.success('已删除')
  load()
}
function onPage(p: number) {
  query.page = p
  load()
}
onMounted(() => {
  load()
  loadRefs()
})
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
