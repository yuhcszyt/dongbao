<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import { cryDemoStore } from '@/features/content/cryDemo'

const recording = ref(false)
const seconds = ref(0)
const audioPath = ref('')
const busy = ref(false)
let ticker: ReturnType<typeof setInterval> | null = null
let h5Recorder: MediaRecorder | null = null
let h5Stream: MediaStream | null = null
let h5Chunks: Blob[] = []
let mpRecorder: ReturnType<typeof uni.getRecorderManager> | null = null

const clearTicker = () => {
  if (ticker) clearInterval(ticker)
  ticker = null
}

function stopRecording() {
  clearTicker()
  recording.value = false
  if (h5Recorder?.state === 'recording') h5Recorder.stop()
  else h5Stream?.getTracks().forEach((track) => track.stop())
  mpRecorder?.stop()
}

async function startH5() {
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    uni.showToast({ title: '请改用上传音频', icon: 'none' })
    return
  }
  busy.value = true
  try {
    h5Stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    h5Chunks = []
    h5Recorder = new MediaRecorder(h5Stream)
    h5Recorder.ondataavailable = (event) => {
      if (event.data.size) h5Chunks.push(event.data)
    }
    h5Recorder.onstop = () => {
      h5Stream?.getTracks().forEach((track) => track.stop())
      const blob = new Blob(h5Chunks, { type: h5Recorder?.mimeType || 'audio/webm' })
      audioPath.value = URL.createObjectURL(blob)
    }
    h5Recorder.start()
    recording.value = true
    seconds.value = 0
    ticker = setInterval(() => {
      seconds.value += 1
      if (seconds.value >= 60) stopRecording()
    }, 1000)
  } catch {
    uni.showToast({ title: '无法访问麦克风', icon: 'none' })
  } finally {
    busy.value = false
  }
}

function startMp() {
  mpRecorder = uni.getRecorderManager()
  mpRecorder.onStop((result) => {
    audioPath.value = result.tempFilePath
  })
  mpRecorder.onError(() => uni.showToast({ title: '录音失败', icon: 'none' }))
  mpRecorder.start({ format: 'mp3', duration: 60_000 })
  recording.value = true
  seconds.value = 0
  ticker = setInterval(() => {
    seconds.value += 1
    if (seconds.value >= 60) stopRecording()
  }, 1000)
}

function toggleRecording() {
  if (busy.value) return
  if (recording.value) {
    stopRecording()
    return
  }
  // #ifdef H5
  void startH5()
  // #endif
  // #ifndef H5
  startMp()
  // #endif
}

function chooseAudio() {
  uni.chooseMessageFile?.({
    count: 1,
    type: 'file',
    extension: ['mp3', 'wav', 'm4a', 'aac', 'ogg'],
    success: (result) => {
      const file = result.tempFiles[0]
      if (file) audioPath.value = file.path
    },
    fail: () => {
      // H5 / 无 chooseMessageFile 时用 chooseFile 或提示
      uni.showToast({ title: '请在支持的环境选择音频', icon: 'none' })
    },
  })
  // #ifdef H5
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'audio/*'
  input.onchange = () => {
    const file = input.files?.[0]
    if (!file) return
    if (audioPath.value.startsWith('blob:')) URL.revokeObjectURL(audioPath.value)
    audioPath.value = URL.createObjectURL(file)
    uni.showToast({ title: '音频已载入（本机）', icon: 'none' })
  }
  input.click()
  // #endif
}

function openResult() {
  uni.navigateTo({ url: '/pages/cry/result' })
}

function analyze() {
  cryDemoStore.addDemoResult()
  openResult()
}

onShow(() => {})
onBeforeUnmount(() => stopRecording())
</script>

<template>
  <view class="page">
    <text class="title">听一听，宝宝想说什么</text>
    <text class="muted">一起了解哭声背后的可能需求</text>

    <button class="mic" :class="{ recording }" @click="toggleRecording">{{ recording ? '■' : '♩' }}</button>
    <text class="status">{{ recording ? `录音中 ${seconds} 秒 · 点击停止` : '点击开始录音' }}</text>

    <view v-if="audioPath" class="audio-box">
      <!-- #ifdef H5 -->
      <audio class="audio" :src="audioPath" controls />
      <!-- #endif -->
      <button class="primary" @click="analyze">查看模拟分析</button>
    </view>

    <button class="outline" @click="chooseAudio">↥ 上传音频</button>
    <button class="link" @click="analyze">不录音，直接体验模拟结果 →</button>
    <text class="notice">录音仅在本机预览，不会上传。<br>分析结果为演示，不代表真实识别。</text>

    <view class="section">
      <text class="card-title">最近分析 · 演示</text>
      <text v-if="!cryDemoStore.state.analyses.length" class="notice">暂无分析记录</text>
      <button v-for="item in cryDemoStore.state.analyses" :key="item.id" class="event" @click="openResult">
        <text class="bubble">▷</text>
        <view>
          <text class="event-title">{{ item.time }}</text>
          <text class="muted">模拟结果，不代表真实分析</text>
        </view>
      </button>
    </view>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 24px 18px 120px; background: #fbfaf7; color: #203f4a; text-align: center; }
.title { display: block; font-size: 23px; font-weight: 800; margin-top: 12px; }
.muted { display: block; color: #71858b; font-size: 14px; margin-top: 6px; }
.mic { width: 148px; height: 148px; margin: 36px auto 20px; border-radius: 50%; background: #328da9; color: white; font-size: 42px; border: 18px solid #e3f3f8; outline: 14px solid #f0f8fb; }
.mic.recording { background: #ca7d69; }
.status { display: block; margin-bottom: 16px; color: #49646d; }
.audio-box { margin: 12px 0; }
.audio { width: 100%; margin-bottom: 10px; }
.primary { width: 100%; min-height: 52px; border-radius: 14px; background: #328da9; color: white; font-weight: 700; }
.outline { width: 100%; min-height: 50px; margin-top: 12px; border-radius: 14px; border: 1px solid #bedbe4; background: white; color: #328da9; }
.link { display: block; margin: 18px auto; background: transparent; color: #2d8098; font-size: 13px; }
.notice { display: block; margin-top: 14px; color: #8b9c9f; font-size: 12px; line-height: 1.6; }
.section { margin-top: 28px; text-align: left; }
.card-title { display: block; font-size: 17px; font-weight: 800; margin-bottom: 10px; }
.event { width: 100%; display: flex; gap: 12px; align-items: center; padding: 14px 0; border-bottom: 1px solid #eff2f1; background: transparent; text-align: left; }
.bubble { width: 37px; height: 37px; border-radius: 50%; background: #ecf6f8; display: grid; place-items: center; }
.event-title { display: block; font-size: 14px; font-weight: 700; }
</style>
