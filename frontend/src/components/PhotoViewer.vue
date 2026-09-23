<script setup>
import { ref, watch, computed, nextTick } from 'vue'

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

const activeAnnotatedUrl = computed(
  () => props.annotatedImageUrl || props.imageUrl || props.debugImageUrl || '',
)

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

const getRuLabel = (className) => MACHINERY_RU[className] || className

const canvasRef = ref(null)
const naturalWidth = ref(0)
const naturalHeight = ref(0)
const showDebugImage = ref(true) // toggle between original+canvas vs debug image
const cachedImage = ref(null)

/**
 * Loads an image from a URL or ObjectURL and stores it in cachedImage.
 */
function loadImage(url) {
  if (!url) return
  const img = new Image()
  img.crossOrigin = 'anonymous'
  img.onload = () => {
    cachedImage.value = img
    renderCanvas()
  }
  img.src = url
}

function resolveImageSource() {
  if (props.imageFile) {
    const url = URL.createObjectURL(props.imageFile)
    loadImage(url)
  } else if (props.rawImageUrl) {
    loadImage(props.rawImageUrl)
  } else if (activeAnnotatedUrl.value) {
    loadImage(activeAnnotatedUrl.value)
  }
}

/**
 * Draws bounding boxes on the canvas overlaying the cached image.
 * This is used when showDebugImage is false (client-side overlay).
 */
function renderCanvas() {
  const canvas = canvasRef.value
  const img = cachedImage.value
  if (!canvas || !img) return

  const ctx = canvas.getContext('2d')
  const width = img.naturalWidth || img.width || 640
  const height = img.naturalHeight || img.height || 480

  canvas.width = width
  canvas.height = height
  naturalWidth.value = width
  naturalHeight.value = height

  ctx.clearRect(0, 0, width, height)
  ctx.drawImage(img, 0, 0, width, height)

  for (const det of props.detections) {
    const [x1, y1, x2, y2] = det.bbox
    const w = x2 - x1
    const h = y2 - y1

    // Box
    ctx.strokeStyle = '#00be46'
    ctx.lineWidth = 3
    ctx.strokeRect(x1, y1, w, h)

    // Label background
    const ruName = getRuLabel(det.class_name)
    const label = `${ruName} ${(det.confidence * 100).toFixed(0)}%`
    ctx.font = 'bold 16px sans-serif'
    const textMetrics = ctx.measureText(label)
    const textH = 22
    ctx.fillStyle = 'rgba(0, 190, 70, 0.85)'
    ctx.fillRect(x1, Math.max(0, y1 - textH), textMetrics.width + 8, textH)

    // Label text
    ctx.fillStyle = '#fff'
    ctx.fillText(label, x1 + 4, Math.max(16, y1 - 5))
  }
}

// Watchers
watch(
  [() => props.imageFile, () => props.rawImageUrl, () => activeAnnotatedUrl.value],
  () => {
    resolveImageSource()
  },
  { immediate: true },
)

watch(showDebugImage, async (isServer) => {
  if (!isServer) {
    await nextTick()
    if (!cachedImage.value) {
      resolveImageSource()
    } else {
      renderCanvas()
    }
  }
})

watch(
  () => props.detections,
  () => {
    renderCanvas()
  },
  { deep: true },
)
</script>

<template>
  <div class="photo-viewer" v-if="imageFile || activeAnnotatedUrl || rawImageUrl">
    <div class="viewer-header">
      <div class="header-left">
        <h3>📷 Результат анализа</h3>
        <a
          v-if="rawImageUrl"
          :href="rawImageUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="raw-link"
          @click.stop
          title="Открыть исходный файл без разметки (доказательная база ДГП)"
        >
          🔍 Исходный снимок (RAW)
        </a>
      </div>
      <label v-if="activeAnnotatedUrl && (imageFile || rawImageUrl)" class="toggle">
        <input type="checkbox" v-model="showDebugImage" />
        Серверная разметка
      </label>
    </div>

    <!-- Option 1: Server-side annotated image -->
    <div v-show="showDebugImage && activeAnnotatedUrl" class="image-container">
      <img :src="activeAnnotatedUrl" alt="Annotated construction site photo" class="result-image" />
    </div>

    <!-- Option 2: Client-side canvas overlay -->
    <div v-show="!showDebugImage || !activeAnnotatedUrl" class="image-container">
      <canvas ref="canvasRef" class="result-image"></canvas>
    </div>

    <!-- Detections list -->
    <div v-if="detections.length" class="detections-list">
      <span v-for="(det, i) in detections" :key="i" class="det-tag">
        {{ getRuLabel(det.class_name) }}
        <small>{{ (det.confidence * 100).toFixed(0) }}%</small>
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
  font-family: sans-serif;
}
.viewer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #eee;
  flex-wrap: wrap;
  gap: 0.5rem;
}
.header-left {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}
.raw-link {
  font-size: 0.8rem;
  color: #2b8a5a;
  text-decoration: none;
  background: #e8f5ed;
  padding: 0.25rem 0.6rem;
  border-radius: 4px;
  font-weight: 600;
  transition: background 0.2s;
  cursor: pointer;
}
.raw-link:hover {
  background: #d4ecdc;
}
.viewer-header h3 { margin: 0; font-size: 1.1rem; }
.toggle {
  display: flex; align-items: center; gap: 0.4rem;
  font-size: 0.85rem; cursor: pointer;
}
.image-container {
  padding: 0 1rem 1rem;
}
.result-image {
  width: 100%;
  height: auto;
  display: block;
  border-radius: 6px;
}
.detections-list {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  padding: 0 1.5rem 1.5rem;
}
.det-tag {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  padding: 0.35rem 0.8rem;
  background: #e0f5e9;
  color: #18312b;
  border-radius: 16px;
  font-size: 0.85rem;
  font-weight: 600;
}
.det-tag small {
  opacity: 0.65;
  font-weight: 400;
}
.no-detections {
  padding: 0 1.5rem 1.5rem;
  color: #888;
  font-style: italic;
}
</style>