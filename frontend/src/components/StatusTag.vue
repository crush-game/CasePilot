<script setup lang="ts">
import type { TicketStatus } from '../types'
import { statusLabels } from '../utils/display'
defineProps<{ status: TicketStatus }>()
</script>
<template><span class="status-tag" :class="`status-${status.toLowerCase()}`"><span></span>{{ statusLabels[status] }}</span></template>
