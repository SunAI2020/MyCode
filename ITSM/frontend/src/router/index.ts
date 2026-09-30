import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/Login.vue') },
    {
      path: '/',
      component: () => import('@/layouts/MainLayout.vue'),
      redirect: '/dashboard',
      children: [
        { path: 'dashboard', name: 'dashboard', component: () => import('@/views/Dashboard.vue') },
        { path: 'customers', name: 'customers', component: () => import('@/views/Customers.vue') },
        { path: 'contracts', name: 'contracts', component: () => import('@/views/Contracts.vue') },
        { path: 'work-orders', name: 'work-orders', component: () => import('@/views/WorkOrders.vue') },
        { path: 'personnel', name: 'personnel', component: () => import('@/views/Personnel.vue') },
        { path: 'issues', name: 'issues', component: () => import('@/views/Issues.vue') },
        { path: 'portal', name: 'portal', component: () => import('@/views/Portal.vue') },
        { path: 'knowledge', name: 'knowledge', component: () => import('@/views/Knowledge.vue') },
        { path: 'workflows', name: 'workflows', component: () => import('@/views/Workflows.vue') },
        { path: 'sla', name: 'sla', component: () => import('@/views/Sla.vue') },
        { path: 'compliance', name: 'compliance', component: () => import('@/views/Compliance.vue') },
      ],
    },
  ],
})

router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) return '/login'
  if (to.path === '/login' && token) return '/'
})

export default router
