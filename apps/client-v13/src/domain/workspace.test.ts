import { describe, expect, it, vi } from 'vitest'
import { createWorkspace, type Backend } from './workspace'
import type { RecordInput, RecordItem, RecordDraft, Baby, MediaAsset } from '@/features/record/domain'
import type { FamilyOverview } from '@/features/content/family'
import type { ParentingAnswer } from '@/features/content/aiTypes'
import type { CryAnalysisResult } from '@/features/content/cryAnalysis'
const baby:Baby={id:'baby-1',nickname:'测试宝宝',gender:'unknown',birth_date:null}
const family:FamilyOverview={id:'family-1',name:'家',role:'owner',user_id:'user-1',display_name:'家人',members:[],families:[],invites:[]}
const input:RecordInput={record_type:'feeding',occurred_at:'2026-10-25T08:00:00Z',payload:{kind:'feeding',feeding_type:'formula',amount_ml:180},note:null}
const record:RecordItem={...input,id:'record-1',baby_id:baby.id,source:'manual'}
const draft:RecordDraft={id:'draft-1',baby_id:baby.id,status:'draft',record_type:'feeding',occurred_at:input.occurred_at,payload:input.payload,source:'voice',missing_fields:[],recognition_warnings:[]}
const media:MediaAsset={id:'media-1',baby_id:baby.id,media_type:'audio',mime_type:'audio/wav',size_bytes:10000,url:'/media/test'}
const answer:ParentingAnswer={summary:'真实后端答复',reasons:[],baby_context:[],actions:[],watch_for:[],sources:[],related_record_ids:[]}
const cry:CryAnalysisResult={id:'cry-1',baby_id:baby.id,created_at:'2026-10-25T08:00:00Z',status:'uncertain',primary_category:null,summary:'证据不足',candidates:[],model_id:'local',model_revision:'1',disclaimer:'仅供参考'}
function backend(){return {
  family:vi.fn().mockResolvedValue(family), getBaby:vi.fn().mockResolvedValue(baby), records:vi.fn().mockResolvedValue([]),
  createBaby:vi.fn().mockResolvedValue(baby),updateBaby:vi.fn().mockResolvedValue(baby),createRecord:vi.fn().mockResolvedValue(record),updateRecord:vi.fn().mockResolvedValue(record),deleteRecord:vi.fn().mockResolvedValue(undefined),restoreRecord:vi.fn().mockResolvedValue(record),confirmDraft:vi.fn().mockResolvedValue({...record,source:'voice'}),
  aiActiveConversation:vi.fn().mockResolvedValue({conversation_id:null,messages:[]}),aiChat:vi.fn().mockResolvedValue({conversation_id:'chat-1',message_id:'message-1',answer}),aiNewConversation:vi.fn().mockResolvedValue({conversation_id:'chat-2'}),
  uploadPath:vi.fn().mockResolvedValue(media),uploadBlob:vi.fn().mockResolvedValue(media),draftFromMedia:vi.fn().mockResolvedValue(draft),transcribe:vi.fn().mockResolvedValue({transcript:'喝了180毫升'}),
  analyzeCry:vi.fn().mockResolvedValue(cry),cryHistory:vi.fn().mockResolvedValue([cry]),explainCry:vi.fn().mockResolvedValue({conversation_id:'chat-1',message_id:'message-2',answer}),switchFamily:vi.fn().mockResolvedValue({}),acceptInvite:vi.fn().mockResolvedValue({}),
} satisfies Backend}
function deferred<T>(){let resolve!:(value:T)=>void;const promise=new Promise<T>(r=>{resolve=r});return {promise,resolve}}

describe('服务端作为唯一业务数据来源',()=>{
  it('初始没有种子数据，建档前可加载空家庭',async()=>{const api=backend();api.getBaby.mockResolvedValue(null);const w=createWorkspace(api);await w.load();expect(w.state.ready).toBe(true);expect(w.state.baby).toBeNull();expect(w.state.records).toEqual([]);expect(api.records).not.toHaveBeenCalled()})
  it('登录失败和读取失败不展示假数据',async()=>{const api=backend();api.family.mockRejectedValue(new Error('登录失败'));const w=createWorkspace(api);await w.load();expect(w.state.ready).toBe(false);expect(w.state.error).toBe('登录失败');expect(w.state.records).toEqual([])})
  it('保存失败不先写本地列表，成功使用后端ID',async()=>{const api=backend(),w=createWorkspace(api);await w.load();api.createRecord.mockRejectedValueOnce(new Error('网络断开'));expect(await w.saveRecord(input)).toBe(false);expect(w.state.records).toEqual([]);expect(await w.saveRecord(input)).toBe(true);expect(w.state.records[0]?.id).toBe(record.id)})
  it('重复点击只发一次新增请求',async()=>{const api=backend(),w=createWorkspace(api);await w.load();const pending=deferred<RecordItem>();api.createRecord.mockReturnValue(pending.promise);const first=w.saveRecord(input);expect(await w.saveRecord(input)).toBe(false);pending.resolve(record);await first;expect(api.createRecord).toHaveBeenCalledTimes(1)})
  it('草稿必须确认后入记录，保留草稿ID与来源',async()=>{const api=backend(),w=createWorkspace(api);await w.load();await w.capture('/voice.wav','audio','record',3000);expect(w.state.records).toEqual([]);expect(api.draftFromMedia).toHaveBeenCalledWith('voice',baby.id,media.id);await w.saveRecord(input);expect(api.confirmDraft).toHaveBeenCalledWith(draft.id,input);expect(api.createRecord).not.toHaveBeenCalled();expect(w.state.records[0]?.source).toBe('voice');expect(w.state.draft).toBeNull()})
  it('草稿确认失败保留草稿供重试',async()=>{const api=backend(),w=createWorkspace(api);await w.load();await w.capture('/photo.jpg','image','record');api.confirmDraft.mockRejectedValue(new Error('校验失败'));await w.saveRecord(input);expect(w.state.draft?.id).toBe(draft.id);expect(w.state.records).toEqual([])})
  it('关闭采集后忽略晚到的上传，不继续识别',async()=>{const api=backend(),w=createWorkspace(api);await w.load();const pending=deferred<MediaAsset>();api.uploadPath.mockReturnValue(pending.promise);const work=w.capture('/voice.wav','audio','record');w.cancelCapture();pending.resolve(media);expect(await work).toBe(false);expect(api.draftFromMedia).not.toHaveBeenCalled();expect(w.state.draft).toBeNull()})
  it('切换作用域后旧保存响应不进入新列表',async()=>{const api=backend(),w=createWorkspace(api);await w.load();const pending=deferred<RecordItem>();api.createRecord.mockReturnValue(pending.promise);const work=w.saveRecord(input);w.clear();pending.resolve(record);expect(await work).toBe(false);expect(w.state.records).toEqual([])})
  it('切换家庭失败也不残留上个家庭的数据',async()=>{const api=backend(),w=createWorkspace(api);api.records.mockResolvedValue([record]);await w.load();api.switchFamily.mockRejectedValue(new Error('无权限'));expect(await w.switchFamily('other')).toBe(false);expect(w.state.family).toBeNull();expect(w.state.records).toEqual([]);expect(w.state.ready).toBe(false)})
  it('删除失败仍保留原记录，删除成功可恢复',async()=>{const api=backend(),w=createWorkspace(api);api.records.mockResolvedValue([record]);await w.load();api.deleteRecord.mockRejectedValueOnce(new Error('无权限'));expect(await w.removeRecord(record.id)).toBe(false);expect(w.state.records).toHaveLength(1);await w.removeRecord(record.id);expect(w.state.records).toHaveLength(0);await w.restoreRecord(record.id);expect(w.state.records).toHaveLength(1)})
})
describe('AI与哭声使用真实接口结果',()=>{
  it('分析失败重试沿用已上传媒体，保留后端幂等语义',async()=>{const api=backend(),w=createWorkspace(api);await w.load();api.analyzeCry.mockRejectedValueOnce(new Error('请求超时'));await w.capture('/cry.wav','audio','cry',10000);expect(w.state.cry).toBeNull();await w.capture('/cry.wav','audio','cry',10000);expect(api.uploadPath).toHaveBeenCalledTimes(1);expect(w.state.cryHistory).toHaveLength(1)})
  it('AI失败不插入演示答复，成功关联真实会话',async()=>{const api=backend(),w=createWorkspace(api);await w.load();api.aiChat.mockRejectedValueOnce(new Error('模型不可用'));expect(await w.sendChat('你好')).toBe(false);expect(w.state.messages).toEqual([]);expect(w.state.chatError).toBe('模型不可用');await w.sendChat('你好');expect(w.state.messages[1]?.content).toBe(answer.summary);expect(w.state.conversationId).toBe('chat-1');await w.sendChat('继续');expect(api.aiChat).toHaveBeenLastCalledWith(baby.id,'继续','chat-1')})
  it('录音转写只填文本，不写入记录',async()=>{const api=backend(),w=createWorkspace(api);await w.load();expect(await w.capture('/voice.wav','audio','chat',3000)).toBe('喝了180毫升');expect(api.createRecord).not.toHaveBeenCalled();expect(api.aiChat).not.toHaveBeenCalled()})
  it('哭声上传使用私有用途，保留不确定结果，不另造日常记录',async()=>{const api=backend(),w=createWorkspace(api);await w.load();await w.capture('/cry.wav','audio','cry',10000);expect(api.uploadPath).toHaveBeenCalledWith('/cry.wav',baby.id,'audio',10000,'cry_analysis');expect(w.state.cry?.status).toBe('uncertain');expect(w.state.cry?.primary_category).toBeNull();expect(w.state.cryHistory).toHaveLength(1);expect(api.createRecord).not.toHaveBeenCalled()})
  it('旧家庭的AI响应不会进入新家庭',async()=>{const api=backend(),w=createWorkspace(api);await w.load();const pending=deferred<unknown>();api.aiChat.mockReturnValue(pending.promise);const work=w.sendChat('测试');w.clear();pending.resolve({conversation_id:'old',message_id:'old',answer});expect(await work).toBe(false);expect(w.state.messages).toEqual([])})
})

it('离开哭声页后丢弃晚到分析，重新进入可读取已保存历史',async()=>{
  const api=backend(),w=createWorkspace(api);await w.load()
  const pending=deferred<CryAnalysisResult>();api.analyzeCry.mockReturnValue(pending.promise)
  const work=w.capture('/cry.wav','audio','cry',10000)
  await vi.waitFor(()=>expect(api.analyzeCry).toHaveBeenCalledTimes(1))
  w.cancelCapture();pending.resolve(cry)
  expect(await work).toBe(false);expect(w.state.cry).toBeNull();expect(w.state.cryHistory).toEqual([])
  await w.loadCryHistory();expect(w.state.cryHistory[0]?.id).toBe(cry.id)
})
