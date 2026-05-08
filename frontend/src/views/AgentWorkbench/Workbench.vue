<template>
  <div class="workbench-container">
    <div class="workbench-header">
      <h2>客服工作台</h2>
    </div>
    <div class="workbench-content">
      <el-empty description="客服工作台开发中..." />
    </div>
  </div>
</template>

<script setup lang="ts">
// 客服工作台 - 待实现
</script>

<style scoped>
.workbench-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f5f5f5;
}

.workbench-header {
  padding: 1rem 2rem;
  background-color: white;
  border-bottom: 1px solid #e0e0e0;
}

.workbench-content {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}
</style>