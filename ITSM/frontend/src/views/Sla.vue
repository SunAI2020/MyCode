<template>
  <div>
    <el-tabs v-model="tab">
      <el-tab-pane label="服务工期" name="cycle">
        <el-card>
          <el-table :data="cycles" v-loading="loading">
            <el-table-column prop="customer_name" label="客户名称" width="130" />
            <el-table-column prop="ci_name" label="业务系统" width="140" show-overflow-tooltip />
            <el-table-column prop="item_project" label="服务类别" width="120" />
            <el-table-column prop="cycle_no" label="期次" width="70" />
            <el-table-column prop="service_start" label="开始" width="110" />
            <el-table-column prop="service_end" label="结束" width="110" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">{{ STATUS_MAP[row.status] || row.status }}</template>
            </el-table-column>
            <el-table-column v-if="canWrite || canDelete" label="操作" width="180">
              <template #default="{ row }">
                <el-button v-if="canWrite" link type="primary" @click="openCycleEdit(row)">编辑</el-button>
                <el-button v-if="canWrite" link type="warning" @click="openCycleDefer(row)">延期</el-button>
                <el-button v-if="canDelete" link type="danger" @click="onDeleteCycle(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="服务提醒" name="reminder">
        <el-card>
          <el-table :data="expiringCycles" v-loading="loading">
            <el-table-column prop="customer_name" label="客户名称" width="130" />
            <el-table-column prop="ci_name" label="业务系统" width="140" show-overflow-tooltip />
            <el-table-column prop="item_project" label="服务类别" width="120" />
            <el-table-column prop="cycle_no" label="期次" width="70" />
            <el-table-column prop="service_start" label="开始时间" width="110" />
            <el-table-column prop="service_end" label="结束时间" width="110" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">{{ STATUS_MAP[row.status] || row.status }}</template>
            </el-table-column>
            <el-table-column v-if="canWrite || canDelete" label="操作" width="240">
              <template #default="{ row }">
                <el-button v-if="canWrite" link type="info" @click="onRemind(row)">提醒</el-button>
                <el-button v-if="canWrite" link type="warning" @click="onUrge(row)">催单</el-button>
                <el-button v-if="canWrite" link type="primary" @click="openCycleDefer(row)">延期</el-button>
                <el-button v-if="canDelete" link type="danger" @click="onCancelCycle(row)">撤销</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="SLA 策略" name="sla">
        <el-card>
          <div class="toolbar"><el-button v-if="canWrite" type="primary" @click="openSla()">新增策略</el-button></div>
          <el-table :data="slas" v-loading="loading">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="customer_level" label="客户级别" width="100" />
            <el-table-column prop="response_limit" label="响应时限" width="100" />
            <el-table-column prop="resolve_limit" label="解决时限" width="100" />
            <el-table-column label="操作" width="150">
              <template #default="{ row }">
                <el-button v-if="canWrite" link type="primary" @click="openSla(row)">编辑</el-button>
                <el-button v-if="canDelete" link type="danger" @click="onDeleteSla(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="slaDlg" :title="slaEditId ? '编辑策略' : '新增策略'" width="480px">
      <el-form :model="slaForm" label-width="90px">
        <el-form-item label="名称"><el-input v-model="slaForm.name" /></el-form-item>
        <el-form-item label="客户级别">
          <el-select v-model="slaForm.customer_level" style="width: 100%">
            <el-option v-for="l in ['金牌', '银牌', '普通']" :key="l" :label="l" :value="l" />
          </el-select>
        </el-form-item>
        <el-form-item label="响应时限"><el-input v-model="slaForm.response_limit" placeholder="如 30分钟" /></el-form-item>
        <el-form-item label="解决时限"><el-input v-model="slaForm.resolve_limit" placeholder="如 24小时" /></el-form-item>
        <el-form-item label="升级链"><el-input v-model="slaForm.escalation_chain" placeholder="执行人→项目经理→部门负责人" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="slaDlg = false">取消</el-button><el-button type="primary" @click="saveSla">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="cycleDlg" :title="cycleMode === 'defer' ? '延期工期' : '编辑工期'" width="480px">
      <el-form :model="cycleForm" label-width="90px">
        <el-form-item v-if="cycleMode !== 'defer'" label="开始时间">
          <el-date-picker v-model="cycleForm.service_start" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="结束时间">
          <el-date-picker v-model="cycleForm.service_end" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item v-if="cycleMode !== 'defer'" label="状态">
          <el-select v-model="cycleForm.status" style="width: 100%">
            <el-option v-for="(label, s) in STATUS_MAP" :key="s" :label="label" :value="s" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="cycleDlg = false">取消</el-button><el-button type="primary" @click="saveCycle">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listSla, createSla, updateSla, deleteSla, listCycles, updateCycle, deleteCycle, remindCycle, urgeCycle, cancelCycle } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const canWrite = computed(() => auth.hasPermission('sla:write'))
const canDelete = computed(() => auth.hasPermission('sla:delete'))

const tab = ref('sla')
const loading = ref(false)
const STATUS_MAP: Record<string, string> = { pending: '待执行', started: '进行中', done: '已完成', cancelled: '已撤销' }
const slas = ref<any[]>([])
const cycles = ref<any[]>([])
const expiringCycles = ref<any[]>([])

const slaDlg = ref(false)
const slaEditId = ref<number | null>(null)
const slaForm = reactive({ name: '', customer_level: '普通', response_limit: '', resolve_limit: '', escalation_chain: '' })

const cycleDlg = ref(false)
const cycleMode = ref<'edit' | 'defer'>('edit')
const cycleEditId = ref<number | null>(null)
const cycleForm = reactive({ service_start: '', service_end: '', status: 'pending' })

async function loadSlas() {
  slas.value = (await listSla({ page: 1, size: 100 })).data.items
}
async function loadCycles() {
  cycles.value = (await listCycles({ page: 1, size: 100 })).data.items
}
async function loadExpiringCycles() {
  expiringCycles.value = (await listCycles({ page: 1, size: 100, expiring: true })).data.items
}

function openSla(row?: any) {
  if (row) {
    slaEditId.value = row.id
    Object.assign(slaForm, { name: row.name, customer_level: row.customer_level, response_limit: row.response_limit, resolve_limit: row.resolve_limit, escalation_chain: row.escalation_chain })
  } else {
    slaEditId.value = null
    Object.assign(slaForm, { name: '', customer_level: '普通', response_limit: '', resolve_limit: '', escalation_chain: '' })
  }
  slaDlg.value = true
}
async function saveSla() {
  if (slaEditId.value) await updateSla(slaEditId.value, slaForm)
  else await createSla(slaForm)
  ElMessage.success('已保存')
  slaDlg.value = false
  loadSlas()
}
async function onDeleteSla(row: any) {
  await ElMessageBox.confirm(`确认删除策略「${row.name}」？`, '提示', { type: 'warning' })
  await deleteSla(row.id)
  loadSlas()
}

function openCycleEdit(row: any) {
  cycleEditId.value = row.id
  cycleMode.value = 'edit'
  Object.assign(cycleForm, { service_start: row.service_start, service_end: row.service_end, status: row.status })
  cycleDlg.value = true
}
function openCycleDefer(row: any) {
  cycleEditId.value = row.id
  cycleMode.value = 'defer'
  Object.assign(cycleForm, { service_start: row.service_start, service_end: row.service_end, status: row.status })
  cycleDlg.value = true
}
async function saveCycle() {
  const payload: any = { service_end: cycleForm.service_end }
  if (cycleMode.value === 'edit') {
    payload.service_start = cycleForm.service_start
    payload.status = cycleForm.status
  }
  await updateCycle(cycleEditId.value!, payload)
  ElMessage.success('已保存')
  cycleDlg.value = false
  loadCycles()
  loadExpiringCycles()
}
async function onDeleteCycle(row: any) {
  await ElMessageBox.confirm(`确认删除该工期（第 ${row.cycle_no} 次）？`, '提示', { type: 'warning' })
  await deleteCycle(row.id)
  ElMessage.success('已删除')
  loadCycles()
}
async function onRemind(row: any) {
  await remindCycle(row.id)
  ElMessage.success('已提醒')
}
async function onUrge(row: any) {
  await urgeCycle(row.id)
  ElMessage.success('已催单')
}
async function onCancelCycle(row: any) {
  await ElMessageBox.confirm(`确认撤销该服务工期（第 ${row.cycle_no} 次）？`, '提示', { type: 'warning' })
  await cancelCycle(row.id)
  ElMessage.success('已撤销')
  loadCycles()
  loadExpiringCycles()
}

onMounted(() => {
  loadSlas()
  loadCycles()
  loadExpiringCycles()
})
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
</style>
