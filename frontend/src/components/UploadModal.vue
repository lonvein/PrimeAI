<script setup>
import { ref } from 'vue'
import { api } from '../services/api'

const emit = defineEmits(['analyzed'])
const stageName = ref('Земляные работы / Котлован')
const selectedFile = ref(null)
const previewUrl = ref('')
const isLoading = ref(false)
const errorMessage = ref('')

const stages = [
  'Подготовка территории / Демонтаж',
  'Земляные работы / Котлован',
  'Устройство фундамента / Сваи',
  'Монолитные работы надземной части',
  'Благоустройство и дорожные работы',
]

function selectFile(event) {
  const file = event.target.files[0] || null
  selectedFile.value = file
  errorMessage.value = ''
  if (file) {
    previewUrl.value = URL.createObjectURL(file)
  } else {
    previewUrl.value = ''
  }
}

async function analyze() {
  if (!selectedFile.value) {
    errorMessage.value = 'Выберите фотографию строительной площадки.'
    return
  }

  isLoading.value = true
  errorMessage.value = ''
  const formData = new FormData()
  formData.append('image', selectedFile.value)
  formData.append('stage_name', stageName.value)

  try {
    const { data } = await api.post('/analyze', formData)
    // Emit the full API response + the local file for PhotoViewer.
    emit('analyzed', { ...data, _localFile: selectedFile.value })
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || 'Не удалось выполнить анализ.'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <form class="upload-form" @submit.prevent="analyze">
    <label>
      Этап СМР
      <select v-model="stageName">
        <option v-for="s in stages" :key="s" :value="s">{{ s }}</option>
      </select>
    </label>

    <label class="file-label">
      Фотография площадки
      <input type="file" accept="image/*" @change="selectFile" />
    </label>

    <!-- Image preview before analysis -->
    <div v-if="previewUrl" class="preview">
      <img :src="previewUrl" alt="Preview" />
    </div>

    <button type="submit" :disabled="isLoading">
      {{ isLoading ? 'Анализируем...' : '📸 Проанализировать снимок' }}
    </button>
    <p v-if="errorMessage" class="error">{{ errorMessage }}</p>
  </form>
</template>

<style scoped>
.upload-form {
  display: grid;
  gap: 1rem;
  padding: 1.5rem;
  background: white;
  border-radius: 10px;
  font-family: sans-serif;
}
label {
  display: grid;
  gap: 0.4rem;
  font-weight: 700;
}
select, input[type="file"], button {
  padding: 0.7rem;
  font: inherit;
}
select {
  border: 2px solid #ddd;
  border-radius: 6px;
  background: #fafafa;
}
button {
  cursor: pointer;
  border: 0;
  background: #18312b;
  color: white;
  border-radius: 6px;
  font-weight: 700;
  font-size: 1rem;
  padding: 0.9rem;
  transition: background 0.2s;
}
button:hover:not(:disabled) { background: #2b5a48; }
button:disabled { cursor: wait; opacity: 0.6; }
.error { color: #b52f2f; margin: 0; }
.preview {
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid #e0e0e0;
}
.preview img {
  width: 100%;
  height: auto;
  display: block;
  max-height: 300px;
  object-fit: cover;
}
</style>