<script setup>
import { ref, onMounted } from 'vue'
import IncidentCard from '../components/IncidentCard.vue'
import UploadModal from '../components/UploadModal.vue'
import PhotoViewer from '../components/PhotoViewer.vue'
import GanttChart from '../components/GanttChart.vue'
import { api } from '../services/api'

const analysis = ref(null)
const localFile = ref(null)
const analytics = ref(null)
const scheduleRows = ref([])
const activeStageName = ref('')
const scheduleFile = ref(null)
const scheduleLoading = ref(false)
const scheduleError = ref('')

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
  const { _localFile, ...apiData } = result
  analysis.value = apiData
  loadAnalytics()
}

async function uploadSchedule() {
  if (!scheduleFile.value) return
  scheduleLoading.value = true
  scheduleError.value = ''
  const formData = new FormData()
  formData.append('file', scheduleFile.value)
  // Pass today's date to get active stage.
  const today = new Date().toISOString().slice(0, 10)
  try {
    const { data } = await api.post(`/schedule/upload?query_date=${today}`, formData)
    scheduleRows.value = data.rows || []
    if (data.active_stage) {
      activeStageName.value = data.active_stage.stage_name
    }
  } catch (e) {
    scheduleError.value = e.response?.data?.detail || 'Не удалось загрузить расписание.'
  } finally {
    scheduleLoading.value = false
  }
}

function selectSchedule(event) {
  scheduleFile.value = event.target.files[0] || null
  scheduleError.value = ''
}

function downloadPdf(id) {
  if (!id) return
  const url = `/api/v1/monitoring/incidents/${id}/pdf`
  window.open(url, '_blank')
}

onMounted(loadAnalytics)
</script>

<template>
  <main class="dashboard">
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

      <!-- Schedule upload section -->
      <div class="section-card">
        <h2>📅 Загрузка расписания работ</h2>
        <p class="hint">Загрузите Excel-файл с графиком строительных работ (ДГП формат).</p>
        <div class="schedule-upload-row">
          <input type="file" accept=".xlsx,.xls" @change="selectSchedule" />
          <button @click="uploadSchedule" :disabled="!scheduleFile || scheduleLoading">
            {{ scheduleLoading ? 'Загрузка...' : '📊 Загрузить расписание' }}
          </button>
        </div>
        <p v-if="scheduleError" class="error">{{ scheduleError }}</p>
        <p v-if="activeStageName" class="active-stage-note">
          Активный этап сегодня: <strong>{{ activeStageName }}</strong>
        </p>
      </div>

      <!-- Gantt chart -->
      <GanttChart
        :rows="scheduleRows"
        :active-stage-name="activeStageName"
      />

      <!-- Photo analysis section -->
      <div class="section-card">
        <h2>📸 Анализ снимка площадки</h2>
        <UploadModal @analyzed="handleAnalyzed" />
      </div>

      <!-- Photo with bounding boxes and original RAW link -->
      <PhotoViewer
        :image-file="localFile"
        :debug-image-url="analysis?.annotated_image_url || analysis?.image_url || analysis?.debug_image_url || ''"
        :annotated-image-url="analysis?.annotated_image_url || ''"
        :raw-image-url="analysis?.raw_image_url || ''"
        :detections="analysis?.detections || []"
      />

      <!-- Incident card -->
      <IncidentCard
        :status="analysis?.status || 'WAITING'"
        :explanation="analysis?.explanation"
        :missing-machinery="analysis?.missing_machinery || []"
        :unexpected-machinery="analysis?.unexpected_machinery || []"
        :observation-quality="analysis?.observation_quality || ''"
        :camera-recommendation="analysis?.camera_recommendation || ''"
        :incident-id="analysis?.incident_id"
        :model-is-construction-specific="analysis?.model_is_construction_specific || false"
      />

      <!-- Recent incidents from DB -->
      <div v-if="analytics?.recent_incidents?.length" class="section-card recent-section">
        <h2>📋 Последние проверки</h2>
        <div v-for="inc in analytics.recent_incidents" :key="inc.id" class="recent-item" :class="inc.status.toLowerCase()">
          <div class="recent-header">
            <div class="recent-header-left">
              <span class="recent-status">{{ inc.status }}</span>
              <span class="recent-stage">{{ inc.stage_name }}</span>
              <span v-if="inc.observation_quality" :class="['recent-quality', 'q-' + inc.observation_quality.toLowerCase()]">
                {{ inc.observation_quality }}
              </span>
            </div>
            <div class="recent-header-right">
              <button
                v-if="inc.status === 'WARNING' || inc.status === 'CRITICAL'"
                class="recent-pdf-btn"
                @click="downloadPdf(inc.id)"
                title="Скачать официальный Акт фиксации ДГП Москвы (PDF)"
              >
                📄 Акт (PDF)
              </button>
              <span class="recent-date">{{ new Date(inc.created_at).toLocaleString('ru-RU') }}</span>
            </div>
          </div>
          <p class="recent-explanation">{{ inc.explanation }}</p>
        </div>
      </div>
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

/* Section cards */
.section-card {
  margin-top: 1.5rem;
  padding: 1.5rem;
  background: white;
  border-radius: 10px;
  font-family: sans-serif;
}
.section-card h2 {
  margin: 0 0 0.75rem;
  font-size: 1.15rem;
}
.hint {
  font-size: 0.85rem;
  color: #777;
  margin: 0 0 1rem;
}

/* Schedule upload */
.schedule-upload-row {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}
.schedule-upload-row button {
  cursor: pointer;
  border: 0;
  background: #18312b;
  color: white;
  border-radius: 6px;
  font-weight: 700;
  font-size: 0.9rem;
  padding: 0.6rem 1.2rem;
  transition: background 0.2s;
}
.schedule-upload-row button:hover:not(:disabled) { background: #2b5a48; }
.schedule-upload-row button:disabled { cursor: wait; opacity: 0.6; }
.error { color: #b52f2f; margin: 0.5rem 0 0; font-size: 0.85rem; }
.active-stage-note {
  margin: 0.75rem 0 0;
  padding: 0.5rem 0.75rem;
  background: #e8f5ed;
  border-radius: 6px;
  font-size: 0.9rem;
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

/* Recent incidents */
.recent-section { margin-top: 2rem; }
.recent-item {
  padding: 0.75rem 1rem;
  border-left: 4px solid #ccc;
  margin-bottom: 0.75rem;
  border-radius: 0 6px 6px 0;
  background: #fafafa;
}
.recent-item.ok { border-left-color: #2b8a5a; }
.recent-item.warning { border-left-color: #e8a317; }
.recent-item.critical { border-left-color: #b52f2f; }
.recent-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  flex-wrap: wrap;
  margin-bottom: 0.4rem;
}
.recent-header-left {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}
.recent-header-right {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.recent-status {
  font-weight: 700;
  font-size: 0.8rem;
  padding: 0.15rem 0.5rem;
  border-radius: 10px;
  background: #f0f0f0;
}
.recent-quality {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.1rem 0.45rem;
  border-radius: 8px;
}
.q-high { background: #e8f5ed; color: #1b6b3e; }
.q-medium { background: #fff8e1; color: #856404; }
.q-low { background: #fff3cd; color: #995a00; }

.recent-pdf-btn {
  background: #0a2540;
  color: #fff;
  border: none;
  font-size: 0.75rem;
  font-weight: 600;
  padding: 0.25rem 0.6rem;
  border-radius: 4px;
  cursor: pointer;
  transition: background 0.15s;
}
.recent-pdf-btn:hover {
  background: #193d64;
}

.recent-stage { font-weight: 600; font-size: 0.85rem; }
.recent-date { font-size: 0.75rem; color: #888; }
.recent-explanation {
  font-size: 0.82rem;
  color: #555;
  line-height: 1.4;
  margin: 0;
}
</style>