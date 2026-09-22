<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'

const props = defineProps({
  /** File object or Blob of the uploaded image. */
  imageFile: { type: [File, Blob], default: null },
  /** URL of the debug image with bounding boxes drawn by backend. */
  debugImageUrl: { type: String, default: '' },
  /** Array of DetectionItem objects from the API. */
  detections: { type: Array, default: () => [] },
})

const canvasRef = ref(null)
const naturalWidth = ref(0)
const naturalHeight = ref(0)
const showDebugImage = ref(true) // toggle between original+canvas vs debug image

/**
 * Draws bounding boxes on the canvas overlaying the uploaded image.
 * This is used when showDebugImage is false (client-side overlay).
 */
function drawBoxes(img) {
  const canvas = canvasRef.value
  if (!canvas || !img) return

  const ctx = canvas.getContext('2d')
  canvas.width = img.naturalWidth
  canvas.height = img.naturalHeight
  naturalWidth.value = img.naturalWidth
  naturalHeight.value = img.naturalHeight

  ctx.drawImage(img, 0, 0)

  for (const det of props.detections) {
    const [x1, y1, x2, y2] = det.bbox
    const w = x2 - x1
    const h = y2 - y1

    // Box
    ctx.strokeStyle = '#00be46'
    ctx.lineWidth = 3
    ctx.strokeRect(x1, y1, w, h)

    // Label background
    const label = `${det.class_name} ${(det.confidence * 100).toFixed(0)}%`
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

// When imageFile changes, draw on canvas.
watch(
  () => props.imageFile,
  async (file) => {
    if (!file) return
    await nextTick()
    const img = new Image()
    img.onload = () => drawBoxes(img)
    img.src = URL.createObjectURL(file)
  },
)
</script>

<template>
  <div class="photo-viewer" v-if="imageFile || debugImageUrl">
    <div class="viewer-header">
      <h3>📷 Результат анализа</h3>
      <label v-if="debugImageUrl && imageFile" class="toggle">
        <input type="checkbox" v-model="showDebugImage" />
        Серверная разметка
      </label>
    </div>

    <!-- Option 1: Server-side annotated image -->
    <div v-if="showDebugImage && debugImageUrl" class="image-container">
      <img :src="debugImageUrl" alt="Annotated construction site photo" class="result-image" />
    </div>

    <!-- Option 2: Client-side canvas overlay -->
    <div v-else-if="imageFile" class="image-container">
      <canvas ref="canvasRef" class="result-image"></canvas>
    </div>

    <!-- Detections list -->
    <div v-if="detections.length" class="detections-list">
      <span v-for="(det, i) in detections" :key="i" class="det-tag">
        {{ det.class_name }}
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
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.5rem 0.5rem;
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