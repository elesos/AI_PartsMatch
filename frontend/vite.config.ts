import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: { host: '0.0.0.0', port: 8881 },
  preview: { host: '0.0.0.0', port: 8881 },
  test: { environment: 'jsdom', setupFiles: './src/test/setup.ts', css: true, globals: true },
})
