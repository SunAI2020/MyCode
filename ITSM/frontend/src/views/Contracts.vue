<template>
  <div>
    <el-tabs v-model="tab">
      <el-tab-pane label="合同" name="contract">
        <el-card>
          <div class="toolbar">
            <el-button type="primary" @click="openContract()">新增合同</el-button>
          </div>
          <el-table :data="contracts" v-loading="loading">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="no" label="编号" />
            <el-table-column prop="type" label="类型" width="110" />
            <el-table-column prop="amount" label="金额" width="110" />
            <el-table-column prop="status" label="状态" width="90" />
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button link type="primary" @click="openContract(row)">编辑</el-button>
                <el-button link type="danger" @click="onDeleteContract(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="合同子项" name="item">
        <el-card>
          <div class="toolbar">
            <el-select v-model="itemFilter.contract_id" placeholder="选择合同" clearable style="width: 240px" @change="loadItems">
              <el-option v-for="c in contracts" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
            <el-button type="primary" @click="openItem()">新增子项</el-button>
          </div>
          <el-table :data="items" v-loading="loading">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="project" label="运维项目" />
            <el-table-column prop="frequency" label="频率" width="70" />
            <el-table-column prop="unit" label="单位" width="90" />
            <el-table-column prop="price" label="价格" width="110" />
            <el-table-column label="操作" width="210">
              <template #default="{ row }">
                <el-button link type="primary" @click="openItem(row)">编辑</el-button>
                <el-button link type="success" @click="onGenerate(row)">生成周期</el-button>
                <el-button link type="danger" @click="onDeleteItem(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="服务对象(CI)" name="ci">
        <el-card>
          <div class="toolbar"><el-button type="primary" @click="openCi()">新增 CI</el-button></div>
          <el-table :data="cis" v-loading="loading">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="type" label="类型" width="110" />
            <el-table-column prop="ip" label="IP" width="140" />
            <el-table-column prop="lifecycle" label="生命周期" width="90" />
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button link type="primary" @click="openCi(row)">编辑</el-button>
                <el-button link type="danger" @click="onDeleteCi(row)">删除</el-button>
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
        <el-form-item label="客户ID"><el-input v-model.number="contractForm.customer_id" /></el-form-item>
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
            <el-option v-for="s in ['草稿', '执行中', '已到期', '已续约']" :key="s" :label="s" :value="s" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="contractDlg = false">取消</el-button><el-button type="primary" @click="saveContract">保存</el-button></template>
    </el-dialog>

    <!-- 子项弹窗 -->
    <el-dialog v-model="itemDlg" :title="itemEditId ? '编辑子项' : '新增子项'" width="520px">
      <el-form :model="itemForm" label-width="90px">
        <el-form-item label="合同ID"><el-input v-model.number="itemForm.contract_id" /></el-form-item>
        <el-form-item label="运维项目"><el-input v-model="itemForm.project" /></el-form-item>
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

    <!-- CI 弹窗 -->
    <el-dialog v-model="ciDlg" :title="ciEditId ? '编辑 CI' : '新增 CI'" width="520px">
      <el-form :model="ciForm" label-width="90px">
        <el-form-item label="客户ID"><el-input v-model.number="ciForm.customer_id" /></el-form-item>
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
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listContracts, createContract, updateContract, deleteContract,
  listItems, createItem, updateItem, deleteItem, generateCycles,
  listCis, createCi, updateCi, deleteCi,
} from '@/api'

const tab = ref('contract')
const loading = ref(false)
const contracts = ref<any[]>([])
const items = ref<any[]>([])
const cis = ref<any[]>([])
const itemFilter = reactive({ contract_id: null as number | null })

const contractDlg = ref(false)
const contractEditId = ref<number | null>(null)
const contractForm = reactive({ customer_id: 1, name: '', type: '安全服务', no: '', amount: null as number | null, start_date: '', end_date: '', status: '草稿' })

const itemDlg = ref(false)
const itemEditId = ref<number | null>(null)
const itemForm = reactive({ contract_id: 1, project: '', frequency: 1, unit: '月', price: null as number | null })

const ciDlg = ref(false)
const ciEditId = ref<number | null>(null)
const ciForm = reactive({ customer_id: 1, name: '', type: '业务系统', ip: '', lifecycle: '在用' })

async function loadContracts() {
  loading.value = true
  try {
    contracts.value = (await listContracts({ page: 1, size: 100 })).data.items
  } finally {
    loading.value = false
  }
}
async function loadItems() {
  const params: any = { page: 1, size: 100 }
  if (itemFilter.contract_id) params.contract_id = itemFilter.contract_id
  items.value = (await listItems(params)).data.items
}
async function loadCis() {
  cis.value = (await listCis({ page: 1, size: 100 })).data.items
}

// 合同
function openContract(row?: any) {
  if (row) {
    contractEditId.value = row.id
    Object.assign(contractForm, { customer_id: row.customer_id, name: row.name, type: row.type, no: row.no, amount: row.amount, start_date: row.start_date, end_date: row.end_date, status: row.status })
  } else {
    contractEditId.value = null
    Object.assign(contractForm, { customer_id: 1, name: '', type: '安全服务', no: '', amount: null, start_date: '', end_date: '', status: '草稿' })
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

// 子项
function openItem(row?: any) {
  if (row) {
    itemEditId.value = row.id
    Object.assign(itemForm, { contract_id: row.contract_id, project: row.project, frequency: row.frequency, unit: row.unit, price: row.price })
  } else {
    itemEditId.value = null
    Object.assign(itemForm, { contract_id: itemFilter.contract_id || 1, project: '', frequency: 1, unit: '月', price: null })
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
  await ElMessageBox.confirm('确认删除该子项？', '提示', { type: 'warning' })
  await deleteItem(row.id)
  loadItems()
}

// CI
function openCi(row?: any) {
  if (row) {
    ciEditId.value = row.id
    Object.assign(ciForm, { customer_id: row.customer_id, name: row.name, type: row.type, ip: row.ip, lifecycle: row.lifecycle })
  } else {
    ciEditId.value = null
    Object.assign(ciForm, { customer_id: 1, name: '', type: '业务系统', ip: '', lifecycle: '在用' })
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
  await ElMessageBox.confirm('确认删除该 CI？', '提示', { type: 'warning' })
  await deleteCi(row.id)
  loadCis()
}

onMounted(() => {
  loadContracts()
  loadItems()
  loadCis()
})
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
</style>
