import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    // In development, forward /api calls to FastAPI so the browser sees one origin.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
