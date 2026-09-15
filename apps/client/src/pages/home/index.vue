<script setup lang="ts">
/** 首页壳：票 08 填内容（宝宝行、问候语、今日指标、快速记录、最近动态）。 */
const openRecord = () => uni.switchTab({ url: '/pages/record/index' })
</script>

<template>
  <view class="page">
    <text class="eyebrow">懂宝</text>
    <text class="page-title">首页</text>
    <text class="muted">首页内容正在搭建：宝宝行、今日记录指标、快速记录、最近动态。</text>
    <button class="link" @click="openRecord">先去记录页 ›</button>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 40px 20px; background: #fbfaf7; color: #203f4a; }
.eyebrow, .page-title, .muted { display: block; }
.eyebrow { color: #328da9; font-size: 13px; font-weight: 750; letter-spacing: 1px; }
.page-title { margin: 6px 0; font-size: 27px; font-weight: 800; }
.muted { color: #71858b; font-size: 15px; line-height: 1.6; }
.link { min-height: 48px; margin-top: 22px; background: transparent; color: #2d8098; font-size: 16px; text-align: left; padding: 0; }
</style>
