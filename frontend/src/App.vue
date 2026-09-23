<script setup>
import { ref, computed } from 'vue'
import Navbar from './components/Navbar.vue'
import DashboardView from './views/DashboardView.vue'
import TimelineView from './views/TimelineView.vue'
import CameraSettingsView from './views/CameraSettingsView.vue'

const activeTab = ref('dashboard')

function handleNavigate(tab) {
  activeTab.value = tab
}

const activeTabComponent = computed(() => {
  if (activeTab.value === 'timeline') return TimelineView
  if (activeTab.value === 'cameras') return CameraSettingsView
  return DashboardView
})
</script>

<template>
  <div class="app-layout">
    <Navbar :active-tab="activeTab" @navigate="handleNavigate" />
    <KeepAlive>
      <component :is="activeTabComponent" />
    </KeepAlive>
  </div>
</template>

<style>
.app-layout {
  min-height: 100vh;
  background: #eef2f0;
}
</style>