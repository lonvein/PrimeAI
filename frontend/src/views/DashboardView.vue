<script setup>
import { ref } from 'vue'
import Navbar from '../components/Navbar.vue'
import IncidentCard from '../components/IncidentCard.vue'
import UploadModal from '../components/UploadModal.vue'

const analysis = ref(null)
</script>

<template>
  <main class="dashboard">
    <Navbar />
    <section>
      <h1>Build Eye AI</h1>
      <p>Мониторинг техники и календарного плана.</p>
      <UploadModal @analyzed="analysis = $event" />
      <IncidentCard
        :status="analysis?.status || 'WAITING'"
        :explanation="analysis?.explanation"
        :missing-machinery="analysis?.missing_machinery"
        :unexpected-machinery="analysis?.unexpected_machinery"
      />
    </section>
  </main>
</template>

<style scoped>
.dashboard { min-height: 100vh; padding: 2rem; background: #eef2f0; color: #18312b; font-family: Georgia, serif; }
section { max-width: 900px; margin: 4rem auto; } h1 { font-size: 4rem; margin: 0; } p { font: 1.1rem sans-serif; }
</style>