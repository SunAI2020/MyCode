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

    <h3 class="sec-title">安全隐患整改</h3>
    <el-row :gutter="16">
      <el-col :span="6" v-for="c in issueCards" :key="c.label">
        <el-card shadow="hover">
          <div class="kpi">
            <div class="num">{{ c.value }}</div>
            <div class="label">{{ c.label }}</div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    <el-card shadow="hover">
      <div ref="issueChartRef" class="chart"></div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, ref } from 'vue'
import * as echarts from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getDashboard } from '@/api'

echarts.use([PieChart, LegendComponent, TooltipComponent, CanvasRenderer])

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

const issueCards = ref([
  { label: '隐患总数', value: 0 },
  { label: '待整改', value: 0 },
  { label: '整改中', value: 0 },
  { label: '已关闭', value: 0 },
])

const issueChartRef = ref<HTMLDivElement | null>(null)
let issueChart: echarts.ECharts | null = null

function pct(v: number) {
  return `${((v ?? 0) * 100).toFixed(1)}%`
}

function renderIssueChart(byStatus: Record<string, number>) {
  if (!issueChartRef.value) return
  if (!issueChart) issueChart = echarts.init(issueChartRef.value)
  const data = Object.entries(byStatus || {}).map(([name, value]) => ({ name, value }))
  issueChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [
      {
        name: '整改进度',
        type: 'pie',
        radius: ['40%', '65%'],
        center: ['50%', '45%'],
        label: { formatter: '{b}: {c}' },
        data: data.length ? data : [{ name: '暂无数据', value: 0 }],
      },
    ],
  })
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
  const issues = d.issues || {}
  issueCards.value[0].value = issues.total ?? 0
  issueCards.value[1].value = issues.by_status?.['待整改'] ?? 0
  issueCards.value[2].value = issues.by_status?.['整改中'] ?? 0
  issueCards.value[3].value = issues.by_status?.['已关闭'] ?? 0
  await nextTick()
  renderIssueChart(issues.by_status || {})
})
</script>

<style scoped>
.kpi { text-align: center; padding: 12px 0; }
.num { font-size: 32px; font-weight: 700; color: #0a4fc0; }
.label { color: #5b6470; margin-top: 4px; }
.sec-title { margin: 20px 0 12px; font-size: 15px; color: #303133; }
.chart { height: 300px; }
</style>
