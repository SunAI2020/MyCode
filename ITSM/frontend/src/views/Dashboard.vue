<template>
  <div class="dash" v-loading="loading">
    <!-- 关键指标 -->
    <section class="kpis">
      <div class="kpi" v-for="k in kpis" :key="k.label">
        <div class="lbl"><span class="st" :style="{ background: k.dot }"></span>{{ k.label }}</div>
        <div class="big num">{{ k.value }}<em>{{ k.unit }}</em></div>
        <div class="sub">{{ k.sub }}</div>
      </div>
    </section>

    <!-- 预警条 -->
    <section class="alert">
      <span class="t"><span class="pulse"></span>待处理预警 {{ warningsTotal }} 项</span>
      <span class="item">派单 <b class="num">{{ stats.warnings.dispatch }}</b></span>
      <span class="item">验收 <b class="num">{{ stats.warnings.acceptance }}</b></span>
      <span class="item">工期 <b class="num">{{ stats.warnings.schedule }}</b></span>
      <span class="item">人员 <b class="num">{{ stats.warnings.personnel }}</b></span>
    </section>

    <!-- 工单状态分布 + 风险管控 -->
    <div class="grid2">
      <div class="panel">
        <h3>工单状态分布 <span class="cap">单位 / 单</span></h3>
        <div class="strips">
          <div class="strip" v-for="s in woStatusList" :key="s.name" :class="s.cls">
            <span class="val num">{{ s.value }}</span>
            <div class="col" :style="{ height: s.pct + '%' }"></div>
            <span class="name">{{ s.name }}</span>
          </div>
        </div>
        <div class="legend">
          <span><i style="background: var(--app-bad)"></i>处理中</span>
          <span><i style="background: var(--app-warn)"></i>待流转</span>
          <span><i style="background: var(--app-ok)"></i>已闭环</span>
        </div>
      </div>

      <div class="panel">
        <h3>风险管控 · 隐患分级 <span class="cap">共 {{ issueTotal }} 项</span></h3>
        <div class="bars">
          <div class="bar-row" v-for="lv in issueLevelList" :key="lv.name">
            <div class="bar-lbl"><span>{{ lv.name }}</span><b class="num" :style="{ color: lv.color }">{{ lv.value }}</b></div>
            <div class="bar-track"><div class="bar-fill" :style="{ width: lv.pct + '%', background: lv.color }"></div></div>
          </div>
        </div>
      </div>
    </div>

    <!-- 合规运营 -->
    <div class="panel">
      <h3>合规运营 <span class="cap">全局</span></h3>
      <div class="compliance">
        <div class="c-kpi"><div class="num c-num">{{ stats.compliance.total }}</div><div class="c-lbl">合规要求</div></div>
        <div class="c-kpi"><div class="num c-num" style="color: var(--app-ok)">{{ stats.compliance.coverageRate }}%</div><div class="c-lbl">核验覆盖率</div></div>
        <div class="c-kpi"><div class="num c-num" style="color: var(--app-accent)">{{ stats.compliance.closureRate }}%</div><div class="c-lbl">闭环率</div></div>
        <div class="c-kpi"><div class="num c-num" style="color: var(--app-warn)">{{ stats.compliance.atRisk }}</div><div class="c-lbl">风险敞口</div></div>
      </div>
    </div>

    <!-- 最近工单 -->
    <div class="panel">
      <h3>最近工单 <span class="cap">实时</span></h3>
      <el-table :data="stats.recent" size="small" style="width: 100%">
        <el-table-column prop="no" label="工单号" width="150">
          <template #default="{ row }"><span class="num no">{{ row.no }}</span></template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="90" />
        <el-table-column label="优先级" width="76">
          <template #default="{ row }"><span class="pri" :class="row.priority">{{ row.priority }}</span></template>
        </el-table-column>
        <el-table-column label="事项" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">{{ row.description || row.project || '—' }}</template>
        </el-table-column>
        <el-table-column label="执行人" width="140">
          <template #default="{ row }">{{ (row.assignee_names || []).join('、') || '—' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="96">
          <template #default="{ row }"><span class="st-pill" :class="statusCls(row.status)">{{ row.status }}</span></template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { getDashboard, listWorkOrders } from '@/api'

const WORK_STATUS = ['待派单', '待执行', '执行中', '待验收', '待结单', '已结单', '已取消', '已关闭']
const LEVELS = ['严重', '高危', '中危', '低危', '信息']
const LEVEL_COLOR: Record<string, string> = {
  严重: 'var(--app-bad)',
  高危: 'var(--app-warn)',
  中危: 'var(--app-accent)',
  低危: 'var(--app-text-3)',
  信息: 'var(--app-ok)',
}

const loading = ref(true)

const stats = reactive({
  customers: 0,
  contractsTotal: 0,
  contractsRunning: 0,
  workOrdersTotal: 0,
  woStatus: {} as Record<string, number>,
  issueLevel: {} as Record<string, number>,
  issueTotal: 0,
  compliance: { total: 0, coverageRate: 0, closureRate: 0, atRisk: 0 },
  warnings: { dispatch: 0, acceptance: 0, schedule: 0, personnel: 0 },
  recent: [] as any[],
})

const warningsTotal = computed(
  () => stats.warnings.dispatch + stats.warnings.acceptance + stats.warnings.schedule + stats.warnings.personnel,
)
const workOrdersActive = computed(() =>
  ['待派单', '待执行', '执行中', '待验收', '待结单'].reduce((s, k) => s + (stats.woStatus[k] || 0), 0),
)

const kpis = computed(() => [
  { label: '在管客户', value: stats.customers, unit: '家', dot: 'var(--app-accent)', sub: '全局客户台账' },
  { label: '执行中项目', value: stats.contractsRunning, unit: '个', dot: 'var(--app-ok)', sub: `共 ${stats.contractsTotal} 个项目` },
  { label: '工单总数', value: stats.workOrdersTotal, unit: '单', dot: 'var(--app-warn)', sub: `进行中 ${workOrdersActive.value}` },
  { label: '待处理预警', value: warningsTotal.value, unit: '项', dot: 'var(--app-bad)', sub: '需优先处置' },
])

const woStatusList = computed(() => {
  const values = WORK_STATUS.map((s) => stats.woStatus[s] || 0)
  const max = Math.max(...values, 1)
  return WORK_STATUS.map((s, i) => ({
    name: s,
    value: values[i],
    pct: Math.round((values[i] / max) * 100),
    cls: stripCls(s),
  }))
})

const issueLevelList = computed(() => {
  const total = LEVELS.reduce((s, l) => s + (stats.issueLevel[l] || 0), 0) || 1
  return LEVELS.map((l) => {
    const v = stats.issueLevel[l] || 0
    return { name: l, value: v, pct: Math.round((v / total) * 100), color: LEVEL_COLOR[l] }
  })
})
const issueTotal = computed(() => stats.issueTotal)

function stripCls(s: string) {
  if (s === '执行中') return 'hot'
  if (['待执行', '待验收', '待结单'].includes(s)) return 'warm'
  if (['已结单', '已关闭'].includes(s)) return 'ok'
  return ''
}

function statusCls(s: string) {
  if (['已结单', '已关闭'].includes(s)) return 'done'
  if (s === '执行中') return 'run'
  if (['待执行', '待验收', '待结单'].includes(s)) return 'wait'
  return 'idle'
}

function sumSeries(s: { series?: { data?: number[] }[] } | undefined) {
  return (s?.series || []).reduce((a, x) => a + (x.data || []).reduce((b, v) => b + (v || 0), 0), 0)
}

onMounted(async () => {
  try {
    const d = (await getDashboard()).data
    stats.customers = d.customers || 0
    stats.contractsTotal = d.contracts?.total || 0
    stats.contractsRunning = d.contracts?.by_status?.['执行中'] || 0
    stats.workOrdersTotal = d.work_orders?.total || 0
    stats.woStatus = d.work_orders?.by_status || {}
    stats.issueLevel = d.issues?.by_level || {}
    stats.issueTotal = d.issues?.total || 0
    const c = d.compliance || {}
    stats.compliance = {
      total: c.total || 0,
      coverageRate: Math.round((c.coverage_rate || 0) * 100),
      closureRate: Math.round((c.closure_rate || 0) * 100),
      atRisk: c.at_risk || 0,
    }
    stats.warnings = {
      dispatch: sumSeries(d.dispatch_warning_by_customer),
      acceptance: sumSeries(d.acceptance_warning_by_customer),
      schedule: sumSeries(d.schedule_warning_by_customer),
      personnel: sumSeries(d.personnel_forecast),
    }
    const wo = (await listWorkOrders({ page: 1, size: 6 })).data
    stats.recent = wo.items || []
  } catch {
    // 接口错误已由拦截器提示；此处仅保证 loading 结束
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.dash { display: flex; flex-direction: column; gap: 14px; }

/* —— 关键指标 —— */
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.kpi {
  position: relative; padding: 16px 18px 14px; border-radius: 10px;
  background: linear-gradient(180deg, var(--app-panel), var(--app-panel-2));
  border: 1px solid var(--app-line); overflow: hidden;
}
.kpi::after {
  content: ''; position: absolute; left: 0; right: 0; top: 0; height: 1px;
  background: linear-gradient(90deg, transparent, var(--app-accent), transparent); opacity: .45;
}
.kpi .lbl { font-size: 12px; color: var(--app-text-3); display: flex; align-items: center; gap: 7px; }
.kpi .st { width: 6px; height: 6px; border-radius: 50%; }
.kpi .big { font-size: 32px; font-weight: 650; line-height: 1.15; margin: 9px 0 4px; letter-spacing: -.5px; color: var(--app-text); }
.kpi .big em { font-style: normal; font-size: 14px; color: var(--app-text-3); margin-left: 5px; font-weight: 400; }
.kpi .sub { font-size: 11px; color: var(--app-text-4); }

/* —— 预警条 —— */
.alert {
  display: flex; align-items: center; gap: 22px; padding: 12px 16px;
  border: 1px solid rgba(245, 183, 75, .28); border-radius: 10px;
  background: linear-gradient(90deg, rgba(245, 183, 75, .10), rgba(245, 183, 75, .02));
  font-size: 13px; color: var(--app-text-2);
}
.alert .t { color: var(--app-warn); font-weight: 650; display: flex; align-items: center; gap: 8px; font-size: 12.5px; }
.alert .pulse {
  width: 8px; height: 8px; border-radius: 50%; background: var(--app-warn);
  box-shadow: 0 0 0 0 rgba(245, 183, 75, .6); animation: pl 1.8s infinite;
}
@keyframes pl {
  0% { box-shadow: 0 0 0 0 rgba(245, 183, 75, .5); }
  70% { box-shadow: 0 0 0 8px rgba(245, 183, 75, 0); }
  100% { box-shadow: 0 0 0 0 rgba(245, 183, 75, 0); }
}
.alert .item { display: flex; align-items: baseline; gap: 6px; }
.alert .item b { color: var(--app-warn); font-size: 15px; font-weight: 700; }

/* —— 两栏面板 —— */
.grid2 { display: grid; grid-template-columns: 1.15fr .85fr; gap: 14px; }
.panel {
  background: linear-gradient(180deg, var(--app-panel), var(--app-panel-2));
  border: 1px solid var(--app-line); border-radius: 10px; padding: 15px 16px 16px;
}
.panel h3 {
  font-size: 12px; font-weight: 650; color: var(--app-text-2); letter-spacing: .3px;
  display: flex; align-items: center; gap: 8px; margin-bottom: 13px;
}
.panel h3 .cap { font-size: 10px; color: var(--app-text-4); font-weight: 500; letter-spacing: .5px; margin-left: auto; }

/* 工单状态分布 */
.strips { display: flex; gap: 10px; height: 132px; align-items: flex-end; padding-top: 8px; }
.strip { flex: 1; display: flex; flex-direction: column; align-items: center; gap: 7px; }
.strip .col { width: 100%; border-radius: 6px 6px 2px 2px; background: linear-gradient(180deg, #26334c, #1c2940); min-height: 3px; }
.strip .val { font-size: 12px; color: var(--app-text-2); font-weight: 600; }
.strip .name { font-size: 10.5px; color: var(--app-text-4); white-space: nowrap; }
.strip.hot .col { background: linear-gradient(180deg, var(--app-bad), #6d2233); }
.strip.warm .col { background: linear-gradient(180deg, var(--app-warn), #6d4a1a); }
.strip.ok .col { background: linear-gradient(180deg, var(--app-ok), #12645a); }
.legend { display: flex; gap: 16px; margin-top: 12px; font-size: 11px; color: var(--app-text-4); }
.legend i { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 5px; }

/* 风险分级 */
.bars { display: flex; flex-direction: column; gap: 13px; }
.bar-lbl { display: flex; justify-content: space-between; font-size: 12px; color: var(--app-text-2); }
.bar-lbl b { font-size: 12px; }
.bar-track { height: 6px; background: var(--app-fill, #1c2940); border-radius: 3px; margin-top: 5px; overflow: hidden; }
.bar-fill { height: 100%; border-radius: 3px; }

/* 合规运营 */
.compliance { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }
.c-kpi { text-align: center; padding: 6px 0; }
.c-num { font-size: 28px; font-weight: 650; letter-spacing: -.5px; color: var(--app-text); }
.c-lbl { font-size: 11.5px; color: var(--app-text-3); margin-top: 3px; }

/* 最近工单 */
.no { font-size: 12px; color: var(--app-text-3); }
.pri { font-size: 11px; font-weight: 700; }
.pri.高 { color: var(--app-bad); }
.pri.中 { color: var(--app-warn); }
.pri.低 { color: var(--app-text-3); }
.st-pill { display: inline-flex; align-items: center; gap: 6px; font-size: 11px; padding: 3px 9px; border-radius: 6px; }
.st-pill::before { content: ''; width: 6px; height: 6px; border-radius: 50%; }
.st-pill.run { color: #9fd8ff; background: rgba(53, 200, 240, .12); }
.st-pill.run::before { background: var(--app-accent); }
.st-pill.wait { color: #ffd9a0; background: rgba(245, 183, 75, .12); }
.st-pill.wait::before { background: var(--app-warn); }
.st-pill.done { color: #a9f0e6; background: rgba(45, 212, 191, .12); }
.st-pill.done::before { background: var(--app-ok); }
.st-pill.idle { color: var(--app-text-3); background: rgba(139, 150, 171, .12); }
.st-pill.idle::before { background: var(--app-text-3); }

@media (max-width: 760px) {
  .kpis { grid-template-columns: repeat(2, 1fr); }
  .grid2 { grid-template-columns: 1fr; }
  .compliance { grid-template-columns: repeat(2, 1fr); }
  .alert { flex-wrap: wrap; gap: 12px 18px; }
}
</style>
