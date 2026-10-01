<template>
  <div>
    <el-tabs v-model="tab">
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

      <el-tab-pane label="服务周期" name="cycle">
        <el-card>
          <el-table :data="cycles" v-loading="loading">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="customer_name" label="客户名称" width="130" />
            <el-table-column prop="project_name" label="项目名称" width="130" />
            <el-table-column prop="ci_name" label="服务目标（系统）" width="140" show-overflow-tooltip />
            <el-table-column prop="item_project" label="服务项目" width="120" />
            <el-table-column prop="cycle_no" label="期次" width="70" />
            <el-table-column prop="service_start" label="开始" width="110" />
            <el-table-column prop="service_end" label="结束" width="110" />
            <el-table-column label="状态" width="90">
              <template #default="{ row }">{{ STATUS_MAP[row.status] || row.status }}</template>
            </el-table-column>
            <el-table-column prop="auto_generated" label="自动生成" width="90" />
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="服务提醒" name="reminder">
        <el-card>
          <el-table :data="reminders" v-loading="loading">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column prop="type" label="类型" width="80" />
            <el-table-column prop="level" label="级别" width="80" />
            <el-table-column prop="content" label="内容" />
            <el-table-column prop="channel" label="渠道" width="90" />
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
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listSla, createSla, updateSla, deleteSla, listCycles, listReminders } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const canWrite = computed(() => auth.hasPermission('sla:write'))
const canDelete = computed(() => auth.hasPermission('sla:delete'))

const tab = ref('sla')
const loading = ref(false)
const STATUS_MAP: Record<string, string> = { pending: '待执行', started: '进行中', done: '已完成' }
const slas = ref<any[]>([])
const cycles = ref<any[]>([])
const reminders = ref<any[]>([])

const slaDlg = ref(false)
const slaEditId = ref<number | null>(null)
const slaForm = reactive({ name: '', customer_level: '普通', response_limit: '', resolve_limit: '', escalation_chain: '' })

async function loadSlas() {
  slas.value = (await listSla({ page: 1, size: 100 })).data.items
}
async function loadCycles() {
  cycles.value = (await listCycles({ page: 1, size: 100 })).data.items
}
async function loadReminders() {
  reminders.value = (await listReminders({ page: 1, size: 100 })).data.items
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

onMounted(() => {
  loadSlas()
  loadCycles()
  loadReminders()
})
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
</style>
