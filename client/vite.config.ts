import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../src/dropmcp/static/dist',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/catalog': 'http://localhost:8000',
      '/api': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/icon.svg': 'http://localhost:8000',
      '/favicon.svg': 'http://localhost:8000',
    },
  },
})
