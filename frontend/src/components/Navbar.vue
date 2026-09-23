<script setup>
defineProps({
  activeTab: { type: String, default: 'dashboard' },
})
defineEmits(['navigate'])
</script>

<template>
  <nav class="navbar">
    <div class="brand" @click="$emit('navigate', 'dashboard')">
      <span class="logo">🏗️</span>
      <span class="title">BUILD / EYE</span>
      <span class="badge">AI</span>
    </div>

    <div class="nav-links">
      <button
        class="nav-btn"
        :class="{ active: activeTab === 'dashboard' }"
        @click="$emit('navigate', 'dashboard')"
      >
        📊 Мониторинг
      </button>
      <button
        class="nav-btn"
        :class="{ active: activeTab === 'timeline' }"
        @click="$emit('navigate', 'timeline')"
      >
        📅 График СМР
      </button>
      <button
        class="nav-btn"
        :class="{ active: activeTab === 'cameras' }"
        @click="$emit('navigate', 'cameras')"
      >
        🎥 Камеры и секторы
      </button>
    </div>

    <span class="subtitle">LIVE SITE MONITOR</span>
  </nav>
</template>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.8rem 2rem;
  background: #18312b;
  color: white;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.15);
  flex-wrap: wrap;
  gap: 1rem;
}
.brand {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  cursor: pointer;
}
.logo { font-size: 1.6rem; }
.title {
  font-size: 1.2rem;
  font-weight: 800;
  letter-spacing: 0.15rem;
}
.badge {
  font-size: 0.65rem;
  padding: 0.15rem 0.4rem;
  background: #2b8a5a;
  border-radius: 4px;
  font-weight: 700;
  letter-spacing: 0.05rem;
}
.nav-links {
  display: flex;
  gap: 0.5rem;
}
.nav-btn {
  background: transparent;
  border: 1px solid transparent;
  color: rgba(255, 255, 255, 0.8);
  padding: 0.5rem 0.9rem;
  border-radius: 6px;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}
.nav-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: white;
}
.nav-btn.active {
  background: #2b8a5a;
  color: white;
  border-color: #3bb377;
}
.subtitle {
  font-size: 0.7rem;
  letter-spacing: 0.25rem;
  opacity: 0.6;
  text-transform: uppercase;
}
</style>