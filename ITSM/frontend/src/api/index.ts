import request from './request'

// ---- 认证 ----
export const login = (data: { username: string; password: string }) => request.post('/auth/login', data)
export const getMe = () => request.get('/auth/me')

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

// ---- 合同子项 ----
export const listItems = (params: any) => request.get('/contract-items', { params })
export const createItem = (data: any) => request.post('/contract-items', data)
export const updateItem = (id: number, data: any) => request.put(`/contract-items/${id}`, data)
export const deleteItem = (id: number) => request.delete(`/contract-items/${id}`)
export const generateCycles = (id: number) => request.post(`/contract-items/${id}/cycles/generate`)

// ---- 服务对象 CI ----
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
export const dispatch = (id: number, data: any) => request.post(`/work-orders/${id}/dispatch`, data)
export const transfer = (id: number, data: any) => request.post(`/work-orders/${id}/assignees/transfer`, data)

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
