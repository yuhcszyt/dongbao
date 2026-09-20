import os from 'node:os'
import { defineConfig, loadEnv } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'
import { resolveMiniProgramApiBase } from './lanIPv4'

export default defineConfig(({ mode }) => {
  const fileEnv = loadEnv(mode, process.cwd(), '')
  const env = {
    VITE_DEV_API_TARGET: process.env.VITE_DEV_API_TARGET || fileEnv.VITE_DEV_API_TARGET,
    VITE_API_BASE_URL: process.env.VITE_API_BASE_URL || fileEnv.VITE_API_BASE_URL,
  }
  // H5 开发代理目标可以是本机 loopback（Vite 和服务端在同一台电脑）。
  const apiTarget = env.VITE_DEV_API_TARGET || 'http://127.0.0.1:8001'

  if (process.env.UNI_PLATFORM === 'mp-weixin') {
    const apiBase = resolveMiniProgramApiBase({
      specified: env.VITE_API_BASE_URL,
      apiTarget,
      interfaces: os.networkInterfaces(),
    })
    process.env.VITE_API_BASE_URL = apiBase
    console.info(`[dongbao] 小程序 API → ${apiBase}`)
  }

  return {
    plugins: [uni()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: {
        '/api': { target: apiTarget, changeOrigin: true },
      },
    },
  }
})
