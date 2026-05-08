import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      redirect: '/chat'
    },
    {
      path: '/chat',
      name: 'user-chat',
      component: () => import('../views/UserChat/UserChat.vue')
    },
    {
      path: '/workbench',
      name: 'agent-workbench',
      component: () => import('../views/AgentWorkbench/Workbench.vue')
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('../views/Admin/Admin.vue')
    }
  ]
})

export default router