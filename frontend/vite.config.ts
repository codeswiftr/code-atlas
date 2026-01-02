import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// Port 5174 - Code Atlas (CodeSwiftr)
export default defineConfig(({ mode }) => {
  // Load env file based on mode
  const env = loadEnv(mode, process.cwd(), '')
  const isProduction = mode === 'production'

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5174,
      host: 'localhost',
      // Proxy only in development
      proxy: isProduction ? undefined : {
        '/api': {
          target: env.VITE_API_URL || 'http://localhost:8002',
          changeOrigin: true,
        },
        '/ws': {
          target: env.VITE_WS_URL || 'ws://localhost:8002',
          ws: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      // Disable sourcemaps in production for smaller bundles
      sourcemap: !isProduction,
    },
    define: {
      // Make build info available at runtime
      __APP_VERSION__: JSON.stringify(process.env.npm_package_version || '0.0.0'),
      __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
    },
  }
})