<script setup lang="ts">
defineProps<{ height?:number; weight?:number }>()
</script>
<template>
  <view class="mini-metrics"><view class="metric"><text class="span">身高</text><text class="b">{{ height ? height+' cm' : '待记录' }}</text><text class="small">最近测量</text></view><view class="metric"><text class="span">体重</text><text class="b">{{ weight ? weight+' kg' : '待记录' }}</text><text class="small">最近测量</text></view><view class="metric"><text class="span">头围</text><text class="b">暂未开放</text></view></view>
</template>
