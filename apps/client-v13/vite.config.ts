import os from 'node:os'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'
import { resolveMiniProgramApiBase } from '../client/lanIPv4'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const target = process.env.VITE_DEV_API_TARGET || env.VITE_DEV_API_TARGET || 'http://127.0.0.1:8001'
  if (process.env.UNI_PLATFORM === 'mp-weixin') {
    process.env.VITE_API_BASE_URL = resolveMiniProgramApiBase({
      specified: process.env.VITE_API_BASE_URL || env.VITE_API_BASE_URL,
      apiTarget: target,
      interfaces: os.networkInterfaces(),
    })
  }
  return {
    plugins: [uni()],
    // Reuse the existing API/auth/domain contracts without forking business rules.
    resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) }, dedupe: ['vue'] },
    define: { 'import.meta.env.UNI_PLATFORM': JSON.stringify(process.env.UNI_PLATFORM || '') },
    server: { host: '0.0.0.0', port: 5174, proxy: { '/api': { target, changeOrigin: true } } },
  }
})
