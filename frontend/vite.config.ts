import path from 'node:path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, import.meta.dirname, 'VITE_')
  const apiProxyTarget =
    env.VITE_API_PROXY_TARGET?.trim() ||
    process.env.VITE_API_PROXY_TARGET?.trim() ||
    'http://127.0.0.1:8000'

  return {
    plugins: [
      react(),
      tailwindcss(),
    ],
    resolve: {
      alias: {
        '@': path.resolve(import.meta.dirname, './src'),
        events: 'events',
      },
      dedupe: ['react', 'react-dom'],
    },
    optimizeDeps: {
      exclude: ['@cornerstonejs/dicom-image-loader'],
      include: [
        'react',
        'react-dom',
        'react/jsx-runtime',
        'dicom-parser',
        'events',
        'pako',
        'uuid',
        '@cornerstonejs/codec-openjph/wasmjs',
        '@cornerstonejs/codec-openjpeg/decodewasmjs',
        '@cornerstonejs/codec-libjpeg-turbo-8bit/decodewasmjs',
        '@cornerstonejs/codec-charls/decodewasmjs',
        '@cornerstonejs/codec-libjxl/decodewasmjs',
      ],
    },
    worker: {
      format: 'es',
    },
    server: {
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
