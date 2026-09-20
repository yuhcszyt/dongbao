/**
 * 语音 / 拍照入口要在「用户点下去」的同一次手势里启动。
 * 首页和记录页都先打开面板，再按 mode 立刻 begin，不能再让用户点第二次。
 *
 * 微信 RecorderManager 是进程单例：onStop / onError 会叠加，必须只绑一次。
 */

export type CaptureMode = 'voice' | 'photo'

export function runCapture(
  mode: CaptureMode,
  ports: { startVoice: () => void; choosePhoto: () => void },
) {
  if (mode === 'voice') ports.startVoice()
  else ports.choosePhoto()
}

export type RecorderLike = {
  onStop: (cb: (result: { tempFilePath: string }) => void) => void
  onError: (cb: () => void) => void
}

export function bindRecorderOnce(
  recorder: RecorderLike,
  bound: { current: boolean },
  handlers: {
    onStop: (result: { tempFilePath: string }) => void
    onError: () => void
  },
) {
  if (bound.current) return
  bound.current = true
  recorder.onStop(handlers.onStop)
  recorder.onError(handlers.onError)
}
