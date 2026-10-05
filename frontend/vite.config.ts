import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// В разработке API — бэкенд на :8000; на стенде /api проксирует nginx (nginx.conf).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
