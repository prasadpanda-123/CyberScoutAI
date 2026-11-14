import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

const apiTarget = process.env.CYBERSCOUT_API_TARGET || 'http://127.0.0.1:5000'

export default defineConfig({
  base: '/static/react/',
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
    dedupe: ['react', 'react-dom', 'react-router', 'react-router-dom'],
  },
  build: {
    outDir: '../dashboard/static/react',
    emptyOutDir: false,
    rollupOptions: {
      output: {
        entryFileNames: 'assets/index.js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name][extname]',
      },
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        secure: false,
      },
      '/admin/api': {
        target: apiTarget,
        changeOrigin: true,
        secure: false,
      },
      '/login': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/logout': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/register': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/forgot-password': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/reset-password': {
        target: apiTarget,
        changeOrigin: true,
      },
      '/admin': {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
})
