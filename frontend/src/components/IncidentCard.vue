<script setup>
defineProps({
  status: { type: String, default: 'OK' },
  explanation: { type: String, default: 'Загрузите снимок для анализа.' },
  missingMachinery: { type: Array, default: () => [] },
  unexpectedMachinery: { type: Array, default: () => [] },
  observationQuality: { type: String, default: '' },
  modelIsConstructionSpecific: { type: Boolean, default: false },
})

const qualityLabels = {
  HIGH: '🟢 Высокая достоверность',
  MEDIUM: '🟡 Средняя достоверность',
  LOW: '🔴 Низкая достоверность (модель не загружена)',
}

const statusLabels = {
  OK: '✅ Соответствует плану',
  WARNING: '⚠️ Требует внимания',
  CRITICAL: '🚨 Критическое отклонение',
  WAITING: '⏳ Ожидание анализа',
}
</script>

<template>
  <article :class="['incident-card', status.toLowerCase()]">
    <div class="status-header">
      <strong class="status-badge">{{ statusLabels[status] || status }}</strong>
      <span v-if="observationQuality" class="quality-badge">
        {{ qualityLabels[observationQuality] || observationQuality }}
      </span>
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
  padding: 0.25rem 0.6rem;
  background: #f5f5f5;
  border-radius: 12px;
  color: #555;
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

.model-note {
  margin: 1rem 0 0;
  font-size: 0.8rem;
  color: #888;
  line-height: 1.4;
}
</style>