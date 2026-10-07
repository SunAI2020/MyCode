<template>
  <div>
    <el-card>
      <div class="toolbar">
        <el-input v-model="query.q" placeholder="关键词检索" clearable style="width: 220px" @keyup.enter="load" />
        <el-select v-model="query.category" placeholder="分类" clearable style="width: 160px" @change="load">
          <el-option v-for="c in ['漏洞', '整改方案', '故障手册', 'SOP', '驻场规范', '其他']" :key="c" :label="c" :value="c" />
        </el-select>
        <el-button type="primary" @click="load">查询</el-button>
        <el-button v-if="canWrite" @click="openCreate">新增条目</el-button>
        <el-button v-if="canDelete" type="warning" @click="onReindex">ES 回填</el-button>
      </div>
      <el-table :data="rows" v-loading="loading">
        <el-table-column prop="title" label="标题" min-width="220" />
        <el-table-column prop="category" label="分类" width="110" />
        <el-table-column prop="status" label="状态" width="90" />
        <el-table-column prop="view_count" label="浏览" width="80" />
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button v-if="canDelete" link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination class="pager" layout="total, prev, pager, next" :total="total" :page-size="query.size" :current-page="query.page" @current-change="onPage" />
    </el-card>

    <el-card class="ask-card">
      <template #header><b>RAG 智能问答</b>（基于已发布知识条目）</template>
      <el-input v-model="question" type="textarea" :rows="2" placeholder="输入运维问题，如：MySQL 主从延迟如何排查？" />
      <div class="ask-actions">
        <el-button type="primary" @click="onAsk">提问</el-button>
      </div>
      <div v-if="answer" class="answer-box">
        <div class="answer">{{ answer.answer }}</div>
        <div v-if="answer.sources?.length" class="sources">
          <div class="src-title">参考条目：</div>
          <div v-for="s in answer.sources" :key="s.id" class="src-item">{{ s.title }}</div>
        </div>
      </div>
    </el-card>

    <el-dialog v-model="createDlg" title="新增知识条目" width="520px">
      <el-form :model="createForm" label-width="70px">
        <el-form-item label="标题"><el-input v-model="createForm.title" /></el-form-item>
        <el-form-item label="分类">
          <el-select v-model="createForm.category" style="width: 100%">
            <el-option v-for="c in ['漏洞', '整改方案', '故障手册', 'SOP', '驻场规范', '其他']" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容"><el-input v-model="createForm.content" type="textarea" :rows="5" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="createDlg = false">取消</el-button><el-button type="primary" @click="onCreate">创建</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listArticles, createArticle, deleteArticle, askKb, reindexKb } from '@/api'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const canWrite = computed(() => auth.hasPermission('kb:write'))
const canDelete = computed(() => auth.hasPermission('kb:delete'))

const rows = ref<any[]>([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ q: '', category: '', page: 1, size: 10 })

const question = ref('')
const answer = ref<any>(null)

const createDlg = ref(false)
const createForm = reactive({ title: '', category: '故障手册', content: '' })

async function load() {
  loading.value = true
  try {
    const res = await listArticles(query)
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
  Object.assign(createForm, { title: '', category: '故障手册', content: '' })
  createDlg.value = true
}
async function onCreate() {
  await createArticle(createForm)
  ElMessage.success('已创建')
  createDlg.value = false
  load()
}
async function onDelete(row: any) {
  await deleteArticle(row.id)
  ElMessage.success('已删除')
  load()
}
async function onReindex() {
  const res = await reindexKb()
  ElMessage.success(`已回填 ${res.data.indexed} 条`)
}
async function onAsk() {
  if (!question.value.trim()) return
  const res = await askKb({ question: question.value })
  answer.value = res.data
}

onMounted(load)
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
.pager { margin-top: 14px; justify-content: flex-end; }
.ask-card { margin-top: 16px; }
.ask-actions { margin-top: 10px; }
.answer-box { margin-top: 12px; background: var(--app-panel); padding: 12px; border-radius: 6px; }
.answer { white-space: pre-wrap; }
.sources { margin-top: 8px; }
.src-title { font-weight: 600; margin-bottom: 4px; }
.src-item { color: var(--app-text-3); font-size: 13px; }
</style>
