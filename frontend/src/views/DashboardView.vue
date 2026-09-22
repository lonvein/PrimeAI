<script setup>
import { ref, onMounted } from 'vue'
import Navbar from '../components/Navbar.vue'
import IncidentCard from '../components/IncidentCard.vue'
import UploadModal from '../components/UploadModal.vue'
import PhotoViewer from '../components/PhotoViewer.vue'
import { api } from '../services/api'

const analysis = ref(null)
const localFile = ref(null)
const analytics = ref(null)

async function loadAnalytics() {
  try {
    const { data } = await api.get('/analytics/summary')
    analytics.value = data
  } catch (e) {
    console.warn('Analytics unavailable:', e)
  }
}

function handleAnalyzed(result) {
  localFile.value = result._localFile || null
  // Remove the non-API field before storing.
  const { _localFile, ...apiData } = result
  analysis.value = apiData
  // Refresh analytics after new analysis.
  loadAnalytics()
}

onMounted(loadAnalytics)
</script>

<template>
  <main class="dashboard">
    <Navbar />

    <section class="content">
      <header class="hero">
        <h1>Build Eye AI</h1>
        <p>Мониторинг техники и календарного плана строительной площадки.</p>
      </header>

      <!-- Analytics summary bar -->
      <div v-if="analytics && analytics.total_incidents > 0" class="analytics-bar">
        <div class="stat">
          <span class="stat-number">{{ analytics.total_incidents }}</span>
          <span class="stat-label">Всего проверок</span>
        </div>
        <div class="stat ok">
          <span class="stat-number">{{ analytics.by_status?.OK || 0 }}</span>
          <span class="stat-label">OK</span>
        </div>
        <div class="stat warning">
          <span class="stat-number">{{ analytics.by_status?.WARNING || 0 }}</span>
          <span class="stat-label">Внимание</span>
        </div>
        <div class="stat critical">
          <span class="stat-number">{{ analytics.by_status?.CRITICAL || 0 }}</span>
          <span class="stat-label">Критичных</span>
        </div>
      </div>

      <!-- Upload form -->
      <UploadModal @analyzed="handleAnalyzed" />

      <!-- Photo with bounding boxes -->
      <PhotoViewer
        :image-file="localFile"
        :debug-image-url="analysis?.debug_image_url || ''"
        :detections="analysis?.detections || []"
      />

      <!-- Incident card -->
      <IncidentCard
        :status="analysis?.status || 'WAITING'"
        :explanation="analysis?.explanation"
        :missing-machinery="analysis?.missing_machinery || []"
        :unexpected-machinery="analysis?.unexpected_machinery || []"
        :observation-quality="analysis?.observation_quality || ''"
        :model-is-construction-specific="analysis?.model_is_construction_specific || false"
      />
    </section>
  </main>
</template>

<style scoped>
.dashboard {
  min-height: 100vh;
  background: #eef2f0;
  color: #18312b;
  font-family: Georgia, serif;
}
.content {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem 1rem 4rem;
}
.hero h1 {
  font-size: 3rem;
  margin: 0 0 0.3rem;
}
.hero p {
  font: 1.1rem/1.4 sans-serif;
  margin: 0 0 1.5rem;
  color: #555;
}

/* Analytics bar */
.analytics-bar {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}
.stat {
  flex: 1;
  min-width: 100px;
  padding: 1rem;
  background: white;
  border-radius: 10px;
  text-align: center;
  border-top: 3px solid #ccc;
}
.stat.ok { border-top-color: #2b8a5a; }
.stat.warning { border-top-color: #e8a317; }
.stat.critical { border-top-color: #b52f2f; }
.stat-number {
  display: block;
  font-size: 2rem;
  font-weight: 700;
  font-family: sans-serif;
}
.stat-label {
  display: block;
  font-size: 0.8rem;
  font-family: sans-serif;
  color: #777;
  margin-top: 0.2rem;
}
</style>