import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Vite + Vitest config (AGENTS.md §1.1). Dev proxy routes /api and /ws to the
// FastAPI backend on :8000 (docs/dashboard.md §6).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      // 127.0.0.1, not localhost: localhost may resolve to ::1 where the
      // backend (bound to 127.0.0.1) is not listening (docs/dashboard.md §6).
      '/api': 'http://127.0.0.1:8000',
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
  },
})
