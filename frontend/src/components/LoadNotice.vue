<script setup lang="ts">
defineProps<{ error: string; offline: boolean }>()
defineEmits<{ retry: [] }>()
</script>
<template><div v-if="offline || error" class="notice warning" role="status"><span>{{ offline ? '网络已断开。已显示的数据保留，连接恢复后继续更新。' : error }}</span><el-button v-if="!offline" text @click="$emit('retry')">重试</el-button></div></template>
