<template>
  <div>
    <el-card>
      <div class="toolbar">
        <el-select v-model="filterType" placeholder="全部类型" clearable style="width: 150px" @change="onPage(1)">
          <el-option v-for="t in ISSUE_TYPES" :key="t" :label="t" :value="t" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="全部状态" clearable style="width: 150px" @change="onPage(1)">
          <el-option v-for="s in ISSUE_STATUS" :key="s" :label="s" :value="s" />
        </el-select>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="id" label="ID" width="60" />
        <el-table-column prop="type" label="隐患类型" width="110" />
        <el-table-column label="级别及数量" width="180">
          <template #default="{ row }">{{ levelCountsLabel(row) }}</template>
        </el-table-column>
        <el-table-column prop="description" label="隐患详情" show-overflow-tooltip />
        <el-table-column prop="customer_name" label="关联客户" width="140" show-overflow-tooltip />
        <el-table-column prop="ci_names" label="关联业务系统" width="150" show-overflow-tooltip />
        <el-table-column prop="work_order_no" label="关联工单" width="130" />
        <el-table-column prop="created_at" label="提交时间" width="170" />
        <el-table-column label="整改情况" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canWrite && row.status === '待整改'" link type="primary" @click="onAction(row, '整改中')">处置</el-button>
            <el-button v-if="canWrite" link type="warning" @click="onAction(row, '忽略')">忽略</el-button>
            <el-button v-if="canWrite" link type="info" @click="onAction(row, '误报')">标记误报</el-button>
            <el-button v-if="canDelete" link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="pager"
        layout="total, prev, pager, next"
        :total="total"
        :page-size="query.size"
        :current-page="query.page"
        @current-change="onPage"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listIssues, updateIssue, deleteIssue } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const canWrite = computed(() => auth.hasPermission('issue:write'))
const canDelete = computed(() => auth.hasPermission('issue:delete'))

const ISSUE_TYPES = ['安全漏洞', '配置缺陷', '基线不合规', '风险隐患']
const ISSUE_STATUS = ['待整改', '整改中', '已关闭', '忽略', '误报']

const rows = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, size: 20 })
const filterType = ref('')
const filterStatus = ref('')

function statusTag(status: string) {
  if (status === '已关闭') return 'success'
  if (status === '整改中') return 'warning'
  if (status === '忽略' || status === '误报') return 'info'
  return 'danger'
}
function levelCountsLabel(row: any) {
  if (row.level_counts) {
    try {
      const m = JSON.parse(row.level_counts)
      const order = ['严重', '高危', '中危', '低危', '其他']
      const parts = order.filter((l) => m[l]).map((l) => `${l}：${m[l]}`)
      if (parts.length) return parts.join('，')
    } catch { /* ignore */ }
  }
  return row.level ? `${row.level}：1` : '—'
}

async function load() {
  loading.value = true
  try {
    const params: any = { page: query.page, size: query.size }
    if (filterType.value) params.type = filterType.value
    if (filterStatus.value) params.status = filterStatus.value
    const r = (await listIssues(params)).data
    rows.value = r.items
    total.value = r.total
  } finally {
    loading.value = false
  }
}
function onPage(p: number) {
  query.page = p
  load()
}
async function onAction(row: any, status: string) {
  await updateIssue(row.id, { status })
  ElMessage.success('已更新')
  load()
}
async function onDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除隐患「${row.type}」？`, '删除', { type: 'warning' })
  } catch {
    return
  }
  await deleteIssue(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(() => {
  if (!auth.user) auth.fetchMe().catch(() => {})
  load()
})
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
