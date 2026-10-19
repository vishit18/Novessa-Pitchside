import path from 'node:path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src'),
      // League and sample match files live in the repo-level data/ folder.
      '@data': path.resolve(import.meta.dirname, '../data'),
    },
  },
  server: { port: 5173, fs: { allow: ['..'] } },
  test: { environment: 'node', include: ['src/**/*.test.ts'] },
})
