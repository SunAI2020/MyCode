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

    <h3 class="sec-title">合规运营</h3>
    <el-row :gutter="16">
      <el-col :span="6" v-for="c in complianceCards" :key="c.label">
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
import { getDashboard } from '@/api'

const cards = ref([
  { label: '客户', value: 0 },
  { label: '合同', value: 0 },
  { label: '工单', value: 0 },
])

const complianceCards = ref([
  { label: '合规要求', value: 0 },
  { label: '覆盖率', value: '0.0%' },
  { label: '闭环率', value: '0.0%' },
  { label: '风险敞口', value: 0 },
])

function pct(v: number) {
  return `${((v ?? 0) * 100).toFixed(1)}%`
}

onMounted(async () => {
  const d = (await getDashboard()).data
  cards.value[0].value = d.customers ?? 0
  cards.value[1].value = d.contracts?.total ?? 0
  cards.value[2].value = d.work_orders?.total ?? 0
  const comp = d.compliance || {}
  complianceCards.value[0].value = comp.total ?? 0
  complianceCards.value[1].value = pct(comp.coverage_rate)
  complianceCards.value[2].value = pct(comp.closure_rate)
  complianceCards.value[3].value = comp.at_risk ?? 0
})
</script>

<style scoped>
.kpi { text-align: center; padding: 12px 0; }
.num { font-size: 32px; font-weight: 700; color: #0a4fc0; }
.label { color: #5b6470; margin-top: 4px; }
.sec-title { margin: 20px 0 12px; font-size: 15px; color: #303133; }
</style>
