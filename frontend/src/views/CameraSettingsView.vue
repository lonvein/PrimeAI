<script setup>
import { ref } from 'vue'

const cameras = ref([
  {
    id: 'CAM-01',
    name: 'Камера 1 (Обзорная мачта)',
    sector: 'Сектор А (Котлован)',
    status: 'online',
    resolution: '2560x1440 (2K)',
    fps: 25,
    rtspUrl: 'rtsp://admin:pass@192.168.1.101:554/stream1',
    assignedStages: ['Земляные работы / Котлован', 'Устройство фундамента / Сваи'],
    lastPing: '12 мс',
  },
  {
    id: 'CAM-02',
    name: 'Камера 2 (КПП / Въездные ворота)',
    sector: 'Периметр и въезд',
    status: 'online',
    resolution: '1920x1080 (FHD)',
    fps: 30,
    rtspUrl: 'rtsp://admin:pass@192.168.1.102:554/stream1',
    assignedStages: ['Обустройство площадки и временных дорог', 'Благоустройство и дорожные работы'],
    lastPing: '18 мс',
  },
  {
    id: 'CAM-03',
    name: 'Камера 3 (Башенный кран №1)',
    sector: 'Сектор Б (Корпус 1)',
    status: 'online',
    resolution: '3840x2160 (4K)',
    fps: 20,
    rtspUrl: 'rtsp://admin:pass@192.168.1.103:554/stream1',
    assignedStages: ['Монолитные работы надземной части'],
    lastPing: '24 мс',
  },
  {
    id: 'CAM-04',
    name: 'Камера 4 (Южный периметр)',
    sector: 'Сектор А (Основание)',
    status: 'standby',
    resolution: '1920x1080 (FHD)',
    fps: 15,
    rtspUrl: 'rtsp://admin:pass@192.168.1.104:554/stream1',
    assignedStages: ['Устройство свайного поля'],
    lastPing: '—',
  },
])

const isTesting = ref(false)
const testMessage = ref('')

function testAllConnections() {
  isTesting.value = true
  testMessage.value = 'Опрос видеопотоков RTSP...'
  setTimeout(() => {
    isTesting.value = false
    testMessage.value = '✅ 3 из 4 камер доступны. Задержка сети в норме (<30 мс).'
  }, 1200)
}
</script>

<template>
  <div class="camera-settings-view">
    <header class="view-header">
      <div>
        <h2>🎥 Конфигурация камер и секторов</h2>
        <p class="subtitle">Управление источниками видеопотоков и привязка к зонам СМР</p>
      </div>

      <button class="test-btn" @click="testAllConnections" :disabled="isTesting">
        {{ isTesting ? 'Проверка...' : '⚡ Проверить статус камер' }}
      </button>
    </header>

    <div v-if="testMessage" class="status-alert">
      {{ testMessage }}
    </div>

    <!-- Recommendations Card -->
    <div class="guidelines-card">
      <div class="guideline-item">
        <span class="guide-icon">📐</span>
        <div>
          <strong>Угол обзора:</strong>
          <p>Оптимальная высота подвеса — 6–12 м под углом 30–45° для минимизации перекрытия техники отвалами грунта.</p>
        </div>
      </div>
      <div class="guideline-item">
        <span class="guide-icon">🔄</span>
        <div>
          <strong>Многоракурсный мониторинг:</strong>
          <p>Для исключения слепых зон котлована задействуйте не менее 2 камер (основной сектор + въездной пандус).</p>
        </div>
      </div>
    </div>

    <!-- Camera List -->
    <div class="camera-grid">
      <div v-for="cam in cameras" :key="cam.id" class="camera-card">
        <div class="cam-header">
          <div class="cam-title">
            <span class="cam-id">{{ cam.id }}</span>
            <strong>{{ cam.name }}</strong>
          </div>
          <span :class="['status-dot', cam.status]"></span>
        </div>

        <div class="cam-body">
          <div class="cam-meta">
            <span>📍 Зона: <strong>{{ cam.sector }}</strong></span>
            <span>📹 Разрешение: <strong>{{ cam.resolution }}</strong></span>
            <span>⚡ Пинг: <strong>{{ cam.lastPing }}</strong></span>
          </div>

          <div class="rtsp-box">
            <code>{{ cam.rtspUrl }}</code>
          </div>

          <div class="assigned-stages">
            <span class="stages-label">Контролируемые этапы:</span>
            <span v-for="st in cam.assignedStages" :key="st" class="stage-tag">
              {{ st }}
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.camera-settings-view {
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
.test-btn {
  background: #18312b;
  color: white;
  border: 0;
  padding: 0.7rem 1.3rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.9rem;
  transition: background 0.2s;
}
.test-btn:hover:not(:disabled) { background: #2b5a48; }
.test-btn:disabled { opacity: 0.6; cursor: wait; }

.status-alert {
  background: #e8f5ed;
  border-left: 4px solid #2b8a5a;
  padding: 0.8rem 1.2rem;
  border-radius: 0 6px 6px 0;
  margin-bottom: 1.5rem;
  font-size: 0.95rem;
  color: #18312b;
  font-weight: 500;
}

.guidelines-card {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1rem;
  background: #fdfaf3;
  border: 1px solid #faeccb;
  border-radius: 8px;
  padding: 1.2rem;
  margin-bottom: 1.5rem;
}
.guideline-item {
  display: flex;
  gap: 0.8rem;
  font-size: 0.88rem;
  line-height: 1.4;
  color: #554422;
}
.guide-icon { font-size: 1.4rem; }
.guideline-item p { margin: 0.2rem 0 0; }

.camera-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(440px, 1fr));
  gap: 1.2rem;
}
.camera-card {
  background: white;
  border-radius: 10px;
  padding: 1.25rem;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06);
  border-top: 3px solid #18312b;
}
.cam-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.9rem;
}
.cam-title {
  display: flex;
  align-items: center;
  gap: 0.6rem;
}
.cam-id {
  background: #18312b;
  color: white;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
}
.status-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}
.status-dot.online { background: #2b8a5a; box-shadow: 0 0 6px #2b8a5a; }
.status-dot.standby { background: #e8a317; }
.status-dot.offline { background: #b52f2f; }

.cam-meta {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.88rem;
  color: #444;
  margin-bottom: 0.75rem;
}
.rtsp-box {
  background: #f4f6f5;
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  margin-bottom: 0.75rem;
}
.rtsp-box code {
  font-family: monospace;
  font-size: 0.78rem;
  color: #225544;
  word-break: break-all;
}

.assigned-stages {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.stages-label {
  font-size: 0.78rem;
  font-weight: 700;
  color: #777;
  text-transform: uppercase;
}
.stage-tag {
  display: inline-block;
  background: #eef2f0;
  color: #18312b;
  font-size: 0.8rem;
  padding: 0.2rem 0.5rem;
  border-radius: 4px;
  font-weight: 500;
}
</style>