<script setup lang="ts">
import { onLaunch } from '@dcloudio/uni-app'
import { session } from '@/services/api'

onLaunch(() => {
  // Phase 1 的事实数据全部来自服务端，客户端不创建示例记录。
  // 启动时序：有本地 token 先当已登录用，没有则静默登录一次；失败进入可恢复的「需要重试」，
  // 由页面上的中文提示承接（这里不重复上报，避免每次启动弹窗）。
  void session.ensureSession().catch(() => undefined)
})
</script>

<style>
page {
  min-height: 100%;
  background: #fbfaf7;
  color: #203f4a;
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
}

view,
text,
button,
input,
textarea,
picker {
  box-sizing: border-box;
}

button {
  margin: 0;
}

button::after {
  border: 0;
}
</style>
