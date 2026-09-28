<script setup>
import { ref, watch, computed, nextTick, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  /** File object or Blob of the uploaded image. */
  imageFile: { type: [File, Blob], default: null },
  /** URL of the annotated image with bounding boxes drawn by backend. */
  debugImageUrl: { type: String, default: '' },
  annotatedImageUrl: { type: String, default: '' },
  imageUrl: { type: String, default: '' },
  /** URL of the raw unmodified original photo. */
  rawImageUrl: { type: String, default: '' },
  /** Array of DetectionItem objects from the API. */
  detections: { type: Array, default: () => [] },
})

const MACHINERY_RU = {
  excavator: 'Экскаватор',
  dump_truck: 'Самосвал',
  roller: 'Каток',
  crane_manipulator: 'Кран-манипулятор',
  manipulator: 'Кран-манипулятор',
  bulldozer: 'Бульдозер',
  mobile_crane: 'Автокран',
  concrete_mixer: 'Бетоносмеситель',
  truck: 'Грузовик',
}

const getRuLabel = (className) => MACHINERY_RU[className] || className

// Mode: 'canvas' (interactive client overlay) | 'annotated' (server image) | 'raw' (unmodified photo)
const viewMode = ref('canvas')

const localBlobUrl = ref('')
const imgRef = ref(null)
const canvasRef = ref(null)
const wrapperRef = ref(null)

const activeAnnotatedUrl = computed(
  () => props.annotatedImageUrl || props.imageUrl || props.debugImageUrl || '',
)

const activeRawUrl = computed(
  () => localBlobUrl.value || props.rawImageUrl || '',
)

const hasAnnotated = computed(() => !!activeAnnotatedUrl.value)
const hasRaw = computed(() => !!activeRawUrl.value)

// What to show in the underlying <img>
const currentDisplaySrc = computed(() => {
  if (viewMode.value === 'annotated') {
    return activeAnnotatedUrl.value || activeRawUrl.value
  }
  // For 'canvas' and 'raw', strictly prioritize clean raw image so no duplicate boxes appear!
  return activeRawUrl.value || activeAnnotatedUrl.value
})

function setMode(mode) {
  viewMode.value = mode
  if (mode === 'canvas') {
    nextTick(() => {
      drawCanvas()
    })
  }
}

function onImageLoaded() {
  if (viewMode.value === 'canvas') {
    drawCanvas()
  }
}

function drawCanvas() {
  const canvas = canvasRef.value
  const img = imgRef.value
  if (!canvas || !img) return
  if (viewMode.value !== 'canvas') return

  const nw = img.naturalWidth
  const nh = img.naturalHeight
  if (!nw || !nh) return

  // Sync canvas internal coordinate space with image native resolution
  canvas.width = nw
  canvas.height = nh

  const ctx = canvas.getContext('2d')
  ctx.clearRect(0, 0, nw, nh)

  // Avoid drawing double boxes if raw image is not yet available and annotated is used
  if (!activeRawUrl.value && activeAnnotatedUrl.value) {
    return
  }

  const detections = props.detections || []
  if (!detections.length) return

  const fontSize = Math.max(14, Math.round(Math.min(nw, nh) * 0.024))
  ctx.font = `bold ${fontSize}px sans-serif`

  for (const det of detections) {
    const bbox = det.bbox
    if (!bbox || bbox.length !== 4) continue
    const [x1, y1, x2, y2] = bbox
    const w = x2 - x1
    const h = y2 - y1

    // Box border (Emerald green)
    ctx.strokeStyle = '#00be46'
    ctx.lineWidth = Math.max(2, Math.round(nw * 0.003))
    ctx.strokeRect(x1, y1, w, h)

    // Russian label text: e.g. "Экскаватор 85%"
    const ruName = getRuLabel(det.class_name)
    const conf = Math.round((det.confidence || 0) * 100)
    const label = `${ruName} ${conf}%`

    const textMetrics = ctx.measureText(label)
    const textW = textMetrics.width
    const padX = 8
    const padY = 5
    const badgeH = fontSize + padY * 2
    const badgeW = textW + padX * 2

    const badgeY = y1 - badgeH >= 0 ? y1 - badgeH : y1

    // Background badge
    ctx.fillStyle = 'rgba(0, 190, 70, 0.92)'
    ctx.fillRect(x1, badgeY, badgeW, badgeH)

    // Text
    ctx.fillStyle = '#ffffff'
    ctx.textBaseline = 'top'
    ctx.fillText(label, x1 + padX, badgeY + padY)
  }
}

// Watchers
watch(
  () => props.imageFile,
  (newFile) => {
    if (localBlobUrl.value) {
      URL.revokeObjectURL(localBlobUrl.value)
      localBlobUrl.value = ''
    }
    if (newFile) {
      localBlobUrl.value = URL.createObjectURL(newFile)
    }
  },
  { immediate: true },
)

watch(
  [() => props.detections, () => currentDisplaySrc.value],
  () => {
    nextTick(() => {
      if (viewMode.value === 'canvas') {
        drawCanvas()
      }
    })
  },
  { deep: true },
)

watch(
  [() => hasRaw.value, () => hasAnnotated.value],
  ([rawAvail, annAvail]) => {
    if (!rawAvail && annAvail && viewMode.value === 'raw') {
      viewMode.value = 'annotated'
    }
  },
)

let resizeObserver = null

onMounted(() => {
  if (wrapperRef.value && typeof ResizeObserver !== 'undefined') {
    resizeObserver = new ResizeObserver(() => {
      if (viewMode.value === 'canvas') {
        drawCanvas()
      }
    })
    resizeObserver.observe(wrapperRef.value)
  }
})

onBeforeUnmount(() => {
  if (resizeObserver) {
    resizeObserver.disconnect()
  }
  if (localBlobUrl.value) {
    URL.revokeObjectURL(localBlobUrl.value)
  }
})
</script>

<template>
  <div class="photo-viewer" v-if="currentDisplaySrc">
    <!-- Header with title, Mode Tabs and RAW Link -->
    <div class="viewer-header">
      <div class="header-left">
        <h3>📷 Результат анализа</h3>
        <div class="view-mode-tabs">
          <button
            type="button"
            class="mode-btn"
            :class="{ active: viewMode === 'canvas' }"
            @click="setMode('canvas')"
            title="Интерактивный слой рамок спецтехники поверх чистого кадра"
          >
            🎯 Интерактивная разметка
          </button>
          <button
            v-if="hasAnnotated"
            type="button"
            class="mode-btn"
            :class="{ active: viewMode === 'annotated' }"
            @click="setMode('annotated')"
            title="Серверный снимок с впеченными подписями ДГП"
          >
            🖼️ Серверный кадр
          </button>
          <button
            v-if="hasRaw"
            type="button"
            class="mode-btn"
            :class="{ active: viewMode === 'raw' }"
            @click="setMode('raw')"
            title="Оригинальный снимок без каких-либо рамок"
          >
            🔍 Чистый RAW
          </button>
        </div>
      </div>

      <div class="header-right" v-if="rawImageUrl">
        <a
          :href="rawImageUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="raw-link"
          @click.stop
          title="Открыть исходный файл без разметки в отдельной вкладке (доказательная база ДГП)"
        >
          ↗ Открыть RAW файл
        </a>
      </div>
    </div>

    <!-- Image + Canvas Wrapper -->
    <div class="image-container">
      <div class="viewer-media-wrapper" ref="wrapperRef">
        <img
          ref="imgRef"
          :src="currentDisplaySrc"
          alt="Снимок строительной площадки"
          class="result-image"
          @load="onImageLoaded"
        />
        <canvas
          v-show="viewMode === 'canvas'"
          ref="canvasRef"
          class="canvas-overlay"
        ></canvas>
      </div>
    </div>

    <!-- Detections list -->
    <div v-if="detections.length" class="detections-list">
      <span v-for="(det, i) in detections" :key="i" class="det-tag">
        {{ getRuLabel(det.class_name) }}
        <small>{{ Math.round((det.confidence || 0) * 100) }}%</small>
      </span>
    </div>
    <p v-else class="no-detections">Объекты строительной техники не обнаружены.</p>
  </div>
</template>

<style scoped>
.photo-viewer {
  margin-top: 1.5rem;
  background: white;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  font-family: sans-serif;
}
.viewer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.85rem 1.25rem;
  border-bottom: 1px solid #eef0f3;
  flex-wrap: wrap;
  gap: 0.75rem;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}
.header-left h3 {
  margin: 0;
  font-size: 1.05rem;
  color: #1a202c;
}
.view-mode-tabs {
  display: inline-flex;
  background: #f1f3f5;
  border-radius: 8px;
  padding: 3px;
  gap: 2px;
}
.mode-btn {
  border: none;
  background: transparent;
  color: #4b5563;
  padding: 0.35rem 0.75rem;
  border-radius: 6px;
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  white-space: nowrap;
}
.mode-btn:hover {
  color: #111827;
  background: rgba(255, 255, 255, 0.5);
}
.mode-btn.active {
  background: white;
  color: #0f766e;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.08);
}
.header-right {
  display: flex;
  align-items: center;
}
.raw-link {
  font-size: 0.8rem;
  color: #2b8a5a;
  text-decoration: none;
  background: #e8f5ed;
  padding: 0.3rem 0.65rem;
  border-radius: 6px;
  font-weight: 600;
  transition: background 0.2s;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
}
.raw-link:hover {
  background: #d4ecdc;
}
.image-container {
  padding: 1rem;
}
.viewer-media-wrapper {
  position: relative;
  width: 100%;
  display: block;
  line-height: 0;
  border-radius: 8px;
  overflow: hidden;
  background: #000;
}
.result-image {
  width: 100%;
  height: auto;
  display: block;
  user-select: none;
}
.canvas-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}
.detections-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0 1.25rem 1.25rem;
}
.det-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.35rem 0.8rem;
  background: #e0f5e9;
  color: #18312b;
  border-radius: 16px;
  font-size: 0.85rem;
  font-weight: 600;
}
.det-tag small {
  opacity: 0.7;
  font-weight: 500;
}
.no-detections {
  padding: 0 1.25rem 1.25rem;
  color: #888;
  font-style: italic;
  margin: 0;
}
</style>