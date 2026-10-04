<template>
  <div>
    <el-card v-loading="loading">
      <div class="toolbar">
        <el-button v-if="canDispatch" type="primary" @click="openAggregate">新增聚合工单</el-button>
      </div>
      <div v-for="sec in workOrderSections" :key="sec.title" class="wo-section">
        <div class="wo-section-head">
          <span class="wo-section-title">{{ sec.title }}</span>
          <span class="wo-section-count">{{ sec.rows.length }}</span>
        </div>
        <el-table v-if="sec.rows.length" :data="sec.rows" size="small" border>
          <el-table-column label="客户" width="190">
            <template #default="{ row }">{{ customerMap.get(row.customer_id)?.name || '' }}</template>
          </el-table-column>
          <el-table-column prop="project" label="服务类别" width="130" />
          <el-table-column prop="type" label="类型" width="100" />
          <el-table-column prop="priority" label="优先级" width="80" />
          <el-table-column label="期次" width="90">
            <template #default="{ row }">{{ row.current_cycle_no != null ? `第${row.current_cycle_no}期` : '—' }}</template>
          </el-table-column>
          <el-table-column label="执行人" width="130">
            <template #default="{ row }">{{ (row.assignee_names || []).join('、') || '—' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="300" fixed="right">
            <template #default="{ row }">
              <el-button link type="success" @click="openEdit(row)">编辑</el-button>
              <el-button link type="primary" :disabled="!canDispatch || !nextAction(row)" @click="onNextAction(row)">{{ nextAction(row) || '—' }}</el-button>
              <el-button link type="warning" :disabled="!canDispatch || !targetList(row).length" @click="openTransition(row)">流转</el-button>
              <el-button link type="danger" :disabled="!canDispatch" @click="onDeleteWorkOrder(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-else class="wo-section-empty">暂无</div>
      </div>
    </el-card>

    <el-dialog v-model="createDlg" title="新增工单" width="560px">
      <el-form :model="createForm" label-width="100px">
        <el-form-item label="客户" required>
          <el-select v-model="createForm.customer_id" style="width: 100%" placeholder="选择客户" @change="onCreateCustomerChange">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目" required>
          <el-select v-model="createForm.contract_id" style="width: 100%" placeholder="选择项目" :disabled="!createForm.customer_id" @change="onCreateContractChange">
            <el-option v-for="c in createContracts" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务类别" required>
          <el-select v-model="createForm.contract_item_id" style="width: 100%" placeholder="选择服务类别" :disabled="!createForm.contract_id" @change="onCreateItemChange">
            <el-option v-for="it in createItems" :key="it.id" :label="it.ci_id ? `${it.project}（${createCiName.get(it.ci_id) || '//'}）` : `${it.project}（//）`" :value="it.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="createForm.type" style="width: 100%">
            <el-option v-for="t in ['客户工单', '驻场工单', '内部任务', '外包工单']" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="createForm.priority" style="width: 100%">
            <el-option v-for="p in ['高', '中', '低']" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务开始时间"><el-date-picker v-model="createForm.service_start" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="服务结束时间"><el-date-picker v-model="createForm.service_end" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="同时生成工期"><el-checkbox v-model="createForm.generate_cycle" /></el-form-item>
        <el-form-item label="派单类型">
          <el-select v-model="createForm.dispatch_type" style="width: 100%">
            <el-option label="内部" value="内部" />
            <el-option label="外包" value="外包" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行人">
          <el-select v-model="createForm.assignee_id" filterable placeholder="选择执行人" style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="同时派单"><el-checkbox v-model="createForm.dispatch" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="createDlg = false">取消</el-button><el-button type="primary" @click="onCreate">创建</el-button></template>
    </el-dialog>

    <el-dialog v-model="aggDlg" title="新增聚合工单" width="640px">
      <el-form label-width="90px">
        <el-form-item label="客户">
          <el-select v-model="aggCustomerId" style="width: 100%" @change="onAggCustomerChange">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="业务系统">
          <div v-if="!aggCustomerId" class="agg-empty">请先选择客户</div>
          <div v-else class="agg-box">
            <el-checkbox :model-value="aggCiAll" :indeterminate="aggCiIndeterminate" @change="toggleAllCi">全选</el-checkbox>
            <el-checkbox-group v-model="aggCiIds">
              <el-checkbox v-for="ci in filteredCis" :key="ci.id" :value="ci.id">{{ ci.name }}</el-checkbox>
            </el-checkbox-group>
          </div>
        </el-form-item>
        <el-form-item label="服务类别">
          <div v-if="!aggCustomerId" class="agg-empty">请先选择客户</div>
          <div v-else-if="!aggGroups.length" class="agg-empty">该客户暂无服务类别</div>
          <div v-else class="agg-box">
            <el-checkbox :model-value="aggAll" :indeterminate="aggIndeterminate" @change="toggleAll">全选</el-checkbox>
            <el-checkbox-group v-model="aggGroupIds">
              <el-checkbox v-for="g in aggGroups" :key="g.key" :value="g.key">
                {{ g.project }}（{{ ciCountOf(g) }} · 每{{ g.frequency }}{{ g.unit }}）
              </el-checkbox>
            </el-checkbox-group>
          </div>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="aggPriority" style="width: 100%">
            <el-option v-for="p in ['高', '中', '低']" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始时间"><el-date-picker v-model="aggServiceStart" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="结束时间"><el-date-picker v-model="aggServiceEnd" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="生成工期"><el-checkbox v-model="aggGenerateCycle" /></el-form-item>
        <el-form-item label="派单类型">
          <el-select v-model="aggDispatchType" style="width: 100%">
            <el-option label="内部" value="内部" />
            <el-option label="外包" value="外包" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行人">
          <el-select v-model="aggAssigneeId" filterable placeholder="选择执行人" style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="立即派单"><el-checkbox v-model="aggDispatch" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="aggDlg = false">取消</el-button>
        <el-button type="primary" :disabled="!aggGroupIds.length" @click="saveAggregate">创建（每个服务类别一个工单）</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="scopeDlg" title="聚合工单明细" width="720px">
      <template v-if="scopeData.work_order">
        <p>工单号：{{ scopeData.work_order.no }}　类型：{{ scopeData.work_order.type }}　状态：{{ scopeData.work_order.status }}</p>
        <el-divider content-position="left">业务系统（{{ scopeData.cis.length }}）</el-divider>
        <el-tag v-for="c in scopeData.cis" :key="c.ci_id" class="scope-tag">{{ c.name }}</el-tag>
        <el-divider content-position="left">服务类别（{{ scopeData.items.length }}）</el-divider>
        <el-tag v-for="i in scopeData.items" :key="i.contract_item_id" class="scope-tag">{{ i.project }}（每 {{ i.frequency }}{{ i.unit }}）</el-tag>
        <el-divider content-position="left">频次（{{ scopeData.cycles.length }}）</el-divider>
        <el-table :data="scopeData.cycles" size="small" border>
          <el-table-column prop="cycle_no" label="序号" width="60" />
          <el-table-column prop="ci_name" label="业务系统" />
          <el-table-column prop="project" label="服务类别" />
          <el-table-column label="开始时间 ~ 结束时间">
            <template #default="{ row }">{{ row.service_start }} ~ {{ row.service_end }}</template>
          </el-table-column>
        </el-table>
      </template>
      <template #footer><el-button @click="scopeDlg = false">关闭</el-button></template>
    </el-dialog>

    <el-dialog v-model="dispatchDlg" title="派单" width="560px">
      <el-form label-width="90px">
        <el-form-item label="派单类型">
          <el-select v-model="dispatchForm.dispatch_type" style="width: 100%">
            <el-option label="内部" value="内部" />
            <el-option label="外包" value="外包" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行人">
          <div class="assignee-list">
            <div v-for="(a, i) in dispatchForm.assignees" :key="i" class="assignee-row">
              <el-select v-model="a.user_id" placeholder="选择执行人" filterable style="width: 180px">
                <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
              </el-select>
              <el-input v-model.number="a.workload_ratio" placeholder="比例%" style="width: 110px" />
              <el-button link type="danger" @click="dispatchForm.assignees.splice(i, 1)">删除</el-button>
            </div>
            <el-button link type="primary" @click="dispatchForm.assignees.push({ user_id: null, workload_ratio: 100 })">+ 添加执行人</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="dispatchDlg = false">取消</el-button><el-button type="primary" @click="onDispatch">派单</el-button></template>
    </el-dialog>

    <el-dialog v-model="detailDlg" title="工单详情" width="520px">
      <template v-if="detailData">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="工单号">{{ detailData.no }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ detailData.type }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detailData.status }}</el-descriptions-item>
          <el-descriptions-item label="优先级">{{ detailData.priority }}</el-descriptions-item>
          <el-descriptions-item label="服务类别">{{ detailData.project || '—' }}</el-descriptions-item>
          <el-descriptions-item label="进度">{{ detailData.progress }}%</el-descriptions-item>
          <el-descriptions-item label="执行人">{{ (detailData.assignee_names || []).join('、') || '—' }}</el-descriptions-item>
          <el-descriptions-item label="描述">{{ detailData.description || '—' }}</el-descriptions-item>
        </el-descriptions>
      </template>
      <template #footer><el-button @click="detailDlg = false">关闭</el-button></template>
    </el-dialog>

    <el-dialog v-model="editAggDlg" title="编辑聚合工单" width="640px">
      <el-form label-width="90px">
        <el-form-item label="客户">
          <el-input :model-value="customerMap.get(editAggCustomerId)?.name || ''" disabled />
        </el-form-item>
        <el-form-item label="业务系统">
          <el-checkbox-group v-model="editAggCiIds">
            <el-checkbox v-for="ci in editAggCis" :key="ci.id" :value="ci.id">{{ ci.name }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="服务类别">
          <el-input :model-value="editAggProject" disabled />
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="editAggPriority" style="width: 100%">
            <el-option v-for="p in ['高', '中', '低']" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始时间"><el-date-picker v-model="editAggServiceStart" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="结束时间"><el-date-picker v-model="editAggServiceEnd" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="重新生成工期"><el-checkbox v-model="editAggRegenerateCycle" /></el-form-item>
        <el-form-item label="派单类型">
          <el-select v-model="editAggDispatchType" style="width: 100%">
            <el-option label="内部" value="内部" />
            <el-option label="外包" value="外包" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行人">
          <el-select v-model="editAggAssigneeId" filterable placeholder="选择执行人" style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="重新派单"><el-checkbox v-model="editAggDispatch" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editAggDlg = false">取消</el-button>
        <el-button type="primary" @click="saveEditAggregate">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="transitionDlg" title="状态流转" width="440px">
      <template v-if="transitionRow">
        <p>工单号：{{ transitionRow.no }}　当前状态：<el-tag>{{ transitionRow.status }}</el-tag></p>
        <el-form label-width="90px" style="margin-top: 12px">
          <el-form-item label="目标状态">
            <el-select v-model="transitionTarget" placeholder="选择流转目标状态" style="width: 100%">
              <el-option v-for="t in transitionTargets" :key="t" :label="t" :value="t" />
            </el-select>
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="transitionDlg = false">取消</el-button>
        <el-button type="primary" @click="onTransition">流转</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="reportUploadDlg" title="上传报告" width="480px">
      <template v-if="reportUploadRow">
        <p>工单号：{{ reportUploadRow.no }}　服务类别：{{ reportUploadRow.project || '—' }}</p>
        <el-form label-width="90px" style="margin-top: 12px">
          <el-form-item label="报告文件">
            <el-upload
              :auto-upload="false"
              :limit="1"
              :on-change="onReportFileChange"
              :on-remove="() => (reportUploadFile = null)"
              accept=".pdf,.docx,.md,.html,.htm,.jpg,.jpeg,.png"
              style="width: 100%"
            >
              <el-button type="primary">选择报告文件</el-button>
              <template #tip>
                <div class="el-upload__tip">支持 PDF / Word / Markdown / HTML / 图片，上传后自动脱敏并加密存储</div>
              </template>
            </el-upload>
          </el-form-item>
        </el-form>
      </template>
      <template #footer>
        <el-button @click="reportUploadDlg = false">取消</el-button>
        <el-button type="primary" :loading="reportUploading" @click="onSubmitReport">上传并提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listWorkOrders, createWorkOrder, updateStatus, dispatch, deleteWorkOrder,
  listCustomers, listCis, listItems, listContracts,
  previewAggregateCycles, createAggregateWorkOrder, editAggregateWorkOrder, getWorkOrderScope,
  listUsers, workflowTransitions, uploadReport,
} from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const rows = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, size: 100 })

// 工单竖向分栏：按状态归入固定 7 栏（已验收→待结单；已取消→已关闭）
const WO_SECTION_OF: Record<string, string> = {
  '待派单': '待派单',
  '待执行': '待执行',
  '执行中': '执行中',
  '待验收': '待验收',
  '已验收': '待结单',
  '已结单': '已结单',
  '已取消': '已关闭',
  '已关闭': '已关闭',
}
const WO_SECTION_ORDER = ['待派单', '待执行', '执行中', '待验收', '待结单', '已结单', '已关闭']
const workOrderSections = computed(() => {
  const buckets: Record<string, any[]> = {}
  for (const t of WO_SECTION_ORDER) buckets[t] = []
  for (const r of rows.value) {
    const t = WO_SECTION_OF[r.status]
    if (t) buckets[t].push(r)
  }
  return WO_SECTION_ORDER.map((t) => ({ title: t, rows: buckets[t] }))
})

const customers = ref<any[]>([])
const cis = ref<any[]>([])
const items = ref<any[]>([])
const users = ref<any[]>([])
// 写权限点（工单创建/派单/转派，与后端 work_order:write 对齐）
const canDispatch = computed(() => auth.hasPermission('work_order:write'))
const customerMap = computed(() => new Map(customers.value.map((c) => [c.id, c])))
const createDlg = ref(false)
const createForm = reactive({
  customer_id: null as number | null,
  contract_id: null as number | null,
  contract_item_id: null as number | null,
  type: '客户工单',
  priority: '中',
  service_start: '', service_end: '', cycle_no: null as number | null,
  generate_cycle: true, dispatch: true, dispatch_type: '内部', assignee_id: null as number | null,
})
const createContracts = ref<any[]>([])  // 所选客户的项目
const createItems = ref<any[]>([])      // 所选项目的服务类别
const createCiName = ref<Map<number, string>>(new Map())  // 业务系统 id → 名称

const dispatchDlg = ref(false)
const dispatchTarget = ref<number | null>(null)
const dispatchForm = reactive({ dispatch_type: '内部', assignees: [{ user_id: null, workload_ratio: 100 }] as any[] })

// 聚合工单（按服务类别逐条打包：勾选几个服务类别就生成几个工单）
const aggDlg = ref(false)
const aggCustomerId = ref<number | null>(null)
const aggCiIds = ref<number[]>([])       // 勾选的业务系统
const aggGroupIds = ref<string[]>([])    // 选中的服务类别组 key
const aggPriority = ref('中')
const aggServiceStart = ref('')
const aggServiceEnd = ref('')
const aggGenerateCycle = ref(true)
const aggDispatch = ref(true)
const aggDispatchType = ref('内部')
const aggAssigneeId = ref<number | null>(null)

const filteredCis = computed(() => cis.value.filter((c) => c.customer_id === aggCustomerId.value))
const aggCiAll = computed(() => filteredCis.value.length > 0 && aggCiIds.value.length === filteredCis.value.length)
const aggCiIndeterminate = computed(() => aggCiIds.value.length > 0 && aggCiIds.value.length < filteredCis.value.length)

// 该客户的服务类别合并视图：同项目 + 同服务类别 + 同配置合并为一条（含其所有业务系统）
const aggGroups = computed(() => {
  const map = new Map<string, any>()
  for (const it of items.value) {
    const key = `${it.contract_id}|${it.project}|${it.frequency}|${it.unit}|${it.price ?? ''}`
    if (!map.has(key)) {
      map.set(key, { key, contract_id: it.contract_id, project: it.project, frequency: it.frequency, unit: it.unit, price: it.price, _members: [], _ciIds: [] })
    }
    const g = map.get(key)
    g._members.push(it)
    if (it.ci_id) g._ciIds.push(it.ci_id)
  }
  return [...map.values()].map((g) => {
    g._ciIds = [...new Set(g._ciIds)]
    g._ciCount = g._ciIds.length
    return g
  })
})
const aggAll = computed(() => aggGroups.value.length > 0 && aggGroupIds.value.length === aggGroups.value.length)
const aggIndeterminate = computed(() => aggGroupIds.value.length > 0 && aggGroupIds.value.length < aggGroups.value.length)

const scopeDlg = ref(false)
const scopeData = ref<any>({ work_order: null, cis: [], items: [], cycles: [] })

const detailDlg = ref(false)
const detailData = ref<any>(null)

// 编辑聚合工单（业务系统可重选、服务类别固定、重新生成工期/重新派单）
const editAggDlg = ref(false)
const editAggWoId = ref<number | null>(null)
const editAggCustomerId = ref<number | null>(null)
const editAggCis = ref<any[]>([])
const editAggCiIds = ref<number[]>([])
const editAggProject = ref('')
const editAggPriority = ref('中')
const editAggServiceStart = ref('')
const editAggServiceEnd = ref('')
const editAggRegenerateCycle = ref(false)
const editAggDispatch = ref(false)
const editAggDispatchType = ref('内部')
const editAggAssigneeId = ref<number | null>(null)

const transitionDlg = ref(false)
const transitionRow = ref<any>(null)
const transitionTarget = ref<string | null>(null)
const transitionTargets = ref<string[]>([])

// 工单状态流转表（默认 ∪ DB 规则；有权限时用接口覆盖）
const DEFAULT_WO_TRANSITIONS: Record<string, string[]> = {
  '待派单': ['待执行', '已取消'],
  '待执行': ['执行中', '已取消'],
  '执行中': ['待验收', '已取消'],
  '待验收': ['已验收', '已取消'],
  '已验收': ['已结单'],
  '已结单': ['已关闭'],
  '已取消': ['已关闭'],
  '已关闭': [],
}
const transitions = ref<Record<string, Record<string, string[]>>>({ work_order: DEFAULT_WO_TRANSITIONS })

const reportUploadDlg = ref(false)
const reportUploadRow = ref<any>(null)
const reportUploadFile = ref<File | null>(null)
const reportUploading = ref(false)

async function load() {
  loading.value = true
  try {
    const res = await listWorkOrders(query)
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
async function openCreate() {
  Object.assign(createForm, { customer_id: null, contract_id: null, contract_item_id: null, type: '客户工单', priority: '中', service_start: '', service_end: '', cycle_no: null, generate_cycle: true, dispatch: true, dispatch_type: '内部', assignee_id: null })
  createContracts.value = []
  createItems.value = []
  createCiName.value = new Map()
  createDlg.value = true
  if (!customers.value.length) customers.value = (await listCustomers({ page: 1, size: 100 })).data.items
}
async function onCreateCustomerChange() {
  createForm.contract_id = null
  createForm.contract_item_id = null
  createContracts.value = []
  createItems.value = []
  createCiName.value = new Map()
  if (!createForm.customer_id) return
  createContracts.value = (await listContracts({ page: 1, size: 100 })).data.items.filter((c: any) => c.customer_id === createForm.customer_id)
  const cs = (await listCis({ page: 1, size: 100, customer_id: createForm.customer_id })).data.items
  createCiName.value = new Map(cs.map((c: any) => [c.id, c.name]))
}
async function onCreateContractChange() {
  createForm.contract_item_id = null
  createItems.value = []
  createForm.service_start = ''
  createForm.service_end = ''
  if (!createForm.contract_id) return
  createItems.value = (await listItems({ page: 1, size: 100, contract_id: createForm.contract_id })).data.items
}
async function onCreateItemChange() {
  createForm.service_start = ''
  createForm.service_end = ''
  createForm.cycle_no = null
  if (!createForm.contract_item_id) return
  // 默认取项目的开始/结束日期
  const contract = createContracts.value.find((c: any) => c.id === createForm.contract_id)
  if (contract) {
    createForm.service_start = contract.start_date || ''
    createForm.service_end = contract.end_date || ''
  }
  // 若可算出下一期工期，用工期起止精化
  try {
    const res = await previewAggregateCycles({ contract_item_ids: [createForm.contract_item_id] })
    const cycles = res.data.cycles[createForm.contract_item_id] || []
    const next = cycles.find((c: any) => !c.has_work_order)
    if (next) {
      createForm.service_start = next.service_start
      createForm.service_end = next.service_end
      createForm.cycle_no = next.cycle_no
    }
  } catch { /* 自动填充失败可手动填写 */ }
}
async function onCreate() {
  if (!createForm.customer_id) return ElMessage.warning('请选择客户')
  if (!createForm.contract_id) return ElMessage.warning('请选择项目')
  if (!createForm.contract_item_id) return ElMessage.warning('请选择服务类别')
  if (!createForm.service_start || !createForm.service_end) return ElMessage.warning('请填写工单开始日期和结束日期！')
  if (createForm.dispatch && !createForm.assignee_id) {
    try {
      await ElMessageBox.confirm('未选择执行人！', '提示', { confirmButtonText: '确定', cancelButtonText: '重选', type: 'warning' })
    } catch {
      return
    }
    createForm.dispatch = false
  }
  const item = createItems.value.find((i: any) => i.id === createForm.contract_item_id)
  const res = await createWorkOrder({
    type: createForm.type,
    priority: createForm.priority,
    contract_id: createForm.contract_id,
    contract_item_id: createForm.contract_item_id,
    ci_id: item?.ci_id ?? null,
    project: item?.project ?? null,
    service_start: createForm.service_start || null,
    service_end: createForm.service_end || null,
    cycle_no: createForm.cycle_no,
    generate_cycle: createForm.generate_cycle,
    dispatch: createForm.dispatch,
    dispatch_type: createForm.dispatch_type,
    assignee_id: createForm.dispatch ? createForm.assignee_id : null,
  })
  if (res.data?.duplicate) {
    ElMessageBox.alert(res.data.message, '重复生成', { type: 'warning' })
    return
  }
  ElMessage.success('工单已创建')
  createDlg.value = false
  load()
}
function openDispatch(row: any) {
  dispatchTarget.value = row.id
  dispatchForm.dispatch_type = '内部'
  dispatchForm.assignees = [{ user_id: users.value[0]?.id ?? null, workload_ratio: 100 }]
  dispatchDlg.value = true
}
async function onDispatch() {
  const assignees = dispatchForm.assignees.filter((a: any) => a.user_id != null)
  if (!assignees.length) return ElMessage.warning('请至少选择一名执行人')
  await dispatch(dispatchTarget.value!, { dispatch_type: dispatchForm.dispatch_type, assignees })
  ElMessage.success('派单完成')
  dispatchDlg.value = false
  load()
}
function nextAction(row: any) {
  const map: Record<string, string> = { '待派单': '派单', '待执行': '执行', '执行中': '提交报告', '待验收': '验收', '已验收': '结单', '已结单': '关闭' }
  return map[row.status] || ''
}
function targetList(row: any) {
  return transitions.value['work_order']?.[row.status] || []
}
function openTransition(row: any) {
  transitionRow.value = row
  transitionTarget.value = null
  transitionTargets.value = targetList(row)
  transitionDlg.value = true
}
async function onTransition() {
  if (!transitionTarget.value) return ElMessage.warning('请选择目标状态')
  await updateStatus(transitionRow.value.id, { status: transitionTarget.value })
  ElMessage.success('已流转')
  transitionDlg.value = false
  load()
}
async function onNextAction(row: any) {
  if (row.status === '待派单') {
    openDispatch(row)
    return
  }
  if (row.status === '执行中') {
    openReportUpload(row)
    return
  }
  const next: Record<string, string> = { '待执行': '执行中', '待验收': '已验收', '已验收': '已结单', '已结单': '已关闭' }
  await updateStatus(row.id, { status: next[row.status] })
  ElMessage.success('状态已更新')
  load()
}
function openReportUpload(row: any) {
  reportUploadRow.value = row
  reportUploadFile.value = null
  reportUploadDlg.value = true
}
function onReportFileChange(file: any) {
  reportUploadFile.value = file.raw || file
}
async function onSubmitReport() {
  if (!reportUploadFile.value) return ElMessage.warning('请选择报告文件')
  const fd = new FormData()
  fd.append('file', reportUploadFile.value)
  fd.append('work_order_id', String(reportUploadRow.value.id))
  fd.append('report_type', '运维报告')
  reportUploading.value = true
  try {
    await uploadReport(fd)
    await updateStatus(reportUploadRow.value.id, { status: '待验收' })
    ElMessage.success('报告已上传并提交')
    reportUploadDlg.value = false
    load()
  } finally {
    reportUploading.value = false
  }
}
async function onDeleteWorkOrder(row: any) {
  let deleteCycles = true
  try {
    await ElMessageBox.confirm(
      `删除工单「${row.no}」后，与该工单关联的服务工期将同步删除。确认？保留工期？`,
      '删除工单',
      { confirmButtonText: '确认', cancelButtonText: '保留工期', distinguishCancelAndClose: true, type: 'warning' },
    )
  } catch (e: any) {
    if (e === 'cancel') {
      deleteCycles = false
    } else {
      return // 关闭弹窗/ESC → 取消删除
    }
  }
  await deleteWorkOrder(row.id, { delete_cycles: deleteCycles })
  ElMessage.success(deleteCycles ? '已删除' : '已删除（工期保留）')
  load()
}

// ---- 聚合工单（按服务类别逐条打包）----
async function openAggregate() {
  aggCustomerId.value = null
  aggCiIds.value = []
  aggGroupIds.value = []
  aggPriority.value = '中'
  aggServiceStart.value = ''
  aggServiceEnd.value = ''
  aggGenerateCycle.value = true
  aggDispatch.value = true
  aggDispatchType.value = '内部'
  aggAssigneeId.value = null
  cis.value = []
  items.value = []
  aggDlg.value = true
  if (!customers.value.length) customers.value = (await listCustomers({ page: 1, size: 100 })).data.items
}
async function onAggCustomerChange() {
  aggCiIds.value = []
  aggGroupIds.value = []
  if (!aggCustomerId.value) {
    cis.value = []
    items.value = []
    return
  }
  cis.value = (await listCis({ page: 1, size: 100, customer_id: aggCustomerId.value })).data.items
  aggCiIds.value = cis.value.map((c) => c.id)  // 默认全选业务系统
  const ciIds = cis.value.map((c) => c.id)
  items.value = ciIds.length ? (await listItems({ page: 1, size: 100, ci_ids: ciIds.join(',') })).data.items : []
  aggGroupIds.value = aggGroups.value.map((g) => g.key)  // 默认全选服务类别
  // 服务起止自动填充：取该客户合同的最早开始 / 最晚结束
  const cs = (await listContracts({ page: 1, size: 100 })).data.items.filter((c: any) => c.customer_id === aggCustomerId.value)
  const starts = cs.map((c: any) => c.start_date).filter(Boolean).sort()
  const ends = cs.map((c: any) => c.end_date).filter(Boolean).sort()
  aggServiceStart.value = starts[0] ?? ''
  aggServiceEnd.value = ends[ends.length - 1] ?? ''
}
function toggleAllCi(v: boolean) {
  aggCiIds.value = v ? filteredCis.value.map((c) => c.id) : []
}
function toggleAll(v: boolean) {
  aggGroupIds.value = v ? aggGroups.value.map((g) => g.key) : []
}
function ciCountOf(g: any) {
  const n = g._ciIds.filter((id: number) => aggCiIds.value.includes(id)).length
  return n > 0 ? `${n}个业务系统` : '未关联业务系统'
}
async function saveAggregate() {
  let count = 0
  for (const key of aggGroupIds.value) {
    const g = aggGroups.value.find((x) => x.key === key)
    if (!g) continue
    // 该组在勾选业务系统下的成员（含「//」不关联业务系统的条目）
    const members = g._members.filter((m: any) => m.ci_id == null || aggCiIds.value.includes(m.ci_id))
    const ciIds = [...new Set(members.map((m: any) => m.ci_id).filter(Boolean))]
    const contractItemIds = members.map((m: any) => m.id)
    if (!contractItemIds.length) continue
    const res = await previewAggregateCycles({ contract_item_ids: contractItemIds })
    const cycles: any[] = []
    for (const iid of contractItemIds) {
      for (const no of (res.data.cycles[iid] || []).map((c: any) => c.cycle_no)) {
        cycles.push({ contract_item_id: iid, cycle_no: no })
      }
    }
    await createAggregateWorkOrder({
      customer_id: aggCustomerId.value,
      ci_ids: ciIds,
      contract_item_ids: contractItemIds,
      cycles,
      priority: aggPriority.value,
      service_start: aggServiceStart.value || null,
      service_end: aggServiceEnd.value || null,
      generate_cycle: aggGenerateCycle.value,
      dispatch: aggDispatch.value,
      dispatch_type: aggDispatchType.value,
      assignee_id: aggDispatch.value ? aggAssigneeId.value : null,
    })
    count++
  }
  ElMessage.success(`已按服务类别创建 ${count} 个工单`)
  aggDlg.value = false
  load()
}
function openEdit(row: any) {
  if (row.contract_item_id == null && row.customer_id) {
    openEditAggregate(row)
  } else {
    detailData.value = row
    detailDlg.value = true
  }
}
async function openEditAggregate(row: any) {
  const scope = (await getWorkOrderScope(row.id)).data
  editAggWoId.value = row.id
  editAggCustomerId.value = row.customer_id ?? null
  editAggCis.value = (await listCis({ page: 1, size: 100, customer_id: row.customer_id })).data.items
  editAggCiIds.value = scope.cis.map((c: any) => c.ci_id)
  editAggProject.value = scope.items.map((it: any) => it.project).join('、') || ''
  editAggPriority.value = row.priority
  const starts = scope.cycles.map((c: any) => c.service_start).filter(Boolean).sort()
  const ends = scope.cycles.map((c: any) => c.service_end).filter(Boolean).sort()
  editAggServiceStart.value = starts[0] ?? ''
  editAggServiceEnd.value = ends[ends.length - 1] ?? ''
  editAggRegenerateCycle.value = true
  editAggDispatch.value = true
  editAggDispatchType.value = scope.dispatch_type || '内部'
  editAggAssigneeId.value = scope.assignee_id ?? null
  editAggDlg.value = true
  if (!users.value.length) {
    try { users.value = (await listUsers()).data } catch {}
  }
}
async function saveEditAggregate() {
  if (!editAggCiIds.value.length) return ElMessage.warning('请选择业务系统')
  if (editAggDispatch.value && !editAggAssigneeId.value) return ElMessage.warning('重新派单需选择执行人')
  await editAggregateWorkOrder(editAggWoId.value!, {
    ci_ids: editAggCiIds.value,
    priority: editAggPriority.value,
    service_start: editAggServiceStart.value || null,
    service_end: editAggServiceEnd.value || null,
    regenerate_cycle: editAggRegenerateCycle.value,
    dispatch: editAggDispatch.value,
    dispatch_type: editAggDispatchType.value,
    assignee_id: editAggDispatch.value ? editAggAssigneeId.value : null,
  })
  ElMessage.success('已保存')
  editAggDlg.value = false
  load()
}
async function openScope(row: any) {
  scopeData.value = (await getWorkOrderScope(row.id)).data
  scopeDlg.value = true
}

onMounted(async () => {
  load()
  customers.value = (await listCustomers({ page: 1, size: 100 })).data.items
  // 执行人 / 流转规则：不依赖 canDispatch（初次挂载时 auth.user 可能尚未加载完成），
  // 直接按 token 拉取；无权限时静默降级
  try {
    users.value = (await listUsers()).data
  } catch {
    // 无人员管理权限时执行人下拉为空
  }
  try {
    transitions.value = (await workflowTransitions()).data
  } catch {
    // 无工作流查看权限时用内置默认流转表
  }
})
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
.wo-section { margin-bottom: 16px; }
.wo-section-head { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.wo-section-title { font-weight: 600; color: #303133; }
.wo-section-count { color: #909399; font-size: 12px; }
.wo-section-empty { color: #c0c4cc; font-size: 13px; padding: 4px 0; }
.pager { margin-top: 14px; justify-content: flex-end; }
.assignee-list { width: 100%; }
.assignee-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
.agg-box { width: 100%; }
.agg-box .el-checkbox-group { display: block; margin-top: 8px; }
.agg-cycle { margin-bottom: 12px; }
.agg-cycle-title { font-weight: 600; margin-bottom: 6px; }
.agg-empty { color: #909399; }
.scope-tag { margin: 0 8px 8px 0; }
.scope-cycle { padding: 3px 0; }
</style>
