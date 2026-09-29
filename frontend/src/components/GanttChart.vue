<script setup>
import { computed } from 'vue'

const props = defineProps({
  /** Array of ScheduleRow objects from the API. */
  rows: { type: Array, default: () => [] },
  /** Currently active stage name (if known). */
  activeStageName: { type: String, default: '' },
})

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

function formatDateRange(start, end) {
  return `${formatDate(start)} – ${formatDate(end)}`
}

// Compute timeline bars.
const timelineData = computed(() => {
  if (!props.rows.length) return { stages: [], minDate: null, maxDate: null, totalDays: 0 }

  const dates = props.rows.flatMap(r => [r.date_start, r.date_end].filter(Boolean)).map(d => new Date(d))
  if (!dates.length) return { stages: [], minDate: null, maxDate: null, totalDays: 0 }

  const minDate = new Date(Math.min(...dates))
  const maxDate = new Date(Math.max(...dates))
  const totalDays = Math.max(1, (maxDate - minDate) / (1000 * 60 * 60 * 24))

  const stages = props.rows.map(row => {
    const start = row.date_start ? new Date(row.date_start) : minDate
    const end = row.date_end ? new Date(row.date_end) : maxDate
    const offsetDays = (start - minDate) / (1000 * 60 * 60 * 24)
    const durationDays = (end - start) / (1000 * 60 * 60 * 24)
    return {
      ...row,
      leftPct: (offsetDays / totalDays) * 100,
      widthPct: Math.max(2, (durationDays / totalDays) * 100),
      isActive: row.stage_name === props.activeStageName,
      isCompleted: Boolean(row.is_completed),
    }
  })

  return { stages, minDate, maxDate, totalDays }
})
</script>

<template>
  <div class="gantt-container" v-if="rows.length">
    <h3>📅 График строительных работ</h3>

    <div class="gantt-chart">
      <div
        v-for="(stage, i) in timelineData.stages"
        :key="i"
        class="gantt-row"
        :class="{ active: stage.isActive, completed: stage.isCompleted }"
      >
        <div class="gantt-label">
          <div class="stage-title-wrap">
            <span class="stage-name" :class="{ completed: stage.isCompleted }">
              {{ stage.stage_name }}
            </span>
            <span v-if="stage.isCompleted" class="badge-completed">✓ Завершен</span>
          </div>
          <span class="stage-dates">{{ formatDateRange(stage.date_start, stage.date_end) }}</span>
        </div>
        <div class="gantt-track">
          <div
            class="gantt-bar"
            :class="{ active: stage.isActive, completed: stage.isCompleted }"
            :style="{ left: stage.leftPct + '%', width: stage.widthPct + '%' }"
          >
            <span class="bar-label" v-if="stage.widthPct > 15">
              {{ stage.days || '' }} дн.
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Machinery details table -->
    <table class="machinery-table">
      <thead>
        <tr>
          <th>Этап</th>
          <th>Нормативная техника</th>
          <th>Подрядчик</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="(row, i) in rows"
          :key="i"
          :class="{ active: row.stage_name === activeStageName, completed: row.is_completed }"
        >
          <td>
            <span :class="{ 'completed-name': row.is_completed }">{{ row.stage_name }}</span>
            <span v-if="row.is_completed" class="badge-completed ml-2">✓ Завершен</span>
          </td>
          <td>{{ row.machinery_plan || '—' }}</td>
          <td>{{ row.contractor || '—' }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.gantt-container {
  margin-top: 1.5rem;
  background: white;
  border-radius: 10px;
  padding: 1.5rem;
  font-family: sans-serif;
}
.gantt-container h3 {
  margin: 0 0 1rem;
  font-size: 1.1rem;
}

.gantt-chart {
  display: grid;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
}
.gantt-row {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 0.75rem;
  align-items: center;
}
.gantt-row.active .gantt-label { font-weight: 700; }
.gantt-row.completed {
  opacity: 0.85;
}

.gantt-label {
  display: flex;
  flex-direction: column;
  font-size: 0.85rem;
  line-height: 1.3;
}
.stage-title-wrap {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-wrap: wrap;
}
.stage-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}
.stage-name.completed, .completed-name {
  text-decoration: line-through;
  color: #64748b;
}
.badge-completed {
  background: #dcfce7;
  color: #15803d;
  font-size: 0.68rem;
  font-weight: 700;
  padding: 0.15rem 0.45rem;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
}
.ml-2 {
  margin-left: 0.4rem;
}
.stage-dates {
  color: #888;
  font-size: 0.75rem;
}

.gantt-track {
  position: relative;
  height: 28px;
  background: #f0f0f0;
  border-radius: 4px;
  overflow: hidden;
}
.gantt-bar {
  position: absolute;
  top: 3px;
  bottom: 3px;
  background: #7eb9a0;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}
.gantt-bar.active {
  background: #2b8a5a;
}
.gantt-bar.completed {
  background: #94a3b8;
}
.bar-label {
  font-size: 0.7rem;
  color: white;
  font-weight: 600;
  white-space: nowrap;
}

/* Machinery table */
.machinery-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
.machinery-table th {
  text-align: left;
  padding: 0.5rem;
  border-bottom: 2px solid #ddd;
  font-weight: 700;
  color: #555;
}
.machinery-table td {
  padding: 0.5rem;
  border-bottom: 1px solid #eee;
}
.machinery-table tr.active {
  background: #e8f5ed;
  font-weight: 600;
}
.machinery-table tr.completed {
  background: #f8fafc;
}
</style>