<template>
  <div>
    <el-card>
      <div class="toolbar">
        <el-button v-if="canDispatch" type="primary" @click="openCreate">新增工单</el-button>
        <el-button v-if="canDispatch" type="primary" @click="openAggregate">新增聚合工单</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column label="客户" width="130">
          <template #default="{ row }">{{ customerMap.get(row.customer_id)?.name || '' }}</template>
        </el-table-column>
        <el-table-column prop="project" label="服务类别" width="130" />
        <el-table-column prop="type" label="类型" width="100" />
        <el-table-column prop="priority" label="优先级" width="80" />
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column prop="current_cycle_no" label="周期" width="70" />
        <el-table-column prop="progress" label="进度" width="80" />
        <el-table-column label="执行人" width="130">
          <template #default="{ row }">{{ (row.assignee_names || []).join('、') || '—' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="260">
          <template #default="{ row }">
            <el-button v-if="row.customer_id" link type="info" @click="openScope(row)">查看</el-button>
            <el-button v-if="canDispatch" link type="primary" @click="openDispatch(row)">派单</el-button>
            <el-button link type="success" @click="openStatus(row)">流转</el-button>
            <el-button v-if="canDispatch" link type="danger" @click="onDeleteWorkOrder(row)">删除</el-button>
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

    <el-dialog v-model="createDlg" title="新增工单" width="460px">
      <el-form :model="createForm" label-width="90px">
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
          <el-select v-model="createForm.contract_item_id" style="width: 100%" placeholder="选择服务类别" :disabled="!createForm.contract_id">
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

    <el-dialog v-model="statusDlg" title="状态流转" width="420px">
      <el-select v-model="statusForm.status" style="width: 100%">
        <el-option v-for="s in ['待派单', '已派单', '计划中', '进行中', '待验收', '已完成', '已关闭', '已取消']" :key="s" :label="s" :value="s" />
      </el-select>
      <template #footer><el-button @click="statusDlg = false">取消</el-button><el-button type="primary" @click="onStatus">确定</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listWorkOrders, createWorkOrder, updateStatus, dispatch, deleteWorkOrder,
  listCustomers, listCis, listItems, listContracts,
  previewAggregateCycles, createAggregateWorkOrder, getWorkOrderScope,
  listUsers,
} from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()

const rows = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, size: 10 })

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
})
const createContracts = ref<any[]>([])  // 所选客户的项目
const createItems = ref<any[]>([])      // 所选项目的服务类别
const createCiName = ref<Map<number, string>>(new Map())  // 业务系统 id → 名称

const dispatchDlg = ref(false)
const dispatchTarget = ref<number | null>(null)
const dispatchForm = reactive({ dispatch_type: '内部', assignees: [{ user_id: null, workload_ratio: 100 }] as any[] })

const statusDlg = ref(false)
const statusTarget = ref<number | null>(null)
const statusForm = reactive({ status: '待派单' })

// 聚合工单（按服务类别逐条打包：勾选几个服务类别就生成几个工单）
const aggDlg = ref(false)
const aggCustomerId = ref<number | null>(null)
const aggCiIds = ref<number[]>([])       // 勾选的业务系统
const aggGroupIds = ref<string[]>([])    // 选中的服务类别组 key
const aggPriority = ref('中')

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
  Object.assign(createForm, { customer_id: null, contract_id: null, contract_item_id: null, type: '客户工单', priority: '中' })
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
  if (!createForm.contract_id) return
  createItems.value = (await listItems({ page: 1, size: 100, contract_id: createForm.contract_id })).data.items
}
async function onCreate() {
  if (!createForm.customer_id) return ElMessage.warning('请选择客户')
  if (!createForm.contract_id) return ElMessage.warning('请选择项目')
  if (!createForm.contract_item_id) return ElMessage.warning('请选择服务类别')
  const item = createItems.value.find((i: any) => i.id === createForm.contract_item_id)
  await createWorkOrder({
    type: createForm.type,
    priority: createForm.priority,
    contract_id: createForm.contract_id,
    contract_item_id: createForm.contract_item_id,
    ci_id: item?.ci_id ?? null,
    project: item?.project ?? null,
  })
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
function openStatus(row: any) {
  statusTarget.value = row.id
  statusForm.status = row.status
  statusDlg.value = true
}
async function onStatus() {
  await updateStatus(statusTarget.value!, statusForm)
  ElMessage.success('状态已更新')
  statusDlg.value = false
  load()
}
async function onDeleteWorkOrder(row: any) {
  await ElMessageBox.confirm(`确认删除工单「${row.no}」？`, '提示', { type: 'warning' })
  await deleteWorkOrder(row.id)
  ElMessage.success('已删除')
  load()
}

// ---- 聚合工单（按服务类别逐条打包）----
async function openAggregate() {
  aggCustomerId.value = null
  aggCiIds.value = []
  aggGroupIds.value = []
  aggPriority.value = '中'
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
    })
    count++
  }
  ElMessage.success(`已按服务类别创建 ${count} 个工单`)
  aggDlg.value = false
  load()
}
async function openScope(row: any) {
  scopeData.value = (await getWorkOrderScope(row.id)).data
  scopeDlg.value = true
}

onMounted(async () => {
  load()
  customers.value = (await listCustomers({ page: 1, size: 100 })).data.items
  if (canDispatch.value) {
    try {
      users.value = (await listUsers()).data
    } catch {
      // 无人员管理权限时静默降级：执行人下拉为空，派单入口已按角色隐藏
    }
  }
})
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
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
