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
        <el-table-column prop="level" label="级别" width="80">
          <template #default="{ row }">
            <el-tag :type="levelTag(row.level)" size="small">{{ row.level }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="隐患描述" show-overflow-tooltip />
        <el-table-column prop="work_order_id" label="关联工单" width="90" />
        <el-table-column label="整改状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="发现时间" width="170" />
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
import { onMounted, reactive, ref } from 'vue'
import { listIssues } from '@/api'

const ISSUE_TYPES = ['安全漏洞', '配置缺陷', '基线不合规', '风险隐患']
const ISSUE_STATUS = ['待整改', '整改中', '已关闭']

const rows = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, size: 20 })
const filterType = ref('')
const filterStatus = ref('')

function levelTag(level: string) {
  return level === '高' ? 'danger' : level === '中' ? 'warning' : 'info'
}
function statusTag(status: string) {
  return status === '已关闭' ? 'success' : status === '整改中' ? 'warning' : 'danger'
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

onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
