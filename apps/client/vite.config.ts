import { defineConfig, loadEnv } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // H5 开发默认把 /api 转到本机 make DEV_LOGIN=1 dev-server（8001）；可用 VITE_DEV_API_TARGET 覆盖。
  const apiTarget = env.VITE_DEV_API_TARGET || 'http://127.0.0.1:8001'

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
