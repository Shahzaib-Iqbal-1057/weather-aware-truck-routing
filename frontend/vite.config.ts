/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  build: {
    // MapLibre alone is ~1 MB minified (~290 kB gzipped). It is lazy-loaded in its own chunk.
    chunkSizeWarningLimit: 1100,
  },
  server: {
    // In dev, forward API calls to Django so the browser sees one origin (no CORS).
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
  },
})
