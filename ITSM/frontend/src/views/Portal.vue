<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="8" v-for="c in overview.contracts" :key="c.id">
        <el-card>
          <div class="stat-title">合同</div>
          <div class="stat-name">{{ c.name }}</div>
          <div class="stat-sub">{{ c.status }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="mt">
      <template #header><b>工单进度</b></template>
      <div class="chips">
        <el-tag v-for="(cnt, status) in overview.work_order_status_counts" :key="status" class="chip">
          {{ status }}：{{ cnt }}
        </el-tag>
        <span v-if="!Object.keys(overview.work_order_status_counts || {}).length" class="muted">暂无工单</span>
      </div>
    </el-card>

    <el-card class="mt">
      <template #header><b>最近工单</b></template>
      <el-table :data="overview.recent_work_orders || []">
        <el-table-column prop="no" label="工单号" width="150" />
        <el-table-column prop="type" label="类型" width="110" />
        <el-table-column prop="status" label="状态" width="100" />
        <el-table-column prop="progress" label="进度" width="80" />
        <el-table-column prop="description" label="描述" min-width="200" />
      </el-table>
    </el-card>

    <el-card class="mt">
      <template #header><b>自助报障</b></template>
      <el-form :model="ticketForm" label-width="90px" style="max-width: 560px">
        <el-form-item label="描述"><el-input v-model="ticketForm.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="ticketForm.priority" style="width: 100%">
            <el-option v-for="p in ['高', '中', '低']" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="联系人"><el-input v-model="ticketForm.contact" /></el-form-item>
        <el-form-item><el-button type="primary" @click="onSubmitTicket">提交报障</el-button></el-form-item>
      </el-form>
    </el-card>

    <el-card class="mt">
      <template #header><b>RAG 自助问答</b></template>
      <el-input v-model="question" type="textarea" :rows="2" placeholder="输入问题" />
      <div class="ask-actions"><el-button type="primary" @click="onAsk">提问</el-button></div>
      <div v-if="answer" class="answer-box">
        <div class="answer">{{ answer.answer }}</div>
        <div v-for="s in answer.sources || []" :key="s.id" class="src-item">{{ s.title }}</div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { portalOverview, createTicket, askKb } from '@/api'

const overview = reactive<any>({ contracts: [], work_order_status_counts: {}, recent_work_orders: [], recent_deliveries: [] })
const ticketForm = reactive({ description: '', priority: '中', contact: '' })
const question = ref('')
const answer = ref<any>(null)

async function load() {
  const res = await portalOverview()
  Object.assign(overview, res.data)
}
async function onSubmitTicket() {
  if (!ticketForm.description.trim()) return ElMessage.warning('请填写描述')
  await createTicket(ticketForm)
  ElMessage.success('报障已提交')
  ticketForm.description = ''
  load()
}
async function onAsk() {
  if (!question.value.trim()) return
  const res = await askKb({ question: question.value })
  answer.value = res.data
}

onMounted(load)
</script>

<style scoped>
.mt { margin-top: 16px; }
.stat-title { color: #57606a; font-size: 13px; }
.stat-name { font-size: 18px; font-weight: 600; margin: 4px 0; }
.stat-sub { color: #57606a; font-size: 13px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip { margin: 0; }
.muted { color: #8c959f; font-size: 13px; }
.ask-actions { margin-top: 10px; }
.answer-box { margin-top: 12px; background: #f6f8fa; padding: 12px; border-radius: 6px; }
.answer { white-space: pre-wrap; }
.src-item { color: #57606a; font-size: 13px; margin-top: 4px; }
</style>
