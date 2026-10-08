import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'node:path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.ts',
    globals: true,
  },
  server: {
    host: true, // bind 0.0.0.0 so the dev server is reachable from outside the container
    port: 5173,
    strictPort: true,
    watch: {
      // Bind-mounted volumes don't always emit inotify events on Linux hosts.
      usePolling: process.env.VITE_USE_POLLING === 'true',
    },
  },
})
