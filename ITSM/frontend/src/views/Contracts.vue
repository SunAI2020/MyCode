<template>
  <div>
    <input ref="fileInput" type="file" accept=".pdf,.docx,.jpg,.jpeg,.png" style="display: none" @change="onFilePicked" />
    <el-tabs v-model="tab">
      <el-tab-pane label="项目" name="contract">
        <el-card>
          <div class="toolbar">
            <el-button v-if="canWrite" type="primary" @click="openContract()">新增项目</el-button>
            <el-button v-if="canWrite" type="primary" plain @click="pickFile()">导入合同</el-button>
          </div>
          <div v-loading="loading">
            <div class="lane" v-for="col in contractColumns" :key="col.key">
              <div class="lane-head">
                <span class="lane-title">{{ col.title }}</span>
                <span class="lane-count">{{ col.list.length }}</span>
              </div>
              <el-table :data="col.list">
                <el-table-column prop="id" label="ID" width="60" />
                <el-table-column prop="name" label="项目名称" />
                <el-table-column prop="no" label="合同编号" />
                <el-table-column prop="type" label="类型" width="110" />
                <el-table-column prop="amount" label="金额" width="110" />
                <el-table-column prop="status" label="状态" width="90" />
                <el-table-column label="操作" width="220">
                  <template #default="{ row }">
                    <el-button link :type="row.archive_count ? 'success' : 'info'" @click="onViewContract(row)">查看合同</el-button>
                    <el-button v-if="canWrite" link type="primary" @click="openContract(row)">编辑</el-button>
                    <el-button v-if="canDelete" link type="danger" @click="onDeleteContract(row)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
            </div>
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="业务系统" name="ci">
        <el-card>
          <div class="toolbar">
            <el-select v-model="ciStatusFilter" placeholder="全部状态" clearable style="width: 150px">
              <el-option v-for="l in ['在用', '下线', '测试']" :key="l" :label="l" :value="l" />
            </el-select>
            <el-button v-if="canWrite" type="primary" @click="openCi()">新增业务系统</el-button>
          </div>
          <el-table :data="filteredCis" v-loading="loading">
            <el-table-column prop="id" label="ID" width="60" />
            <el-table-column label="项目名称" sortable :sort-by="contractNameOf">
              <template #default="{ row }">{{ contractNameOf(row) }}</template>
            </el-table-column>
            <el-table-column prop="name" label="业务系统" sortable />
            <el-table-column prop="type" label="类型" width="110" />
            <el-table-column prop="ip" label="IP" width="140" />
            <el-table-column prop="lifecycle" label="状态" width="90" sortable>
              <template #default="{ row }">
                <el-tag :type="lifecycleTag(row.lifecycle)" size="small">{{ row.lifecycle }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column v-if="canWrite || canDelete" label="操作" width="150">
              <template #default="{ row }">
                <el-button v-if="canWrite" link type="primary" @click="openCi(row)">编辑</el-button>
                <el-button v-if="canDelete" link type="danger" @click="onDeleteCi(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="服务类别" name="item">
        <el-card>
          <div class="toolbar">
            <el-select v-model="itemFilter.ci_id" placeholder="选择业务系统" clearable style="width: 240px" @change="loadItems">
              <el-option v-for="c in cis" :key="c.id" :label="c.name" :value="c.id" />
            </el-select>
            <el-button v-if="canWrite" type="primary" @click="openItem()">新增服务子项</el-button>
          </div>
          <el-table :data="groupedItems" v-loading="loading">
            <el-table-column label="客户名称">
              <template #default="{ row }">{{ customerNameOf(row) }}</template>
            </el-table-column>
            <el-table-column label="项目名称">
              <template #default="{ row }">{{ contractNameOf(row) }}</template>
            </el-table-column>
            <el-table-column label="业务系统">
              <template #default="{ row }">
                <template v-if="row._ciCount > 1">{{ row._ciCount }}个业务系统</template>
                <template v-else>{{ row._ciIds.length ? ciNameById(row._ciIds[0]) : '//' }}</template>
              </template>
            </el-table-column>
            <el-table-column prop="project" label="服务类别" />
            <el-table-column label="服务频率" width="110">
              <template #default="{ row }">{{ row.frequency }}次/{{ row.unit }}</template>
            </el-table-column>
            <el-table-column prop="price" label="价格" width="110" />
            <el-table-column v-if="canWrite || canDelete" label="操作" width="210">
              <template #default="{ row }">
                <el-button v-if="canWrite" link type="primary" @click="openItem(row)">编辑</el-button>
                <el-button v-if="canWrite && row._workOrderCount === 0" link type="success" class="gen-cycle-btn" @click="openGenWorkOrder(row)">生成工单</el-button>
                <el-button v-if="canWrite && row._workOrderCount > 0" link type="danger" @click="openModifyWorkOrder(row)">修改工单</el-button>
                <el-button v-if="canDelete" link type="danger" @click="onDeleteItem(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <!-- 项目弹窗（新建/编辑，字段与导入识别表一致） -->
    <el-dialog v-model="contractDlg" :title="contractEditId ? '编辑项目' : '新增项目'" width="720px" top="4vh">
      <el-form :model="contractForm" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="24">
            <el-form-item label="项目名称"><el-input v-model="contractForm.name" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户名称">
              <el-select v-model="contractForm.customer_id" style="width: 100%">
                <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="合同编号"><el-input v-model="contractForm.no" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="类型">
              <el-select v-model="contractForm.type" style="width: 100%" @change="onTypeChange">
                <el-option v-for="t in contractTypes" :key="t" :label="t" :value="t" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="金额"><el-input v-model.number="contractForm.amount" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="开始日期"><el-date-picker v-model="contractForm.start_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="结束日期"><el-date-picker v-model="contractForm.end_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="签署日期"><el-date-picker v-model="contractForm.sign_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="是否驻场服务"><el-switch v-model="contractForm.has_onsite" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="状态">
              <el-select v-model="contractForm.status" style="width: 100%">
                <el-option v-for="s in ['洽谈中', '执行中', '已到期', '已续约']" :key="s" :label="s" :value="s" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="服务地点"><el-input v-model="contractForm.service_location" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="人员要求"><el-input v-model="contractForm.staff_requirement" type="textarea" :rows="2" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="验收标准"><el-input v-model="contractForm.accept_standard" type="textarea" :rows="2" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="交付文档"><el-input v-model="contractForm.delivery_docs" type="textarea" :rows="2" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="验收报告格式"><el-input v-model="contractForm.acceptance_report_format" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer><el-button @click="contractDlg = false">取消</el-button><el-button type="primary" @click="saveContract">保存</el-button></template>
    </el-dialog>

    <!-- 新建项目类型弹窗 -->
    <el-dialog v-model="newTypeDlg" title="新建项目类型" width="420px">
      <el-form label-width="80px">
        <el-form-item label="类型名称"><el-input v-model="newTypeName" placeholder="请输入新的项目类型" @keyup.enter="confirmNewType" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="newTypeDlg = false">取消</el-button>
        <el-button type="primary" @click="confirmNewType">确定</el-button>
      </template>
    </el-dialog>

    <!-- 服务类别弹窗 -->
    <el-dialog v-model="itemDlg" :title="itemEditId ? '编辑服务类别' : '新增服务类别'" width="520px">
      <el-form :model="itemForm" label-width="110px">
        <el-form-item label="项目名称">
          <el-select v-model="itemForm.contract_id" style="width: 100%" :disabled="!!itemEditId" @change="onItemContractChange">
            <el-option v-for="c in contracts" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="业务系统" label-position="top" class="ci-form-item">
          <el-checkbox-group v-model="itemForm.ci_ids" class="ci-checkbox-list">
            <el-checkbox v-for="c in projectCis" :key="c.id" :value="c.id">{{ c.name }}</el-checkbox>
          </el-checkbox-group>
          <div v-if="!itemForm.ci_ids.length" class="ci-empty">未选择 → 记作「//」（不关联具体系统）</div>
        </el-form-item>
        <el-form-item label="服务类别">
          <el-select v-model="itemForm.project" filterable allow-create default-first-option style="width: 100%" placeholder="选择或输入服务类别">
            <el-option v-for="p in PROJECTS" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="频率"><el-input-number v-model="itemForm.frequency" :min="1" /></el-form-item>
        <el-form-item label="单位">
          <el-select v-model="itemForm.unit" filterable allow-create default-first-option style="width: 100%">
            <el-option v-for="u in ['天', '周', '月', '季度', '半年', '年', '不定期']" :key="u" :label="u" :value="u" />
          </el-select>
        </el-form-item>
        <el-form-item label="价格"><el-input v-model.number="itemForm.price" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="itemDlg = false">取消</el-button><el-button type="primary" @click="saveItem">保存</el-button></template>
    </el-dialog>

    <!-- 业务系统弹窗 -->
    <el-dialog v-model="ciDlg" :title="ciEditId ? '编辑业务系统' : '新增业务系统'" width="520px">
      <el-form :model="ciForm" label-width="90px">
        <el-form-item label="项目">
          <el-select v-model="ciForm.contract_id" style="width: 100%">
            <el-option v-for="c in contracts" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="名称"><el-input v-model="ciForm.name" /></el-form-item>
        <el-form-item label="类型">
          <el-autocomplete v-model="ciForm.type" :fetch-suggestions="queryCiTypes" :trigger-on-focus="true" placeholder="选择或输入类型" style="width: 100%" />
        </el-form-item>
        <el-form-item label="IP"><el-input v-model="ciForm.ip" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="ciForm.lifecycle" style="width: 100%">
            <el-option v-for="l in ['在用', '下线', '测试']" :key="l" :label="l" :value="l" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="ciDlg = false">取消</el-button><el-button type="primary" @click="saveCi">保存</el-button></template>
    </el-dialog>

    <!-- 导入存档弹窗 -->
    <!-- 识别中提示 -->
    <el-dialog v-model="recognizing" width="320px" :show-close="false" :close-on-click-modal="false" :close-on-press-escape="false" append-to-body>
      <div v-loading="true" element-loading-text="正在识别中...，请您耐心等待！" element-loading-background="rgba(255,255,255,0.9)" style="min-height: 100px;"></div>
    </el-dialog>

    <el-dialog v-model="importDlg" title="合同原件导入 - 识别结果" width="840px" top="4vh">
      <el-alert v-if="importOriginalName" :title="`原件：${importOriginalName}`" type="info" :closable="false" style="margin-bottom: 12px" />
      <el-form :model="importForm" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="24">
            <el-form-item label="所属项目">
              <el-select v-model="importTargetProjectId" filterable allow-create default-first-option style="width: 100%" @change="onTargetProjectChange">
                <el-option :value="null" label="新建项目" />
                <el-option v-for="c in contracts" :key="c.id" :label="c.name" :value="c.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="项目名称"><el-input v-model="importForm.name" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="客户名称"><el-input v-model="importForm.customer_name" placeholder="无法自动识别时可手动填写" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="合同编号"><el-input v-model="importForm.contract_no" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="签署日期"><el-date-picker v-model="importForm.sign_date" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="合同金额"><el-input v-model.number="importForm.amount" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="是否驻场服务"><el-switch v-model="importForm.has_onsite" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="服务期限"><el-input v-model="importForm.service_period" placeholder="如 2026-01-01 至 2026-12-31" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="服务地点"><el-input v-model="importForm.service_location" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="人员要求"><el-input v-model="importForm.staff_requirement" type="textarea" :rows="2" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="验收标准"><el-input v-model="importForm.accept_standard" type="textarea" :rows="2" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="交付文档"><el-input v-model="importForm.delivery_docs" type="textarea" :rows="2" /></el-form-item>
          </el-col>
          <el-col :span="24">
            <el-form-item label="验收报告格式"><el-input v-model="importForm.acceptance_report_format" /></el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <el-divider content-position="left">业务系统</el-divider>
      <div class="obj-list">
        <div v-for="(o, i) in importForm.service_objects" :key="i" class="obj-row">
          <el-select v-model="importForm.service_objects[i]" filterable allow-create default-first-option placeholder="选择或输入业务系统" style="width: 300px">
            <el-option v-for="c in cis" :key="c.id" :label="c.name" :value="c.name" />
          </el-select>
          <el-button link type="danger" @click="importForm.service_objects.splice(i, 1)">删除</el-button>
        </div>
        <el-button link type="primary" @click="importForm.service_objects.push('')">+ 添加业务系统</el-button>
      </div>

      <el-divider content-position="left">服务类别</el-divider>
      <el-table :data="importForm.service_items" size="small" border>
        <el-table-column label="业务系统" width="150">
          <template #default="{ row }">
            <el-select v-model="row.service_object" clearable placeholder="默认首个" size="small">
              <el-option v-for="o in importForm.service_objects" :key="o" :label="o" :value="o" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="服务类别" min-width="160">
          <template #default="{ row }">
            <el-select v-model="row.project" filterable allow-create size="small" style="width: 100%">
              <el-option v-for="p in PROJECTS" :key="p" :label="p" :value="p" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="频次" width="110">
          <template #default="{ row }"><el-input-number v-model="row.frequency" :min="1" size="small" /></template>
        </el-table-column>
        <el-table-column label="单位" width="110">
          <template #default="{ row }">
            <el-select v-model="row.unit" filterable allow-create default-first-option size="small">
              <el-option v-for="u in ['天', '周', '月', '季度', '半年', '年', '不定期']" :key="u" :label="u" :value="u" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="价格" width="120">
          <template #default="{ row }"><el-input v-model.number="row.price" size="small" /></template>
        </el-table-column>
        <el-table-column label="操作" width="70">
          <template #default="{ $index }"><el-button link type="danger" @click="importForm.service_items.splice($index, 1)">删除</el-button></template>
        </el-table-column>
      </el-table>
      <el-button link type="primary" style="margin-top: 8px" @click="importForm.service_items.push({ project: '', frequency: 1, unit: '月', price: null, service_object: null })">+ 添加服务类别</el-button>

      <el-alert v-if="importMineruExpired" title="mineru的token已过期！请重新获取！" type="error" :closable="false" style="margin-top: 12px" />
      <el-alert v-if="importNoText" title="未能从文件中提取文字（可能是扫描件/图片），请手动录入或换用文字版 PDF" type="error" :closable="false" style="margin-top: 12px" />
      <template v-if="importTextPreview">
        <el-alert title="已用规则识别（未配置大模型），请核对补充；下方为原文片段" type="warning" :closable="false" style="margin-top: 12px" />
        <div class="text-preview">{{ importTextPreview }}</div>
      </template>

      <template #footer>
        <el-button @click="importDlg = false">取消</el-button>
        <el-button type="primary" :loading="importLoading" @click="onConfirmImport">确认导入</el-button>
      </template>
    </el-dialog>

    <!-- 合同原件列表弹窗（一个项目可归档多份） -->
    <el-dialog v-model="archiveDlg" :title="`合同原件 · ${archiveProjectName}`" width="560px">
      <el-table :data="archives" size="small">
        <el-table-column prop="original_filename" label="文件名" />
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ (row.file_size / 1024).toFixed(1) }} KB</template>
        </el-table-column>
        <el-table-column label="操作" width="110">
          <template #default="{ row }">
            <el-button link type="primary" @click="onDownloadArchive(row)">查看 / 下载</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <!-- 生成工单弹窗 -->
    <el-dialog v-model="genWoDlg" title="生成工单" width="560px">
      <el-form :model="genWoForm" label-width="100px">
        <el-form-item label="客户名称"><el-input :model-value="genWoCustomerName" disabled /></el-form-item>
        <el-form-item label="项目名称"><el-input :model-value="genWoProjectName" disabled /></el-form-item>
        <el-form-item label="业务系统">
          <el-select v-model="genWoForm.member_id" style="width: 100%" @change="onGenMemberChange">
            <el-option v-for="m in genWoMembers" :key="m.id" :label="m.ci_id ? ciNameById(m.ci_id) : '//'" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务类别"><el-input :model-value="genWoProject" disabled /></el-form-item>
        <el-form-item label="工单类型">
          <el-select v-model="genWoForm.type" style="width: 100%">
            <el-option v-for="t in ['客户工单', '驻场工单', '内部任务', '外包工单']" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="genWoForm.priority" style="width: 100%">
            <el-option v-for="p in ['高', '中', '低']" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务开始时间"><el-date-picker v-model="genWoForm.service_start" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="服务结束时间"><el-date-picker v-model="genWoForm.service_end" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="同时生成工期"><el-checkbox v-model="genWoForm.generate_cycle" /></el-form-item>
        <el-form-item label="派单类型">
          <el-select v-model="genWoForm.dispatch_type" style="width: 100%">
            <el-option label="内部" value="内部" />
            <el-option label="外包" value="外包" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行人">
          <el-select v-model="genWoForm.assignee_id" filterable placeholder="选择执行人" style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="同时派单"><el-checkbox v-model="genWoForm.dispatch" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="genWoDlg = false">取消</el-button><el-button type="primary" @click="saveGenWorkOrder">生成</el-button></template>
    </el-dialog>

    <!-- 修改工单弹窗 -->
    <el-dialog v-model="editWoDlg" title="修改工单" width="500px">
      <el-form :model="editWoForm" label-width="90px">
        <el-form-item label="类型">
          <el-select v-model="editWoForm.type" style="width: 100%">
            <el-option v-for="t in ['客户工单', '驻场工单', '内部任务', '外包工单']" :key="t" :label="t" :value="t" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="editWoForm.priority" style="width: 100%">
            <el-option v-for="p in ['高', '中', '低']" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="服务开始时间"><el-date-picker v-model="editWoForm.service_start" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="服务结束时间"><el-date-picker v-model="editWoForm.service_end" type="date" value-format="YYYY-MM-DD" style="width: 100%" /></el-form-item>
        <el-form-item label="派单类型">
          <el-select v-model="editWoForm.dispatch_type" style="width: 100%">
            <el-option label="内部" value="内部" />
            <el-option label="外包" value="外包" />
          </el-select>
        </el-form-item>
        <el-form-item label="执行人">
          <el-select v-model="editWoForm.assignee_id" clearable filterable placeholder="选择执行人（选择后重新派单）" style="width: 100%">
            <el-option v-for="u in users" :key="u.id" :label="u.name" :value="u.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述"><el-input v-model="editWoForm.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="editWoDlg = false">取消</el-button><el-button type="primary" @click="saveEditWorkOrder">保存</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  listContracts, createContract, updateContract, deleteContract,
  listItems, createItem, updateItem, deleteItem,
  listCis, createCi, updateCi, deleteCi, listCustomers,
  uploadContractArchive, confirmContractArchive, listContractArchives, downloadContractArchive,
  listDicts, createDict,
  createWorkOrder, listUsers, previewAggregateCycles, listWorkOrders, editWorkOrder,
} from '@/api'
import { useAuthStore } from '@/stores/auth'

const tab = ref('contract')
const loading = ref(false)
const contracts = ref<any[]>([])
const customers = ref<any[]>([])
const items = ref<any[]>([])
const cis = ref<any[]>([])
const ciStatusFilter = ref('')
const filteredCis = computed(() => ciStatusFilter.value ? cis.value.filter((c: any) => c.lifecycle === ciStatusFilter.value) : cis.value)
function lifecycleTag(s: string) {
  return s === '在用' ? 'success' : s === '测试' ? 'warning' : 'info'
}
const itemFilter = reactive({ ci_id: null as number | null })

// 写/删权限按权限点裁剪（与后端 contract:write / contract:delete 对齐）
const auth = useAuthStore()
const canWrite = computed(() => auth.hasPermission('contract:write'))
const canDelete = computed(() => auth.hasPermission('contract:delete'))

const contractDlg = ref(false)
const contractEditId = ref<number | null>(null)
const contractForm = reactive({
  customer_id: 1, name: '', type: '安全服务', no: '', amount: null as number | null,
  start_date: '', end_date: '', status: '洽谈中',
  sign_date: '', has_onsite: false, service_location: '',
  staff_requirement: '', accept_standard: '', delivery_docs: '', acceptance_report_format: '',
})

// 项目类型（合同类型）：选择「其他」时弹窗新建自定义类型
const CONTRACT_TYPES = ['安全服务', '安全运维', '设备升级', '购买设备', '机房改造', '其他']
const contractTypes = ref<string[]>(CONTRACT_TYPES)
const newTypeDlg = ref(false)
const newTypeName = ref('')

function onTypeChange(val: string) {
  if (val === '其他') {
    newTypeName.value = ''
    newTypeDlg.value = true
  }
}
async function confirmNewType() {
  const name = newTypeName.value.trim()
  if (!name) return ElMessage.warning('请输入类型名称')
  if (contractTypes.value.includes(name)) return ElMessage.warning('该类型已存在')
  try {
    await createDict({ category: 'contract_type', name })
    contractTypes.value.splice(contractTypes.value.length - 1, 0, name) // 插到「其他」之前
    contractForm.type = name
    newTypeDlg.value = false
    ElMessage.success('已新建项目类型')
  } catch { /* 后端拒绝由响应拦截器统一提示 */ }
}

async function loadContractTypes() {
  try {
    const names = (await listDicts('contract_type')).data
    if (names && names.length) contractTypes.value = names
  } catch { /* 字典加载失败则用默认值 */ }
}

const itemDlg = ref(false)
const itemEditId = ref<number | null>(null)
const itemEditGroup = ref<any[]>([])  // 编辑时保存组内原始条目（聚合组）
const itemForm = reactive({
  contract_id: null as number | null,
  ci_ids: [] as number[],
  project: '', frequency: 1, unit: '月', price: null as number | null,
})
// 服务类别枚举（与后端 seed 的 project 字典一致）
const PROJECTS = ['漏洞扫描', '渗透测试', '应急演练', '安全加固', '安全培训', '代码审计', '基线核查', '安全巡检', '安全评估', '应急处置', '重保值守', '攻防演练', '安全防护', '设备巡检', '等保测评', '故障排查']

const ciDlg = ref(false)
const ciEditId = ref<number | null>(null)
const ciForm = reactive({ contract_id: 1, name: '', type: '业务系统', ip: '', lifecycle: '在用' })
const CI_TYPES = ['业务系统', '网络设备', '服务器', '机房', '数据库']
function queryCiTypes(_query: string, cb: (results: any[]) => void) {
  cb(CI_TYPES.map((t) => ({ value: t })))
}

// ---- 生成工单 ----
const genWoDlg = ref(false)
const genWoMembers = ref<any[]>([])
const users = ref<any[]>([])
const genWoForm = reactive({
  member_id: null as number | null,
  type: '客户工单', priority: '中',
  service_start: '', service_end: '', cycle_no: null as number | null,
  generate_cycle: true, dispatch: true, dispatch_type: '内部', assignee_id: null as number | null,
})
const genWoCustomerName = computed(() => { const m = genWoMembers.value[0]; return m ? customerNameOf(m) : '' })
const genWoProjectName = computed(() => { const m = genWoMembers.value[0]; return m ? contractNameOf(m) : '' })
const genWoProject = computed(() => genWoMembers.value[0]?.project ?? '')
const editWoDlg = ref(false)
const editWoId = ref<number | null>(null)
const editWoForm = reactive({ type: '客户工单', priority: '中', description: '', service_start: '', service_end: '', dispatch_type: '内部', assignee_id: null as number | null })

// ---- 合同原件导入 ----
const fileInput = ref<HTMLInputElement | null>(null)
const importDlg = ref(false)
const importLoading = ref(false)
const recognizing = ref(false) // 上传识别中（显示「正在识别中」对话框）
const importArchiveId = ref<number | null>(null)
const importOriginalName = ref('')
const importTextPreview = ref('')
const importNoText = ref(false)
const importMineruExpired = ref(false)
const importTargetProjectId = ref<number | string | null>(null) // null = 新建项目；string = 直接输入的新项目名（经 onTargetProjectChange 归一）
const archiveDlg = ref(false)
const archiveProjectName = ref('')
const archives = ref<any[]>([])
const importForm = reactive({
  name: '',
  customer_id: null as number | null,
  customer_name: '',
  contract_no: '',
  sign_date: '',
  amount: null as number | null,
  has_onsite: false,
  service_period: '',
  service_location: '',
  staff_requirement: '',
  accept_standard: '',
  delivery_docs: '',
  acceptance_report_format: '',
  service_objects: [] as string[],
  service_items: [] as any[],
})

function pickFile() {
  fileInput.value?.click()
}

function resetImportForm() {
  importTargetProjectId.value = null
  Object.assign(importForm, {
    name: '', customer_id: null, customer_name: '', contract_no: '', sign_date: '',
    amount: null, has_onsite: false, service_period: '', service_location: '', staff_requirement: '',
    accept_standard: '', delivery_docs: '', acceptance_report_format: '',
    service_objects: [], service_items: [],
  })
}

function onTargetProjectChange(val: number | string | null) {
  // allow-create 直接输入新项目名（string）→ 视为「新建项目」，名称同步到项目名称字段
  if (typeof val === 'string' && val.trim()) {
    importForm.name = val.trim()
    importTargetProjectId.value = null
  }
}

async function onFilePicked(e: Event) {
  const input = e.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  recognizing.value = true
  importLoading.value = true
  try {
    const res = await uploadContractArchive(file)
    const d = res.data
    importArchiveId.value = d.archive_id
    importOriginalName.value = d.original_filename
    importTextPreview.value = d.text_preview || ''
    importNoText.value = d.has_text === false
    importMineruExpired.value = !!d.mineru_expired
    const ex = d.extracted || {}
    resetImportForm()
    importForm.name = ex.name || ''
    importForm.customer_name = ex.customer_name || ''
    importForm.contract_no = ex.contract_no || ''
    importForm.sign_date = ex.sign_date || ''
    importForm.amount = ex.amount ?? null
    importForm.has_onsite = !!ex.has_onsite
    importForm.service_period = ex.service_period || ''
    importForm.service_location = ex.service_location || ''
    importForm.staff_requirement = ex.staff_requirement || ''
    importForm.accept_standard = ex.accept_standard || ''
    importForm.delivery_docs = ex.delivery_docs || ''
    importForm.acceptance_report_format = ex.acceptance_report_format || ''
    importForm.service_objects = ex.service_objects || []
    importForm.service_items = (ex.service_items || []).map((it: any) => ({
      project: it.project, frequency: it.frequency ?? 1, unit: it.unit || '月',
      price: it.price ?? null, service_object: it.service_object || null,
    }))
    importDlg.value = true
  } finally {
    importLoading.value = false
    recognizing.value = false
    input.value = ''
  }
}

async function onConfirmImport() {
  if (!importArchiveId.value) return
  importLoading.value = true
  try {
    await confirmContractArchive(importArchiveId.value, {
      contract_id: importTargetProjectId.value,
      name: importForm.name,
      customer_id: importForm.customer_id,
      customer_name: importForm.customer_name,
      contract_no: importForm.contract_no,
      sign_date: importForm.sign_date || null,
      amount: importForm.amount,
      has_onsite: importForm.has_onsite,
      service_period: importForm.service_period || null,
      service_location: importForm.service_location || null,
      staff_requirement: importForm.staff_requirement || null,
      accept_standard: importForm.accept_standard || null,
      delivery_docs: importForm.delivery_docs || null,
      acceptance_report_format: importForm.acceptance_report_format || null,
      service_objects: importForm.service_objects.filter((o: string) => o && o.trim()),
      service_items: importForm.service_items.filter((it: any) => it.project && it.project.trim()),
    })
    ElMessage.success(importTargetProjectId.value ? '导入完成，已挂到所选项目' : '导入完成，已生成项目与业务系统/项目')
    importDlg.value = false
    loadContracts()
    loadCis()
    loadItems()
  } finally {
    importLoading.value = false
  }
}

async function loadContracts() {
  loading.value = true
  try {
    contracts.value = (await listContracts({ page: 1, size: 100 })).data.items
  } finally {
    loading.value = false
  }
}
async function loadCustomers() {
  customers.value = (await listCustomers({ page: 1, size: 100 })).data.items
}
async function loadItems() {
  const params: any = { page: 1, size: 100 }
  if (itemFilter.ci_id) params.ci_id = itemFilter.ci_id
  items.value = (await listItems(params)).data.items
}
async function loadCis() {
  cis.value = (await listCis({ page: 1, size: 100 })).data.items
}

// 列表父级名称映射
const contractMap = computed(() => new Map(contracts.value.map((c) => [c.id, c])))
const customerMap = computed(() => new Map(customers.value.map((c) => [c.id, c])))
const ciMap = computed(() => new Map(cis.value.map((c) => [c.id, c])))
function contractNameOf(row: any) {
  return contractMap.value.get(row.contract_id)?.name ?? ''
}
function customerNameOf(row: any) {
  const c = contractMap.value.get(row.contract_id)
  return c ? (customerMap.value.get(c.customer_id)?.name ?? '') : ''
}
function ciNameOf(row: any) {
  return row.ci_id ? (ciMap.value.get(row.ci_id)?.name ?? '') : '//'
}
function ciNameById(id: number) {
  return ciMap.value.get(id)?.name ?? ''
}

// 项目三栏看板：执行中 / 洽谈中 / 已过期（已续约归入执行中）
const executingContracts = computed(() => contracts.value.filter((c: any) => c.status === '执行中' || c.status === '已续约'))
const negotiatingContracts = computed(() => contracts.value.filter((c: any) => c.status === '洽谈中'))
const expiredContracts = computed(() => contracts.value.filter((c: any) => c.status === '已到期'))
const contractColumns = computed(() => [
  { key: 'executing', title: '执行中', list: executingContracts.value },
  { key: 'negotiating', title: '洽谈中', list: negotiatingContracts.value },
  { key: 'expired', title: '已过期', list: expiredContracts.value },
])

// 服务类别列表聚合：同项目 + 同服务类别 + 同配置（频率/单位/价格）的多业务系统合并为一条
const groupedItems = computed(() => {
  const map = new Map<string, any>()
  for (const it of items.value) {
    const key = `${it.contract_id}|${it.project}|${it.frequency}|${it.unit}|${it.price ?? ''}`
    if (!map.has(key)) {
      map.set(key, { contract_id: it.contract_id, project: it.project, frequency: it.frequency, unit: it.unit, price: it.price, _members: [], _ciIds: [] })
    }
    const g = map.get(key)
    g._members.push(it)
    if (it.ci_id) g._ciIds.push(it.ci_id)
  }
  return [...map.values()].map((g) => {
    g._ciIds = [...new Set(g._ciIds)]
    g._ciCount = g._ciIds.length
    g._workOrderCount = g._members.reduce((s: number, m: any) => s + (m.work_order_count || 0), 0)
    return g
  })
})

// 合同
function openContract(row?: any) {
  if (row) {
    contractEditId.value = row.id
    Object.assign(contractForm, {
      customer_id: row.customer_id, name: row.name, type: row.type, no: row.no, amount: row.amount,
      start_date: row.start_date || '', end_date: row.end_date || '', status: row.status,
      sign_date: row.sign_date || '', has_onsite: !!row.has_onsite, service_location: row.service_location || '',
      staff_requirement: row.staff_requirement || '', accept_standard: row.accept_standard || '',
      delivery_docs: row.delivery_docs || '', acceptance_report_format: row.acceptance_report_format || '',
    })
  } else {
    contractEditId.value = null
    Object.assign(contractForm, {
      customer_id: 1, name: '', type: '安全服务', no: '', amount: null,
      start_date: '', end_date: '', status: '洽谈中',
      sign_date: '', has_onsite: false, service_location: '',
      staff_requirement: '', accept_standard: '', delivery_docs: '', acceptance_report_format: '',
    })
  }
  contractDlg.value = true
}
async function saveContract() {
  const payload = {
    ...contractForm,
    start_date: contractForm.start_date || null,
    end_date: contractForm.end_date || null,
    sign_date: contractForm.sign_date || null,
  }
  if (contractEditId.value) await updateContract(contractEditId.value, payload)
  else await createContract(payload)
  ElMessage.success('已保存')
  contractDlg.value = false
  loadContracts()
}
async function onDeleteContract(row: any) {
  await ElMessageBox.confirm(`确认删除项目「${row.name}」？`, '提示', { type: 'warning' })
  await deleteContract(row.id)
  loadContracts()
}
async function onViewContract(row: any) {
  try {
    const list = await listContractArchives({ page: 1, size: 100, contract_id: row.id })
    archives.value = list.data.items
    if (!archives.value.length) {
      ElMessage.warning('该项目尚未导入合同原件')
      return
    }
    archiveProjectName.value = row.name
    archiveDlg.value = true
  } catch {
    ElMessage.error('加载合同原件失败')
  }
}
async function onDownloadArchive(a: any) {
  try {
    const blob = await downloadContractArchive(a.id)
    const url = URL.createObjectURL(blob)
    window.open(url, '_blank')
  } catch {
    ElMessage.error('下载原件失败')
  }
}

// 服务类别
const projectCis = computed(() => cis.value.filter((c) => c.contract_id === itemForm.contract_id))
function onItemContractChange() {
  // 新增时切换项目 → 业务系统默认全选该项目全部业务系统
  if (!itemEditId.value) itemForm.ci_ids = projectCis.value.map((c) => c.id)
}
function openItem(row?: any) {
  if (row) {
    const members = row._members ?? [row]
    itemEditId.value = members[0]?.id ?? row.id
    itemEditGroup.value = members
    Object.assign(itemForm, {
      contract_id: row.contract_id ?? null,
      ci_ids: [...(row._ciIds ?? (row.ci_id ? [row.ci_id] : []))],
      project: row.project, frequency: row.frequency, unit: row.unit, price: row.price,
    })
  } else {
    itemEditId.value = null
    itemEditGroup.value = []
    Object.assign(itemForm, { contract_id: contracts.value[0]?.id ?? null, ci_ids: [], project: '', frequency: 1, unit: '月', price: null })
    onItemContractChange()
  }
  itemDlg.value = true
}
async function saveItem() {
  if (!itemForm.project || !itemForm.project.trim()) {
    ElMessage.warning('请填写服务类别')
    return
  }
  const base = { project: itemForm.project, frequency: itemForm.frequency, unit: itemForm.unit, price: itemForm.price }
  const newCiIds = itemForm.ci_ids || []
  if (itemEditGroup.value.length) {
    // 编辑组：diff 同步 —— 删被取消的业务系统条目、更新保留条目、为新增业务系统建条目（保留原 id，不破坏已生成工期/工单关联）
    const oldCiIds = itemEditGroup.value.map((m: any) => m.ci_id)
    for (const m of itemEditGroup.value) {
      if (m.ci_id == null) {
        if (newCiIds.length) await deleteItem(m.id)          // 原「//」条目，现已选具体业务系统 → 删
        else await updateItem(m.id, { ...base })             // 仍不关联业务系统 → 保留并更新字段
      } else if (newCiIds.includes(m.ci_id)) {
        await updateItem(m.id, { ...base })                  // 保留：仅更新共享字段，ci_id 不变
      } else {
        await deleteItem(m.id)                               // 被取消勾选 → 删
      }
    }
    for (const ciId of newCiIds) {
      if (!oldCiIds.includes(ciId)) await createItem({ ci_id: ciId, contract_id: itemForm.contract_id, ...base })
    }
    if (!newCiIds.length && !oldCiIds.includes(null)) {
      await createItem({ ci_id: null, contract_id: itemForm.contract_id, ...base })  // 边界：清空后补一条「//」
    }
  } else {
    // 新增：重复校验（同一客户 + 同一业务系统 + 同一服务类别）
    const dup = items.value.find((it: any) =>
      it.contract_id === itemForm.contract_id &&
      it.project === itemForm.project &&
      it.ci_id != null &&
      newCiIds.includes(it.ci_id)
    )
    if (dup) {
      ElMessageBox.alert(
        `${customerNameOf(dup)}客户的${ciNameById(dup.ci_id)}业务系统，已经存在${itemForm.project}服务类别，请勿重复提交！`,
        '重复提交',
        { type: 'warning' }
      )
      return
    }
    // 新增：勾选 N 个 → 批量生成 N 条；全不选 → 1 条（不关联具体系统，记作「//」）
    if (!newCiIds.length) {
      await createItem({ ci_id: null, contract_id: itemForm.contract_id, ...base })
    } else {
      for (const ciId of newCiIds) await createItem({ ci_id: ciId, contract_id: itemForm.contract_id, ...base })
    }
  }
  ElMessage.success('已保存')
  itemDlg.value = false
  itemEditGroup.value = []
  loadItems()
}
async function openGenWorkOrder(row: any) {
  const members = row._members ?? [row]
  genWoMembers.value = members
  const first = members[0]
  Object.assign(genWoForm, {
    member_id: first?.id ?? null,
    type: '客户工单', priority: '中',
    service_start: '', service_end: '', cycle_no: null,
    generate_cycle: true, dispatch: true, dispatch_type: '内部', assignee_id: null,
  })
  genWoDlg.value = true
  if (!users.value.length) {
    try { users.value = (await listUsers()).data } catch { /* 无人员权限时执行人下拉为空 */ }
  }
  await onGenMemberChange()
}
async function onGenMemberChange() {
  genWoForm.service_start = ''
  genWoForm.service_end = ''
  genWoForm.cycle_no = null
  const m = genWoMembers.value.find((x: any) => x.id === genWoForm.member_id)
  if (!m) return
  // 默认取项目的开始/结束日期
  const contract = contractMap.value.get(m.contract_id)
  if (contract) {
    genWoForm.service_start = contract.start_date || ''
    genWoForm.service_end = contract.end_date || ''
  }
  // 若可算出下一期工期，用工期起止精化
  try {
    const res = await previewAggregateCycles({ contract_item_ids: [m.id] })
    const cycles = res.data.cycles[m.id] || []
    const next = cycles.find((c: any) => !c.has_work_order)
    if (next) {
      genWoForm.service_start = next.service_start
      genWoForm.service_end = next.service_end
      genWoForm.cycle_no = next.cycle_no
    }
  } catch { /* 自动填充失败可手动填写 */ }
}
async function saveGenWorkOrder() {
  const m = genWoMembers.value.find((x: any) => x.id === genWoForm.member_id)
  if (!m) return ElMessage.warning('请选择业务系统')
  if (!genWoForm.service_start || !genWoForm.service_end) return ElMessage.warning('请填写工单开始日期和结束日期！')
  if (genWoForm.dispatch && !genWoForm.assignee_id) {
    try {
      await ElMessageBox.confirm('未选择执行人！', '提示', { confirmButtonText: '确定', cancelButtonText: '重选', type: 'warning' })
    } catch {
      return
    }
    genWoForm.dispatch = false
  }
  const res = await createWorkOrder({
    type: genWoForm.type,
    priority: genWoForm.priority,
    contract_id: m.contract_id,
    contract_item_id: m.id,
    ci_id: m.ci_id,
    project: m.project,
    service_start: genWoForm.service_start || null,
    service_end: genWoForm.service_end || null,
    cycle_no: genWoForm.cycle_no,
    generate_cycle: genWoForm.generate_cycle,
    dispatch: genWoForm.dispatch,
    dispatch_type: genWoForm.dispatch_type,
    assignee_id: genWoForm.dispatch ? genWoForm.assignee_id : null,
  })
  if (res.data?.duplicate) {
    ElMessageBox.alert(res.data.message, '重复生成', { type: 'warning' })
    return
  }
  ElMessage.success('工单已生成')
  genWoDlg.value = false
  loadItems()
}
async function openModifyWorkOrder(row: any) {
  const m = (row._members ?? [row])[0]
  if (!m) return
  const res = await listWorkOrders({ page: 1, size: 100, contract_item_id: m.id })
  const wo = res.data.items?.[0]
  if (!wo) return ElMessage.warning('未找到对应工单')
  editWoId.value = wo.id
  Object.assign(editWoForm, { type: wo.type, priority: wo.priority, description: wo.description, service_start: '', service_end: '', dispatch_type: '内部', assignee_id: null })
  if (!users.value.length) {
    try { users.value = (await listUsers()).data } catch {}
  }
  try {
    const p = await previewAggregateCycles({ contract_item_ids: [m.id] })
    const cycles = p.data.cycles[m.id] || []
    const c = cycles.find((x: any) => x.cycle_no === wo.current_cycle_no)
    if (c) {
      editWoForm.service_start = c.service_start
      editWoForm.service_end = c.service_end
    }
  } catch {}
  editWoDlg.value = true
}
async function saveEditWorkOrder() {
  await editWorkOrder(editWoId.value!, {
    type: editWoForm.type,
    priority: editWoForm.priority,
    description: editWoForm.description,
    service_start: editWoForm.service_start || null,
    service_end: editWoForm.service_end || null,
    dispatch: editWoForm.assignee_id != null,
    dispatch_type: editWoForm.dispatch_type,
    assignee_id: editWoForm.assignee_id,
  })
  ElMessage.success('已保存')
  editWoDlg.value = false
  loadItems()
}
async function onDeleteItem(row: any) {
  const members = row._members ?? [row]
  const n = members.length
  await ElMessageBox.confirm(n > 1 ? `确认删除该服务类别（${n}个业务系统）？` : '确认删除该服务类别？', '提示', { type: 'warning' })
  for (const m of members) await deleteItem(m.id)
  loadItems()
}

// 业务系统
function openCi(row?: any) {
  if (row) {
    ciEditId.value = row.id
    Object.assign(ciForm, { contract_id: row.contract_id, name: row.name, type: row.type, ip: row.ip, lifecycle: row.lifecycle })
  } else {
    ciEditId.value = null
    Object.assign(ciForm, { contract_id: 1, name: '', type: '业务系统', ip: '', lifecycle: '在用' })
  }
  ciDlg.value = true
}
async function saveCi() {
  if (ciEditId.value) await updateCi(ciEditId.value, ciForm)
  else await createCi(ciForm)
  ElMessage.success('已保存')
  ciDlg.value = false
  loadCis()
}
async function onDeleteCi(row: any) {
  await ElMessageBox.confirm('确认删除该业务系统？', '提示', { type: 'warning' })
  await deleteCi(row.id)
  loadCis()
}

onMounted(() => {
  loadContracts()
  loadCustomers()
  loadItems()
  loadCis()
  loadContractTypes()
})
</script>

<style scoped>
.toolbar { display: flex; gap: 12px; margin-bottom: 14px; }
.lane { margin-bottom: 16px; }
.lane-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.lane-title { font-weight: 600; font-size: 15px; }
.lane-count { color: #909399; }
.gen-cycle-btn.is-disabled { color: #909399 !important; }
.obj-row { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.ci-checkbox-list { display: flex; flex-direction: column; gap: 4px; }
.ci-empty { color: #999; font-size: 12px; margin-top: 4px; }
/* 与「项目名称」label（右对齐、宽 110px、右内边距 12px）的「项」字左缘对齐：110 - 12 - 4 字宽 */
.ci-form-item :deep(.el-form-item__label),
.ci-form-item :deep(.el-form-item__content) { margin-left: calc(110px - 12px - 4em); }
.text-preview { margin-top: 8px; max-height: 200px; overflow: auto; white-space: pre-wrap; background: #f5f7fa; padding: 8px; border-radius: 4px; font-size: 12px; color: #666; }
</style>
