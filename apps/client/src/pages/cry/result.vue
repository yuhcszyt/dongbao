<script setup lang="ts">
function askDongbao() {
  uni.switchTab({ url: '/pages/ai/index' })
}

function backToCry() {
  uni.navigateBack({ fail: () => uni.navigateTo({ url: '/pages/cry/index' }) })
}
</script>

<template>
  <view class="page">
    <view class="warn">ⓘ 模拟结果，不代表真实分析</view>
    <text class="notice">当前为演示流程。正式哭声模型接入前，不会对音频做真实判断。</text>

    <view class="card">
      <text class="tag">可能需求 · 演示</text>
      <text class="title">可以先排查这些需求</text>
      <text class="muted">仅凭哭声不能确定原因，需要结合宝宝现场表现与日常记录。</text>
      <view class="row"><text>1　回顾上次喂奶时间</text></view>
      <view class="row"><text>2　观察是否有困倦表现</text></view>
      <view class="row"><text>3　检查尿布与环境</text></view>
    </view>

    <view class="card">
      <text class="card-title">其他可能</text>
      <view class="chips">
        <text class="chip">需要安抚</text>
        <text class="chip">饥饿</text>
        <text class="chip">不舒服</text>
      </view>
      <text class="muted">以上仅展示产品如何组织信息，并非对音频的判断。</text>
    </view>

    <button class="primary" @click="askDongbao">结合记录问懂宝</button>
    <button class="outline" @click="backToCry">重新录音</button>
    <text class="notice">仅供育儿参考，不用于医疗诊断</text>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 18px 18px 40px; background: #fbfaf7; color: #203f4a; }
.warn { border-radius: 12px; background: #fff0df; color: #b88346; padding: 10px 12px; font-size: 12px; }
.notice { display: block; margin: 14px 0; color: #8b9c9f; font-size: 12px; line-height: 1.6; text-align: center; }
.card { margin-top: 14px; border-radius: 19px; background: white; border: 1px solid #eef1ef; padding: 17px; }
.tag { display: inline-block; padding: 4px 10px; border-radius: 20px; background: #edf6f8; color: #328da9; font-size: 11px; }
.title { display: block; margin: 14px 0 8px; font-size: 22px; font-weight: 800; }
.muted { display: block; color: #71858b; font-size: 13px; line-height: 1.55; }
.row { padding: 13px 0; border-bottom: 1px solid #e9eff0; font-size: 14px; font-weight: 700; }
.row:last-child { border: 0; }
.card-title { display: block; font-size: 16px; font-weight: 800; margin-bottom: 10px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0; }
.chip { padding: 6px 12px; border-radius: 19px; background: #edf4f6; font-size: 12px; color: #328da9; }
.primary { width: 100%; min-height: 52px; margin-top: 16px; border-radius: 14px; background: #328da9; color: white; font-weight: 700; }
.outline { width: 100%; min-height: 50px; margin-top: 10px; border-radius: 14px; border: 1px solid #bedbe4; background: white; color: #328da9; }
</style>
