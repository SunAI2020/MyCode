<template>
  <div>
    <el-card>
      <div class="toolbar">
        <el-button v-if="canDispatch" type="primary" @click="openCreate">新增工单</el-button>
        <el-button v-if="canDispatch" type="primary" @click="openAggregate">新增聚合工单</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="no" label="工单号" width="150" />
        <el-table-column prop="type" label="类型" width="100" />
        <el-table-column label="客户" width="130">
          <template #default="{ row }">{{ customerMap.get(row.customer_id)?.name || '' }}</template>
        </el-table-column>
        <el-table-column prop="project" label="运维项目" width="130" />
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column prop="priority" label="优先级" width="80" />
        <el-table-column prop="progress" label="进度" width="80" />
        <el-table-column label="执行人" width="130">
          <template #default="{ row }">{{ (row.assignee_names || []).join('、') || '—' }}</template>
        </el-table-column>
        <el-table-column prop="current_cycle_no" label="周期" width="70" />
        <el-table-column label="操作" width="210">
          <template #default="{ row }">
            <el-button v-if="row.customer_id" link type="info" @click="openScope(row)">查看</el-button>
            <el-button v-if="canDispatch" link type="primary" @click="openDispatch(row)">派单</el-button>
            <el-button link type="success" @click="openStatus(row)">流转</el-button>
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
        <el-form-item label="接单ID"><el-input v-model.number="createForm.receive_id" /></el-form-item>
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

    <el-dialog v-model="aggDlg" title="新增聚合工单" width="760px">
      <el-form label-width="90px">
        <el-form-item label="客户">
          <el-select v-model="aggCustomerId" style="width: 100%" @change="onAggCustomerChange">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务对象">
          <div class="agg-box">
            <el-checkbox :model-value="aggCiAll" :indeterminate="aggCiIndeterminate" @change="toggleAllCi">全选</el-checkbox>
            <el-checkbox-group v-model="aggCiIds" @change="onAggCiChange">
              <el-checkbox v-for="ci in filteredCis" :key="ci.id" :value="ci.id">{{ ci.name }}</el-checkbox>
            </el-checkbox-group>
          </div>
        </el-form-item>
        <el-form-item label="服务项目">
          <div class="agg-box">
            <el-checkbox :model-value="aggItemAll" :indeterminate="aggItemIndeterminate" @change="toggleAllItem">全选</el-checkbox>
            <el-checkbox-group v-model="aggItemIds" @change="onAggItemChange">
              <el-checkbox v-for="it in filteredItems" :key="it.id" :value="it.id">{{ it.project }}</el-checkbox>
            </el-checkbox-group>
          </div>
        </el-form-item>
        <el-form-item label="频次">
          <div v-if="!filteredItems.length" class="agg-empty">请先选择服务对象 / 服务项目</div>
          <div v-for="it in filteredItems" :key="it.id" class="agg-cycle">
            <div class="agg-cycle-title">{{ it.project }}（每 {{ it.frequency }}{{ it.unit }}）</div>
            <el-checkbox-group v-model="aggCycles[it.id]">
              <el-checkbox v-for="cy in cycleOptions[it.id] || []" :key="cy.cycle_no" :value="cy.cycle_no">
                #{{ cy.cycle_no }}（{{ cy.service_start }} ~ {{ cy.service_end }}）
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
      <template #footer><el-button @click="aggDlg = false">取消</el-button><el-button type="primary" @click="saveAggregate">创建</el-button></template>
    </el-dialog>

    <el-dialog v-model="scopeDlg" title="聚合工单明细" width="720px">
      <template v-if="scopeData.work_order">
        <p>工单号：{{ scopeData.work_order.no }}　类型：{{ scopeData.work_order.type }}　状态：{{ scopeData.work_order.status }}</p>
        <el-divider content-position="left">服务对象（{{ scopeData.cis.length }}）</el-divider>
        <el-tag v-for="c in scopeData.cis" :key="c.ci_id" class="scope-tag">{{ c.name }}</el-tag>
        <el-divider content-position="left">服务项目（{{ scopeData.items.length }}）</el-divider>
        <el-tag v-for="i in scopeData.items" :key="i.contract_item_id" class="scope-tag">{{ i.project }}（每 {{ i.frequency }}{{ i.unit }}）</el-tag>
        <el-divider content-position="left">频次（{{ scopeData.cycles.length }}）</el-divider>
        <div v-for="cy in scopeData.cycles" :key="cy.contract_item_id + '-' + cy.cycle_no" class="scope-cycle">
          {{ itemProjectMap[cy.contract_item_id] || cy.contract_item_id }}　第 {{ cy.cycle_no }} 次　{{ cy.service_start }} ~ {{ cy.service_end }}
        </div>
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
import { ElMessage } from 'element-plus'
import {
  listWorkOrders, createWorkOrder, updateStatus, dispatch,
  listCustomers, listCis, listItems,
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
const itemProjectMap = computed(() => {
  const m: Record<number, string> = {}
  for (const i of items.value) m[i.id] = i.project
  return m
})

const createDlg = ref(false)
const createForm = reactive({ receive_id: null as number | null, type: '客户工单', priority: '中' })

const dispatchDlg = ref(false)
const dispatchTarget = ref<number | null>(null)
const dispatchForm = reactive({ dispatch_type: '内部', assignees: [{ user_id: null, workload_ratio: 100 }] as any[] })

const statusDlg = ref(false)
const statusTarget = ref<number | null>(null)
const statusForm = reactive({ status: '待派单' })

// 聚合工单
const aggDlg = ref(false)
const aggCustomerId = ref<number | null>(null)
const aggCiIds = ref<number[]>([])
const aggItemIds = ref<number[]>([])
const aggCycles = ref<Record<number, number[]>>({})
const cycleOptions = ref<Record<number, any[]>>({})
const aggPriority = ref('中')

const filteredCis = computed(() => cis.value.filter((c) => c.customer_id === aggCustomerId.value))
const filteredItems = computed(() => items.value.filter((i) => aggCiIds.value.includes(i.ci_id)))
const aggCiAll = computed(() => filteredCis.value.length > 0 && aggCiIds.value.length === filteredCis.value.length)
const aggCiIndeterminate = computed(() => aggCiIds.value.length > 0 && aggCiIds.value.length < filteredCis.value.length)
const aggItemAll = computed(() => filteredItems.value.length > 0 && aggItemIds.value.length === filteredItems.value.length)
const aggItemIndeterminate = computed(() => aggItemIds.value.length > 0 && aggItemIds.value.length < filteredItems.value.length)

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
function openCreate() {
  Object.assign(createForm, { receive_id: null, type: '客户工单', priority: '中' })
  createDlg.value = true
}
async function onCreate() {
  await createWorkOrder(createForm)
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

// ---- 聚合工单 ----
async function openAggregate() {
  aggCustomerId.value = null
  aggCiIds.value = []
  aggItemIds.value = []
  aggCycles.value = {}
  cycleOptions.value = {}
  aggPriority.value = '中'
  cis.value = []
  items.value = []
  aggDlg.value = true
  if (!customers.value.length) customers.value = (await listCustomers({ page: 1, size: 100 })).data.items
}
async function onAggCustomerChange() {
  if (!aggCustomerId.value) {
    cis.value = []
    items.value = []
    aggCiIds.value = []
    aggItemIds.value = []
    aggCycles.value = {}
    cycleOptions.value = {}
    return
  }
  cis.value = (await listCis({ page: 1, size: 100, customer_id: aggCustomerId.value })).data.items
  aggCiIds.value = cis.value.map((c) => c.id)  // 默认全选
  await onAggCiChange()
}
async function onAggCiChange() {
  if (!aggCiIds.value.length) {
    items.value = []
    aggItemIds.value = []
    aggCycles.value = {}
    cycleOptions.value = {}
    return
  }
  items.value = (await listItems({ page: 1, size: 100, ci_ids: aggCiIds.value.join(',') })).data.items
  aggItemIds.value = items.value.map((i) => i.id)  // 默认全选
  await onAggItemChange()
}
async function onAggItemChange() {
  if (!aggItemIds.value.length) {
    aggCycles.value = {}
    cycleOptions.value = {}
    return
  }
  const res = await previewAggregateCycles({ contract_item_ids: aggItemIds.value })
  cycleOptions.value = res.data.cycles
  const next: Record<number, number[]> = {}
  for (const it of filteredItems.value) {
    next[it.id] = (cycleOptions.value[it.id] || []).map((c: any) => c.cycle_no)  // 默认全选
  }
  aggCycles.value = next
}
function toggleAllCi(v: boolean) {
  aggCiIds.value = v ? filteredCis.value.map((c) => c.id) : []
  onAggCiChange()
}
function toggleAllItem(v: boolean) {
  aggItemIds.value = v ? filteredItems.value.map((i) => i.id) : []
  onAggItemChange()
}
async function saveAggregate() {
  const cycles: any[] = []
  for (const iid of aggItemIds.value) {
    for (const no of aggCycles.value[iid] || []) {
      cycles.push({ contract_item_id: iid, cycle_no: no })
    }
  }
  await createAggregateWorkOrder({
    customer_id: aggCustomerId.value,
    ci_ids: aggCiIds.value,
    contract_item_ids: aggItemIds.value,
    cycles,
    priority: aggPriority.value,
  })
  ElMessage.success('聚合工单已创建')
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
