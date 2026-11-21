<script setup lang="ts">
import { ref } from 'vue'
import { errorMessage, request } from '../api/client'
import type { components } from '../types/openapi'

type Hint = components['schemas']['ExperienceHint']
type Scope = components['schemas']['RecallQuery']
const props = defineProps<{ scope: Scope; offline: boolean }>()
const hits = ref<Hint[] | null>(null)
const error = ref('')
const busy = ref(false)
async function recall() {
  if (busy.value || props.offline) return
  busy.value = true
  error.value = ''
  hits.value = null
  try {
    hits.value = await request<Hint[]>('/experience-recall', { method: 'POST', body: JSON.stringify(props.scope) })
  } catch (failure) { error.value = errorMessage(failure) }
  finally { busy.value = false }
}
</script>

<template>
  <section class="panel solution-panel">
    <div class="section-title"><h2>已发布历史案例</h2></div>
    <el-button :loading="busy" :disabled="offline" @click="recall">查找同范围案例</el-button>
    <p v-if="error" class="notice danger" role="alert">{{ error }}</p>
    <p v-if="hits?.length === 0" class="muted">当前没有匹配的已发布案例。</p>
    <article v-for="hit in hits" :key="hit.publication_id">
      <p class="wrap-text"><strong>{{ hit.problem }}</strong></p>
      <p class="wrap-text">{{ hit.verified_steps }}</p>
      <router-link :to="`/tickets/${hit.source_ticket_id}`" class="table-text-link">查看历史工单 · 发布版本 {{ hit.revision }}</router-link>
    </article>
  </section>
</template>
