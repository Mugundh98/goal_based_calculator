import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/ · https://vitest.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    // In development, forward /api calls to FastAPI so the browser sees one origin.
    // API_PROXY_TARGET points it at a backend on another port.
    proxy: {
      '/api': process.env.API_PROXY_TARGET ?? 'http://127.0.0.1:8000',
    },
  },
  test: {
    // Component tests run in a simulated browser (jsdom); end-to-end tests live in e2e/.
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.{ts,tsx}', 'src/test/**', 'src/main.tsx', 'src/vite-env.d.ts'],
      reporter: ['text-summary', 'text'],
    },
  },
})
