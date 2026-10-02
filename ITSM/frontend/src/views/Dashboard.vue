<template>
  <div>
    <template v-for="(section, si) in sections" :key="section.title">
      <h3 class="sec-title">{{ section.title }}</h3>
      <el-row :gutter="16">
        <el-col :span="6" v-for="(c, ci) in section.charts" :key="c.title">
          <el-card shadow="hover" class="chart-card">
            <div class="chart-head">
              <span class="chart-title">{{ c.title }}</span>
              <span class="chart-num">{{ c.total }}</span>
            </div>
            <div :ref="(el) => setRef(el, si * 4 + ci)" class="chart"></div>
          </el-card>
        </el-col>
      </el-row>
    </template>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import * as echarts from 'echarts/core'
import { PieChart, BarChart } from 'echarts/charts'
import { LegendComponent, TooltipComponent, GridComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { getDashboard } from '@/api'

echarts.use([PieChart, BarChart, LegendComponent, TooltipComponent, GridComponent, CanvasRenderer])

type ChartCell = { title: string; total: number | string }

const sections = ref<{ title: string; charts: ChartCell[] }[]>([
  {
    title: '基本情况',
    charts: [
      { title: '客户（行业）', total: 0 },
      { title: '项目（状态）', total: 0 },
      { title: '工单（状态）', total: 0 },
      { title: '人员接单（近一年）', total: 0 },
    ],
  },
  {
    title: '执行情况',
    charts: [
      { title: '服务项目工单', total: 0 },
      { title: '安全隐患（CVE 分级）', total: 0 },
      { title: '整改情况', total: 0 },
      { title: '人员绩效', total: 0 },
    ],
  },
  {
    title: '合规运营',
    charts: [
      { title: '合规要求（出处×维度）', total: 0 },
      { title: '核验情况（单位）', total: 0 },
      { title: '合规覆盖率（单位）', total: 0 },
      { title: '风险敞口（单位）', total: 0 },
    ],
  },
])

// 12 个图表的定义：kind=pie/stacked，key=后端字段，pct=覆盖率（数字按平均%）
const CHART_DEFS = [
  { kind: 'pie', key: 'customers_by_industry' },
  { kind: 'pie', key: 'contracts_by_status' },
  { kind: 'pie', key: 'work_orders_by_status' },
  { kind: 'stacked', key: 'engineer_workload' },
  { kind: 'stacked', key: 'project_workload' },
  { kind: 'stacked', key: 'issue_by_type_level' },
  { kind: 'stacked', key: 'issue_by_type_status' },
  { kind: 'stacked', key: 'performance_by_engineer' },
  { kind: 'stacked', key: 'compliance_by_reg_source' },
  { kind: 'stacked', key: 'check_by_customer' },
  { kind: 'stacked', key: 'coverage_by_customer', pct: true },
  { kind: 'stacked', key: 'risk_by_customer' },
]

const chartRefs = ref<HTMLDivElement[]>([])
const charts: echarts.ECharts[] = []

function setRef(el: unknown, i: number) {
  if (el) chartRefs.value[i] = el as HTMLDivElement
}

function renderPie(i: number, data: { name: string; value: number }[]) {
  const el = chartRefs.value[i]
  if (!el) return
  if (!charts[i]) charts[i] = echarts.init(el)
  charts[i].setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 10 } },
    series: [
      {
        type: 'pie',
        radius: ['30%', '52%'], // 带缺口（环形）
        center: ['50%', '50%'],
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2, shadowBlur: 12, shadowColor: 'rgba(0,0,0,0.25)' },
        label: { formatter: '{b}：{c}', color: '#303133', fontSize: 11 },
        labelLine: { length: 6, length2: 4, smooth: true },
        data: data.length ? data : [{ name: '暂无数据', value: 0 }],
      },
    ],
  })
}

function renderStacked(i: number, d: { categories: string[]; series: { name: string; data: number[] }[] }, pct = false) {
  const el = chartRefs.value[i]
  if (!el) return
  if (!charts[i]) charts[i] = echarts.init(el)
  charts[i].setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { bottom: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 10 } },
    grid: { left: 8, right: 16, top: 8, bottom: 28, containLabel: true },
    xAxis: { type: 'value', axisLabel: { formatter: pct ? '{value}%' : '{value}' } },
    yAxis: { type: 'category', data: d.categories },
    series: d.series.map((s) => ({ name: s.name, type: 'bar', stack: 'total', barMaxWidth: 18, data: s.data })),
  })
}

function totalOfPie(data: { value: number }[]) {
  return data.reduce((s, d) => s + d.value, 0)
}

function totalOfStacked(d: { series: { data: number[] }[] }) {
  return d.series.reduce((s, ser) => s + (ser.data || []).reduce((a, v) => a + (v || 0), 0), 0)
}

function avgCoverage(d: { series: { data: number[] }[] }) {
  const vals = d.series.flatMap((s) => s.data || []).filter((v) => v > 0)
  if (!vals.length) return '0%'
  return `${(vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1)}%`
}

onMounted(async () => {
  const d = (await getDashboard()).data
  CHART_DEFS.forEach((def, i) => {
    const data = d[def.key] || (def.kind === 'pie' ? [] : { categories: [], series: [] })
    const row = Math.floor(i / 4)
    const col = i % 4
    if (def.kind === 'pie') {
      renderPie(i, data as { name: string; value: number }[])
      sections.value[row].charts[col].total = totalOfPie(data as { value: number }[])
    } else {
      const stacked = data as { categories: string[]; series: { name: string; data: number[] }[] }
      renderStacked(i, stacked, def.pct)
      sections.value[row].charts[col].total = def.pct ? avgCoverage(stacked) : totalOfStacked(stacked)
    }
  })
})
</script>

<style scoped>
.sec-title { margin: 12px 0 8px; font-size: 14px; color: #303133; border-left: 4px solid #0a3d91; padding-left: 8px; }
.chart-card { margin-bottom: 8px; }
.chart-head { display: flex; justify-content: space-between; align-items: center; padding: 2px 4px 4px; }
.chart-title { font-size: 13px; color: #303133; font-weight: 600; }
.chart-num { font-size: 18px; font-weight: 700; color: #0a3d91; }
.chart { height: 200px; }
</style>
