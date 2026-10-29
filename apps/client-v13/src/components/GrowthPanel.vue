<script setup lang="ts">
import { computed, ref } from 'vue'
import type { RecordItem } from '@/features/record/domain'
import { growthPoints, recordView } from '../domain/presentation'
import { chartSource } from '../domain/chart'
import RecordTimeline from './RecordTimeline.vue'

const props = defineProps<{ records: RecordItem[]; age: string }>()
const emit = defineEmits<{ create: []; select: [id: string] }>()
const tab = ref('data'), curve = ref<'height_cm' | 'weight_kg'>('height_cm'), detail = ref(false)
const measurements = computed(() => props.records.filter(item => item.record_type === 'growth'))
const height = computed(() => growthPoints(props.records, 'height_cm').at(-1)?.value)
const weight = computed(() => growthPoints(props.records, 'weight_kg').at(-1)?.value)
const points = computed(() => growthPoints(props.records, curve.value))
const chart = computed(() => chartSource(points.value))
const label = computed(() => curve.value === 'height_cm' ? '身高 (cm)' : '体重 (kg)')
function switchCurve() { curve.value = curve.value === 'height_cm' ? 'weight_kg' : 'height_cm' }
</script>

<template>
  <view class="page">
    <view class="header"><view class="header-title">成长</view><button class="icon-btn" @tap="emit('create')">＋</button></view>
    <view class="growth-top"><view class="growth-tabs"><button v-for="item in [{key:'data',name:'数据'},{key:'timeline',name:'时间线'},{key:'milestone',name:'里程碑'}]" :key="item.key" :class="{active:tab === item.key}" @tap="tab = item.key">{{ item.name }}</button></view></view>
    <view v-if="tab === 'data'" class="content">
      <view class="section-title">生长发育</view>
      <view class="card growth-card">
        <view class="close-row"><view class="h3">{{ age }}</view><button class="outline-btn" @tap="switchCurve">切换曲线</button></view>
        <view class="metrics growth-metrics"><view class="metric"><text class="span">体重</text><text class="b">{{ weight ? weight+' kg' : '待记录' }}</text></view><view class="metric"><text class="span">身高</text><text class="b">{{ height ? height+' cm' : '待记录' }}</text></view><view class="metric"><text class="span">头围</text><text class="small">暂未开放</text></view></view>
        <image v-if="points.length" class="chart-image" :src="chart" mode="aspectFit" /><view v-else class="empty">还没有{{ label }}记录</view>
        <view class="legend"><text class="span">{{ label }}</text></view>
        <view class="small growth-note">实际测量趋势，不含医学百分位评估</view>
        <button class="link wide growth-detail-link" @tap="detail = true">查看详细生长曲线 →</button>
      </view>
      <view class="section-title">发育里程碑<button class="link" @tap="tab = 'milestone'">全部 ›</button></view>
      <view class="card growth-card"><view class="empty">发育里程碑暂未开放</view></view>
    </view>
    <view v-else-if="tab === 'timeline'" class="content"><view class="card"><view class="card-title">成长时间线</view><view class="timeline"><RecordTimeline :records="measurements.map(recordView)" @select="emit('select',$event)" /></view></view></view>
    <view v-else class="content"><view class="card"><view class="card-title">里程碑</view><view class="empty">发育里程碑暂未开放</view></view></view>
    <view v-if="detail" class="overlay-view growth-detail">
      <view class="overlay-head"><button class="icon-btn" @tap="detail = false">‹</button><view class="h3">详细生长曲线</view></view>
      <scroll-view scroll-y class="growth-detail-body"><view class="overlay-body"><view class="close-row"><text class="b">{{ label }}</text><button class="outline-btn" @tap="switchCurve">切换曲线</button></view><image v-if="points.length" class="chart-image" :src="chart" mode="aspectFit" /><view v-else class="empty">暂无测量记录</view><view class="small">实际测量趋势，不含医学百分位评估；点击记录可修改测量值。</view><view class="timeline"><RecordTimeline :records="measurements.map(recordView)" @select="emit('select',$event)" /></view><button class="primary-btn wide" @tap="emit('create')">＋ 添加身高体重</button></view></scroll-view>
    </view>
  </view>
</template>

<style scoped>
.growth-card{margin-top:0}.growth-metrics{margin-top:12px}.growth-note{text-align:center;margin-top:10px}.growth-detail-link{margin-top:7px}.growth-detail{display:flex;flex-direction:column;bottom:calc(70px + env(safe-area-inset-bottom))}.growth-detail-body{flex:1;min-height:0;height:0}.legend{color:#6759f6}
@media(min-width:700px){.growth-detail{max-width:430px;margin:0 auto}}
</style>
