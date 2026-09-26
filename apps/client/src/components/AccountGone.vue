<template>
  <view class="gone">
    <view class="mark">✅</view>
    <text class="eyebrow">懂宝</text>
    <text class="title">账号已注销</text>
    <text class="muted">你的账号已注销。共同家庭的记录会保留给其他成员；最后一位成员注销的家庭数据已删除。下次进入小程序会开始一个新的空账号。</text>
  </view>
</template>

<style scoped>
.gone { max-width: 520px; margin: 0 auto; padding-top: 34px; text-align: center; }
.mark { display: grid; place-items: center; width: 82px; height: 82px; margin: 0 auto 22px; border-radius: 50%; background: var(--db-apricot); font-size: 45px; }
.eyebrow, .title, .muted { display: block; }
.eyebrow { color: var(--db-primary); font-size: 13px; font-weight: 750; letter-spacing: 1px; }
.title { margin: 10px 0 4px; font-size: 27px; font-weight: 800; line-height: 1.25; }
.muted { color: var(--db-muted); font-size: 14px; line-height: 1.55; }
</style>
