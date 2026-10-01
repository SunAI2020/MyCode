<template>
  <div>
    <template v-for="(section, si) in sections" :key="section.title">
      <h3 class="sec-title">{{ section.title }}</h3>
      <el-row :gutter="16">
        <el-col :span="6" v-for="(c, ci) in section.charts" :key="c">
          <el-card shadow="hover" class="chart-card">
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

const sections = [
  { title: '基本情况', charts: ['客户', '项目', '工单', '人员'] },
  { title: '执行情况', charts: ['服务项目', '安全隐患', '整改情况', '人员绩效'] },
  { title: '合规运营', charts: ['合规要求', '核验情况', '合规覆盖率', '风险敞口'] },
]

const chartRefs = ref<HTMLDivElement[]>([])
const charts: echarts.ECharts[] = []

function setRef(el: unknown, i: number) {
  if (el) chartRefs.value[i] = el as HTMLDivElement
}

function renderPie(i: number, title: string, data: { name: string; value: number }[]) {
  const el = chartRefs.value[i]
  if (!el) return
  if (!charts[i]) charts[i] = echarts.init(el)
  charts[i].setOption({
    title: { text: title, left: 'center', top: 4, textStyle: { fontSize: 13 } },
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: ['45%', '70%'], // 带缺口（环形）
        center: ['50%', '48%'],
        roseType: 'area', // 面积玫瑰，模拟立体
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2, shadowBlur: 12, shadowColor: 'rgba(0,0,0,0.25)' },
        label: { formatter: '{b}: {c}' },
        data: data.length ? data : [{ name: '暂无数据', value: 0 }],
      },
    ],
  })
}

function renderStacked(i: number, title: string, d: { categories: string[]; series: { name: string; data: number[] }[] }, pct = false) {
  const el = chartRefs.value[i]
  if (!el) return
  if (!charts[i]) charts[i] = echarts.init(el)
  charts[i].setOption({
    title: { text: title, left: 'center', top: 4, textStyle: { fontSize: 13 } },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { bottom: 0 },
    grid: { left: 8, right: 16, top: 32, bottom: 46, containLabel: true },
    xAxis: { type: 'value', axisLabel: { formatter: pct ? '{value}%' : '{value}' } },
    yAxis: { type: 'category', data: d.categories },
    series: d.series.map((s) => ({ name: s.name, type: 'bar', stack: 'total', barMaxWidth: 18, data: s.data })),
  })
}

onMounted(async () => {
  const d = (await getDashboard()).data
  renderPie(0, '客户（行业）', d.customers_by_industry || [])
  renderPie(1, '项目（状态）', d.contracts_by_status || [])
  renderPie(2, '工单（状态）', d.work_orders_by_status || [])
  renderStacked(3, '人员接单（近一年）', d.engineer_workload || { categories: [], series: [] })
  renderStacked(4, '服务项目工单', d.project_workload || { categories: [], series: [] })
  renderStacked(5, '安全隐患（CVE 分级）', d.issue_by_type_level || { categories: [], series: [] })
  renderStacked(6, '整改情况', d.issue_by_type_status || { categories: [], series: [] })
  renderStacked(7, '人员绩效', d.performance_by_engineer || { categories: [], series: [] })
  renderStacked(8, '合规要求（出处×维度）', d.compliance_by_reg_source || { categories: [], series: [] })
  renderStacked(9, '核验情况（单位）', d.check_by_customer || { categories: [], series: [] })
  renderStacked(10, '合规覆盖率（单位）', d.coverage_by_customer || { categories: [], series: [] }, true)
  renderStacked(11, '风险敞口（单位）', d.risk_by_customer || { categories: [], series: [] })
})
</script>

<style scoped>
.sec-title { margin: 20px 0 12px; font-size: 15px; color: #303133; border-left: 4px solid #0a3d91; padding-left: 8px; }
.chart-card { margin-bottom: 8px; }
.chart { height: 300px; }
</style>
