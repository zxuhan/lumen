import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'

// Frontend and backend stay same-origin through the dev proxy, so httpOnly cookies and SSE need no cross-origin setup.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    // Bind the IPv4 loopback explicitly; otherwise Vite only listens on ::1 and direct connections to 127.0.0.1 are refused
    host: '127.0.0.1',
    port: 7301,
    strictPort: true,
    proxy: {
      '/api': { target: 'http://localhost:7302', changeOrigin: true },
      '/events': { target: 'http://localhost:7302', changeOrigin: true },
    },
  },
})
