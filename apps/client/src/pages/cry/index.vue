<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { onHide, onShow } from '@dcloudio/uni-app'
import { cryAnalysisStore } from '@/features/content/cryAnalysis'
import { recordStore, errorText } from '@/features/record/store'
import { createVoiceCapture } from '@/features/record/voiceCapture'
import { api } from '@/services/api'

const recording = ref(false)
const seconds = ref(0)
const audioPath = ref('')
const busy = ref(false)
const message = ref('')
const { state } = recordStore
let ticker: ReturnType<typeof setInterval> | null = null
let h5Blob: Blob | null = null
const starting = ref(false)
let operation = 0
let alive = true
const clearTicker = () => { if (ticker) clearInterval(ticker); ticker = null }
function clearAudio() {
  if (audioPath.value.startsWith('blob:')) URL.revokeObjectURL(audioPath.value)
  audioPath.value = ''
  h5Blob = null
}
const voice = createVoiceCapture({
  started() {
    starting.value = false
    recording.value = true
    seconds.value = 0
    clearTicker()
    ticker = setInterval(() => { seconds.value += 1 }, 1000)
  },
  stopped(file, duration) {
    clearTicker()
    recording.value = false
    seconds.value = Math.round(duration / 1000)
    if (typeof file === 'string') audioPath.value = file
    else { h5Blob = file; audioPath.value = URL.createObjectURL(file) }
  },
  failed(error, stillRecording) {
    starting.value = false
    if (!stillRecording) { clearTicker(); recording.value = false }
    message.value = error
  },
}, { minimumMs: 2000, shortMessage: '请至少录制两秒清晰哭声，再点击停止。' })
function cancelRecording() {
  voice.cancel()
  clearTicker()
  starting.value = false
  recording.value = false
}
async function toggleRecording() {
  if (busy.value || starting.value) return
  if (recording.value) { voice.stop(); return }
  clearAudio()
  message.value = ''
  starting.value = true
  await voice.start()
}

function chooseAudio() {
  if (busy.value || starting.value || recording.value) return
  // #ifndef H5
  uni.chooseMessageFile?.({
    count: 1,
    type: 'file',
    extension: ['mp3', 'wav', 'm4a', 'aac', 'ogg'],
    success: (result) => {
      const file = result.tempFiles[0]
      if (file && alive) { clearAudio(); seconds.value = 0; audioPath.value = file.path }
    },
    fail: () => {
      // H5 / 无 chooseMessageFile 时用 chooseFile 或提示
      uni.showToast({ title: '请在支持的环境选择音频', icon: 'none' })
    },
  })
  // #endif
  // #ifdef H5
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'audio/*'
  input.onchange = () => {
    const file = input.files?.[0]
    if (!file || !alive) return
    clearAudio()
    h5Blob = file
    audioPath.value = URL.createObjectURL(file)
    const probe = new Audio(audioPath.value)
    probe.onloadedmetadata = () => {
      if (Number.isFinite(probe.duration)) seconds.value = Math.ceil(probe.duration)
    }
    uni.showToast({ title: '音频已载入', icon: 'none' })
  }
  input.click()
  // #endif
}

function openResult(id?: string) {
  if (id) cryAnalysisStore.select(id)
  uni.navigateTo({ url: '/pages/cry/result' })
}

async function analyze() {
  if (!audioPath.value || busy.value || recording.value || starting.value) return
  const version = operation
  busy.value = true
  message.value = ''
  try {
    if (!state.baby) await recordStore.load()
    if (!state.baby) throw new Error('请先完善宝宝档案')
    const duration = seconds.value > 0 ? seconds.value * 1000 : undefined
    const media = h5Blob
      ? await api.uploadBlob(h5Blob, state.baby.id, 'audio', duration, 'cry_analysis')
      : await api.uploadPath(audioPath.value, state.baby.id, 'audio', duration, 'cry_analysis')
    const result = await api.analyzeCry(state.baby.id, media.id)
    if (!alive || version !== operation) return
    cryAnalysisStore.add(result)
    openResult()
  } catch (reason) {
    if (alive && version === operation) message.value = errorText(reason)
  } finally {
    if (alive && version === operation) busy.value = false
  }
}

onShow(() => { if (!state.baby && !state.loading) void recordStore.load() })
onHide(() => { operation++; busy.value = false; cancelRecording() })
onBeforeUnmount(() => {
  alive = false
  operation++
  cancelRecording()
  if (audioPath.value.startsWith('blob:')) URL.revokeObjectURL(audioPath.value)
})
</script>

<template>
  <view class="page">
    <text class="title">听一听，宝宝想说什么</text>
    <text class="muted">一起了解哭声背后的可能需求</text>

    <button class="mic" aria-label="开始或停止录音" :disabled="busy || starting" :class="{ recording }" @click="toggleRecording">{{ recording ? '■' : '♩' }}</button>
    <text class="status">{{ recording ? `录音中 ${seconds} 秒 · 点击停止` : starting ? '正在申请麦克风权限…' : '点击开始录音' }}</text>

    <button v-if="recording || starting" class="outline" @click="cancelRecording">取消录音</button>
    <view v-if="audioPath" class="audio-box">
      <!-- #ifdef H5 -->
      <audio class="audio" :src="audioPath" controls />
      <!-- #endif -->
      <button class="primary" :disabled="busy || recording || starting" @click="analyze">{{ busy ? '正在分析…' : '分析哭声' }}</button>
    </view>

    <button class="outline" :disabled="busy || recording || starting" @click="chooseAudio">↥ 上传音频</button>
    <text v-if="message" class="error">{{ message }}</text>
    <text class="notice">音频会上传用于实验性分析。结果只表示声音与样本的匹配程度，不能确定宝宝哭泣的真实原因。</text>

    <view class="section">
      <text class="card-title">最近分析</text>
      <text v-if="!cryAnalysisStore.state.analyses.length" class="notice">暂无分析记录</text>
      <button v-for="item in cryAnalysisStore.state.analyses" :key="item.id" class="event" @click="openResult(item.id)">
        <text class="bubble">▷</text>
        <view>
          <text class="event-title">{{ item.time }}</text>
          <text class="muted">{{ item.summary }}</text>
        </view>
      </button>
    </view>
  </view>
</template>

<style scoped>
.page { padding: 24px 18px 40px; background: var(--db-background); color: var(--db-text); text-align: center; }
.title { display: block; font-size: 23px; font-weight: 800; margin-top: 12px; }
.muted { display: block; color: var(--db-muted); font-size: 14px; margin-top: 6px; }
.mic { width: 148px; height: 148px; margin: 36px auto 20px; border-radius: 50%; background: var(--db-primary); color: white; font-size: 42px; border: 18px solid var(--db-soft); outline: 14px solid var(--db-soft); }
.mic.recording { background: #ca7d69; }
.status { display: block; margin-bottom: 16px; color: var(--db-muted); }
.audio-box { margin: 12px 0; }
.audio { width: 100%; margin-bottom: 10px; }
.primary { width: 100%; min-height: 52px; border-radius: 14px; background: var(--db-primary); color: white; font-weight: 700; }
.primary[disabled] { opacity: .55; }
.outline { width: 100%; min-height: 50px; margin-top: 12px; border-radius: 14px; border: 1px solid var(--db-border); background: var(--db-surface); color: var(--db-primary); }
.error { display: block; margin-top: 14px; color: #b35d52; font-size: 13px; }
.notice { display: block; margin-top: 14px; color: var(--db-muted); font-size: 14px; line-height: 1.6; }
.section { margin-top: 28px; text-align: left; }
.card-title { display: block; font-size: 17px; font-weight: 800; margin-bottom: 10px; }
.event { width: 100%; display: flex; gap: 12px; align-items: center; padding: 14px 0; border-bottom: 1px solid var(--db-border); background: transparent; text-align: left; }
.bubble { width: 37px; height: 37px; border-radius: 50%; background: var(--db-soft); display: grid; place-items: center; }
.event-title { display: block; font-size: 14px; font-weight: 700; }
</style>
