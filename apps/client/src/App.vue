<script setup lang="ts">
import { onLaunch } from '@dcloudio/uni-app'

onLaunch(() => {
  // Phase 1 的事实数据全部来自服务端，客户端不创建示例记录。
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
