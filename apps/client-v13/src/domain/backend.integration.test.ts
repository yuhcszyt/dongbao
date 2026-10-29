import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import type { RecordInput } from '@/features/record/domain'

// Opt-in: executes the actual frontend API and workspace against an isolated local backend.
// No browser, GUI, real WeChat login or external model service is used.
describe.skipIf(process.env.DONGBAO_LIVE_API !== '1')('真实HTTP前后端联调',()=>{
  const storage=new Map<string,string>()
  let api: typeof import('@/services/api').api
  let workspace: ReturnType<typeof import('./workspace').createWorkspace>
  beforeAll(async()=>{
    const base=process.env.VITE_API_BASE_URL||''
    if(!base.startsWith('http://127.0.0.1:8013/'))throw new Error('Live verification requires the dedicated localhost:8013 backend')
    vi.stubGlobal('uni',{
      getSystemInfoSync:()=>({uniPlatform:'h5'}),getStorageSync:(key:string)=>storage.get(key),
      setStorageSync:(key:string,value:string)=>storage.set(key,value),removeStorageSync:(key:string)=>storage.delete(key),
      request:async(options:{url:string;method:string;header:Record<string,string>;data?:unknown;success:(response:unknown)=>void;fail:(error:unknown)=>void})=>{
        try {const response=await fetch(options.url,{method:options.method,headers:{...options.header,'Content-Type':'application/json'},body:options.data?JSON.stringify(options.data):undefined});options.success({statusCode:response.status,data:await response.json().catch(()=>null)})}
        catch(error){options.fail({errMsg:String(error)})}
      },
    })
    api=(await import('@/services/api')).api
    workspace=(await import('./workspace')).createWorkspace(api)
  })
  afterAll(async()=>{if(api)await api.deleteAccount();vi.unstubAllGlobals()})
  it('开发登录、建档、结构化记录、刷新、编辑、删除与恢复',async()=>{
    await workspace.load();expect(workspace.state.ready).toBe(true);expect(workspace.state.baby).toBeNull()
    expect(await workspace.saveBaby({nickname:'V13接口验收',birth_date:null,gender:'unknown'})).toBe(true)
    const input:RecordInput={record_type:'feeding',occurred_at:new Date().toISOString(),payload:{kind:'feeding',feeding_type:'formula',amount_ml:180},note:'isolated integration check'}
    expect(await workspace.saveRecord(input)).toBe(true)
    const id=workspace.state.records[0]!.id
    await workspace.load();expect(workspace.state.records[0]?.id).toBe(id)
    expect(await workspace.saveRecord({...input,payload:{...input.payload,amount_ml:200}},id)).toBe(true)
    const summary=await api.dailySummary(workspace.state.baby!.id,new Date().toLocaleDateString('en-CA'),'Asia/Shanghai')
    expect(summary.feeding_ml).toBe(200)
    expect(await workspace.removeRecord(id)).toBe(true);expect(workspace.state.records).toHaveLength(0)
    expect(await workspace.restoreRecord(id)).toBe(true);expect(workspace.state.records).toHaveLength(1)
  })
  it('真实上传与草稿确认；禁用识别时仍可手动修正，不伪造识别值',async()=>{
    const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aPz8AAAAASUVORK5CYII=','base64')
    const result=await workspace.capture(new Blob([png],{type:'image/png'}),'image','record')
    expect(result).toBe(true);expect(workspace.state.draft?.id).toBeTruthy();expect(workspace.state.records).toHaveLength(1)
    expect(workspace.state.draft?.recognition_warnings.length).toBeGreaterThan(0)
    const input:RecordInput={record_type:'complementary_food',occurred_at:new Date().toISOString(),payload:{kind:'complementary_food',food_name:'南瓜粥',amount_text:'半碗'},note:'manually confirmed'}
    expect(await workspace.saveRecord(input)).toBe(true)
    expect(workspace.state.records[0]?.source).toBe('photo')
  })
  it('无外部模型时读取后端降级答复与真实会话历史',async()=>{
    expect(await workspace.sendChat('今天记录了什么？')).toBe(true)
    expect(workspace.state.messages[1]?.structured_payload?.summary).toBeTruthy()
    await workspace.loadChat();expect(workspace.state.messages.length).toBeGreaterThanOrEqual(2)
  },30000)
  it('真实家庭邀请生成、预览与撤销',async()=>{
    const invite=await api.createInvite();expect(invite.token).toBeTruthy()
    const preview=await api.previewInvite(invite.token);expect(preview.family_name).toBe(workspace.state.family?.name)
    await api.revokeInvite(invite.id)
    await expect(api.previewInvite(invite.token)).rejects.toThrow()
  })
})
