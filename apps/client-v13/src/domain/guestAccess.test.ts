import { expect, it, vi } from 'vitest'
import { createGuestAccess } from './guestAccess'

it('游客进入和请求登录提示都不发起登录，取消不执行业务操作',()=>{
  const login=vi.fn(),action=vi.fn(),gate=createGuestAccess(login)
  expect(gate.state.authenticated).toBe(false)
  expect(login).not.toHaveBeenCalled()
  gate.require(action)
  expect(gate.state.visible).toBe(true);expect(gate.state.agreed).toBe(false)
  gate.cancel()
  expect(gate.state.visible).toBe(false);expect(login).not.toHaveBeenCalled();expect(action).not.toHaveBeenCalled()
})
it('未确认说明时不能登录，确认后执行原操作且只执行一次',async()=>{
  const login=vi.fn().mockResolvedValue(undefined),action=vi.fn(),gate=createGuestAccess(login)
  gate.require(action);await gate.confirm();expect(login).not.toHaveBeenCalled()
  gate.state.agreed=true;await gate.confirm()
  expect(gate.state.authenticated).toBe(true);expect(action).toHaveBeenCalledTimes(1)
  const next=vi.fn();gate.require(next);expect(next).toHaveBeenCalledTimes(1);expect(login).toHaveBeenCalledTimes(1)
})
it('登录失败保留原操作供重试，不显示已登录',async()=>{
  const login=vi.fn().mockRejectedValueOnce(new Error('网络失败')).mockResolvedValue(undefined),action=vi.fn(),gate=createGuestAccess(login)
  gate.require(action);gate.state.agreed=true;await gate.confirm()
  expect(gate.state.authenticated).toBe(false);expect(gate.state.error).toBe('网络失败');expect(action).not.toHaveBeenCalled()
  await gate.confirm();expect(action).toHaveBeenCalledTimes(1)
})
it('重复确认只发起一次请求，重置后丢弃晚到结果',async()=>{
  let resolve!:()=>void
  const login=vi.fn(()=>new Promise<void>(r=>{resolve=r})),action=vi.fn(),gate=createGuestAccess(login)
  gate.require(action);gate.state.agreed=true
  const first=gate.confirm();await gate.confirm();expect(login).toHaveBeenCalledTimes(1)
  gate.reset();resolve();await first
  expect(gate.state.authenticated).toBe(false);expect(action).not.toHaveBeenCalled()
})
it('取消待办后重新登录不会执行已取消操作',async()=>{
  const old=vi.fn(),next=vi.fn(),gate=createGuestAccess(async()=>{})
  gate.require(old);gate.cancel();gate.require(next);gate.state.agreed=true;await gate.confirm()
  expect(old).not.toHaveBeenCalled();expect(next).toHaveBeenCalledTimes(1)
})

it('登录成功恢复操作时已解除忙碌状态，导航和建档不会被拦截',async()=>{
  const gate=createGuestAccess(async()=>{})
  const action=vi.fn(()=>expect(gate.state.busy).toBe(false))
  gate.require(action);gate.state.agreed=true;await gate.confirm()
  expect(action).toHaveBeenCalledTimes(1)
})
