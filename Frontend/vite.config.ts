import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api/agent': 'http://127.0.0.1:8787' },
  },
  preview: {
    proxy: { '/api/agent': 'http://127.0.0.1:8787' },
  },
})
