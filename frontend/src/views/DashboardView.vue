<script setup>
import { ref, computed, onMounted } from 'vue'
import PhotoViewer from '../components/PhotoViewer.vue'
import { api } from '../services/api'

const analysis = ref(null)
const localFile = ref(null)
const selectedDate = ref('2026-09-05')
const isLoading = ref(false)
const errorMessage = ref('')
const isDragOver = ref(false)
const analytics = ref(null)

const MACHINERY_RU = {
  excavator: 'Экскаватор',
  dump_truck: 'Самосвал',
  bulldozer: 'Бульдозер',
  concrete_mixer: 'Автобетоносмеситель',
  mobile_crane: 'Автокран',
  crane_manipulator: 'Кран-манипулятор',
  manipulator: 'Кран-манипулятор',
  roller: 'Каток',
  truck: 'Грузовик',
}

const statusLabels = {
  OK: '✅ СООТВЕТСТВУЕТ ПЛАНУ',
  WARNING: '⚠️ ТРЕБУЕТ ВНИМАНИЯ',
  CRITICAL: '🚨 КРИТИЧЕСКОЕ ОТКЛОНЕНИЕ',
  WAITING: '⏳ ОЖИДАНИЕ АНАЛИЗА',
}

const qualityLabels = {
  HIGH: '🟢 Высокое качество (детальный план)',
  MEDIUM: '🟡 Среднее качество ракурса',
  LOW: '🟠 Ограниченное качество (дальний ракурс)',
}

async function loadAnalytics() {
  try {
    const { data } = await api.get('/analytics/summary')
    analytics.value = data
  } catch (e) {
    console.warn('Analytics unavailable:', e)
  }
}

async function runAnalysis(file, customDate = null, preset = null) {
  if (!file && !preset) return
  isLoading.value = true
  errorMessage.value = ''

  const formData = new FormData()
  if (file) {
    formData.append('image', file)
  }
  const dateToSend = customDate || selectedDate.value
  if (dateToSend) {
    formData.append('date', dateToSend)
  }
  if (preset) {
    formData.append('preset', preset)
  }

  try {
    const { data } = await api.post('/analyze', formData)
    analysis.value = data
    if (file) {
      localFile.value = file
    }
    if (data.detected_date) {
      selectedDate.value = data.detected_date
    }
    loadAnalytics()
  } catch (err) {
    errorMessage.value = err.response?.data?.detail || 'Ошибка при анализе снимка.'
  } finally {
    isLoading.value = false
  }
}

function handleFileInput(e) {
  const file = e.target.files[0]
  if (file) {
    runAnalysis(file)
  }
}

function handleDrop(e) {
  isDragOver.value = false
  const file = e.dataTransfer.files[0]
  if (file) {
    runAnalysis(file)
  }
}

async function handleDateChange() {
  if (localFile.value) {
    await runAnalysis(localFile.value, selectedDate.value)
  }
}

async function loadPreset(presetKey) {
  isLoading.value = true
  errorMessage.value = ''
  try {
    // Fetch preset image asset
    const imgUrl = '/static/demo/site_2026-09-20_deficit.png'
    const res = await fetch(imgUrl)
    const blob = await res.blob()
    const filename = presetKey === 'norm' ? 'site_2026-09-05_norm.png' : 'site_2026-09-20_deficit.png'
    const file = new File([blob], filename, { type: 'image/png' })

    const date = presetKey === 'norm' ? '2026-09-05' : '2026-09-20'
    selectedDate.value = date

    await runAnalysis(file, date, presetKey)
  } catch (e) {
    errorMessage.value = 'Не удалось загрузить демо-снимок: ' + (e.message || e)
    isLoading.value = false
  }
}

const planFactRows = computed(() => {
  if (!analysis.value) return []
  const plan = analysis.value.machinery_plan || {}
  const fact = analysis.value.machinery_fact || {}

  const allKeys = Array.from(new Set([...Object.keys(plan), ...Object.keys(fact)]))
  if (!allKeys.length) return []

  return allKeys.map((key) => {
    const pCount = plan[key] || 0
    const fCount = fact[key] || 0
    let statusText = '✓ Норма'
    let statusClass = 'status-ok'

    if (pCount > 0 && fCount < pCount) {
      statusText = `✗ Дефицит (-${pCount - fCount})`
      statusClass = 'status-deficit'
    } else if (pCount === 0 && fCount > 0) {
      statusText = `⚠️ Вне плана (+${fCount})`
      statusClass = 'status-unexpected'
    }

    return {
      key,
      nameRu: MACHINERY_RU[key] || key,
      plan: pCount,
      fact: fCount,
      statusText,
      statusClass,
    }
  })
})

function downloadPdf() {
  const id = analysis.value?.incident_id
  if (!id) return
  window.open(`/api/v1/monitoring/incidents/${id}/pdf`, '_blank')
}

onMounted(() => {
  loadAnalytics()
  // Load default demo preset on startup for immediate rich experience
  loadPreset('norm')
})
</script>

<template>
  <main class="dashboard-container">
    <!-- Top Header Bar -->
    <header class="dashboard-header">
      <div class="header-titles">
        <h1>🏗️ Build Eye AI — Оперативный мониторинг СМР</h1>
        <p class="subtitle">
          Автоматическое сопоставление даты снимка с календарным графиком ДГП Москвы
        </p>
      </div>

      <div class="header-actions">
        <router-link to="/timeline" class="schedule-link-badge" title="Открыть полный интерактивный график работ и диаграмму Ганта">
          📅 Календарный график СМР (ДГП) ↗
        </router-link>

        <div v-if="analytics && analytics.total_incidents > 0" class="mini-stats">
          <span class="mini-stat">Всего: <strong>{{ analytics.total_incidents }}</strong></span>
          <span class="mini-stat stat-ok">OK: <strong>{{ analytics.by_status?.OK || 0 }}</strong></span>
          <span class="mini-stat stat-warn">Внимание: <strong>{{ analytics.by_status?.WARNING || 0 }}</strong></span>
          <span class="mini-stat stat-crit">Критично: <strong>{{ analytics.by_status?.CRITICAL || 0 }}</strong></span>
        </div>
      </div>
    </header>

    <div v-if="errorMessage" class="error-banner">
      {{ errorMessage }}
    </div>

    <!-- Main Two-Column Desktop Layout (60% / 40%) -->
    <div class="two-column-layout">
      <!-- LEFT COLUMN (60%): Upload, Presets & Photo Viewer -->
      <section class="left-col">
        <!-- Compact Dropzone & Presets Toolbar -->
        <div class="upload-panel">
          <div
            class="dropzone"
            :class="{ 'drag-over': isDragOver, 'is-loading': isLoading }"
            @dragover.prevent="isDragOver = true"
            @dragleave.prevent="isDragOver = false"
            @drop.prevent="handleDrop"
          >
            <input
              id="file-upload"
              type="file"
              accept="image/*"
              class="hidden-file-input"
              @change="handleFileInput"
            />
            <label for="file-upload" class="dropzone-label">
              <span class="upload-icon">📷</span>
              <span class="upload-text">
                <strong>Перетащите фото площадки</strong> или <span class="browse-link">выберите файл</span>
              </span>
            </label>
          </div>

          <!-- Quick 1-Click Demo Presets -->
          <div class="presets-toolbar">
            <span class="presets-title">Демо-пресеты:</span>
            <button
              class="btn-preset preset-norm"
              :disabled="isLoading"
              @click="loadPreset('norm')"
              title="Тестовый снимок земляных работ в срок (статус OK)"
            >
              🟢 [Тест: Норма]
            </button>
            <button
              class="btn-preset preset-critical"
              :disabled="isLoading"
              @click="loadPreset('critical')"
              title="Тестовый снимок с дефицитом самосвалов (статус CRITICAL)"
            >
              🔴 [Тест: Срыв сроков]
            </button>
          </div>
        </div>

        <!-- Viewer with Bounding Boxes & RAW link -->
        <div class="viewer-wrapper">
          <PhotoViewer
            :image-file="localFile"
            :debug-image-url="analysis?.annotated_image_url || analysis?.image_url || analysis?.debug_image_url || ''"
            :annotated-image-url="analysis?.annotated_image_url || ''"
            :raw-image-url="analysis?.raw_image_url || ''"
            :detections="analysis?.detections || []"
          />
        </div>
      </section>

      <!-- RIGHT COLUMN (40%): Date, Stage Badge, Plan vs Fact Table & Verdict -->
      <section class="right-col">
        <!-- 1. Date & Active Stage Card -->
        <div class="card stage-card">
          <div class="card-header-row">
            <div class="date-group">
              <label for="date-input" class="date-label">
                <span class="cal-icon">📅</span> <strong>Дата снимка:</strong>
              </label>
              <input
                id="date-input"
                type="date"
                v-model="selectedDate"
                class="date-input"
                @change="handleDateChange"
                title="Автоматически определено из EXIF / имени файла. Кликните для изменения даты."
              />
            </div>
            <span v-if="analysis?.photo_timestamp" class="exif-badge" title="Дата извлечена из метаданных EXIF снимка">
              EXIF ✓
            </span>
          </div>

          <div class="stage-badge-box">
            <div class="stage-tag">АКТИВНЫЙ ЭТАП ПО ПЛАНУ</div>
            <h3 class="stage-title">{{ analysis?.stage_name || analysis?.active_stage || 'Определение этапа...' }}</h3>
            <div v-if="analysis?.stage_planned_period" class="stage-period">
              Период по графику СМР:
              <strong>{{ analysis.stage_planned_period.start }}</strong> — <strong>{{ analysis.stage_planned_period.end }}</strong>
            </div>
          </div>
        </div>

        <!-- 2. Plan vs Fact Table -->
        <div class="card table-card">
          <div class="card-title-row">
            <h4>📊 План vs Факт применения техники</h4>
            <span class="table-subtitle">Контроль ДГП Москвы</span>
          </div>

          <div v-if="planFactRows.length" class="table-scroll">
            <table class="plan-fact-table">
              <thead>
                <tr>
                  <th>Тип техники</th>
                  <th class="text-center">План</th>
                  <th class="text-center">Факт</th>
                  <th>Статус</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in planFactRows" :key="row.key">
                  <td class="machinery-name">{{ row.nameRu }}</td>
                  <td class="text-center font-bold">{{ row.plan }}</td>
                  <td class="text-center font-bold" :class="{ 'fact-zero': row.fact === 0 && row.plan > 0 }">
                    {{ row.fact }}
                  </td>
                  <td>
                    <span :class="['status-chip', row.statusClass]">{{ row.statusText }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="empty-table-note">
            Техника для сопоставления не определена. Загрузите снимок площадки.
          </div>
        </div>

        <!-- 3. Managerial Verdict Card -->
        <div
          v-if="analysis"
          :class="['card', 'verdict-card', (analysis.compliance_status || analysis.status || 'OK').toLowerCase()]"
        >
          <div class="verdict-header">
            <div class="status-pill">
              {{ statusLabels[analysis.compliance_status || analysis.status] || analysis.status }}
            </div>
            <div v-if="analysis.observation_quality" class="quality-pill">
              {{ qualityLabels[analysis.observation_quality] || analysis.observation_quality }}
            </div>
          </div>

          <!-- Camera angle warning recommendation -->
          <div v-if="analysis.observation_quality === 'LOW'" class="camera-warning">
            <div class="cam-icon">⚠️</div>
            <div class="cam-text">
              <strong>Рекомендация ДГП по ракурсу камеры:</strong>
              <p>{{ analysis.camera_recommendation || 'Острый угол съемки с верхнего яруса. Рекомендуется использовать секторную камеру въезда.' }}</p>
            </div>
          </div>

          <p class="verdict-explanation">
            {{ analysis.explanation }}
          </p>

          <!-- 1-Click PDF Act Generation Button -->
          <div v-if="analysis.incident_id || analysis.status === 'WARNING' || analysis.status === 'CRITICAL'" class="act-btn-container">
            <button
              class="btn-act-pdf"
              @click="downloadPdf"
              title="Сформировать официальный юридически значимый Акт фиксации нарушений ДГП Москвы в формате PDF"
            >
              📄 Сформировать Акт нарушений (PDF)
            </button>
            <span class="act-hint">Официальный документ со штампом ДГП г. Москвы и фотофиксацией</span>
          </div>
        </div>
      </section>
    </div>
  </main>
</template>

<style scoped>
.dashboard-container {
  min-height: calc(100vh - 4.5rem);
  background: #f4f7f5;
  color: #18312b;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  padding: 1rem 1.5rem 2rem;
  box-sizing: border-box;
}

/* Header */
.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 1rem;
  padding-bottom: 0.75rem;
  border-bottom: 1px solid #dce4e0;
}
.header-titles h1 {
  font-size: 1.4rem;
  margin: 0 0 0.2rem;
  color: #142a24;
  font-weight: 700;
}
.subtitle {
  font-size: 0.85rem;
  color: #556;
  margin: 0;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}
.schedule-link-badge {
  background: #e8f5ed;
  color: #1f6b45;
  border: 1px solid #c2e2cf;
  font-size: 0.82rem;
  font-weight: 600;
  padding: 0.35rem 0.8rem;
  border-radius: 6px;
  text-decoration: none;
  transition: all 0.2s;
}
.schedule-link-badge:hover {
  background: #d5ecde;
  color: #134e30;
}
.mini-stats {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  font-size: 0.8rem;
}
.mini-stat {
  background: white;
  padding: 0.25rem 0.6rem;
  border-radius: 6px;
  border: 1px solid #e0e0e0;
}
.stat-ok strong { color: #2b8a5a; }
.stat-warn strong { color: #d97706; }
.stat-crit strong { color: #b52f2f; }

.error-banner {
  background: #fee2e2;
  border: 1px solid #ef4444;
  color: #991b1b;
  padding: 0.6rem 1rem;
  border-radius: 6px;
  margin-bottom: 1rem;
  font-size: 0.85rem;
  font-weight: 500;
}

/* Two-column layout */
.two-column-layout {
  display: grid;
  grid-template-columns: 58% 42%;
  gap: 1.25rem;
  align-items: start;
}

@media (max-width: 1024px) {
  .two-column-layout {
    grid-template-columns: 1fr;
  }
}

/* Left Column */
.left-col {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.upload-panel {
  background: white;
  border-radius: 8px;
  padding: 0.75rem 1rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.dropzone {
  border: 2px dashed #b5cfc4;
  border-radius: 6px;
  padding: 0.75rem 1rem;
  text-align: center;
  background: #f9fcfb;
  cursor: pointer;
  transition: border-color 0.2s, background-color 0.2s;
}
.dropzone.drag-over {
  border-color: #2b8a5a;
  background: #eef8f2;
}
.dropzone.is-loading {
  opacity: 0.6;
  pointer-events: none;
}
.hidden-file-input { display: none; }
.dropzone-label {
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.6rem;
  font-size: 0.88rem;
  color: #334;
}
.upload-icon { font-size: 1.2rem; }
.browse-link {
  color: #2b8a5a;
  text-decoration: underline;
  font-weight: 600;
}

.presets-toolbar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-wrap: wrap;
  padding-top: 0.2rem;
  border-top: 1px solid #f0f4f2;
}
.presets-title {
  font-size: 0.8rem;
  color: #667;
  font-weight: 600;
}
.btn-preset {
  cursor: pointer;
  border: 1px solid transparent;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  font-size: 0.82rem;
  font-weight: 600;
  transition: all 0.15s;
}
.btn-preset:disabled {
  opacity: 0.5;
  cursor: wait;
}
.preset-norm {
  background: #e8f5ed;
  color: #1b6b3e;
  border-color: #bce0cc;
}
.preset-norm:hover:not(:disabled) {
  background: #d4ecdc;
}
.preset-critical {
  background: #fee2e2;
  color: #991b1b;
  border-color: #fca5a5;
}
.preset-critical:hover:not(:disabled) {
  background: #fecaca;
}

.viewer-wrapper {
  background: white;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
  overflow: hidden;
}

/* Right Column */
.right-col {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.card {
  background: white;
  border-radius: 8px;
  padding: 1rem 1.25rem;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
}

/* Date & Stage Card */
.stage-card {
  border-left: 4px solid #2b8a5a;
}
.card-header-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.6rem;
}
.date-group {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}
.date-label {
  font-size: 0.85rem;
  color: #334;
  display: flex;
  align-items: center;
  gap: 0.3rem;
}
.date-input {
  border: 1px solid #cbd5e1;
  border-radius: 4px;
  padding: 0.25rem 0.5rem;
  font-size: 0.85rem;
  font-weight: 600;
  color: #1e293b;
  background: #f8fafc;
  cursor: pointer;
}
.date-input:focus {
  outline: none;
  border-color: #2b8a5a;
  background: white;
}
.exif-badge {
  background: #e0f2fe;
  color: #0369a1;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 0.15rem 0.45rem;
  border-radius: 4px;
}
.stage-badge-box {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 0.65rem 0.85rem;
}
.stage-tag {
  font-size: 0.68rem;
  font-weight: 800;
  color: #64748b;
  letter-spacing: 0.5px;
  margin-bottom: 0.2rem;
}
.stage-title {
  margin: 0 0 0.3rem;
  font-size: 1.05rem;
  color: #0f172a;
  font-weight: 700;
  line-height: 1.3;
}
.stage-period {
  font-size: 0.78rem;
  color: #64748b;
}

/* Plan vs Fact Table */
.card-title-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.6rem;
}
.card-title-row h4 {
  margin: 0;
  font-size: 0.95rem;
  color: #1e293b;
  font-weight: 700;
}
.table-subtitle {
  font-size: 0.72rem;
  color: #64748b;
  font-weight: 600;
}
.table-scroll {
  overflow-x: auto;
}
.plan-fact-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
}
.plan-fact-table th {
  background: #f1f5f9;
  color: #475569;
  font-weight: 600;
  text-align: left;
  padding: 0.4rem 0.6rem;
  border-bottom: 2px solid #e2e8f0;
}
.plan-fact-table td {
  padding: 0.45rem 0.6rem;
  border-bottom: 1px solid #f1f5f9;
}
.machinery-name {
  font-weight: 600;
  color: #1e293b;
}
.text-center { text-align: center; }
.font-bold { font-weight: 700; }
.fact-zero { color: #dc2626; }

.status-chip {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 4px;
  font-size: 0.74rem;
  font-weight: 600;
}
.status-ok { background: #dcfce7; color: #15803d; }
.status-deficit { background: #fee2e2; color: #b91c1c; }
.status-unexpected { background: #fef3c7; color: #b45309; }

.empty-table-note {
  font-size: 0.8rem;
  color: #94a3b8;
  font-style: italic;
  padding: 0.5rem 0;
}

/* Verdict Card */
.verdict-card {
  border-left: 4px solid #94a3b8;
}
.verdict-card.ok { border-left-color: #22c55e; }
.verdict-card.warning { border-left-color: #f59e0b; }
.verdict-card.critical { border-left-color: #ef4444; }

.verdict-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.6rem;
}
.status-pill {
  font-size: 0.92rem;
  font-weight: 800;
}
.verdict-card.ok .status-pill { color: #16a34a; }
.verdict-card.warning .status-pill { color: #d97706; }
.verdict-card.critical .status-pill { color: #dc2626; }

.quality-pill {
  font-size: 0.72rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: 10px;
  background: #f1f5f9;
  color: #475569;
}

.camera-warning {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  background: #fffbeb;
  border-left: 3px solid #f59e0b;
  border-radius: 4px;
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.6rem;
  font-size: 0.78rem;
}
.cam-icon { font-size: 1rem; }
.cam-text strong { color: #92400e; display: block; margin-bottom: 0.15rem; }
.cam-text p { margin: 0; color: #78350f; line-height: 1.35; }

.verdict-explanation {
  font-size: 0.82rem;
  line-height: 1.45;
  color: #334155;
  margin: 0 0 0.8rem;
}

.act-btn-container {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding-top: 0.6rem;
  border-top: 1px solid #f1f5f9;
}
.btn-act-pdf {
  background: #0a2540;
  color: #ffffff;
  border: none;
  padding: 0.6rem 1rem;
  font-size: 0.85rem;
  font-weight: 700;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  transition: all 0.2s;
  box-shadow: 0 2px 4px rgba(10, 37, 64, 0.2);
}
.btn-act-pdf:hover {
  background: #153965;
  transform: translateY(-1px);
}
.act-hint {
  font-size: 0.72rem;
  color: #64748b;
  text-align: center;
}
</style>