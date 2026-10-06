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
            <div :ref="(el) => setRef(el, c._idx)" class="chart"></div>
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

type ChartCell = {
  title: string
  key: string
  kind: 'pie' | 'stacked'
  pct?: boolean
  wrapLabel?: boolean
  total: number | string
  _idx?: number
}

const sections = ref<{ title: string; charts: ChartCell[] }[]>([
  {
    title: '基本情况',
    charts: [
      { title: '客户（行业）', key: 'customers_by_industry', kind: 'pie', total: 0 },
      { title: '项目（状态）', key: 'contracts_by_status', kind: 'pie', total: 0 },
      { title: '工单（状态）', key: 'work_orders_by_status', kind: 'pie', total: 0 },
      { title: '人员接单（近一年）', key: 'engineer_workload', kind: 'stacked', total: 0 },
    ],
  },
  {
    title: '执行情况',
    charts: [
      { title: '派单预警', key: 'dispatch_warning_by_customer', kind: 'stacked', wrapLabel: true, total: 0 },
      { title: '验收预警', key: 'acceptance_warning_by_customer', kind: 'stacked', wrapLabel: true, total: 0 },
      { title: '工期预警', key: 'schedule_warning_by_customer', kind: 'stacked', wrapLabel: true, total: 0 },
      { title: '人员预警', key: 'personnel_forecast', kind: 'stacked', wrapLabel: true, total: 0 },
    ],
  },
  {
    title: '风险管控',
    charts: [
      { title: '安全隐患（CVE 分级）', key: 'issue_by_type_level', kind: 'stacked', total: 0 },
      { title: '整改情况', key: 'issue_by_type_status', kind: 'stacked', total: 0 },
    ],
  },
  {
    title: '合规运营',
    charts: [
      { title: '合规要求（出处×维度）', key: 'compliance_by_reg_source', kind: 'stacked', total: 0 },
      { title: '核验情况（单位）', key: 'check_by_customer', kind: 'stacked', wrapLabel: true, total: 0 },
      { title: '合规覆盖率（单位）', key: 'coverage_by_customer', kind: 'stacked', pct: true, wrapLabel: true, total: 0 },
      { title: '风险敞口（单位）', key: 'risk_by_customer', kind: 'stacked', wrapLabel: true, total: 0 },
    ],
  },
])

// 给每个图表单元格分配跨行累计的全局序号，供 echarts 容器 ref 定位
let _seq = 0
for (const s of sections.value) {
  for (const c of s.charts) c._idx = _seq++
}

const chartRefs = ref<HTMLDivElement[]>([])
const charts: echarts.ECharts[] = []

function setRef(el: unknown, i: number | undefined) {
  if (el && typeof i === 'number') chartRefs.value[i] = el as HTMLDivElement
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

function renderStacked(i: number, d: { categories: string[]; series: { name: string; data: number[] }[] }, pct = false, wrapLabel = false) {
  const el = chartRefs.value[i]
  if (!el) return
  if (!charts[i]) charts[i] = echarts.init(el)
  const yAxis: Record<string, any> = { type: 'category', data: d.categories }
  if (wrapLabel) {
    yAxis.axisLabel = {
      formatter: (val: string) => {
        const s = String(val || '')
        if (s.length <= 6) return s
        const half = Math.ceil(s.length / 2)
        return `${s.slice(0, half)}\n${s.slice(half)}`
      },
    }
  }
  charts[i].setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { bottom: 0, itemWidth: 10, itemHeight: 10, textStyle: { fontSize: 10 } },
    grid: { left: 8, right: 16, top: 8, bottom: 28, containLabel: true },
    xAxis: { type: 'value', axisLabel: { formatter: pct ? '{value}%' : '{value}' } },
    yAxis,
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
  for (const s of sections.value) {
    for (const c of s.charts) {
      const i = c._idx as number
      const data = d[c.key] || (c.kind === 'pie' ? [] : { categories: [], series: [] })
      if (c.kind === 'pie') {
        renderPie(i, data as { name: string; value: number }[])
        c.total = totalOfPie(data as { value: number }[])
      } else {
        const stacked = data as { categories: string[]; series: { name: string; data: number[] }[] }
        renderStacked(i, stacked, c.pct, c.wrapLabel)
        c.total = c.pct ? avgCoverage(stacked) : totalOfStacked(stacked)
      }
    }
  }
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
