<template>
  <nav class="navbar">
    <div class="brand">
      <span class="logo">🏗️</span>
      <span class="title">BUILD / EYE</span>
    </div>
    <span class="subtitle">LIVE SITE MONITOR</span>
  </nav>
</template>

<style scoped>
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 2rem;
  background: #18312b;
  color: white;
  font-family: sans-serif;
}
.brand {
  display: flex;
  align-items: center;
  gap: 0.7rem;
}
.logo { font-size: 1.8rem; }
.title {
  font-size: 1.3rem;
  font-weight: 800;
  letter-spacing: 0.2rem;
}
.subtitle {
  font-size: 0.75rem;
  letter-spacing: 0.3rem;
  opacity: 0.6;
  text-transform: uppercase;
}
</style>