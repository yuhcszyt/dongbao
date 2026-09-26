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
  --db-primary: #7560a8;
  --db-primary-pale: #c5b8df;
  --db-soft: #f0ebf7;
  --db-background: #fbfaf7;
  --db-surface: #ffffff;
  --db-text: #342e42;
  --db-muted: #716979;
  --db-border: #e5dfed;
  --db-apricot: #f4e6d5;
  --db-overlay: rgba(52, 46, 66, .46);
  min-height: 100%;
  background: var(--db-background);
  color: var(--db-text);
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
  min-height: 48px;
}

.page { overflow-wrap: anywhere; }

button[disabled] { opacity: .6; }
button:focus-visible, input:focus-visible, textarea:focus-visible { outline: 2px solid var(--db-primary); outline-offset: 3px; }

button::after {
  border: 0;
}
</style>
