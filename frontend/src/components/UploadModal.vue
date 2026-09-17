<script setup>
import { ref } from 'vue'
import { api } from '../services/api'

const emit = defineEmits(['analyzed'])
const stageName = ref('Земляные работы / Котлован')
const selectedFile = ref(null)
const isLoading = ref(false)
const errorMessage = ref('')

function selectFile(event) {
	selectedFile.value = event.target.files[0] || null
	errorMessage.value = ''
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
		emit('analyzed', data)
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
				<option>Подготовка территории / Демонтаж</option>
				<option>Земляные работы / Котлован</option>
				<option>Устройство фундамента / Сваи</option>
				<option>Монолитные работы надземной части</option>
				<option>Благоустройство и дорожные работы</option>
			</select>
		</label>
		<label>
			Фотография площадки
			<input type="file" accept="image/*" @change="selectFile" />
		</label>
		<button type="submit" :disabled="isLoading">
			{{ isLoading ? 'Анализируем...' : 'Проанализировать снимок' }}
		</button>
		<p v-if="errorMessage" class="error">{{ errorMessage }}</p>
	</form>
</template>

<style scoped>
.upload-form { display: grid; gap: 1rem; padding: 1.5rem; background: white; border-radius: 10px; font-family: sans-serif; }
label { display: grid; gap: .4rem; font-weight: 700; }
select, input, button { padding: .7rem; font: inherit; }
button { cursor: pointer; border: 0; background: #18312b; color: white; border-radius: 6px; }
button:disabled { cursor: wait; opacity: .6; }
.error { color: #b52f2f; margin: 0; }
</style>