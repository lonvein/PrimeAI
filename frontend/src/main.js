import { createApp } from 'vue'
import App from './App.vue'

// Global reset styles (no Tailwind dependency)
const style = document.createElement('style')
style.textContent = `
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: Georgia, serif; background: #eef2f0; color: #18312b; }
  img { max-width: 100%; height: auto; }
`
document.head.appendChild(style)

createApp(App).mount('#app')