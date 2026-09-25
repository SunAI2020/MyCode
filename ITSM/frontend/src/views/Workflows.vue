<template>
  <div>
    <el-card>
      <div class="toolbar">
        <el-select v-model="entity" style="width: 180px" @change="loadTransitions">
          <el-option label="工单" value="work_order" />
          <el-option label="变更单" value="change_order" />
          <el-option label="外包" value="outsourcing" />
        </el-select>
        <el-button type="primary" @click="openCreate">新增规则</el-button>
      </div>

      <h3 class="sec">有效状态流转（默认 ∪ DB 规则）</h3>
      <div class="transitions">
        <div v-for="(targets, from) in transitions[entity] || {}" :key="from" class="from-row">
          <el-tag type="info">{{ from }}</el-tag>
          <span class="arrow">→</span>
          <el-tag v-for="t in targets" :key="t" class="to-tag">{{ t }}</el-tag>
        </div>
      </div>
    </el-card>

    <el-card class="mt">
      <template #header><b>自定义规则</b>（DB 覆盖/扩展，默认保留）</template>
      <el-table :data="rules" v-loading="loading">
        <el-table-column prop="entity" label="实体" width="120" />
        <el-table-column prop="from_status" label="源状态" width="110" />
        <el-table-column prop="to_status" label="目标状态" width="110" />
        <el-table-column prop="enabled" label="启用" width="80">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '是' : '否' }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button link type="primary" @click="onToggle(row)">{{ row.enabled ? '停用' : '启用' }}</el-button>
            <el-button link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="pager" layout="total, prev, pager, next" :total="total" :page-size="query.size" :current-page="query.page" @current-change="onPage" />
    </el-card>

    <el-dialog v-model="createDlg" title="新增工作流规则" width="440px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="实体">
          <el-select v-model="createForm.entity" style="width: 100%">
            <el-option label="工单" value="work_order" />
            <el-option label="变更单" value="change_order" />
            <el-option label="外包" value="outsourcing" />
          </el-select>
        </el-form-item>
        <el-form-item label="源状态"><el-input v-model="createForm.from_status" /></el-form-item>
        <el-form-item label="目标状态"><el-input v-model="createForm.to_status" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="createForm.name" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="createDlg = false">取消</el-button><el-button type="primary" @click="onCreate">创建</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listWorkflowRules, workflowTransitions, createWorkflowRule, updateWorkflowRule, deleteWorkflowRule } from '@/api'

const entity = ref('work_order')
const transitions = ref<any>({})
const rules = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, size: 10 })

const createDlg = ref(false)
const createForm = reactive({ entity: 'work_order', from_status: '', to_status: '', name: '' })

async function loadTransitions() {
  const res = await workflowTransitions()
  transitions.value = res.data
}
async function load() {
  loading.value = true
  try {
    const res = await listWorkflowRules(query)
    rules.value = res.data.items
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
  Object.assign(createForm, { entity: entity.value, from_status: '', to_status: '', name: '' })
  createDlg.value = true
}
async function onCreate() {
  await createWorkflowRule(createForm)
  ElMessage.success('规则已创建')
  createDlg.value = false
  load()
  loadTransitions()
}
async function onToggle(row: any) {
  await updateWorkflowRule(row.id, { enabled: !row.enabled })
  load()
  loadTransitions()
}
async function onDelete(row: any) {
  await deleteWorkflowRule(row.id)
  ElMessage.success('已删除')
  load()
  loadTransitions()
}

onMounted(() => {
  load()
  loadTransitions()
})
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
.sec { margin: 8px 0 12px; }
.transitions { display: flex; flex-direction: column; gap: 8px; }
.from-row { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.arrow { color: #8c959f; }
.to-tag { margin: 0; }
.mt { margin-top: 16px; }
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
