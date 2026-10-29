<script setup lang="ts">
import { ref } from 'vue'
defineProps<{ agreed: boolean; busy: boolean; error: string }>()
const emit = defineEmits<{ agree: [value: boolean]; confirm: []; cancel: [] }>()
const details = ref(false)
</script>
<template>
  <view class="modal-mask login-mask" @tap="emit('cancel')">
    <scroll-view scroll-y class="sheet login-sheet" @tap.stop>
      <view class="grab" />
      <view class="close-row"><text class="sheet-title">登录懂宝</text><button class="icon-btn" :disabled="busy" @tap="emit('cancel')">×</button></view>
      <view class="login-mark">👶🏻</view>
      <view class="h3">登录后，记录宝宝的每一步成长</view>
      <view class="small">首次微信登录将自动注册懂宝账号，已有账号直接登录。</view>
      <button class="primary-btn wide" :disabled="busy" @tap="emit('confirm')">{{ busy ? '正在登录…' : '微信登录 / 注册' }}</button>
      <checkbox-group @change="emit('agree', $event.detail.value.includes('agree'))"><label class="login-consent"><checkbox value="agree" :checked="agreed" :disabled="busy" color="#6759f6" /><text>我已阅读并同意</text><text class="link" @tap.stop="details = !details">登录及数据使用说明</text></label></checkbox-group>
      <view v-if="details" class="draft-preview">微信登录用于识别你的懂宝账号，首次登录会创建账号和家庭。登录凭证保存在本机，宝宝档案和记录保存在服务端，并按家庭成员权限共享。语音、照片仅在你主动采集并上传时处理。不要求提供手机号、微信头像或昵称。可在设置退出登录或注销账号。</view>
      <view v-if="error" class="error-box" role="alert">{{ error }}</view>
      <button class="soft-btn wide" :disabled="busy" @tap="emit('cancel')">暂不登录，继续浏览</button>
    </scroll-view>
  </view>
</template>
<style scoped>
.login-mask{z-index:120}.login-sheet{height:65vh;text-align:center}.login-mark{font-size:48px;margin:12px}.login-consent{display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:4px;font-size:12px;margin:16px 0;color:#7b8098}.draft-preview{text-align:left}.login-consent checkbox{transform:scale(.8)}
</style>
