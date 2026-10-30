import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom', setupFiles: './src/test/setup.ts' },
  server: { port: 5173, proxy: { '/api': 'http://127.0.0.1:8000', '/output': 'http://127.0.0.1:8000' } },
  build: {
    chunkSizeWarningLimit: 1300,
    rollupOptions: {
      output: { manualChunks: { react: ['react', 'react-dom', 'framer-motion'], three: ['three', '@react-three/fiber'] } },
    },
  },
})
