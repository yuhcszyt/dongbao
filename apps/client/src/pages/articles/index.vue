<script setup lang="ts">
import { computed, ref } from 'vue'
import { onLoad } from '@dcloudio/uni-app'
import { ARTICLES } from '@/features/content/articles'
import { babyDisplayName } from '@/features/record/domain'
import { recordStore } from '@/features/record/store'

const filter = ref('推荐')
const babyName = computed(() => babyDisplayName(recordStore.state.baby?.nickname))
const visible = computed(() =>
  filter.value === '推荐' ? ARTICLES : ARTICLES.filter((item) => item.category === filter.value),
)

function openArticle(id: number) {
  uni.navigateTo({ url: `/pages/article/index?id=${id}` })
}

onLoad(() => void recordStore.load())
</script>

<template>
  <view class="page">
    <text class="title">为{{ babyName }}推荐</text>
    <text class="muted">根据宝宝当前阶段与近期记录 · 内容示例</text>
    <view class="chips">
      <button v-for="item in ['推荐', '喂养', '睡眠', '发育']" :key="item" :class="{ active: filter === item }" @click="filter = item">{{ item }}</button>
    </view>
    <view v-for="item in visible" :key="item.id" class="card" @click="openArticle(item.id)">
      <view class="art" :style="{ background: item.color }">{{ item.emoji }}</view>
      <text class="card-title">{{ item.title }}</text>
      <text class="muted">{{ item.why }}</text>
      <text class="muted">◷ {{ item.minutes }} 分钟阅读 · 内容示例</text>
    </view>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 18px 18px 40px; background: #fbfaf7; color: #203f4a; }
.title { display: block; font-size: 22px; font-weight: 800; }
.muted { display: block; color: #71858b; font-size: 13px; margin-top: 6px; line-height: 1.5; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 14px 0; }
.chips button { padding: 7px 14px; border-radius: 19px; background: #edf4f6; color: #49646d; font-size: 13px; }
.chips .active { background: #328da9; color: white; }
.card { margin-top: 12px; border-radius: 19px; background: white; border: 1px solid #eef1ef; padding: 16px; }
.art { height: 110px; border-radius: 13px; display: flex; align-items: center; justify-content: center; font-size: 48px; margin-bottom: 10px; }
.card-title { display: block; font-size: 17px; font-weight: 800; }
</style>
