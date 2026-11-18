<script setup lang="ts">
withDefaults(defineProps<{ name: string; size?: number }>(), { size: 20 })
const paths: Record<string, string> = {
  layers: 'M12 3 2 8l10 5 10-5-10-5ZM2 12l10 5 10-5M2 16l10 5 10-5',
  inbox: 'M4 3h16v18H4V3Zm0 11h5l1 3h4l1-3h5M8 7h8M8 10h5',
  users: 'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M16 3a4 4 0 0 1 0 8M22 21v-2a4 4 0 0 0-3-3.87M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z',
  plus: 'M12 5v14M5 12h14', arrow: 'M5 12h14M13 6l6 6-6 6', back: 'm15 18-6-6 6-6',
  refresh: 'M20 7v5h-5M4 17v-5h5M6.1 7a7 7 0 0 1 11.55-2L20 8M4 16l2.35 3A7 7 0 0 0 18 17',
  check: 'm5 12 4 4L19 6', clock: 'M12 7v5l3 2M22 12a10 10 0 1 1-20 0 10 10 0 0 1 20 0Z',
  shield: 'm12 3 8 4v6c0 5-8 8-8 8s-8-3-8-8V7l8-4Zm-4 9 3 3 5-6',
  file: 'M14 2H5v20h14V7l-5-5Zm0 0v5h5M8 12h8M8 16h6',
}
</script>
<template><svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="paths[name] || paths.file" /></svg></template>
