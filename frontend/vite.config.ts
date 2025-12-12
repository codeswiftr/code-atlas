import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// Port 5174 - Code Atlas (CodeSwiftr)
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5174,
    host: 'localhost',
    proxy: {
      '/api': {
        target: 'http://localhost:8002',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8002',
        ws: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
  },
})