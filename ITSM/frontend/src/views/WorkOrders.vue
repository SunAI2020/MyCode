<template>
  <div>
    <el-card>
      <div class="toolbar">
        <el-button type="primary" @click="openCreate">新增工单</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="no" label="工单号" width="150" />
        <el-table-column prop="type" label="类型" width="100" />
        <el-table-column prop="project" label="运维项目" width="130" />
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column prop="priority" label="优先级" width="80" />
        <el-table-column prop="progress" label="进度" width="80" />
        <el-table-column prop="current_cycle_no" label="周期" width="70" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDispatch(row)">派单</el-button>
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
              <el-input v-model.number="a.user_id" placeholder="用户ID" style="width: 130px" />
              <el-input v-model.number="a.workload_ratio" placeholder="比例%" style="width: 110px" />
              <el-button link type="danger" @click="dispatchForm.assignees.splice(i, 1)">删除</el-button>
            </div>
            <el-button link type="primary" @click="dispatchForm.assignees.push({ user_id: 1, workload_ratio: 100 })">+ 添加执行人</el-button>
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
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listWorkOrders, createWorkOrder, updateStatus, dispatch } from '@/api'

const rows = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, size: 10 })

const createDlg = ref(false)
const createForm = reactive({ receive_id: null as number | null, type: '客户工单', priority: '中' })

const dispatchDlg = ref(false)
const dispatchTarget = ref<number | null>(null)
const dispatchForm = reactive({ dispatch_type: '内部', assignees: [{ user_id: 1, workload_ratio: 100 }] as any[] })

const statusDlg = ref(false)
const statusTarget = ref<number | null>(null)
const statusForm = reactive({ status: '待派单' })

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
  dispatchForm.assignees = [{ user_id: 1, workload_ratio: 100 }]
  dispatchDlg.value = true
}
async function onDispatch() {
  await dispatch(dispatchTarget.value!, dispatchForm)
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

onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
.pager { margin-top: 14px; justify-content: flex-end; }
.assignee-list { width: 100%; }
.assignee-row { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; }
</style>
