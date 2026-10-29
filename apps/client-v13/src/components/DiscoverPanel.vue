<script setup lang="ts">
import { computed, ref } from 'vue'
defineProps<{ age:string }>()
const emit=defineEmits<{ unavailable:[title:string] }>()
const search=ref(''),category=ref('推荐')
// Navigation topics from the design, never presented as published articles or medical advice.
const topics=[{title:'宝宝辅食添加指南',category:'喂养',emoji:'🥗',intro:'从泥糊到小块，怎么吃更科学？'},{title:'宝宝夜醒的常见原因与应对方法',category:'睡眠',emoji:'👶',intro:'了解宝宝的睡眠节奏'},{title:'出牙期护理全攻略',category:'发育',emoji:'🦷',intro:'了解宝宝出牙期的变化'},{title:'宝宝便便颜色对照表',category:'喂养',emoji:'🥣',intro:'学习观察与记录'}]
const visible=computed(()=>topics.filter(item=>(['推荐','当月'].includes(category.value)||item.category===category.value)&&item.title.includes(search.value.trim())))
</script>
<template>
  <view class="page">
    <view class="header"><view class="header-title">发现</view></view>
    <view class="searchbar">⌕ <input v-model="search" placeholder="搜索育儿知识、文章、问题…" /></view>
    <view class="rec-tabs"><button v-for="item in ['推荐','当月','喂养','睡眠','发育']" :key="item" :class="{active:category === item}" @tap="category = item">{{ item === '推荐' ? '为你推荐' : item === '当月' ? '当月月龄' : item }}</button></view>
    <view class="discover-hero"><view><view class="h3">{{ age === '生日待完善' ? '宝宝' : age+'宝宝' }}<br />睡眠全攻略</view><view class="p">如何应对夜醒、睡眠倒退？</view><button class="primary-btn" @tap="emit('unavailable','文章阅读')">暂未开放</button></view><view class="sleep-ill">😴</view></view>
    <view class="section-title discover-heading">猜你喜欢 <button class="link" @tap="emit('unavailable','文章推荐')">换一批</button></view>
    <view class="article-list"><view class="small">内容服务暂未开放，以下仅保留设计中的主题入口。</view><view v-for="item in visible" :key="item.title" class="article" @tap="emit('unavailable',item.title)"><view class="thumb">{{ item.emoji }}</view><view><text class="b">{{ item.title }}</text><view class="p">{{ item.intro }}</view><text class="small">暂未开放</text></view></view><view v-if="!visible.length" class="empty">没有匹配的主题</view></view>
  </view>
</template>
