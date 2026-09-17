<script setup>
defineProps({
	status: { type: String, default: 'OK' },
	explanation: { type: String, default: 'Загрузите снимок для анализа.' },
	missingMachinery: { type: Array, default: () => [] },
	unexpectedMachinery: { type: Array, default: () => [] },
})
</script>

<template>
	<article :class="status.toLowerCase()">
		<strong>{{ status }}</strong>
		<p>{{ explanation }}</p>
		<p v-if="missingMachinery.length">Не хватает: {{ missingMachinery.join(', ') }}</p>
		<p v-if="unexpectedMachinery.length">Нетипичная техника: {{ unexpectedMachinery.join(', ') }}</p>
	</article>
</template>

<style scoped>article { margin-top: 2rem; padding: 1.5rem; border-left: 5px solid #bb4d2b; background: white; font-family: sans-serif; } .ok { border-color: #2b8a5a; } .critical { border-color: #b52f2f; }</style>