<script setup lang="ts">
import { computed, ref } from 'vue'
import { articleTopics } from '../domain/articleTopics'
defineProps<{ age:string }>()
const emit=defineEmits<{ unavailable:[title:string]; back:[] }>()
const search=ref(''),category=ref('推荐')

const visible=computed(()=>articleTopics.filter(item=>(['推荐','当月'].includes(category.value)||item.category===category.value)&&item.title.includes(search.value.trim())))
</script>
<template>
  <view class="page">
    <view class="header"><button class="icon-btn" aria-label="返回首页" @tap="emit('back')">‹</button><view class="header-title">推荐文章</view><view class="header-spacer" /></view>
    <view class="searchbar">⌕ <input v-model="search" placeholder="搜索育儿知识、文章、问题…" /></view>
    <view class="rec-tabs"><button v-for="item in ['推荐','当月','喂养','睡眠','发育']" :key="item" :class="{active:category === item}" @tap="category = item">{{ item === '推荐' ? '为你推荐' : item === '当月' ? '当月月龄' : item }}</button></view>
    <view class="discover-hero"><view><view class="h3">{{ age === '生日待完善' ? '宝宝' : age+'宝宝' }}<br />睡眠全攻略</view><view class="p">如何应对夜醒、睡眠倒退？</view><button class="primary-btn" @tap="emit('unavailable','文章阅读')">暂未开放</button></view><view class="sleep-ill">😴</view></view>
    <view class="section-title discover-heading">猜你喜欢 <button class="link" @tap="emit('unavailable','文章推荐')">换一批</button></view>
    <view class="article-list"><view class="small">内容服务暂未开放，以下仅保留设计中的主题入口。</view><view v-for="item in visible" :key="item.title" class="article" @tap="emit('unavailable',item.title)"><view class="thumb">{{ item.emoji }}</view><view><text class="b">{{ item.title }}</text><view class="p">{{ item.intro }}</view><text class="small">暂未开放</text></view></view><view v-if="!visible.length" class="empty">没有匹配的主题</view></view>
  </view>
</template>
