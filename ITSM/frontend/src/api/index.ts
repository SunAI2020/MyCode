import request from './request'
import axios from 'axios'

// ---- 认证 ----
export const login = (data: { username: string; password: string }) => request.post('/auth/login', data)
export const getMe = () => request.get('/auth/me')

// ---- 数据看板 ----
export const getDashboard = () => request.get('/dashboard')

// ---- 人员管理 ----
export const listUsers = () => request.get('/users')
export const createUser = (data: any) => request.post('/users', data)
export const updateUser = (id: number, data: any) => request.put(`/users/${id}`, data)
export const deleteUser = (id: number) => request.delete(`/users/${id}`)

// ---- 权限管理（角色权限矩阵）----
export const listPermissions = () => request.get('/permissions')
export const listRoles = () => request.get('/permissions/roles')
export const getRolePermissions = (code: string) => request.get(`/permissions/roles/${code}/permissions`)
export const updateRolePermissions = (code: string, data: any) => request.put(`/permissions/roles/${code}/permissions`, data)

// ---- 安全隐患（问题整改）----
export const listIssues = (params: any) => request.get('/issues', { params })

// ---- 字典枚举 ----
export const listDicts = (category: string) => request.get(`/dicts/${category}`)
export const createDict = (data: any) => request.post('/dicts', data)

// ---- 客户 ----
export const listCustomers = (params: any) => request.get('/customers', { params })
export const createCustomer = (data: any) => request.post('/customers', data)
export const updateCustomer = (id: number, data: any) => request.put(`/customers/${id}`, data)
export const deleteCustomer = (id: number) => request.delete(`/customers/${id}`)

// ---- 合同 ----
export const listContracts = (params: any) => request.get('/contracts', { params })
export const createContract = (data: any) => request.post('/contracts', data)
export const updateContract = (id: number, data: any) => request.put(`/contracts/${id}`, data)
export const deleteContract = (id: number) => request.delete(`/contracts/${id}`)

// ---- 合同原件档案 ----
export const uploadContractArchive = (file: File) => {
  const fd = new FormData()
  fd.append('file', file)
  // 上传 + 后端文字提取（MinerU flash 秒级）；放宽到 120s 留余量
  return request.post('/contract-archives/upload', fd, { timeout: 120000 })
}
export const confirmContractArchive = (id: number, data: any) => request.post(`/contract-archives/${id}/confirm`, data)
export const listContractArchives = (params: any) => request.get('/contract-archives', { params })
// 下载原件需返回二进制，绕过统一 JSON 响应拦截器，用原生 axios + token
export const downloadContractArchive = async (id: number): Promise<Blob> => {
  const token = localStorage.getItem('token')
  const res = await axios.get(`/api/v1/contract-archives/${id}/download`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    responseType: 'blob',
  })
  return res.data as Blob
}

// ---- 合同子项 ----
export const listItems = (params: any) => request.get('/contract-items', { params })
export const createItem = (data: any) => request.post('/contract-items', data)
export const updateItem = (id: number, data: any) => request.put(`/contract-items/${id}`, data)
export const deleteItem = (id: number) => request.delete(`/contract-items/${id}`)
export const generateCycles = (id: number) => request.post(`/contract-items/${id}/cycles/generate`)

// ---- 业务系统 CI ----
export const listCis = (params: any) => request.get('/cmdb-cis', { params })
export const createCi = (data: any) => request.post('/cmdb-cis', data)
export const updateCi = (id: number, data: any) => request.put(`/cmdb-cis/${id}`, data)
export const deleteCi = (id: number) => request.delete(`/cmdb-cis/${id}`)

// ---- 接单 / 工单 ----
export const listReceives = (params: any) => request.get('/receives', { params })
export const createReceive = (data: any) => request.post('/receives', data)
export const listWorkOrders = (params: any) => request.get('/work-orders', { params })
export const createWorkOrder = (data: any) => request.post('/work-orders', data)
export const updateStatus = (id: number, data: any) => request.put(`/work-orders/${id}/status`, data)
export const deleteWorkOrder = (id: number) => request.delete(`/work-orders/${id}`)
export const dispatch = (id: number, data: any) => request.post(`/work-orders/${id}/dispatch`, data)
export const transfer = (id: number, data: any) => request.post(`/work-orders/${id}/assignees/transfer`, data)
export const previewAggregateCycles = (data: any) => request.post('/work-orders/aggregate/preview', data)
export const createAggregateWorkOrder = (data: any) => request.post('/work-orders/aggregate', data)
export const getWorkOrderScope = (id: number) => request.get(`/work-orders/${id}/scope`)

// ---- SLA / 周期 / 提醒 ----
export const listSla = (params: any) => request.get('/sla-policies', { params })
export const createSla = (data: any) => request.post('/sla-policies', data)
export const updateSla = (id: number, data: any) => request.put(`/sla-policies/${id}`, data)
export const deleteSla = (id: number) => request.delete(`/sla-policies/${id}`)
export const listCycles = (params: any) => request.get('/cycles', { params })
export const listReminders = (params: any) => request.get('/reminders', { params })

// ---- 知识库 / RAG ----
export const listArticles = (params: any) => request.get('/kb-articles', { params })
export const createArticle = (data: any) => request.post('/kb-articles', data)
export const deleteArticle = (id: number) => request.delete(`/kb-articles/${id}`)
export const askKb = (data: any) => request.post('/kb-articles/ask', data)
export const reindexKb = () => request.post('/kb-articles/reindex')

// ---- 自助门户 ----
export const portalOverview = () => request.get('/portal/overview')
export const createTicket = (data: any) => request.post('/portal/tickets', data)

// ---- 工作流规则 ----
export const listWorkflowRules = (params: any) => request.get('/workflow-rules', { params })
export const workflowTransitions = () => request.get('/workflow-rules/transitions')
export const createWorkflowRule = (data: any) => request.post('/workflow-rules', data)
export const updateWorkflowRule = (id: number, data: any) => request.put(`/workflow-rules/${id}`, data)
export const deleteWorkflowRule = (id: number) => request.delete(`/workflow-rules/${id}`)

// ---- 合规运营 ----
export const listRequirements = (params: any) => request.get('/compliance/requirements', { params })
export const createRequirement = (data: any) => request.post('/compliance/requirements', data)
export const updateRequirement = (id: number, data: any) => request.put(`/compliance/requirements/${id}`, data)
export const deleteRequirement = (id: number) => request.delete(`/compliance/requirements/${id}`)
export const listEvidence = (rid: number) => request.get(`/compliance/requirements/${rid}/evidence`)
export const addEvidence = (rid: number, data: any) => request.post(`/compliance/requirements/${rid}/evidence`, data)
export const verifyEvidenceChain = (rid: number) => request.get(`/compliance/requirements/${rid}/evidence/verify`)
export const createCheck = (rid: number, data: any) => request.post(`/compliance/requirements/${rid}/checks`, data)
export const listChecks = (params: any) => request.get('/compliance/checks', { params })
export const updateCheck = (id: number, data: any) => request.put(`/compliance/checks/${id}`, data)
export const complianceOverview = (params: any) => request.get('/compliance/overview', { params })
export const createReport = (data: any) => request.post('/compliance/reports', data)
export const listReports = (params: any) => request.get('/compliance/reports', { params })
export const getReport = (id: number) => request.get(`/compliance/reports/${id}`)
export const signReport = (id: number) => request.post(`/compliance/reports/${id}/sign`)
export const listTemplates = (params: any) => request.get('/compliance/templates', { params })
export const applyTemplate = (id: number, data: any) => request.post(`/compliance/templates/${id}/apply`, data)
