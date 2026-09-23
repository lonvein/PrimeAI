<script setup>
import { ref } from 'vue'
import Navbar from './components/Navbar.vue'
import DashboardView from './views/DashboardView.vue'
import TimelineView from './views/TimelineView.vue'
import CameraSettingsView from './views/CameraSettingsView.vue'

const activeTab = ref('dashboard')

function handleNavigate(tab) {
  activeTab.value = tab
}
</script>

<template>
  <div class="app-layout">
    <Navbar :active-tab="activeTab" @navigate="handleNavigate" />
    <DashboardView v-if="activeTab === 'dashboard'" />
    <TimelineView v-else-if="activeTab === 'timeline'" />
    <CameraSettingsView v-else-if="activeTab === 'cameras'" />
  </div>
</template>

<style>
.app-layout {
  min-height: 100vh;
  background: #eef2f0;
}
</style>