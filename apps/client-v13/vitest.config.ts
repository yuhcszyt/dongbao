import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
export default defineConfig({
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) }, dedupe: ['vue'] },
  test: { include: ['src/**/*.test.ts', '../client/src/services/*.test.ts', '../client/src/features/record/voiceCapture.test.ts'] },
})
