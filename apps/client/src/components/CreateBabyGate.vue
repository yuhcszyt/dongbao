<script setup lang="ts">
/**
 * 无宝宝时三页（首页 / 记录 / 档案）共用的建档引导。
 *
 * 三页各自摆一份表单，改一次文案就要改三处——所以这里连提交一起收进来：
 * 页面只说「没有宝宝就显示这个」，表单、校验、失败提示与重试都在这一处。
 */
import ProfileForm from '@/components/ProfileForm.vue'
import type { Baby } from '@/features/record/domain'
import { recordStore } from '@/features/record/store'

const { state } = recordStore

async function submit(input: Pick<Baby, 'nickname' | 'birth_date' | 'gender'>) {
  // 失败时什么都不做：中文提示由 store 给出，输入都留在原地，可以直接再点一次。
  if (!(await recordStore.saveBaby(input))) return
  uni.showToast({ title: '建档完成', icon: 'success' })
}
</script>

<template>
  <view class="gate">
    <view class="baby-mark">👶🏻</view>
    <text class="eyebrow">欢迎来到懂宝</text>
    <text class="page-title">先认识一下宝宝</text>
    <text class="muted">只需三项，之后就可以开始记录每天吃睡拉撒。</text>
    <ProfileForm
      :submitting="state.saving"
      submit-text="创建宝宝档案"
      :error="state.error"
      :retryable="state.retryable"
      @submit="submit"
      @retry="recordStore.retrySession"
    />
  </view>
</template>

<style scoped>
.gate { max-width: 520px; margin: 0 auto; padding-top: 34px; text-align: center; }
.baby-mark { display: grid; place-items: center; width: 82px; height: 82px; margin: 0 auto 22px; border-radius: 50%; background: #f2e8d8; font-size: 45px; }
.eyebrow, .page-title, .muted { display: block; }
.eyebrow { color: #328da9; font-size: 13px; font-weight: 750; letter-spacing: 1px; }
.page-title { margin: 8px 0 6px; font-size: 27px; font-weight: 800; line-height: 1.25; }
.muted { color: #71858b; font-size: 14px; line-height: 1.55; }
</style>
