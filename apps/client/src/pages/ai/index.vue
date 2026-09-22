<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AccountGone from '@/components/AccountGone.vue'
import { aiChatStore } from '@/features/content/aiChat'
import { babyDisplayName, nowParts } from '@/features/record/domain'
import { recordStore } from '@/features/record/store'
import { api, ApiError, SessionError } from '@/services/api'

const { state } = recordStore
const question = ref('')
const babyName = computed(() => babyDisplayName(state.baby?.nickname))
const ageLabel = computed(() => {
  const birth = state.baby?.birth_date
  if (!birth) return '月龄待完善'
  const parts = birth.split('-').map(Number)
  const todayParts = nowParts().date.split('-').map(Number)
  const y = parts[0] ?? 0
  const m = parts[1] ?? 1
  const d = parts[2] ?? 1
  const ty = todayParts[0] ?? 0
  const tm = todayParts[1] ?? 1
  const td = todayParts[2] ?? 1
  let months = (ty - y) * 12 + (tm - m)
  if (td < d) months -= 1
  return `${Math.max(0, months)} 月龄`
})
const prompts = ['帮我看看最近的睡眠记录', '今天一共喝了多少奶？', '辅食应该什么时候开始添加？']

const recording = ref(false)
const pendingPreview = ref('')
const pendingMediaId = ref<string | null>(null)
let h5Recorder: MediaRecorder | null = null
let h5Stream: MediaStream | null = null
let h5Chunks: Blob[] = []
let mpRecorder: ReturnType<typeof uni.getRecorderManager> | null = null
let startedAt = 0

async function ask(text?: string) {
  const babyId = state.baby?.id
  if (!babyId) {
    uni.showToast({ title: '请先完善宝宝档案', icon: 'none' })
    return
  }
  const q = (text ?? question.value).trim()
  const mediaId = pendingMediaId.value
  if (!q && !mediaId) {
    uni.showToast({ title: '请先输入问题或选一张图片', icon: 'none' })
    return
  }
  question.value = ''
  const preview = pendingPreview.value
  pendingPreview.value = ''
  pendingMediaId.value = null
  await aiChatStore.ask(babyId, q, mediaId, preview || undefined)
}

function clearPendingPhoto() {
  pendingPreview.value = ''
  pendingMediaId.value = null
}

function choosePhoto() {
  const babyId = state.baby?.id
  if (!babyId) {
    uni.showToast({ title: '请先完善宝宝档案', icon: 'none' })
    return
  }
  uni.chooseImage({
    count: 1,
    sizeType: ['compressed'],
    sourceType: ['camera', 'album'],
    success(result) {
      const path = result.tempFilePaths[0]
      if (!path) return
      pendingPreview.value = path
      uni.showLoading({ title: '上传图片…' })
      void api
        .uploadPath(path, babyId, 'image')
        .then((media) => {
          pendingMediaId.value = media.id
        })
        .catch((error) => {
          clearPendingPhoto()
          const message = error instanceof ApiError || error instanceof SessionError ? error.message : '图片上传失败'
          uni.showToast({ title: message, icon: 'none' })
        })
        .finally(() => uni.hideLoading())
    },
  })
}

function clearChat() {
  const babyId = state.baby?.id
  if (!babyId) {
    uni.showToast({ title: '请先完善宝宝档案', icon: 'none' })
    return
  }
  if (!aiChatStore.state.messages.length) {
    uni.showToast({ title: '还没有对话记录', icon: 'none' })
    return
  }
  uni.showModal({
    title: '清空对话？',
    content: '宝宝档案和日常记录会保留，仅新开一条聊天。',
    success: ({ confirm }) => {
      if (confirm) void aiChatStore.clear(babyId)
    },
  })
}

function stopVoice() {
  // #ifdef H5
  if (h5Recorder?.state === 'recording') h5Recorder.stop()
  // #endif
  // #ifndef H5
  mpRecorder?.stop()
  // #endif
  recording.value = false
}

async function sendVoiceAsQuestion(filePathOrBlob: string | Blob, durationMs: number) {
  const babyId = state.baby?.id
  if (!babyId) return
  uni.showLoading({ title: '正在转写…' })
  try {
    const media =
      typeof filePathOrBlob === 'string'
        ? await api.uploadPath(filePathOrBlob, babyId, 'audio', durationMs)
        : await api.uploadBlob(filePathOrBlob, babyId, 'audio', durationMs)
    // 复用草稿 ASR，但不 confirm，避免写入正式记录
    const draft = await api.draftFromMedia('voice', babyId, media.id)
    const text = (draft.transcript || '').trim()
    if (!text) {
      uni.showToast({ title: '没听清，请改打字', icon: 'none' })
      return
    }
    question.value = text
    await ask(text)
  } catch (error) {
    const message = error instanceof ApiError || error instanceof SessionError ? error.message : '语音失败，请改打字'
    uni.showToast({ title: message, icon: 'none' })
  } finally {
    uni.hideLoading()
  }
}

async function startVoice() {
  const babyId = state.baby?.id
  if (!babyId) {
    uni.showToast({ title: '请先完善宝宝档案', icon: 'none' })
    return
  }
  if (recording.value) {
    stopVoice()
    return
  }
  // #ifdef H5
  try {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') throw new Error('unsupported')
    h5Stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    h5Chunks = []
    const mimeType = MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : 'audio/webm'
    h5Recorder = new MediaRecorder(h5Stream, { mimeType })
    h5Recorder.ondataavailable = (event) => {
      if (event.data.size) h5Chunks.push(event.data)
    }
    h5Recorder.onstop = () => {
      h5Stream?.getTracks().forEach((track) => track.stop())
      h5Stream = null
      const durationMs = Math.min(60_000, Date.now() - startedAt)
      const blob = new Blob(h5Chunks, { type: h5Recorder?.mimeType || 'audio/webm' })
      h5Recorder = null
      recording.value = false
      void sendVoiceAsQuestion(blob, durationMs)
    }
    startedAt = Date.now()
    h5Recorder.start()
    recording.value = true
  } catch {
    uni.showToast({ title: '无法录音，请改打字', icon: 'none' })
  }
  // #endif
  // #ifndef H5
  mpRecorder = uni.getRecorderManager()
  mpRecorder.onStop((result) => {
    recording.value = false
    void sendVoiceAsQuestion(result.tempFilePath, Math.min(60_000, Date.now() - startedAt))
  })
  mpRecorder.onError(() => {
    recording.value = false
    uni.showToast({ title: '录音失败', icon: 'none' })
  })
  startedAt = Date.now()
  mpRecorder.start({ format: 'mp3', duration: 60_000 })
  recording.value = true
  // #endif
}

onBeforeUnmount(() => stopVoice())

onShow(() => {
  void recordStore.load(nowParts().date).then(() => {
    if (state.baby?.id) void aiChatStore.load(state.baby.id)
  })
})
</script>

<template>
  <view class="page">
    <AccountGone v-if="state.accountDeleted" />
    <template v-else>
      <view class="head">
        <view class="brand">
          <text class="cloud">•ᴗ•</text>
          <view>
            <text class="title">懂宝 AI</text>
            <text class="muted">正在结合：{{ babyName }} · {{ ageLabel }}</text>
          </view>
        </view>
        <button class="link" @click="clearChat">清空</button>
      </view>

      <view v-if="aiChatStore.state.banner" class="warn">{{ aiChatStore.state.banner }}</view>

      <view v-if="!aiChatStore.state.messages.length" class="welcome">
        <text class="title">今天有什么想和我聊聊？</text>
        <text class="muted">我会结合{{ babyName }}的档案、近期记录，并检索专业育儿知识。</text>
        <view class="card">
          <text class="card-title">从这些问题开始</text>
          <button v-for="item in prompts" :key="item" class="outline" :disabled="aiChatStore.state.loading" @click="ask(item)">{{ item }}</button>
        </view>
      </view>

      <view v-for="(msg, index) in aiChatStore.state.messages" :key="index" class="thread">
        <view class="user">
          <image v-if="msg.imagePreview" class="user-photo" :src="msg.imagePreview" mode="aspectFill" />
          <text>{{ msg.q }}</text>
        </view>
        <view class="answer">
          <text class="card-title">{{ msg.answer?.summary || msg.a }}</text>
          <view v-if="msg.answer?.actions?.length" class="block">
            <text class="label">现在可以怎么做</text>
            <text v-for="(line, i) in msg.answer.actions" :key="i" class="line">· {{ line }}</text>
          </view>
          <view v-if="msg.answer?.watch_for?.length" class="block">
            <text class="label">需要观察什么</text>
            <text v-for="(line, i) in msg.answer.watch_for" :key="i" class="line">· {{ line }}</text>
          </view>
          <view v-if="msg.answer?.sources?.length" class="block">
            <text class="label">参考</text>
            <text v-for="(src, i) in msg.answer.sources" :key="i" class="line">· {{ src.title }}</text>
          </view>
          <text v-if="msg.answer?.watch_for?.length && msg.answer?.medical_disclaimer" class="notice">{{ msg.answer.medical_disclaimer }}</text>
        </view>
      </view>

      <view v-if="pendingPreview" class="pending">
        <image class="pending-photo" :src="pendingPreview" mode="aspectFill" />
        <text class="muted">已选图片，可再写一句问题后发送</text>
        <button class="link" @click="clearPendingPhoto">去掉</button>
      </view>

      <view class="composer">
        <button class="mic" :class="{ on: recording }" @click="startVoice">{{ recording ? '■' : '🎤' }}</button>
        <button class="mic" :disabled="aiChatStore.state.loading" @click="choosePhoto">🖼</button>
        <input v-model="question" class="input" maxlength="500" placeholder="继续问懂宝…" confirm-type="send" :disabled="aiChatStore.state.loading" @confirm="ask()" />
        <button class="send" :disabled="aiChatStore.state.loading" @click="ask()">{{ aiChatStore.state.loading ? '…' : '↑' }}</button>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 14px 19px calc(120px + env(safe-area-inset-bottom)); background: #fbfaf7; color: #203f4a; }
.head { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.brand { display: flex; gap: 10px; align-items: center; }
.cloud { width: 40px; height: 32px; border-radius: 50%; background: #b7e4f5; color: #25516a; font-size: 16px; letter-spacing: 3px; text-align: center; line-height: 32px; }
.title { display: block; font-size: 18px; font-weight: 800; }
.muted { display: block; color: #71858b; font-size: 13px; line-height: 1.5; margin-top: 4px; }
.link { background: transparent; color: #2d8098; font-size: 12px; }
.warn { margin: 14px 0; border-radius: 12px; background: #fff0df; color: #b88346; padding: 10px 12px; font-size: 12px; }
.welcome { margin-top: 18px; }
.welcome .title { font-size: 23px; }
.card { margin-top: 16px; border-radius: 19px; background: white; border: 1px solid #eef1ef; padding: 16px; }
.card-title { display: block; font-size: 16px; font-weight: 800; margin-bottom: 8px; }
.outline { display: block; width: 100%; margin-top: 10px; min-height: 48px; border-radius: 14px; border: 1px solid #bedbe4; background: white; color: #328da9; font-size: 14px; }
.user { margin: 18px 0 12px 28px; padding: 12px 15px; border-radius: 17px 17px 4px 17px; background: #d8edf4; font-size: 14px; }
.user-photo { display: block; width: 120px; height: 120px; border-radius: 10px; margin-bottom: 8px; }
.answer { margin: 12px 0; padding: 16px; border-radius: 4px 18px 18px 18px; background: white; border: 1px solid #eef1ef; }
.block { margin-top: 10px; }
.label { display: block; font-size: 12px; font-weight: 700; color: #2d8098; margin-bottom: 4px; }
.line { display: block; font-size: 13px; line-height: 1.6; color: #203f4a; }
.notice { display: block; margin-top: 10px; color: #8b9c9f; font-size: 11px; }
.pending { display: flex; align-items: center; gap: 10px; margin: 12px 0 72px; padding: 10px 12px; border-radius: 12px; background: #edf6f8; }
.pending-photo { width: 48px; height: 48px; border-radius: 8px; flex-shrink: 0; }
.composer { position: fixed; left: 0; right: 0; bottom: calc(50px + env(safe-area-inset-bottom)); display: flex; align-items: center; gap: 8px; padding: 10px 15px; background: white; border-top: 1px solid #e9eff0; }
.mic { width: 40px; height: 40px; flex-shrink: 0; border-radius: 50%; background: #edf6f8; color: #328da9; font-size: 16px; line-height: 40px; }
.mic.on { background: #f8d7da; color: #a33; }
.input { flex: 1; min-width: 0; height: 44px; line-height: 44px; border-radius: 22px; background: #f3f7f8; padding: 0 15px; font-size: 15px; }
.send { width: 40px; height: 40px; flex-shrink: 0; border-radius: 50%; background: #328da9; color: white; font-size: 18px; line-height: 40px; }
</style>
