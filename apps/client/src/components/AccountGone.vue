<script setup lang="ts">
/**
 * 注销完成后的终态：首页、记录页、档案页共用一份，文案只有一处（票 10）。
 *
 * 两句话必须同时在场：
 * - 「永久删除、不可恢复」——家长要知道注销是不可逆的；
 * - 「下次进入会开始一个新的空账号」——票 05 的会话模块就是「注销后不自动重登，
 *   新会话等下一次冷启动或显式操作」，所以这里不能写「不会再自动登录」：
 *   那与下一次冷启动的静默登录自相矛盾，会让人以为注销没生效。
 */
</script>

<template>
  <view class="gone">
    <view class="mark">✅</view>
    <text class="eyebrow">懂宝</text>
    <text class="title">账号已注销</text>
    <text class="muted">宝宝档案、全部记录、语音和照片都已永久删除，旧数据无法恢复。下次进入小程序会开始一个新的空账号。</text>
  </view>
</template>

<style scoped>
.gone { max-width: 520px; margin: 0 auto; padding-top: 34px; text-align: center; }
.mark { display: grid; place-items: center; width: 82px; height: 82px; margin: 0 auto 22px; border-radius: 50%; background: #f2e8d8; font-size: 45px; }
.eyebrow, .title, .muted { display: block; }
.eyebrow { color: #328da9; font-size: 13px; font-weight: 750; letter-spacing: 1px; }
.title { margin: 10px 0 4px; font-size: 27px; font-weight: 800; line-height: 1.25; }
.muted { color: #71858b; font-size: 14px; line-height: 1.55; }
</style>
