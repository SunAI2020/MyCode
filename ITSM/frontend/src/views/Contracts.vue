<template>
  <div>
    <el-tabs v-model="tab">
      <el-tab-pane label="合同" name="contract">
        <el-card>
          <div class="toolbar">
            <el-button v-if="canWrite" type="primary" @click="openContract()">新增合同</el-button>
          </div>
          <el-table :data="contracts" v-loading="loading">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="no" label="编号" />
            <el-table-column prop="type" label="类型" width="110" />
            <el-table-column prop="amount" label="金额" width="110" />
            <el-table-column prop="status" label="状态" width="90" />
            <el-table-column v-if="canWrite || canDelete" label="操作" width="150">
              <template #default="{ row }">
                <el-button v-if="canWrite" link type="primary" @click="openContract(row)">编辑</el-button>
                <el-button v-if="canDelete" link type="danger" @click="onDeleteContract(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="服务对象" name="ci">
        <el-card>
          <div class="toolbar"><el-button v-if="canWrite" type="primary" @click="openCi()">新增服务对象</el-button></div>
          <el-table :data="cis" v-loading="loading">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column label="合同名称">
              <template #default="{ row }">{{ contractNameOf(row) }}</template>
            </el-table-column>
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="type" label="类型" width="110" />
            <el-table-column prop="ip" label="IP" width="140" />
            <el-table-column prop="lifecycle" label="生命周期" width="90" />
            <el-table-column v-if="canWrite || canDelete" label="操作" width="150">
              <template #default="{ row }">
                <el-button v-if="canWrite" link type="primary" @click="openCi(row)">编辑</el-button>
                <el-button v-if="canDelete" link type="danger" @click="onDeleteCi(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="服务项目" name="item">
        <el-card>
          <div class="toolbar">
            <el-select v-model="itemFilter.ci_id" placeholder="选择服务对象" clearable style="width: 240px" @change="loadItems">
              <el-option v-for="c in cis" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
            <el-button v-if="canWrite" type="primary" @click="openItem()">新增服务项目</el-button>
          </div>
          <el-table :data="items" v-loading="loading">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column label="服务对象">
              <template #default="{ row }">{{ ciNameOf(row) }}</template>
            </el-table-column>
            <el-table-column label="合同名称">
              <template #default="{ row }">{{ contractNameOf(row) }}</template>
            </el-table-column>
            <el-table-column label="客户名称">
              <template #default="{ row }">{{ customerNameOf(row) }}</template>
            </el-table-column>
            <el-table-column prop="project" label="运维项目" />
            <el-table-column prop="frequency" label="频率" width="70" />
            <el-table-column prop="unit" label="单位" width="90" />
            <el-table-column prop="price" label="价格" width="110" />
            <el-table-column v-if="canWrite || canDelete" label="操作" width="210">
              <template #default="{ row }">
                <el-button v-if="canWrite" link type="primary" @click="openItem(row)">编辑</el-button>
                <el-button v-if="canWrite" link type="success" @click="onGenerate(row)">生成周期</el-button>
                <el-button v-if="canDelete" link type="danger" @click="onDeleteItem(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 合同弹窗 -->
    <el-dialog v-model="contractDlg" :title="contractEditId ? '编辑合同' : '新增合同'" width="520px">
      <el-form :model="contractForm" label-width="80px">
        <el-form-item label="名称"><el-input v-model="contractForm.name" /></el-form-item>
        <el-form-item label="客户名称">
          <el-select v-model="contractForm.customer_id" style="width: 100%">
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="合同编号"><el-input v-model="contractForm.no" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="contractForm.type" style="width: 100%">
            <el-option v-for="t in ['安全服务', '安全运维', '设备升级', '购买设备', '机房改造', '其他']" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="金额"><el-input v-model.number="contractForm.amount" /></el-form-item>
        <el-form-item label="开始日期"><el-date-picker v-model="contractForm.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="结束日期"><el-date-picker v-model="contractForm.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="contractForm.status" style="width: 100%">
            <el-option v-for="s in ['洽谈中', '执行中', '已到期', '已续约']" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="contractDlg = false">取消</el-button><el-button type="primary" @click="saveContract">保存</el-button></template>
    </el-dialog>

    <!-- 服务项目弹窗 -->
    <el-dialog v-model="itemDlg" :title="itemEditId ? '编辑服务项目' : '新增服务项目'" width="520px">
      <el-form :model="itemForm" label-width="90px">
        <el-form-item label="服务对象">
          <el-select v-model="itemForm.ci_id" style="width: 100%">
            <el-option v-for="c in cis" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="运维项目">
          <el-select v-model="itemForm.project" style="width: 100%">
            <el-option v-for="p in PROJECTS" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="频率"><el-input-number v-model="itemForm.frequency" :min="1" /></el-form-item>
        <el-form-item label="单位">
          <el-select v-model="itemForm.unit" style="width: 100%">
            <el-option v-for="u in ['天', '周', '月', '季度', '半年', '年', '不定期']" :key="u" :label="u" :value="u" />
          </el-select>
        </el-form-item>
        <el-form-item label="价格"><el-input v-model.number="itemForm.price" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="itemDlg = false">取消</el-button><el-button type="primary" @click="saveItem">保存</el-button></template>
    </el-dialog>

    <!-- 服务对象弹窗 -->
    <el-dialog v-model="ciDlg" :title="ciEditId ? '编辑服务对象' : '新增服务对象'" width="520px">
      <el-form :model="ciForm" label-width="90px">
        <el-form-item label="合同">
          <el-select v-model="ciForm.contract_id" style="width: 100%">
            <el-option v-for="c in contracts" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称"><el-input v-model="ciForm.name" /></el-form-item>
        <el-form-item label="类型">
          <el-select v-model="ciForm.type" style="width: 100%">
            <el-option v-for="t in ['业务系统', '网络设备', '服务器', '机房', '数据库']" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="IP"><el-input v-model="ciForm.ip" /></el-form-item>
        <el-form-item label="生命周期">
          <el-select v-model="ciForm.lifecycle" style="width: 100%">
            <el-option v-for="l in ['新增', '在用', '变更', '下线']" :key="l" :label="l" :value="l" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="ciDlg = false">取消</el-button><el-button type="primary" @click="saveCi">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listContracts, createContract, updateContract, deleteContract,
  listItems, createItem, updateItem, deleteItem, generateCycles,
  listCis, createCi, updateCi, deleteCi, listCustomers,
} from '@/api'
import { useAuthStore } from '@/stores/auth'

const tab = ref('contract')
const loading = ref(false)
const contracts = ref<any[]>([])
const customers = ref<any[]>([])
const items = ref<any[]>([])
const cis = ref<any[]>([])
const itemFilter = reactive({ ci_id: null as number | null })

// 写/删权限与后端 WRITE_ROLE(sys_admin,sys_ops) / 删除(sys_admin) 对齐，避免 ticket_mgr 看到按钮却 403
const auth = useAuthStore()
const canWrite = computed(() => {
  const r = auth.roles()
  return r.includes('sys_admin') || r.includes('sys_ops')
})
const canDelete = computed(() => auth.roles().includes('sys_admin'))

const contractDlg = ref(false)
const contractEditId = ref<number | null>(null)
const contractForm = reactive({ customer_id: 1, name: '', type: '安全服务', no: '', amount: null as number | null, start_date: '', end_date: '', status: '洽谈中' })

const itemDlg = ref(false)
const itemEditId = ref<number | null>(null)
const itemForm = reactive({ ci_id: 1, project: '', frequency: 1, unit: '月', price: null as number | null })
// 运维项目枚举（与后端 seed 的 project 字典一致）
const PROJECTS = ['漏洞扫描', '渗透测试', '应急演练', '安全加固', '安全培训', '代码审计', '基线核查', '安全巡检', '安全评估', '应急处置', '重保值守', '攻防演练', '安全防护', '设备巡检', '等保测评', '故障排查']

const ciDlg = ref(false)
const ciEditId = ref<number | null>(null)
const ciForm = reactive({ contract_id: 1, name: '', type: '业务系统', ip: '', lifecycle: '在用' })

async function loadContracts() {
  loading.value = true
  try {
    contracts.value = (await listContracts({ page: 1, size: 100 })).data.items
  } finally {
    loading.value = false
  }
}
async function loadCustomers() {
  customers.value = (await listCustomers({ page: 1, size: 100 })).data.items
}
async function loadItems() {
  const params: any = { page: 1, size: 100 }
  if (itemFilter.ci_id) params.ci_id = itemFilter.ci_id
  items.value = (await listItems(params)).data.items
}
async function loadCis() {
  cis.value = (await listCis({ page: 1, size: 100 })).data.items
}

// 列表父级名称映射
const contractMap = computed(() => new Map(contracts.value.map((c) => [c.id, c])))
const customerMap = computed(() => new Map(customers.value.map((c) => [c.id, c])))
const ciMap = computed(() => new Map(cis.value.map((c) => [c.id, c])))
function contractNameOf(row: any) {
  return contractMap.value.get(row.contract_id)?.name ?? ''
}
function customerNameOf(row: any) {
  const c = contractMap.value.get(row.contract_id)
  return c ? (customerMap.value.get(c.customer_id)?.name ?? '') : ''
}
function ciNameOf(row: any) {
  return ciMap.value.get(row.ci_id)?.name ?? ''
}

// 合同
function openContract(row?: any) {
  if (row) {
    contractEditId.value = row.id
    Object.assign(contractForm, { customer_id: row.customer_id, name: row.name, type: row.type, no: row.no, amount: row.amount, start_date: row.start_date, end_date: row.end_date, status: row.status })
  } else {
    contractEditId.value = null
    Object.assign(contractForm, { customer_id: 1, name: '', type: '安全服务', no: '', amount: null, start_date: '', end_date: '', status: '洽谈中' })
  }
  contractDlg.value = true
}
async function saveContract() {
  if (contractEditId.value) await updateContract(contractEditId.value, contractForm)
  else await createContract(contractForm)
  ElMessage.success('已保存')
  contractDlg.value = false
  loadContracts()
}
async function onDeleteContract(row: any) {
  await ElMessageBox.confirm(`确认删除合同「${row.name}」？`, '提示', { type: 'warning' })
  await deleteContract(row.id)
  loadContracts()
}

// 服务项目
function openItem(row?: any) {
  if (row) {
    itemEditId.value = row.id
    Object.assign(itemForm, { ci_id: row.ci_id, project: row.project, frequency: row.frequency, unit: row.unit, price: row.price })
  } else {
    itemEditId.value = null
    Object.assign(itemForm, { ci_id: itemFilter.ci_id || cis.value[0]?.id || 1, project: '', frequency: 1, unit: '月', price: null })
  }
  itemDlg.value = true
}
async function saveItem() {
  if (itemEditId.value) await updateItem(itemEditId.value, itemForm)
  else await createItem(itemForm)
  ElMessage.success('已保存')
  itemDlg.value = false
  loadItems()
}
async function onGenerate(row: any) {
  const res = await generateCycles(row.id)
  ElMessage.success(`生成周期完成：新增 ${res.data.created} / 共 ${res.data.total}`)
}
async function onDeleteItem(row: any) {
  await ElMessageBox.confirm('确认删除该服务项目？', '提示', { type: 'warning' })
  await deleteItem(row.id)
  loadItems()
}

// 服务对象
function openCi(row?: any) {
  if (row) {
    ciEditId.value = row.id
    Object.assign(ciForm, { contract_id: row.contract_id, name: row.name, type: row.type, ip: row.ip, lifecycle: row.lifecycle })
  } else {
    ciEditId.value = null
    Object.assign(ciForm, { contract_id: 1, name: '', type: '业务系统', ip: '', lifecycle: '在用' })
  }
  ciDlg.value = true
}
async function saveCi() {
  if (ciEditId.value) await updateCi(ciEditId.value, ciForm)
  else await createCi(ciForm)
  ElMessage.success('已保存')
  ciDlg.value = false
  loadCis()
}
async function onDeleteCi(row: any) {
  await ElMessageBox.confirm('确认删除该服务对象？', '提示', { type: 'warning' })
  await deleteCi(row.id)
  loadCis()
}

onMounted(() => {
  loadContracts()
  loadCustomers()
  loadItems()
  loadCis()
})
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
</style>
