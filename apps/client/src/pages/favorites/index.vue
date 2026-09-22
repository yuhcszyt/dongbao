<script setup lang="ts">
import { computed } from 'vue'
import { contentStore } from '@/features/content/articles'

const favorites = computed(() => contentStore.favoriteArticles())

function openArticle(id: number) {
  uni.navigateTo({ url: `/pages/article/index?id=${id}` })
}
</script>

<template>
  <view class="page">
    <text class="title">我的收藏</text>
    <text class="muted">把有用的内容留在身边 · 本机收藏，内容示例</text>

    <view v-if="!favorites.length" class="empty">
      还没有收藏<br>
      <text class="muted">打开文章，点击「收藏」即可保留。</text>
    </view>

    <view v-for="item in favorites" :key="item.id" class="card" @click="openArticle(item.id)">
      <view class="art" :style="{ background: item.color }">{{ item.emoji }}</view>
      <text class="card-title">{{ item.title }}</text>
      <text class="muted">{{ item.why }}</text>
    </view>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 18px 18px 40px; background: var(--db-background); color: var(--db-text); }
.title { display: block; font-size: 22px; font-weight: 800; }
.muted { display: block; color: var(--db-muted); font-size: 13px; margin-top: 6px; line-height: 1.5; }
.empty { margin-top: 48px; text-align: center; color: var(--db-muted); line-height: 1.8; }
.card { margin-top: 14px; border-radius: 19px; background: var(--db-surface); border: 1px solid var(--db-border); padding: 16px; }
.art { height: 100px; border-radius: 13px; display: flex; align-items: center; justify-content: center; font-size: 44px; margin-bottom: 10px; }
.card-title { display: block; font-size: 17px; font-weight: 800; }
</style>
