<template>
  <div>
    <el-card>
      <div class="toolbar">
        <el-select v-model="filterType" placeholder="全部类型" clearable style="width: 150px" @change="onPage(1)">
          <el-option v-for="t in REPORT_TYPES" :key="t" :label="t" :value="t" />
        </el-select>
        <el-select v-model="filterStatus" placeholder="全部状态" clearable style="width: 150px" @change="onPage(1)">
          <el-option v-for="s in REPORT_STATUS" :key="s" :label="s" :value="s" />
        </el-select>
        <el-button v-if="canWrite" type="primary" @click="openCreate">新增报告</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="title" label="标题" show-overflow-tooltip />
        <el-table-column prop="report_type" label="报告类型" width="110" />
        <el-table-column prop="customer_name" label="客户" width="130" />
        <el-table-column prop="project_name" label="项目" width="140" show-overflow-tooltip />
        <el-table-column prop="work_order_no" label="关联工单" width="120" />
        <el-table-column prop="report_no" label="报告编号" width="130" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="statusTag(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="summary" label="摘要" show-overflow-tooltip />
        <el-table-column prop="created_at" label="创建时间" width="170" />
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button v-if="row.has_file" link type="info" @click="openPreview(row)">预览</el-button>
            <el-button v-if="row.has_file" link type="success" @click="onDownload(row)">下载</el-button>
            <el-button v-if="row.html_filename" link type="warning" @click="onDownloadGenerated(row, 'html')">HTML</el-button>
            <el-button v-if="row.docx_filename" link type="warning" @click="onDownloadGenerated(row, 'docx')">Word</el-button>
            <el-button v-if="canWrite" link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canDelete" link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="pager" layout="total, prev, pager, next" :total="total" :page-size="query.size" :current-page="query.page" @current-change="onPage" />
    </el-card>

    <el-dialog v-model="dlg" :title="editingId ? '编辑报告' : '新增报告'" width="520px">
      <el-form :model="form" label-width="90px">
        <el-form-item label="标题" required><el-input v-model="form.title" /></el-form-item>
        <el-form-item label="报告类型">
          <el-select v-model="form.report_type" style="width: 100%">
            <el-option v-for="t in REPORT_TYPES" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="客户">
          <el-select v-model="form.customer_id" clearable filterable placeholder="选择客户" style="width: 100%">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目">
          <el-select v-model="form.contract_id" clearable filterable placeholder="选择项目" style="width: 100%">
            <el-option v-for="c in contracts" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="报告编号"><el-input v-model="form.report_no" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option v-for="s in REPORT_STATUS" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
        <el-form-item label="摘要"><el-input v-model="form.summary" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dlg = false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="previewDlg" :title="previewData.title || '报告预览'" width="720px">
      <pre class="preview-text">{{ previewData.masked_text || '（无可预览文本）' }}</pre>
      <template #footer><el-button @click="previewDlg = false">关闭</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listReportLedger, createReportLedger, updateReportLedger, deleteReportLedger, listCustomers, listContracts, previewReport, downloadReport, downloadGeneratedReport } from '@/api'
import { useAuthStore } from '@/stores/auth'

const REPORT_TYPES = ['运维报告', '履职报告', '验收报告', '安全报告', '其他']
const REPORT_STATUS = ['草稿', '已提交', '已签署']

const auth = useAuthStore()
const canWrite = computed(() => auth.roles().some((r: string) => ['sys_admin', 'sys_ops', 'ticket_mgr'].includes(r)))
const canDelete = computed(() => auth.roles().some((r: string) => ['sys_admin', 'sys_ops'].includes(r)))

const rows = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, size: 20 })
const filterType = ref('')
const filterStatus = ref('')
const customers = ref<any[]>([])
const contracts = ref<any[]>([])
const dlg = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({ title: '', report_type: '运维报告', customer_id: null as number | null, contract_id: null as number | null, report_no: '', status: '草稿', summary: '' })
const previewDlg = ref(false)
const previewData = ref<any>({})

function statusTag(s: string) {
  return s === '已签署' ? 'success' : s === '已提交' ? 'primary' : 'info'
}

async function load() {
  loading.value = true
  try {
    const params: any = { page: query.page, size: query.size }
    if (filterType.value) params.report_type = filterType.value
    if (filterStatus.value) params.status = filterStatus.value
    const r = (await listReportLedger(params)).data
    rows.value = r.items
    total.value = r.total
  } finally {
    loading.value = false
  }
}
async function loadRefs() {
  customers.value = (await listCustomers({ page: 1, size: 100 })).data.items
  contracts.value = (await listContracts({ page: 1, size: 100 })).data.items
}
function openCreate() {
  editingId.value = null
  Object.assign(form, { title: '', report_type: '运维报告', customer_id: null, contract_id: null, report_no: '', status: '草稿', summary: '' })
  dlg.value = true
}
function openEdit(row: any) {
  editingId.value = row.id
  Object.assign(form, { title: row.title, report_type: row.report_type, customer_id: row.customer_id, contract_id: row.contract_id, report_no: row.report_no, status: row.status, summary: row.summary })
  dlg.value = true
}
async function save() {
  if (!form.title.trim()) return ElMessage.warning('请填写标题')
  const payload = { title: form.title, report_type: form.report_type, customer_id: form.customer_id, contract_id: form.contract_id, report_no: form.report_no, status: form.status, summary: form.summary }
  if (editingId.value) await updateReportLedger(editingId.value, payload)
  else await createReportLedger(payload)
  ElMessage.success('已保存')
  dlg.value = false
  load()
}
async function onDelete(row: any) {
  await ElMessageBox.confirm(`确认删除「${row.title}」？`, '提示', { type: 'warning' })
  await deleteReportLedger(row.id)
  ElMessage.success('已删除')
  load()
}
async function openPreview(row: any) {
  previewData.value = (await previewReport(row.id)).data
  previewDlg.value = true
}
async function onDownload(row: any) {
  const blob = await downloadReport(row.id)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = row.original_filename || `${row.title}`
  a.click()
  URL.revokeObjectURL(url)
}
async function onDownloadGenerated(row: any, kind: 'html' | 'docx') {
  const blob = await downloadGeneratedReport(row.id, kind)
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = kind === 'html' ? `${row.title}.html` : `${row.title}.docx`
  a.click()
  URL.revokeObjectURL(url)
}
function onPage(p: number) {
  query.page = p
  load()
}
onMounted(() => {
  load()
  if (canWrite.value) loadRefs()
})
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
.pager { margin-top: 14px; justify-content: flex-end; }
.preview-text { white-space: pre-wrap; word-break: break-all; max-height: 60vh; overflow: auto; background: var(--app-panel); padding: 12px; border-radius: 4px; }
</style>
