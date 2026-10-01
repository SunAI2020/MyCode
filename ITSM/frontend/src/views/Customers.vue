<template>
  <div>
    <el-card>
      <div class="toolbar">
        <el-input v-model="query.name" placeholder="按名称搜索" style="width: 220px" clearable @keyup.enter="load" />
        <el-button v-if="canWrite" type="primary" @click="openCreate">新增客户</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="name" label="名称" />
        <el-table-column prop="level" label="级别" width="90" />
        <el-table-column prop="industry" label="行业" />
        <el-table-column prop="contact" label="联系人" />
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button v-if="canWrite" link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canDelete" link type="danger" @click="onDelete(row)">删除</el-button>
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

    <el-dialog v-model="dlg" :title="editId ? '编辑客户' : '新增客户'" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="级别">
          <el-select v-model="form.level" style="width: 100%">
            <el-option v-for="l in ['金牌', '银牌', '普通']" :key="l" :label="l" :value="l" />
          </el-select>
        </el-form-item>
        <el-form-item label="行业"><el-input v-model="form.industry" /></el-form-item>
        <el-form-item label="联系人"><el-input v-model="form.contact" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listCustomers, createCustomer, updateCustomer, deleteCustomer } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const canWrite = computed(() => auth.hasPermission('customer:write'))
const canDelete = computed(() => auth.hasPermission('customer:delete'))

const rows = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ page: 1, size: 10, name: '' })
const dlg = ref(false)
const editId = ref<number | null>(null)
const form = reactive({ name: '', level: '普通', industry: '', contact: '' })

async function load() {
  loading.value = true
  try {
    const res = await listCustomers(query)
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
  editId.value = null
  Object.assign(form, { name: '', level: '普通', industry: '', contact: '' })
  dlg.value = true
}
function openEdit(row: any) {
  editId.value = row.id
  Object.assign(form, { name: row.name, level: row.level, industry: row.industry, contact: row.contact })
  dlg.value = true
}
async function save() {
  if (editId.value) {
    await updateCustomer(editId.value, form)
  } else {
    await createCustomer(form)
  }
  ElMessage.success('已保存')
  dlg.value = false
  load()
}
async function onDelete(row: any) {
  await ElMessageBox.confirm(`确认删除客户「${row.name}」？`, '提示', { type: 'warning' })
  await deleteCustomer(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
.pager { margin-top: 14px; justify-content: flex-end; }
</style>
