<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { onHide, onShow } from '@dcloudio/uni-app'
import AccountGone from '@/components/AccountGone.vue'
import { aiChatStore } from '@/features/content/aiChat'
import { babyDisplayName, nowParts } from '@/features/record/domain'
import { recordStore, errorText } from '@/features/record/store'
import { api } from '@/services/api'
import { createVoiceCapture } from '@/features/record/voiceCapture'
import type { CaptureResult } from '@/features/record/quickCapture'
import { requestQuickAction } from '@/features/record/quickAction'

const { state } = recordStore
const question = ref('')
const babyName = computed(() => babyDisplayName(state.baby?.nickname))
const ageLabel = computed(() => {
  if (!state.baby?.birth_date) return '月龄待完善'
  const birth = new Date(state.baby.birth_date + 'T00:00:00')
  const today = new Date()
  const months = (today.getFullYear() - birth.getFullYear()) * 12 + today.getMonth() - birth.getMonth() - Number(today.getDate() < birth.getDate())
  return `${Math.max(0, months)} 月龄`
})
const prompts = ['帮我看看最近的睡眠记录', '今天一共喝了多少奶？', '辅食应该什么时候开始添加？']
const recording = ref(false)
const starting = ref(false)
const working = ref(false)
const refreshing = ref(false)
const pendingPreview = ref('')
const pendingMediaId = ref<string | null>(null)
const pending = ref<CaptureResult[]>([])
const selectedDraft = ref('')
const activeDraft = computed(() => pending.value.find((item) => item.draft_id === selectedDraft.value) ?? pending.value[0])
const busy = computed(() => working.value || refreshing.value || starting.value || aiChatStore.state.loading)
let photoVersion = 0
let alive = true
let refreshVersion = 0
let retryVoice: (() => Promise<void>) | null = null
const failedReply = ref<{ draftId: string; requestId: string; text: string; mediaId?: string } | null>(null)
const canRetryVoice = ref(false)
const newRequestId = () => 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
  const r = Math.floor(Math.random() * 16)
  return (c === 'x' ? r : (r & 3) | 8).toString(16)
})

async function refresh() {
  const babyId = state.baby?.id
  if (!babyId) return
  const version = ++refreshVersion
  refreshing.value = true
  try {
    const result = await api.pendingCaptures(babyId)
    if (version !== refreshVersion || !alive) return
    pending.value = result
    await aiChatStore.load(babyId)
  } catch (error) {
    if (version === refreshVersion) aiChatStore.state.banner = errorText(error)
  } finally {
    if (version === refreshVersion) refreshing.value = false
  }
}

async function submitReply(reply: NonNullable<typeof failedReply.value>) {
  failedReply.value = reply
  const result = await api.replyCapture(reply.draftId, reply.requestId, reply.text, reply.mediaId)
  failedReply.value = null
  if (result.state === 'saved') {
    uni.showToast({ title: '已成功记录', icon: 'success' })
    await recordStore.load(nowParts().date)
  }
  await refresh()
}

async function ask(text?: string) {
  if (busy.value || recording.value) return
  const babyId = state.baby?.id
  if (!babyId) return
  const q = (text ?? question.value).trim()
  if (!q && !pendingMediaId.value && !failedReply.value) return
  working.value = true
  aiChatStore.state.banner = ''
  try {
    if (activeDraft.value || failedReply.value) {
      await submitReply(failedReply.value ?? { draftId: activeDraft.value!.draft_id, requestId: newRequestId(), text: q })
    } else {
      const ok = await aiChatStore.ask(babyId, q, pendingMediaId.value, pendingPreview.value || undefined)
      if (!ok) return
    }
    question.value = ''
    clearPendingPhoto()
  } catch (error) {
    aiChatStore.state.banner = errorText(error)
  } finally {
    working.value = false
  }
}

function clearPendingPhoto() { photoVersion++; pendingPreview.value = ''; pendingMediaId.value = null }

function choosePhoto() {
  if (busy.value || recording.value || activeDraft.value) return
  const babyId = state.baby?.id
  if (!babyId) return
  const version = ++photoVersion
  working.value = true
  uni.chooseImage({
    count: 1, sizeType: ['compressed'], sourceType: ['camera', 'album'],
    async success(result) {
      const path = result.tempFilePaths[0]
      if (!path || !alive || version !== photoVersion) { working.value = false; return }
      try {
        const media = await api.uploadPath(path, babyId, 'image')
        if (alive && version === photoVersion) { pendingPreview.value = path; pendingMediaId.value = media.id }
      } catch (error) { aiChatStore.state.banner = errorText(error) }
      finally { working.value = false }
    },
    fail(result) {
      working.value = false
      if (!result.errMsg.includes('cancel')) aiChatStore.state.banner = '无法打开照片，请检查权限后重试。'
    },
  })
}

async function cancelDraft() {
  if (busy.value || !activeDraft.value?.media) return
  working.value = true
  try {
    const result = await api.cancelCapture(activeDraft.value.media.id)
    if (result.state === 'saved') {
      uni.showToast({ title: '这条已保存，可查看修改', icon: 'none' })
      await recordStore.load(nowParts().date)
    }
    failedReply.value = null
    question.value = ''
    await refresh()
  } catch (error) { aiChatStore.state.banner = errorText(error) }
  finally { working.value = false }
}

function clearChat() {
  if (busy.value || recording.value) return
  if (pending.value.length) { aiChatStore.state.banner = '还有待补充的记录，请先补充或取消。'; return }
  uni.showModal({
    title: '新开对话？', content: '日常记录会保留，当前聊天将收起。',
    success: ({ confirm }) => { if (confirm && state.baby) void aiChatStore.clear(state.baby.id) },
  })
}

async function sendVoice(file: string | Blob, duration: number) {
  const babyId = state.baby?.id
  if (!babyId) return
  working.value = true
  aiChatStore.state.banner = ''
  canRetryVoice.value = false
  // 上传成功后重试沿用同一个媒体；补充请求沿用同一个 request_id。
  let mediaId: string | undefined
  const target = activeDraft.value?.draft_id
  const requestId = newRequestId()
  const run = async () => {
    working.value = true
    try {
      mediaId ??= (typeof file === 'string' ? await api.uploadPath(file, babyId, 'audio', duration) : await api.uploadBlob(file, babyId, 'audio', duration)).id
      if (target) await submitReply({ draftId: target, requestId, text: '', mediaId })
      else {
        const result = await api.transcribe(mediaId)
        question.value = result.transcript
        const ok = await aiChatStore.ask(babyId, result.transcript)
        if (!ok) return
        question.value = ''
      }
      retryVoice = null
      canRetryVoice.value = false
    } catch (error) { aiChatStore.state.banner = errorText(error); canRetryVoice.value = true }
    finally { working.value = false }
  }
  retryVoice = run
  await run()
}

const voice = createVoiceCapture({
  started() { starting.value = false; recording.value = true },
  stopped(file, duration) { recording.value = false; void sendVoice(file, duration) },
  failed(message, stillRecording) { starting.value = false; recording.value = !!stillRecording; aiChatStore.state.banner = message },
})
function startVoice() {
  if (recording.value) { voice.stop(); return }
  if (busy.value || failedReply.value) return
  starting.value = true
  aiChatStore.state.banner = ''
  void voice.start()
}
function cancelVoice() { voice.cancel(); starting.value = false; recording.value = false }
function openRecord(recordId: string) {
  requestQuickAction({ kind: 'edit', record_id: recordId })
  uni.switchTab({ url: '/pages/record/index' })
}

onHide(cancelVoice)
onBeforeUnmount(() => { alive = false; refreshVersion++; clearPendingPhoto(); cancelVoice() })
onShow(async () => {
  if (working.value) return
  refreshing.value = true
  await recordStore.load(nowParts().date)
  refreshing.value = false
  await refresh()
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
        <button class="link" :disabled="busy || recording" @click="clearChat">新对话</button>
      </view>

      <view v-if="aiChatStore.state.banner" class="warn">{{ aiChatStore.state.banner }}</view>
      <button v-if="canRetryVoice" class="outline" :disabled="busy" @click="retryVoice?.()">重试刚才的语音</button>
      <button v-else-if="failedReply" class="outline" :disabled="busy" @click="ask()">重试补充记录</button>
      <button v-else-if="aiChatStore.state.banner" class="outline" :disabled="busy" @click="refresh">重新加载</button>
      <view v-if="activeDraft" class="card followup">
        <text class="card-title">再说一句，就能记好</text>
        <view v-if="pending.length > 1">
          <button v-for="item in pending" :key="item.draft_id" class="outline" :disabled="busy || recording || !!failedReply" @click="selectedDraft = item.draft_id">{{ item.transcript || '照片记录' }}</button>
        </view>
        <text class="line">{{ activeDraft.question }}</text>
        <button class="outline" :disabled="busy || !!failedReply" @click="startVoice">{{ recording ? '■ 说完了' : '🎤 点这里说' }}</button>
        <button class="link" :disabled="busy || recording" @click="cancelDraft">取消这条待记录事项</button>
      </view>
      <view v-if="working || refreshing || starting || aiChatStore.state.loading" class="muted" role="status">{{ refreshing ? '正在加载…' : '正在处理，请稍候…' }}</view>
      <view v-if="recording" class="card">
        <text class="line">正在听你说，说完点“说完了”。</text>
        <button class="outline" @click="startVoice">■ 说完了</button>
        <button class="link" @click="cancelVoice">取消录音</button>
      </view>

      <view v-if="!activeDraft && !refreshing && !aiChatStore.state.messages.length" class="welcome">
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
          <button v-for="recordId in msg.answer?.related_record_ids || []" :key="recordId" class="outline" @click="openRecord(recordId)">查看 / 修改这条记录</button>
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
        <button class="mic" aria-label="语音输入" :class="{ on: recording }" :disabled="busy || !!failedReply" @click="startVoice">{{ recording ? '■' : '🎤' }}</button>
        <button class="mic" aria-label="选择照片" :disabled="busy || recording || !!activeDraft" @click="choosePhoto">🖼</button>
        <input v-model="question" class="input" maxlength="500" :placeholder="activeDraft ? '在这里补充，或点麦克风说…' : '继续问懂宝…'" confirm-type="send" :disabled="busy || recording || !!failedReply" @confirm="ask()" />
        <button class="send" aria-label="发送" :disabled="busy || recording" @click="ask()">{{ busy ? '…' : '↑' }}</button>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 14px 19px calc(120px + env(safe-area-inset-bottom)); background: var(--db-background); color: var(--db-text); }
.head { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.brand { display: flex; gap: 10px; align-items: center; }
.cloud { width: 40px; height: 32px; border-radius: 50%; background: var(--db-soft); color: var(--db-text); font-size: 16px; letter-spacing: 3px; text-align: center; line-height: 32px; }
.title { display: block; font-size: 18px; font-weight: 800; }
.muted { display: block; color: var(--db-muted); font-size: 13px; line-height: 1.5; margin-top: 4px; }
.link { background: transparent; color: var(--db-primary); font-size: 12px; }
.warn { margin: 14px 0; border-radius: 12px; background: #fff0df; color: #b88346; padding: 10px 12px; font-size: 12px; }
.welcome { margin-top: 18px; }
.welcome .title { font-size: 23px; }
.card { margin-top: 16px; border-radius: 19px; background: var(--db-surface); border: 1px solid var(--db-border); padding: 16px; }
.card-title { display: block; font-size: 16px; font-weight: 800; margin-bottom: 8px; }
.outline { display: block; width: 100%; margin-top: 10px; min-height: 48px; border-radius: 14px; border: 1px solid var(--db-border); background: var(--db-surface); color: var(--db-primary); font-size: 14px; }
.user { margin: 18px 0 12px 28px; padding: 12px 15px; border-radius: 17px 17px 4px 17px; background: var(--db-soft); font-size: 14px; }
.user-photo { display: block; width: 120px; height: 120px; border-radius: 10px; margin-bottom: 8px; }
.answer { margin: 12px 0; padding: 16px; border-radius: 4px 18px 18px 18px; background: var(--db-surface); border: 1px solid var(--db-border); }
.block { margin-top: 10px; }
.label { display: block; font-size: 12px; font-weight: 700; color: var(--db-primary); margin-bottom: 4px; }
.line { display: block; font-size: 16px; line-height: 1.7; color: var(--db-text); }
.followup .card-title { font-size: 20px; }
.followup .outline { min-height: 56px; font-size: 20px; }
.notice { display: block; margin-top: 10px; color: var(--db-muted); font-size: 11px; }
.pending { display: flex; align-items: center; gap: 10px; margin: 12px 0 72px; padding: 10px 12px; border-radius: 12px; background: var(--db-soft); }
.pending-photo { width: 48px; height: 48px; border-radius: 8px; flex-shrink: 0; }
.composer { position: fixed; left: 0; right: 0; bottom: calc(50px + env(safe-area-inset-bottom)); display: flex; align-items: center; gap: 8px; padding: 10px 15px; background: var(--db-surface); border-top: 1px solid var(--db-border); }
.mic { width: 44px; height: 44px; padding: 0; flex-shrink: 0; border-radius: 50%; background: var(--db-soft); color: var(--db-primary); font-size: 16px; line-height: 44px; }
.mic.on { background: #f8d7da; color: #a33; }
.input { flex: 1; min-width: 0; height: 44px; line-height: 44px; border-radius: 22px; background: var(--db-soft); padding: 0 15px; font-size: 15px; }
.send { width: 44px; height: 44px; padding: 0; flex-shrink: 0; border-radius: 50%; background: var(--db-primary); color: white; font-size: 18px; line-height: 44px; }
</style>
