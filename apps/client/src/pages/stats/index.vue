<script setup lang="ts">
import { computed } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { dateOf, nowParts, shiftDate, type RecordItem } from '@/features/record/domain'
import { recordStore } from '@/features/record/store'

const { state } = recordStore

const days = computed(() => {
  const today = nowParts().date
  return Array.from({ length: 7 }, (_, index) => {
    const date = shiftDate(today, index - 6)
    const dayRecords = state.records.filter((item) => dateOf(item.occurred_at) === date)
    const milk = dayRecords
      .filter((item) => item.record_type === 'feeding')
      .reduce((sum, item) => sum + Number(item.payload.amount_ml || 0), 0)
    return { date, day: Number(date.slice(8)), milk }
  })
})

const maxMilk = computed(() => Math.max(1, ...days.value.map((item) => item.milk)))
const todaySummary = computed(() => recordStore.summaryFor(nowParts().date))
const todayCount = computed(() => {
  const today = nowParts().date
  return state.records.filter((item: RecordItem) => dateOf(item.occurred_at) === today).length
})

onShow(() => void recordStore.load(nowParts().date))
</script>

<template>
  <view class="page">
    <text class="title">记录里，看见成长</text>
    <text class="muted">仅统计已录入的数据，未记录不代表没有发生。 · 前端本地聚合</text>

    <view v-if="todaySummary" class="card metrics">
      <view><text class="num">{{ todaySummary.feeding_ml }}</text><text class="label">奶量 ml</text></view>
      <view><text class="num">{{ todaySummary.sleep_minutes }}</text><text class="label">睡眠 分钟</text></view>
      <view><text class="num">{{ todaySummary.diaper_count }}</text><text class="label">尿布 次</text></view>
      <view><text class="num">{{ todaySummary.complementary_food_count }}</text><text class="label">辅食 次</text></view>
    </view>

    <view class="card">
      <text class="card-title">近 7 天奶量 · ml</text>
      <view class="bars">
        <view v-for="item in days" :key="item.date" class="bar-wrap">
          <view class="bar" :style="{ height: `${Math.max(4, (item.milk / maxMilk) * 100)}%` }" />
          <text class="bar-label">{{ item.day }}日<br>{{ item.milk }}</text>
        </view>
      </view>
    </view>

    <view class="card">
      <text class="card-title">记录概览</text>
      <text class="muted">共有 {{ state.records.length }} 条记录，{{ todayCount }} 条来自今天。</text>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 18px 18px 40px; background: var(--db-background); color: var(--db-text); }
.title { display: block; font-size: 23px; font-weight: 800; }
.muted { display: block; color: var(--db-muted); font-size: 13px; margin-top: 6px; line-height: 1.55; }
.card { margin-top: 16px; border-radius: 19px; background: var(--db-surface); border: 1px solid var(--db-border); padding: 17px; }
.metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; text-align: center; }
.num { display: block; font-size: 18px; font-weight: 800; color: var(--db-primary); }
.label { display: block; margin-top: 4px; font-size: 14px; color: var(--db-muted); }
.card-title { display: block; font-size: 16px; font-weight: 800; margin-bottom: 14px; }
.bars { display: flex; align-items: flex-end; gap: 8px; height: 130px; padding-bottom: 36px; }
.bar-wrap { flex: 1; height: 100%; display: flex; flex-direction: column; justify-content: flex-end; align-items: center; position: relative; }
.bar { width: 100%; border-radius: 6px 6px 0 0; background: var(--db-primary-pale); min-height: 4px; }
.bar-label { position: absolute; bottom: -34px; width: 100%; text-align: center; font-size: 10px; color: var(--db-muted); line-height: 1.3; }
</style>
