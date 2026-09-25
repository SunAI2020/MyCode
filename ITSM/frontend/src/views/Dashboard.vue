<template>
  <div>
    <el-row :gutter="16">
      <el-col :span="8" v-for="c in cards" :key="c.label">
        <el-card shadow="hover">
          <div class="kpi">
            <div class="num">{{ c.value }}</div>
            <div class="label">{{ c.label }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { listCustomers, listContracts, listWorkOrders } from '@/api'

const cards = ref([
  { label: '客户', value: 0 },
  { label: '合同', value: 0 },
  { label: '工单', value: 0 },
])

onMounted(async () => {
  const [c, ct, w] = await Promise.all([
    listCustomers({ page: 1, size: 1 }),
    listContracts({ page: 1, size: 1 }),
    listWorkOrders({ page: 1, size: 1 }),
  ])
  cards.value[0].value = c.data.total
  cards.value[1].value = ct.data.total
  cards.value[2].value = w.data.total
})
</script>

<style scoped>
.kpi { text-align: center; padding: 12px 0; }
.num { font-size: 32px; font-weight: 700; color: #0a4fc0; }
.label { color: #5b6470; margin-top: 4px; }
</style>
