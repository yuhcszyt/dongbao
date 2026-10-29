<script setup lang="ts">
import { recordTitle } from '../domain/presentation'
import type { BabyRecord } from '../domain/model'
defineProps<{ records: BabyRecord[] }>()
const emit = defineEmits<{ select: [id: string] }>()
const colors: Record<string,string> = { 喂奶:'#ff6374',睡眠:'#6759f6',辅食:'#32be6d',排便:'#9b6a45',尿布:'#55bde8',身高体重:'#ff72aa' }
</script>
<template>
  <view v-if="!records.length" class="empty">这个时间范围还没有记录，记下宝宝的第一笔吧</view>
  <view v-for="record in records" :key="record.id" class="t-row" @tap="emit('select', record.id)">
    <view class="dot" :style="{ color: colors[record.type] || '#6759f6' }" />
    <view class="t-time">{{ record.time }}<view class="small">{{ record.date.slice(5) }}</view></view>
    <view class="t-main"><text class="strong">{{ recordTitle(record) }}</text><view class="t-sub">{{ [record.note,record.source].filter(Boolean).join(' · ') }}</view></view>
  </view>
</template>
