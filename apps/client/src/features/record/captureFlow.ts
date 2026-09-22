/**
 * 语音 / 拍照入口要在「用户点下去」的同一次手势里启动。
 * 首页和记录页都先打开面板，再按 mode 立刻 begin，不能再让用户点第二次。
 *
 * 微信 RecorderManager 是进程单例：onStop / onError 会叠加，必须只绑一次。
 */

export type CaptureMode = 'voice' | 'photo'

export type CapturePorts = {
  startVoice: () => void
  /** 拍照默认只开相机（首页/记录页快速入口）；面板内可再选相册。 */
  choosePhoto: (opts?: { cameraOnly?: boolean }) => void
}

export function runCapture(mode: CaptureMode, ports: CapturePorts) {
  if (mode === 'voice') ports.startVoice()
  else ports.choosePhoto({ cameraOnly: true })
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
