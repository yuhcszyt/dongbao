import { reactive } from 'vue'

/** No storage or network work until the user explicitly confirms login. */
export function createGuestAccess(login: () => Promise<void>) {
  const state = reactive({ authenticated: false, visible: false, agreed: false, busy: false, error: '' })
  let pending: (() => void) | null = null
  let revision = 0
  function require(action: () => void) {
    if (state.authenticated) { action(); return }
    pending = action; state.visible = true; state.error = ''; state.agreed = false
  }
  function cancel() {
    if (state.busy) return
    pending = null; state.visible = false; state.agreed = false; state.error = ''
  }
  async function confirm() {
    if (state.busy) return
    if (!state.agreed) { state.error = '请先阅读并同意登录及数据使用说明'; return }
    const current = revision
    state.busy = true; state.error = ''
    try {
      await login()
      if (current !== revision) return
      state.authenticated = true; state.visible = false; state.busy = false
      const action = pending; pending = null
      action?.()
    } catch (error) {
      if (current === revision) state.error = error instanceof Error ? error.message : '登录失败，请重试'
    } finally { if (current === revision) state.busy = false }
  }
  function reset() {
    revision++; pending = null
    Object.assign(state, { authenticated: false, visible: false, agreed: false, busy: false, error: '' })
  }
  return { state, require, confirm, cancel, reset }
}
