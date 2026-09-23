<script setup>
defineProps({
  status: { type: String, default: 'OK' },
  explanation: { type: String, default: 'Загрузите снимок для анализа.' },
  missingMachinery: { type: Array, default: () => [] },
  unexpectedMachinery: { type: Array, default: () => [] },
  observationQuality: { type: String, default: '' },
  cameraRecommendation: { type: String, default: '' },
  modelIsConstructionSpecific: { type: Boolean, default: false },
  incidentId: { type: [Number, String], default: null },
})

const qualityMeta = {
  HIGH: {
    label: '🟢 Высокое качество ракурса (детальный план)',
    class: 'quality-high',
  },
  MEDIUM: {
    label: '🟡 Среднее качество ракурса',
    class: 'quality-medium',
  },
  LOW: {
    label: '🟠 Ограниченное качество (дальний ракурс / угол съемки)',
    class: 'quality-low',
  },
}

const statusLabels = {
  OK: '✅ Соответствует плану',
  WARNING: '⚠️ Требует внимания',
  CRITICAL: '🚨 Критическое отклонение',
  WAITING: '⏳ Ожидание анализа',
}

const downloadPdf = (id) => {
  if (!id) return
  const url = `/api/v1/monitoring/incidents/${id}/pdf`
  window.open(url, '_blank')
}
</script>

<template>
  <article :class="['incident-card', status.toLowerCase()]">
    <div class="status-header">
      <strong class="status-badge">{{ statusLabels[status] || status }}</strong>
      <span
        v-if="observationQuality"
        :class="['quality-badge', qualityMeta[observationQuality]?.class || '']"
      >
        {{ qualityMeta[observationQuality]?.label || observationQuality }}
      </span>
    </div>

    <!-- Camera angle recommendation for LOW quality -->
    <div v-if="observationQuality === 'LOW'" class="camera-recommendation-box">
      <div class="rec-icon">⚠️</div>
      <div class="rec-content">
        <strong>Рекомендация ДГП по ракурсу камеры:</strong>
        <p>{{ cameraRecommendation || 'Качество ракурса: LOW (дальний план / острый угол съемки с верхнего яруса). Рекомендуется скорректировать угол наклона или переключиться на секторную камеру въезда №2.' }}</p>
      </div>
    </div>

    <p class="explanation">{{ explanation }}</p>

    <div v-if="missingMachinery.length" class="machinery-section missing">
      <span class="section-label">Не хватает:</span>
      <span v-for="m in missingMachinery" :key="m" class="tag missing-tag">{{ m }}</span>
    </div>

    <div v-if="unexpectedMachinery.length" class="machinery-section unexpected">
      <span class="section-label">Нетипичная:</span>
      <span v-for="m in unexpectedMachinery" :key="m" class="tag unexpected-tag">{{ m }}</span>
    </div>

    <!-- 1-Click PDF Act generation button for DGP -->
    <div v-if="(status === 'WARNING' || status === 'CRITICAL') && incidentId" class="act-actions">
      <button class="pdf-btn" @click="downloadPdf(incidentId)" title="Сформировать юридически значимый Акт фиксации нарушений ДГП Москвы">
        📄 Сформировать Акт для ДГП (PDF)
      </button>
      <span class="pdf-hint">Официальный Акт строительного контроля с фотофиксацией и таблицей План-Факт</span>
    </div>

    <p v-if="!modelIsConstructionSpecific && status !== 'WAITING'" class="model-note">
      ℹ️ Используется базовая модель (COCO). Для точной детекции строительной техники
      необходимо дообучение на специализированном датасете.
    </p>
  </article>
</template>

<style scoped>
.incident-card {
  margin-top: 1.5rem;
  padding: 1.5rem;
  border-left: 5px solid #888;
  background: white;
  border-radius: 0 10px 10px 0;
  font-family: sans-serif;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}
.ok { border-color: #2b8a5a; }
.warning { border-color: #e8a317; }
.critical { border-color: #b52f2f; }
.waiting { border-color: #888; }

.status-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
.status-badge {
  font-size: 1.15rem;
}
.quality-badge {
  font-size: 0.8rem;
  padding: 0.3rem 0.7rem;
  border-radius: 12px;
  font-weight: 600;
  border: 1px solid transparent;
}
.quality-high {
  background: #e8f5ed;
  color: #1b6b3e;
  border-color: #c3e6cb;
}
.quality-medium {
  background: #fff8e1;
  color: #856404;
  border-color: #ffeeba;
}
.quality-low {
  background: #fff3cd;
  color: #995a00;
  border-color: #ffd8a8;
}

.camera-recommendation-box {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  background: #fdf7e7;
  border-left: 4px solid #f39c12;
  border-radius: 4px;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
}
.rec-icon {
  font-size: 1.2rem;
}
.rec-content strong {
  color: #8a5300;
  font-size: 0.85rem;
  display: block;
  margin-bottom: 0.25rem;
}
.rec-content p {
  margin: 0;
  font-size: 0.82rem;
  color: #444;
  line-height: 1.4;
}

.explanation {
  margin: 0 0 1rem;
  line-height: 1.5;
  color: #333;
}

.machinery-section {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-bottom: 0.5rem;
}
.section-label {
  font-weight: 700;
  font-size: 0.85rem;
  color: #555;
  margin-right: 0.3rem;
}
.tag {
  display: inline-block;
  padding: 0.2rem 0.6rem;
  border-radius: 12px;
  font-size: 0.8rem;
  font-weight: 600;
}
.missing-tag { background: #fde8e8; color: #b52f2f; }
.unexpected-tag { background: #fff5e0; color: #b87d00; }

.act-actions {
  margin-top: 1.25rem;
  padding-top: 1rem;
  border-top: 1px solid #edf2f7;
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}
.pdf-btn {
  background: #0a2540;
  color: #ffffff;
  border: none;
  padding: 0.6rem 1.2rem;
  font-size: 0.9rem;
  font-weight: 700;
  border-radius: 6px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  transition: background 0.2s, transform 0.1s;
  box-shadow: 0 2px 4px rgba(10, 37, 64, 0.2);
}
.pdf-btn:hover {
  background: #153965;
  transform: translateY(-1px);
}
.pdf-btn:active {
  transform: translateY(0);
}
.pdf-hint {
  font-size: 0.78rem;
  color: #666;
}

.model-note {
  margin: 1rem 0 0;
  font-size: 0.8rem;
  color: #888;
  line-height: 1.4;
}
</style>