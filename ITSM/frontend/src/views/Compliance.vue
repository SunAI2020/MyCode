<template>
  <div>
    <el-tabs v-model="tab" @tab-change="onTabChange">
      <el-tab-pane label="合规要求" name="requirement">
        <el-card>
          <div class="toolbar">
            <el-select v-model="filterCustomer" placeholder="全部客户" clearable style="width: 180px" @change="loadRequirements">
              <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
            <el-select v-model="filterCategory" placeholder="全部维度" clearable style="width: 140px" @change="loadRequirements">
              <el-option v-for="v in CATEGORIES" :key="v" :label="v" :value="v" />
            </el-select>
            <el-select v-model="filterSourceType" placeholder="全部来源" clearable style="width: 140px" @change="loadRequirements">
              <el-option v-for="v in SOURCE_TYPES" :key="v" :label="v" :value="v" />
            </el-select>
            <el-button v-if="canWrite" type="primary" @click="openRequirement()">新增要求</el-button>
          </div>
          <el-table :data="requirements" v-loading="loading">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column label="客户" width="120">
              <template #default="{ row }">{{ customerName(row.customer_id) }}</template>
            </el-table-column>
            <el-table-column prop="clause" label="条款 / 要求" show-overflow-tooltip />
            <el-table-column prop="category" label="维度" width="80" />
            <el-table-column prop="source_type" label="来源" width="100" />
            <el-table-column prop="reg_source" label="出处" width="130" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="70" />
            <el-table-column label="操作" width="240">
              <template #default="{ row }">
                <el-button link type="primary" @click="openEvidence(row)">证据</el-button>
                <el-button v-if="canWrite" link type="success" @click="openCheck(row)">核验</el-button>
                <el-button v-if="canWrite" link type="primary" @click="openRequirement(row)">编辑</el-button>
                <el-button v-if="canDelete" link type="danger" @click="onDeleteRequirement(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-pagination
            class="pager"
            layout="total, prev, pager, next"
            :total="total"
            :page-size="size"
            :current-page="page"
            @current-change="onPage"
          />
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="合规核验" name="check">
        <el-card>
          <el-table :data="checks" v-loading="loading">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="requirement_id" label="要求ID" width="80" />
            <el-table-column prop="check_type" label="核验方式" width="100" />
            <el-table-column prop="status" label="状态" width="90" />
            <el-table-column prop="result" label="结果" width="80" />
            <el-table-column prop="check_date" label="核验日期" width="120" />
            <el-table-column label="操作" width="120">
              <template #default="{ row }">
                <el-button v-if="canWrite" link type="primary" @click="openCheckUpdate(row)">提交结果</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="合规看板" name="overview">
        <el-card>
          <div class="toolbar">
            <el-select v-model="ovCustomer" placeholder="全部客户" clearable style="width: 180px" @change="loadOverview">
              <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
            <el-button type="primary" @click="loadOverview">刷新</el-button>
          </div>
          <el-row :gutter="16" class="metric-row">
            <el-col :span="4"><div class="metric"><div class="metric-num">{{ metrics.total }}</div><div class="metric-label">合规要求</div></div></el-col>
            <el-col :span="4"><div class="metric"><div class="metric-num">{{ pct(metrics.coverage_rate) }}</div><div class="metric-label">合规覆盖率</div></div></el-col>
            <el-col :span="4"><div class="metric"><div class="metric-num">{{ pct(metrics.closure_rate) }}</div><div class="metric-label">闭环率</div></div></el-col>
            <el-col :span="4"><div class="metric"><div class="metric-num">{{ pct(metrics.traceability_rate) }}</div><div class="metric-label">留痕完整率</div></div></el-col>
            <el-col :span="4"><div class="metric"><div class="metric-num">{{ metrics.at_risk }}</div><div class="metric-label">风险敞口</div></div></el-col>
          </el-row>
          <div ref="chartRef" class="chart"></div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="履职报告" name="report">
        <el-card>
          <div class="toolbar">
            <el-select v-model="repCustomer" placeholder="全部客户" clearable style="width: 180px" @change="loadReports">
              <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
            <el-button v-if="canWrite" type="primary" @click="openReportCreate">生成报告</el-button>
          </div>
          <el-table :data="reports" v-loading="loading">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column label="客户" width="140">
              <template #default="{ row }">{{ customerName(row.customer_id) }}</template>
            </el-table-column>
            <el-table-column label="工期" width="220">
              <template #default="{ row }">{{ row.period_start || '—' }} ~ {{ row.period_end || '—' }}</template>
            </el-table-column>
            <el-table-column prop="status" label="状态" width="90" />
            <el-table-column prop="sign" label="签署" width="90" />
            <el-table-column prop="created_at" label="生成时间" width="170" />
            <el-table-column label="操作" width="140">
              <template #default="{ row }">
                <el-button link type="primary" @click="openReport(row)">查看</el-button>
                <el-button link type="success" v-if="canWrite && row.sign !== '已签署'" @click="onSignReport(row)">签署</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="监管模板库" name="template">
        <el-card>
          <div class="toolbar">
            <el-select v-model="tplSource" placeholder="全部标准" clearable style="width: 180px" @change="loadTemplates">
              <el-option v-for="v in TPL_SOURCES" :key="v" :label="v" :value="v" />
            </el-select>
            <el-button type="primary" @click="loadTemplates">刷新</el-button>
          </div>
          <el-table :data="templates" v-loading="loading">
            <el-table-column prop="reg_source" label="标准" width="130" />
            <el-table-column prop="domain" label="领域" width="140" show-overflow-tooltip />
            <el-table-column prop="title" label="条款标题" width="170" show-overflow-tooltip />
            <el-table-column prop="clause" label="要求原文" show-overflow-tooltip />
            <el-table-column prop="category" label="维度" width="70" />
            <el-table-column label="操作" width="90">
              <template #default="{ row }">
                <el-button v-if="canWrite" link type="primary" @click="openApplyTemplate(row)">应用</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 新增/编辑要求 -->
    <el-dialog v-model="reqDlg" :title="reqEditId ? '编辑要求' : '新增要求'" width="560px">
      <el-form :model="reqForm" label-width="90px">
        <el-form-item label="客户" required>
          <el-select v-model="reqForm.customer_id" style="width: 100%" placeholder="选择客户">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源类型">
          <el-select v-model="reqForm.source_type" style="width: 100%">
            <el-option v-for="v in SOURCE_TYPES" :key="v" :label="v" :value="v" />
          </el-select>
        </el-form-item>
        <el-form-item label="归属ID">
          <el-input-number v-model="reqForm.source_id" :min="0" style="width: 100%" placeholder="服务类别/合同 ID（可选）" />
        </el-form-item>
        <el-form-item label="条款/要求" required>
          <el-input v-model="reqForm.clause" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="维度">
          <el-select v-model="reqForm.category" style="width: 100%">
            <el-option v-for="v in CATEGORIES" :key="v" :label="v" :value="v" />
          </el-select>
        </el-form-item>
        <el-form-item label="出处">
          <el-input v-model="reqForm.reg_source" placeholder="如 公安部176号令 / 等保2.0 / 合同条款" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="reqForm.status" style="width: 100%">
            <el-option v-for="v in ['启用', '停用']" :key="v" :label="v" :value="v" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="reqDlg = false">取消</el-button><el-button type="primary" @click="saveRequirement">保存</el-button></template>
    </el-dialog>

    <!-- 证据链抽屉 -->
    <el-drawer v-model="evidenceDlg" :title="`证据链 · 要求 #${evidenceReqId}`" size="480px">
      <el-form :inline="true" class="ev-form">
        <el-form-item label="说明">
          <el-input v-model="evForm.note" placeholder="证据说明" style="width: 220px" />
        </el-form-item>
        <el-button v-if="canWrite" type="primary" @click="saveEvidence">上传证据</el-button>
        <el-button type="warning" plain @click="verifyChain">验证链</el-button>
      </el-form>
      <el-timeline>
        <el-timeline-item v-for="e in evidence" :key="e.id" :timestamp="e.occurred_at" placement="top">
          <div><el-tag size="small" :type="e.evidence_type === '自动' ? 'info' : 'success'">{{ e.evidence_type }}</el-tag>
            <el-tag size="small" type="warning" style="margin-left:6px">{{ e.source_type }}</el-tag>
          </div>
          <div class="ev-note">{{ e.note || `来源实体 #${e.source_id ?? '—'}` }}</div>
        </el-timeline-item>
      </el-timeline>
    </el-drawer>

    <!-- 发起核验 -->
    <el-dialog v-model="checkDlg" :title="`发起核验 · 要求 #${checkReqId}`" width="480px">
      <el-form :model="checkForm" label-width="90px">
        <el-form-item label="核验方式">
          <el-select v-model="checkForm.check_type" style="width: 100%">
            <el-option v-for="v in CHECK_TYPES" :key="v" :label="v" :value="v" />
          </el-select>
        </el-form-item>
        <el-form-item label="核验日期">
          <el-date-picker v-model="checkForm.check_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="checkForm.note" type="textarea" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="checkDlg = false">取消</el-button><el-button type="primary" @click="saveCheck">发起</el-button></template>
    </el-dialog>

    <!-- 提交核验结果 -->
    <el-dialog v-model="checkUpdateDlg" :title="`提交核验结果 · #${checkUpdateId}`" width="480px">
      <el-form :model="checkUpdateForm" label-width="90px">
        <el-form-item label="结果">
          <el-select v-model="checkUpdateForm.result" style="width: 100%" clearable placeholder="通过/不通过/部分">
            <el-option v-for="v in ['通过', '不通过', '部分']" :key="v" :label="v" :value="v" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="checkUpdateForm.note" type="textarea" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="checkUpdateDlg = false">取消</el-button><el-button type="primary" @click="saveCheckUpdate">提交</el-button></template>
    </el-dialog>

    <!-- 生成履职报告 -->
    <el-dialog v-model="reportDlg" title="生成履职报告" width="480px">
      <el-form :model="reportForm" label-width="90px">
        <el-form-item label="客户" required>
          <el-select v-model="reportForm.customer_id" style="width: 100%" placeholder="选择客户">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="工期起">
          <el-date-picker v-model="reportForm.period_start" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="工期止">
          <el-date-picker v-model="reportForm.period_end" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="reportDlg = false">取消</el-button><el-button type="primary" @click="saveReport">生成</el-button></template>
    </el-dialog>

    <!-- 履职报告详情 -->
    <el-drawer v-model="reportViewDlg" :title="`履职报告 · #${reportDetail.id}`" size="680px">
      <template v-if="reportDetail.content">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="合规覆盖率">{{ pct(reportDetail.content.metrics.coverage_rate) }}</el-descriptions-item>
          <el-descriptions-item label="闭环率">{{ pct(reportDetail.content.metrics.closure_rate) }}</el-descriptions-item>
          <el-descriptions-item label="留痕完整率">{{ pct(reportDetail.content.metrics.traceability_rate) }}</el-descriptions-item>
          <el-descriptions-item label="风险敞口">{{ reportDetail.content.metrics.at_risk }}</el-descriptions-item>
        </el-descriptions>
        <h4 class="sec-title">覆盖矩阵（{{ reportDetail.content.requirements.length }} 项）</h4>
        <el-table :data="reportDetail.content.requirements" size="small" max-height="300">
          <el-table-column prop="category" label="维度" width="70" />
          <el-table-column prop="clause" label="条款 / 要求" show-overflow-tooltip />
          <el-table-column prop="evidence_count" label="证据" width="60" />
          <el-table-column prop="check_status" label="核验" width="80" />
        </el-table>
        <h4 class="sec-title">证据清单（{{ reportDetail.content.evidence.length }} 条）</h4>
        <el-table :data="reportDetail.content.evidence" size="small" max-height="260">
          <el-table-column prop="source_type" label="来源" width="80" />
          <el-table-column prop="source_id" label="实体ID" width="80" />
          <el-table-column prop="occurred_at" label="时间" width="180" />
        </el-table>
      </template>
    </el-drawer>

    <!-- 应用模板 -->
    <el-dialog v-model="applyTplDlg" :title="`应用模板 · ${applyTpl?.title || ''}`" width="480px">
      <el-form :model="applyTplForm" label-width="90px">
        <el-form-item label="客户" required>
          <el-select v-model="applyTplForm.customer_id" style="width: 100%" placeholder="选择客户">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="applyTplDlg = false">取消</el-button><el-button type="primary" :loading="applyTplLoading" @click="saveApplyTemplate">应用</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as echarts from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import {
  listRequirements, createRequirement, updateRequirement, deleteRequirement,
  listEvidence, addEvidence, verifyEvidenceChain, createCheck, listChecks, updateCheck,
  listCustomers, complianceOverview, createReport, listReports, getReport, signReport,
  listTemplates, applyTemplate,
} from '@/api'
import { useAuthStore } from '@/stores/auth'

echarts.use([BarChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer])

const auth = useAuthStore()
const canWrite = computed(() => auth.hasPermission('compliance:write'))
const canDelete = computed(() => auth.hasPermission('compliance:delete'))

const CATEGORIES = ['技术', '组织', '制度', '台账', '流程']
const SOURCE_TYPES = ['监管', '合同义务', '服务类别']
const CHECK_TYPES = ['巡查', '自查', '攻防校验', '复测']
const TPL_SOURCES = ['等保2.0', '密码测评', '数据安全', '公安部176号令', '关基保护']

const tab = ref('requirement')
const loading = ref(false)
const customers = ref<any[]>([])
const requirements = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const size = ref(20)
const filterCustomer = ref<number | null>(null)
const filterCategory = ref('')
const filterSourceType = ref('')

const reqDlg = ref(false)
const reqEditId = ref<number | null>(null)
const reqForm = reactive<any>({ customer_id: null, source_type: '监管', source_id: null, clause: '', category: '技术', reg_source: '', status: '启用' })

const evidenceDlg = ref(false)
const evidenceReqId = ref<number | null>(null)
const evidence = ref<any[]>([])
const evForm = reactive({ note: '' })

const checkDlg = ref(false)
const checkReqId = ref<number | null>(null)
const checkForm = reactive<any>({ check_type: '巡查', check_date: null, note: '' })

const checks = ref<any[]>([])
const checkUpdateDlg = ref(false)
const checkUpdateId = ref<number | null>(null)
const checkUpdateForm = reactive<any>({ result: null, note: '' })

const ovCustomer = ref<number | null>(null)
const metrics = ref<any>({ total: 0, covered: 0, verified: 0, at_risk: 0, coverage_rate: 0, closure_rate: 0, traceability_rate: 0, by_category: [] })
const chartRef = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

const repCustomer = ref<number | null>(null)
const reports = ref<any[]>([])
const reportDlg = ref(false)
const reportForm = reactive<any>({ customer_id: null, period_start: null, period_end: null })
const reportViewDlg = ref(false)
const reportDetail = ref<any>({ id: 0, content: null })

const tplSource = ref('')
const templates = ref<any[]>([])
const applyTplDlg = ref(false)
const applyTpl = ref<any>(null)
const applyTplForm = reactive<any>({ customer_id: null })
const applyTplLoading = ref(false)

function customerName(id: number) {
  return customers.value.find((c) => c.id === id)?.name || `#${id}`
}

async function loadCustomers() {
  customers.value = (await listCustomers({ page: 1, size: 100 })).data.items
}
async function loadRequirements() {
  loading.value = true
  try {
    const params: any = { page: page.value, size: size.value }
    if (filterCustomer.value) params.customer_id = filterCustomer.value
    if (filterCategory.value) params.category = filterCategory.value
    if (filterSourceType.value) params.source_type = filterSourceType.value
    const r = (await listRequirements(params)).data
    requirements.value = r.items
    total.value = r.total
  } finally {
    loading.value = false
  }
}
async function loadChecks() {
  checks.value = (await listChecks({ page: 1, size: 100 })).data.items
}
function onPage(p: number) { page.value = p; loadRequirements() }

function openRequirement(row?: any) {
  if (row) {
    reqEditId.value = row.id
    Object.assign(reqForm, { customer_id: row.customer_id, source_type: row.source_type, source_id: row.source_id, clause: row.clause, category: row.category, reg_source: row.reg_source, status: row.status })
  } else {
    reqEditId.value = null
    Object.assign(reqForm, { customer_id: null, source_type: '监管', source_id: null, clause: '', category: '技术', reg_source: '', status: '启用' })
  }
  reqDlg.value = true
}
async function saveRequirement() {
  if (!reqForm.customer_id) return ElMessage.warning('请选择客户')
  if (!reqForm.clause) return ElMessage.warning('请填写条款/要求')
  const data = { ...reqForm }
  if (reqEditId.value) await updateRequirement(reqEditId.value, data)
  else await createRequirement(data)
  ElMessage.success('已保存')
  reqDlg.value = false
  loadRequirements()
}
async function onDeleteRequirement(row: any) {
  await ElMessageBox.confirm(`确认删除该合规要求？`, '提示', { type: 'warning' })
  await deleteRequirement(row.id)
  ElMessage.success('已删除')
  loadRequirements()
}

async function openEvidence(row: any) {
  evidenceReqId.value = row.id
  evidenceDlg.value = true
  await loadEvidence()
}
async function loadEvidence() {
  evidence.value = (await listEvidence(evidenceReqId.value!)).data
}
async function saveEvidence() {
  if (!evForm.note) return ElMessage.warning('请填写证据说明')
  await addEvidence(evidenceReqId.value!, { requirement_id: evidenceReqId.value, note: evForm.note, source_type: '人工', evidence_type: '人工' })
  ElMessage.success('已上传')
  evForm.note = ''
  loadEvidence()
}

async function verifyChain() {
  const r = (await verifyEvidenceChain(evidenceReqId.value!)).data
  if (r.intact) ElMessage.success(`哈希链完整（${r.total} 条证据）`)
  else ElMessage.error(`哈希链被篡改：记录 ${r.broken_ids.join(', ')}`)
}

function openCheck(row: any) {
  checkReqId.value = row.id
  Object.assign(checkForm, { check_type: '巡查', check_date: null, note: '' })
  checkDlg.value = true
}
async function saveCheck() {
  await createCheck(checkReqId.value!, { requirement_id: checkReqId.value, ...checkForm })
  ElMessage.success('已发起核验')
  checkDlg.value = false
  loadChecks()
}

function openCheckUpdate(row: any) {
  checkUpdateId.value = row.id
  Object.assign(checkUpdateForm, { result: row.result, note: row.note || '' })
  checkUpdateDlg.value = true
}
async function saveCheckUpdate() {
  await updateCheck(checkUpdateId.value!, { ...checkUpdateForm })
  ElMessage.success('已提交')
  checkUpdateDlg.value = false
  loadChecks()
}

function pct(v: number) {
  return `${((v ?? 0) * 100).toFixed(1)}%`
}

async function loadOverview() {
  const params: any = {}
  if (ovCustomer.value) params.customer_id = ovCustomer.value
  metrics.value = (await complianceOverview(params)).data
  await nextTick()
  renderChart()
}

function renderChart() {
  if (!chartRef.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const cats = metrics.value.by_category || []
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['总数', '已覆盖', '已核验'] },
    grid: { left: 40, right: 20, top: 40, bottom: 30 },
    xAxis: { type: 'category', data: cats.map((c: any) => c.category) },
    yAxis: { type: 'value', minInterval: 1 },
    series: [
      { name: '总数', type: 'bar', data: cats.map((c: any) => c.total) },
      { name: '已覆盖', type: 'bar', data: cats.map((c: any) => c.covered) },
      { name: '已核验', type: 'bar', data: cats.map((c: any) => c.verified) },
    ],
  })
}

function onTabChange(name: string | number) {
  if (name === 'requirement') loadRequirements()
  else if (name === 'overview') loadOverview()
  else if (name === 'report') loadReports()
  else if (name === 'template') loadTemplates()
}

async function loadTemplates() {
  loading.value = true
  try {
    const params: any = {}
    if (tplSource.value) params.reg_source = tplSource.value
    templates.value = (await listTemplates(params)).data
  } finally {
    loading.value = false
  }
}

function openApplyTemplate(row: any) {
  applyTpl.value = row
  applyTplForm.customer_id = null
  applyTplDlg.value = true
}

async function saveApplyTemplate() {
  if (!applyTplForm.customer_id) return ElMessage.warning('请选择客户')
  if (applyTplLoading.value) return
  applyTplLoading.value = true
  try {
    await applyTemplate(applyTpl.value!.id, { customer_id: applyTplForm.customer_id })
    ElMessage.success('已应用模板为合规要求')
    applyTplDlg.value = false
    loadRequirements()
  } catch {
    ElMessage.error('应用模板失败')
  } finally {
    applyTplLoading.value = false
  }
}

async function loadReports() {
  loading.value = true
  try {
    const params: any = { page: 1, size: 100 }
    if (repCustomer.value) params.customer_id = repCustomer.value
    reports.value = (await listReports(params)).data.items
  } finally {
    loading.value = false
  }
}

function openReportCreate() {
  Object.assign(reportForm, { customer_id: null, period_start: null, period_end: null })
  reportDlg.value = true
}

async function saveReport() {
  if (!reportForm.customer_id) return ElMessage.warning('请选择客户')
  await createReport({ ...reportForm })
  ElMessage.success('已生成')
  reportDlg.value = false
  loadReports()
}

async function openReport(row: any) {
  const r = (await getReport(row.id)).data
  reportDetail.value = r
  reportViewDlg.value = true
}

async function onSignReport(row: any) {
  await ElMessageBox.confirm(`确认签署履职报告 #${row.id}？`, '提示', { type: 'warning' })
  await signReport(row.id)
  ElMessage.success('已签署')
  loadReports()
}

onMounted(() => {
  loadCustomers()
  loadRequirements()
  loadChecks()
})
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; align-items: center; }
.pager { margin-top: 14px; display: flex; justify-content: flex-end; }
.ev-form { margin-bottom: 8px; }
.ev-note { color: #555; font-size: 13px; }
.metric-row { margin-bottom: 16px; }
.metric { text-align: center; padding: 16px 0; background: #f7f8fa; border-radius: 6px; }
.metric-num { font-size: 24px; font-weight: 600; color: #303133; }
.metric-label { margin-top: 6px; font-size: 13px; color: #909399; }
.chart { height: 320px; margin-top: 8px; }
.sec-title { margin: 16px 0 8px; font-size: 14px; color: #303133; }
</style>
