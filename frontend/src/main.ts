import { createApp } from 'vue'
import { ElAlert, ElCard, ElTag } from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'

createApp(App).use(ElAlert).use(ElCard).use(ElTag).mount('#app')
