<template>
  <div class="admin-container">
    <div class="admin-header">
      <h2>管理后台</h2>
    </div>
    <div class="admin-content">
      <el-empty description="管理后台开发中..." />
    </div>
  </div>
</template>

<script setup lang="ts">
// 管理后台 - 待实现
</script>

<style scoped>
.admin-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f5f5f5;
}

.admin-header {
  padding: 1rem 2rem;
  background-color: white;
  border-bottom: 1px solid #e0e0e0;
}

.admin-content {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>