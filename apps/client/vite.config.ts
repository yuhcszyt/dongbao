import { defineConfig, loadEnv } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [uni()],
    server: {
      host: '0.0.0.0',
      port: 5173,
      proxy: env.VITE_DEV_API_TARGET
        ? { '/api': { target: env.VITE_DEV_API_TARGET, changeOrigin: true } }
        : undefined,
    },
  }
})
