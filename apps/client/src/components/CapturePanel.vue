<script setup lang="ts">
import { computed, onBeforeUnmount, ref } from 'vue'
import { createQuickCapture } from '@/features/record/quickCapture'
import { createVoiceCapture } from '@/features/record/voiceCapture'
import { runCapture, type CaptureMode } from '@/features/record/captureFlow'
import { recordWhatText, type RecordItem, type RecordType } from '@/features/record/domain'

const props = defineProps<{ babyId: string }>()
const emit = defineEmits<{ close: []; manual: [type: RecordType]; saved: [record: RecordItem]; edit: [record: RecordItem] }>()
const recording = ref(false)
const opening = ref(false)
const error = ref('')
const previewPath = ref('')
let alive = true
let photoGeneration = 0
const flow = createQuickCapture(props.babyId, (result) => {
  if (result.state === 'saved' && result.record) emit('saved', result.record)
  if (result.state === 'needs_input') {
    emit('close')
    uni.switchTab({ url: '/pages/ai/index' })
  }
})
const { state } = flow
const voice = createVoiceCapture({
  started() { opening.value = false; recording.value = true },
  stopped(file, duration, capturedAt) {
    recording.value = false
    void flow.submit(file, 'audio', duration, capturedAt)
  },
  failed(message, stillRecording) { opening.value = false; recording.value = !!stillRecording; error.value = message },
})
const busy = computed(() => state.busy || state.cancelling || opening.value)
const saved = computed(() => state.result?.state === 'saved' ? state.result.record : null)

async function startVoice() {
  if (busy.value || recording.value) return
  if (state.error && !await flow.cancel()) return
  error.value = ''
  opening.value = true
  void voice.start()
}

function stopVoice() { error.value = ''; voice.stop() }

async function choosePhoto() {
  if (busy.value || recording.value) return
  if (state.error && !await flow.cancel()) return
  error.value = ''
  opening.value = true
  const generation = ++photoGeneration
  uni.chooseImage({
    count: 1, sizeType: ['compressed'], sourceType: ['camera'],
    success(result) {
      if (!alive || generation !== photoGeneration) return
      opening.value = false
      const path = result.tempFilePaths[0]
      if (!path) { emit('close'); return }
      previewPath.value = path
      void flow.submit(path, 'image')
    },
    fail(result) {
      if (!alive || generation !== photoGeneration) return
      opening.value = false
      if (result.errMsg.includes('cancel')) emit('close')
      else error.value = '无法打开相机，请检查相机权限后重试。'
    },
  })
}

function begin(mode: CaptureMode) { runCapture(mode, { startVoice, choosePhoto }) }

async function requestClose() {
  if (state.cancelling) return
  photoGeneration++
  voice.cancel()
  recording.value = false
  opening.value = false
  if (saved.value || await flow.cancel()) emit('close')
}

function editSaved() {
  if (!saved.value) return
  emit('edit', saved.value)
}

function viewSaved() { emit('close'); uni.switchTab({ url: '/pages/ai/index' }) }

function reset() { voice.cancel(); photoGeneration++; flow.dispose() }
defineExpose({ begin, reset, requestClose })
onBeforeUnmount(() => { alive = false; reset() })
</script>

<template>
  <view class="capture">
    <view class="heading">
      <text class="title">{{ saved ? '✓ 已成功记录' : '给宝宝记一笔' }}</text>
      <button class="close" aria-label="关闭" :disabled="state.cancelling" @click="requestClose">×</button>
    </view>
    <template v-if="saved">
      <text class="saved-summary">{{ recordWhatText(saved) }}</text>
      <text class="lead">已保存，在懂宝 AI 和记录里都能看到。</text>
      <button class="primary" @click="viewSaved">去懂宝 AI 查看</button>
      <button class="secondary" @click="editSaved">修改这条记录</button>
      <button class="secondary" @click="requestClose">完成</button>
    </template>
    <template v-else>
      <text class="lead">{{ recording ? '正在听你说，说完点下面的大按钮。' : '说一说，或拍一张，懂宝帮你记好。' }}</text>
      <image v-if="previewPath" class="preview" :src="previewPath" mode="aspectFit" />
      <view v-if="busy" class="status" role="status">{{ state.cancelling ? '正在确认取消结果…' : opening ? '正在打开，请稍候…' : '正在帮你识别、记好，请稍候…' }}</view>
      <button v-if="recording" class="primary speak" @click="stopVoice">■ 说完了</button>
      <view v-else-if="!busy" class="capture-buttons">
        <button class="primary" @click="startVoice">🎤 {{ error || state.error ? '重新说' : '语音记录' }}</button>
        <button class="photo" @click="choosePhoto">📷 {{ error || state.error ? '重新拍' : '拍照记录' }}</button>
      </view>
      <text v-if="error || state.error" class="warning" role="alert">{{ error || state.error }}</text>
      <button v-if="state.error && !busy && !state.cancelRequested" class="primary" @click="flow.retry">重试这次记录</button>
      <button class="secondary" :disabled="state.cancelling" @click="requestClose">取消</button>
      <button v-if="!recording && !busy && !state.error" class="secondary" @click="emit('manual', 'feeding')">手动填写</button>
    </template>
  </view>
</template>

<style scoped>
.capture { padding-bottom: 12px; color: var(--db-text); }
.heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.title { font-size: 24px; font-weight: 800; }
.close { flex-shrink: 0; width: 48px; height: 48px; line-height: 48px; border-radius: 50%; background: var(--db-soft); color: var(--db-text); font-size: 28px; padding: 0; }
.lead { display: block; margin: 18px 0; font-size: 18px; line-height: 1.6; color: var(--db-muted); }
.capture-buttons { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.primary, .photo, .secondary { margin-top: 12px; min-height: 52px; border-radius: 14px; font-size: 18px; font-weight: 650; }
.primary { background: var(--db-primary); color: white; }
.speak { min-height: 76px; font-size: 24px; }
.photo { background: var(--db-apricot); color: #6c5137; }
.secondary { background: var(--db-surface); color: var(--db-primary); border: 1px solid var(--db-border); }
.status { padding: 16px; border-radius: 14px; background: var(--db-soft); color: var(--db-primary); font-size: 18px; line-height: 1.6; }
.warning { display: block; margin-top: 16px; padding: 12px; border-radius: 12px; background: #fff4e5; color: #815b2f; font-size: 16px; line-height: 1.6; }
.saved-summary { display: block; margin-top: 24px; font-size: 23px; line-height: 1.5; font-weight: 700; }
.preview { width: 100%; height: 160px; border-radius: 14px; }
</style>
