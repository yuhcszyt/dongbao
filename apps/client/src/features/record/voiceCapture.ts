type MpOwner = { start: () => void; stop: (file: string) => void; error: () => void }
const bindings = new WeakMap<object, { active: boolean; owner?: MpOwner }>()

/** 微信录音器是全局单例，只注册一组分发器；取消后晚到事件不会落到新会话。 */
function bindMp(recorder: ReturnType<typeof uni.getRecorderManager>) {
  let binding = bindings.get(recorder)
  if (binding) return binding
  binding = { active: false }
  bindings.set(recorder, binding)
  recorder.onStart(() => binding!.owner?.start())
  recorder.onStop((result) => {
    binding!.active = false
    const owner = binding!.owner
    binding!.owner = undefined
    owner?.stop(result.tempFilePath)
  })
  recorder.onError(() => {
    binding!.active = false
    const owner = binding!.owner
    binding!.owner = undefined
    owner?.error()
  })
  return binding
}

/** 首页采集与 AI 补充共用，释放设备与本次回调。 */
export function createVoiceCapture(handlers: {
  started: () => void
  stopped: (file: string | Blob, duration: number, capturedAt: string) => void
  failed: (message: string, stillRecording?: boolean) => void
}, options: { minimumMs?: number; shortMessage?: string } = {}) {
  const minimumMs = options.minimumMs ?? 2000
  let generation = 0
  let startedAt = 0
  let timer: ReturnType<typeof setTimeout> | undefined
  let stopNative: (() => void) | undefined
  let release: (() => void) | undefined
  let starting = false
  let recording = false

  function clean() {
    clearTimeout(timer)
    release?.()
    release = undefined
    stopNative = undefined
    starting = false
    recording = false
  }

  function cancel() {
    generation++
    const stop = stopNative
    clean()
    try { stop?.() } catch { /* 取消不能阻塞关闭 */ }
  }

  async function start() {
    if (starting || recording) return
    starting = true
    const current = ++generation
    const begin = () => {
      if (current !== generation) return
      starting = false
      recording = true
      startedAt = Date.now()
      timer = setTimeout(stop, 60_000)
      handlers.started()
    }
    const done = (file: string | Blob) => {
      if (current !== generation) return
      const duration = Math.min(60_000, Date.now() - startedAt)
      const stamp = new Date(startedAt).toISOString()
      clean()
      generation++
      if (duration < minimumMs) handlers.failed(options.shortMessage ?? '没听完整，请再说一遍，至少说两秒。')
      else handlers.stopped(file, duration, stamp)
    }
    try {
      if (import.meta.env.UNI_PLATFORM === 'h5') {
        if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') throw new Error('unsupported')
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
        if (current !== generation) { stream.getTracks().forEach((track) => track.stop()); return }
        const mimeType = MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : 'audio/webm'
        const recorder = new MediaRecorder(stream, { mimeType })
        const chunks: Blob[] = []
        release = () => { recorder.onstop = null; recorder.onerror = null; stream.getTracks().forEach((track) => track.stop()) }
        recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data) }
        recorder.onstop = () => done(new Blob(chunks, { type: mimeType }))
        recorder.onerror = () => { if (current === generation) { cancel(); handlers.failed('录音失败，请检查麦克风权限后重试。') } }
        stopNative = () => { if (recorder.state === 'recording') recorder.stop() }
        recorder.start()
        begin()
      } else {
        const recorder = uni.getRecorderManager()
        const onError = () => { if (current === generation) { cancel(); handlers.failed('无法录音，请检查微信麦克风权限后重试。') } }
        const binding = bindMp(recorder)
        if (binding.active) throw new Error('recorder busy')
        const owner = { start: begin, stop: done, error: onError }
        binding.active = true
        binding.owner = owner
        release = () => { if (binding.owner === owner) binding.owner = undefined }
        stopNative = () => recorder.stop()
        recorder.start({ duration: 60_000, format: 'wav', sampleRate: 16_000, numberOfChannels: 1 })
      }
    } catch {
      if (current === generation) { cancel(); handlers.failed('无法录音，请检查麦克风权限后重试。') }
    }
  }

  function stop() {
    if (!recording) return
    if (Date.now() - startedAt < minimumMs) { handlers.failed(options.shortMessage ?? '请再说一会儿，说完点“说完了”。', true); return }
    recording = false
    clearTimeout(timer)
    try { stopNative?.() } catch { cancel(); handlers.failed('录音没有完成，请重新说一遍。') }
  }

  return { start, stop, cancel }
}
