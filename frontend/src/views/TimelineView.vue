<script setup>
import { ref, onMounted, computed } from 'vue'
import GanttChart from '../components/GanttChart.vue'
import { api } from '../services/api'

const scheduleRows = ref([])
const selectedDate = ref('2026-09-20')
const activeStage = ref(null)
const isLoading = ref(false)
const errorMessage = ref('')
const scheduleFile = ref(null)

// Default sample schedule rows for immediate demonstration before upload
const defaultRows = [
  {
    index: 0,
    stage_name: 'Снос строений и расчистка пятна застройки',
    zone: 'Сектор А (Основной)',
    date_start: '2026-09-01T00:00:00',
    date_end: '2026-09-12T00:00:00',
    days: 12,
    machinery_plan: 'Экскаватор (2), Самосвал (4)',
    required_machinery: { excavator: 2, dump_truck: 4 },
    contractor: 'ООО "МосДемонтаж"',
  },
  {
    index: 1,
    stage_name: 'Обустройство площадки и временных дорог',
    zone: 'Периметр объекта',
    date_start: '2026-09-10T00:00:00',
    date_end: '2026-09-18T00:00:00',
    days: 9,
    machinery_plan: 'Бульдозер (1), Каток (1), Грузовик (2)',
    required_machinery: { bulldozer: 1, roller: 1, truck: 2 },
    contractor: 'АО "УМиАТ-3"',
  },
  {
    index: 2,
    stage_name: 'Разработка грунта котлована с погрузкой',
    zone: 'Сектор А (Котлован)',
    date_start: '2026-09-15T00:00:00',
    date_end: '2026-10-05T00:00:00',
    days: 21,
    machinery_plan: 'Экскаватор (2), Самосвал (6)',
    required_machinery: { excavator: 2, dump_truck: 6 },
    contractor: 'ООО "ТрансСтройЗем"',
  },
  {
    index: 3,
    stage_name: 'Устройство свайного поля (буронабивные сваи)',
    zone: 'Сектор А (Основание)',
    date_start: '2026-09-28T00:00:00',
    date_end: '2026-10-18T00:00:00',
    days: 21,
    machinery_plan: 'Автокран (1), Автобетоносмеситель (3)',
    required_machinery: { mobile_crane: 1, concrete_mixer: 3 },
    contractor: 'ООО "СпецФундамент"',
  },
  {
    index: 4,
    stage_name: 'Устройство фундаментной плиты (бетонирование)',
    zone: 'Сектор А (Захватка 1-2)',
    date_start: '2026-10-15T00:00:00',
    date_end: '2026-11-05T00:00:00',
    days: 22,
    machinery_plan: 'Автобетоносмеситель (5), Автокран (2)',
    required_machinery: { concrete_mixer: 5, mobile_crane: 2 },
    contractor: 'АО "Монолит-Бетон"',
  },
  {
    index: 5,
    stage_name: 'Возведение монолитных ж/б конструкций 1-5 этажей',
    zone: 'Сектор Б (Корпус 1)',
    date_start: '2026-11-01T00:00:00',
    date_end: '2026-12-15T00:00:00',
    days: 45,
    machinery_plan: 'Башенный кран (1), Автокран (1), Грузовик (2)',
    required_machinery: { mobile_crane: 2, truck: 2 },
    contractor: 'АО "Монолит-Бетон"',
  },
  {
    index: 6,
    stage_name: 'Устройство асфальтобетонных проездов и благоустройство',
    zone: 'Зона подъезда / Двор',
    date_start: '2026-12-10T00:00:00',
    date_end: '2026-12-28T00:00:00',
    days: 19,
    machinery_plan: 'Каток (2), Самосвал (2), Кран-манипулятор (1)',
    required_machinery: { roller: 2, dump_truck: 2, crane_manipulator: 1 },
    contractor: 'ООО "ДорСтройЛидер"',
  },
]

function updateActiveStageForDate() {
  if (!scheduleRows.value.length) return
  const target = new Date(selectedDate.value)
  const matches = scheduleRows.value.filter((r) => {
    if (!r.date_start || !r.date_end) return false
    const start = new Date(r.date_start)
    const end = new Date(r.date_end)
    return target >= start && target <= end
  })

  // Pick stage that started latest if multiple overlap
  if (matches.length > 0) {
    activeStage.value = matches.sort((a, b) => new Date(b.date_start) - new Date(a.date_start))[0]
  } else {
    activeStage.value = null
  }
}

async function handleScheduleUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  isLoading.value = true
  errorMessage.value = ''
  const fd = new FormData()
  fd.append('file', file)
  try {
    const { data } = await api.post(`/schedule/upload?query_date=${selectedDate.value}`, fd)
    scheduleRows.value = data.rows || []
    activeStage.value = data.active_stage || null
  } catch (err) {
    errorMessage.value = err.response?.data?.detail || 'Ошибка загрузки файла.'
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  scheduleRows.value = defaultRows
  updateActiveStageForDate()
})
</script>

<template>
  <div class="timeline-view">
    <header class="view-header">
      <div>
        <h2>📅 График строительно-монтажных работ</h2>
        <p class="subtitle">Интеграция с календарным планом ДГП и сопоставление нормативной техники</p>
      </div>

      <div class="upload-box">
        <label class="upload-btn">
          📂 Загрузить Excel (.xlsx)
          <input type="file" accept=".xlsx,.xls" @change="handleScheduleUpload" />
        </label>
      </div>
    </header>

    <div v-if="errorMessage" class="error-banner">
      {{ errorMessage }}
    </div>

    <!-- Date selector simulator -->
    <div class="date-selector-card">
      <div class="date-input-group">
        <label for="date-select"><strong>Текущая дата анализа:</strong></label>
        <input
          id="date-select"
          type="date"
          v-model="selectedDate"
          @change="updateActiveStageForDate"
        />
      </div>

      <div v-if="activeStage" class="active-badge">
        <div class="active-title">
          <span class="pulse"></span>
          Активный этап: <strong>{{ activeStage.stage_name }}</strong>
        </div>
        <div class="active-details">
          <span>📍 Зона: <strong>{{ activeStage.zone || 'Вся площадка' }}</strong></span>
          <span>🚜 Нормативная техника: <strong>{{ activeStage.machinery_plan }}</strong></span>
          <span>🏢 Подрядчик: <strong>{{ activeStage.contractor }}</strong></span>
        </div>
      </div>
      <div v-else class="inactive-badge">
        На выбранную дату ({{ selectedDate }}) активных этапов в графике не предусмотрено.
      </div>
    </div>

    <!-- Visual Gantt Chart -->
    <GanttChart
      :rows="scheduleRows"
      :active-stage-name="activeStage?.stage_name || ''"
    />
  </div>
</template>

<style scoped>
.timeline-view {
  max-width: 1000px;
  margin: 0 auto;
  padding: 2rem 1rem 4rem;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
}
.view-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.view-header h2 {
  font-size: 1.8rem;
  color: #18312b;
  margin: 0 0 0.3rem;
}
.subtitle {
  color: #666;
  font-size: 0.95rem;
  margin: 0;
}
.upload-btn {
  background: #18312b;
  color: white;
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  display: inline-block;
  transition: background 0.2s;
}
.upload-btn:hover { background: #2b5a48; }
.upload-btn input { display: none; }

.error-banner {
  background: #fde8e8;
  color: #b52f2f;
  padding: 0.75rem 1rem;
  border-radius: 6px;
  margin-bottom: 1rem;
  font-weight: 500;
}

.date-selector-card {
  background: white;
  border-radius: 10px;
  padding: 1.25rem 1.5rem;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  margin-bottom: 1.5rem;
}
.date-input-group {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-bottom: 1rem;
}
.date-input-group input {
  padding: 0.5rem 0.8rem;
  border: 1px solid #ccc;
  border-radius: 6px;
  font-size: 0.95rem;
}
.active-badge {
  background: #e8f5ed;
  border-left: 4px solid #2b8a5a;
  padding: 1rem;
  border-radius: 0 6px 6px 0;
}
.active-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.05rem;
  margin-bottom: 0.5rem;
  color: #18312b;
}
.pulse {
  width: 10px;
  height: 10px;
  background: #2b8a5a;
  border-radius: 50%;
  box-shadow: 0 0 0 rgba(43, 138, 90, 0.4);
  animation: pulse 1.5s infinite;
}
@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(43, 138, 90, 0.7); }
  70% { box-shadow: 0 0 0 8px rgba(43, 138, 90, 0); }
  100% { box-shadow: 0 0 0 0 rgba(43, 138, 90, 0); }
}
.active-details {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
  font-size: 0.88rem;
  color: #333;
}
.inactive-badge {
  background: #f9f9f9;
  border: 1px dashed #ccc;
  padding: 0.8rem;
  border-radius: 6px;
  color: #777;
  font-size: 0.9rem;
}
</style>