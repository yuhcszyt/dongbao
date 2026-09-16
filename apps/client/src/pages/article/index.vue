<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { contentStore } from '@/features/content/articles'
import { babyDisplayName } from '@/features/record/domain'
import { recordStore } from '@/features/record/store'

const articleId = ref(0)
const article = computed(() => contentStore.article(articleId.value))
const favorited = computed(() => contentStore.isFavorite(articleId.value))
const babyName = computed(() => babyDisplayName(recordStore.state.baby?.nickname))

function toggleFavorite() {
  const added = contentStore.toggleFavorite(articleId.value)
  uni.showToast({ title: added ? '已收藏文章' : '已取消收藏', icon: 'none' })
}

function askAbout() {
  uni.switchTab({ url: '/pages/ai/index' })
}

function goBack() {
  uni.navigateBack({ fail: () => uni.navigateTo({ url: '/pages/articles/index' }) })
}

onLoad((query) => {
  articleId.value = Number(query?.id ?? 0) || 0
  void recordStore.load()
})
</script>

<template>
  <view class="page">
    <view class="top">
      <text class="tag">{{ article.category }}与陪伴</text>
      <button class="link" @click="toggleFavorite">{{ favorited ? '已收藏 ♥' : '收藏 ♡' }}</button>
    </view>
    <text class="title">{{ article.title }}</text>
    <view class="card hero">
      <text class="card-title">为什么推荐给你</text>
      <text class="muted">{{ article.why }}</text>
    </view>
    <view class="art" :style="{ background: article.color }">{{ article.emoji }}</view>
    <text class="section">{{ article.intro }}</text>
    <text class="body">{{ article.body }}</text>
    <text class="section">{{ article.sub }}</text>
    <text class="body">{{ article.detail }}</text>
    <view class="warn">内容示例 · 尚未接入已审核专业内容与来源</view>
    <button class="primary" @click="askAbout">针对{{ babyName }}，问问懂宝</button>
    <button class="outline" @click="goBack">返回</button>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 18px 18px 40px; background: #fbfaf7; color: #203f4a; }
.top { display: flex; justify-content: space-between; align-items: center; }
.tag { padding: 4px 10px; border-radius: 20px; background: #edf6f8; color: #328da9; font-size: 11px; }
.link { background: transparent; color: #2d8098; font-size: 14px; }
.title { display: block; margin: 14px 0; font-size: 26px; font-weight: 800; line-height: 1.35; }
.card { border-radius: 19px; background: white; border: 1px solid #eef1ef; padding: 16px; margin-bottom: 14px; }
.hero { background: linear-gradient(120deg, #e3f3f7, #f1f8fa); border-color: #d9edf2; }
.card-title { display: block; font-weight: 800; margin-bottom: 6px; }
.muted, .body { display: block; color: #70858d; font-size: 14px; line-height: 1.9; }
.art { height: 160px; border-radius: 13px; display: flex; align-items: center; justify-content: center; font-size: 64px; margin-bottom: 16px; }
.section { display: block; margin: 20px 0 8px; font-size: 17px; font-weight: 800; }
.warn { margin: 18px 0; border-radius: 12px; background: #fff0df; color: #b88346; padding: 10px 12px; font-size: 12px; }
.primary { width: 100%; min-height: 52px; border-radius: 14px; background: #328da9; color: white; font-weight: 700; }
.outline { width: 100%; min-height: 50px; margin-top: 10px; border-radius: 14px; border: 1px solid #bedbe4; background: white; color: #328da9; }
</style>
