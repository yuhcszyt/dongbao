import { reactive } from 'vue'
import type { api } from '@/services/api'
import type { Baby, MediaAsset, RecordDraft, RecordInput, RecordItem } from '@/features/record/domain'
import type { FamilyOverview } from '@/features/content/family'
import type { AiActiveConversation, ParentingAnswer } from '@/features/content/aiTypes'
import type { CryAnalysisResult } from '@/features/content/cryAnalysis'

export type Backend = Pick<typeof api, 'family' | 'getBaby' | 'records' | 'createBaby' | 'updateBaby' | 'createRecord' | 'updateRecord' | 'deleteRecord' | 'restoreRecord' | 'confirmDraft' | 'aiActiveConversation' | 'aiChat' | 'aiNewConversation' | 'uploadPath' | 'uploadBlob' | 'draftFromMedia' | 'transcribe' | 'analyzeCry' | 'cryHistory' | 'explainCry' | 'switchFamily' | 'acceptInvite'>
export const errorText = (error: unknown) => error instanceof Error ? error.message : '操作未完成，请稍后重试'
export function answerText(answer: Partial<ParentingAnswer>): string {
  return [answer.summary, ...(answer.reasons || []), ...(answer.baby_context || []),
    (answer.actions || []).length ? `建议：\n${answer.actions!.join('\n')}` : '',
    (answer.watch_for || []).length ? `留意：\n${answer.watch_for!.join('\n')}` : '',
    answer.medical_disclaimer].filter(Boolean).join('\n\n')
}

/** Server-owned data stays in memory only. An epoch rejects responses from an old family/session. */
export function createWorkspace(backend: Backend) {
  const state = reactive({
    family: null as FamilyOverview | null, baby: null as Baby | null, records: [] as RecordItem[],
    messages: [] as AiActiveConversation['messages'], conversationId: null as string | null,
    draft: null as RecordDraft | null, cry: null as CryAnalysisResult | null, cryHistory: [] as CryAnalysisResult[],
    busy: {} as Record<string, boolean>, error: '', chatError: '', captureError: '', historyError: '', ready: false,
  })
  let epoch = 0
  let captureEpoch = 0
  let uploaded: { file:string|Blob; kind:'audio'|'image'; purpose:string; babyId:string; media:MediaAsset } | null = null
  function clear() {
    epoch++; captureEpoch++; uploaded=null
    state.family=null; state.baby=null; state.records=[]; state.messages=[]; state.conversationId=null
    state.draft=null; state.cry=null; state.cryHistory=[]; state.busy={}; state.error=''; state.chatError=''; state.captureError=''; state.historyError=''; state.ready=false
  }
  const busy = () => Object.values(state.busy).some(Boolean)
  function babyId() { if(!state.baby) throw new Error('请先建立宝宝档案'); return state.baby.id }
  async function load() {
    clear()
    const current=epoch
    state.busy.load=true
    try {
      const family=await backend.family()
      if(current!==epoch)return
      const baby=await backend.getBaby()
      if(current!==epoch)return
      const records=baby ? await backend.records(baby.id) : []
      if(current!==epoch)return
      state.family=family; state.baby=baby; state.records=records; state.ready=true
    } catch(error) { if(current===epoch) state.error=errorText(error) }
    finally { if(current===epoch)state.busy.load=false }
  }
  function upsert(record: RecordItem) {
    state.records=[record,...state.records.filter(r=>r.id!==record.id)].sort((a,b)=>b.occurred_at.localeCompare(a.occurred_at))
  }
  async function saveRecord(input: RecordInput, editId?: string): Promise<boolean> {
    if(state.busy.save)return false
    const id=babyId(), current=epoch, draftId=state.draft?.id
    state.busy.save=true; state.error=''
    try {
      const result=editId ? await backend.updateRecord(id,editId,input)
        : draftId ? await backend.confirmDraft(draftId,input) : await backend.createRecord(id,input)
      if(current!==epoch)return false
      upsert(result); state.draft=null; return true
    } catch(error) { if(current===epoch)state.error=errorText(error); return false }
    finally { if(current===epoch)state.busy.save=false }
  }
  async function removeRecord(id:string) {
    if(state.busy.save)return false
    const scope=babyId(),current=epoch;state.busy.save=true;state.error=''
    try { await backend.deleteRecord(scope,id); if(current!==epoch)return false;state.records=state.records.filter(r=>r.id!==id);return true }
    catch(error){if(current===epoch)state.error=errorText(error);return false}
    finally{if(current===epoch)state.busy.save=false}
  }
  async function restoreRecord(id:string) {
    if(state.busy.save)return false
    const scope=babyId(),current=epoch;state.busy.save=true;state.error=''
    try{const result=await backend.restoreRecord(scope,id);if(current!==epoch)return false;upsert(result);return true}
    catch(error){if(current===epoch)state.error=errorText(error);return false}
    finally{if(current===epoch)state.busy.save=false}
  }
  async function saveBaby(input: Pick<Baby,'nickname'|'birth_date'|'gender'>) {
    if(state.busy.save)return false
    const current=epoch;state.busy.save=true;state.error=''
    try {
      const result=state.baby ? await backend.updateBaby(state.baby.id,input) : await backend.createBaby(input)
      if(current!==epoch)return false
      state.baby=result;return true
    }catch(error){if(current===epoch)state.error=errorText(error);return false}
    finally{if(current===epoch)state.busy.save=false}
  }
  async function loadChat() {
    if(!state.baby || state.busy.chat)return
    const current=epoch,id=babyId();state.busy.chat=true;state.chatError=''
    try{const result=await backend.aiActiveConversation(id);if(current!==epoch)return;state.messages=result.messages;state.conversationId=result.conversation_id}
    catch(error){if(current===epoch)state.chatError=errorText(error)}
    finally{if(current===epoch)state.busy.chat=false}
  }
  async function sendChat(message:string) {
    if(!message.trim() || state.busy.chat)return false
    const current=epoch,id=babyId();state.busy.chat=true;state.chatError=''
    try {
      const result=await backend.aiChat(id,message,state.conversationId)
      if(current!==epoch)return false
      state.conversationId=result.conversation_id
      state.messages.push({id:`question-${result.message_id}`,role:'user',content:message,created_at:new Date().toISOString()},
        {id:result.message_id,role:'assistant',content:answerText(result.answer),structured_payload:result.answer,created_at:new Date().toISOString()})
      return true
    }catch(error){if(current===epoch)state.chatError=errorText(error);return false}
    finally{if(current===epoch)state.busy.chat=false}
  }
  async function newChat() {
    if(state.busy.chat)return
    const current=epoch,id=babyId();state.busy.chat=true;state.chatError=''
    try{const result=await backend.aiNewConversation(id);if(current!==epoch)return;state.conversationId=result.conversation_id;state.messages=[]}
    catch(error){if(current===epoch)state.chatError=errorText(error)}
    finally{if(current===epoch)state.busy.chat=false}
  }
  function cancelCapture() {captureEpoch++;uploaded=null;state.draft=null;state.busy.capture=false;state.captureError=''}
  async function capture(file:string|Blob, kind:'audio'|'image', purpose:'record'|'chat'|'cry', duration?:number): Promise<string | boolean> {
    if(state.busy.capture)return false
    const current=epoch,operation=++captureEpoch,id=babyId()
    const active=()=>current===epoch && operation===captureEpoch
    state.busy.capture=true;state.captureError='';state.draft=null
    try {
      const cached=uploaded?.file===file && uploaded.kind===kind && uploaded.purpose===purpose && uploaded.babyId===id ? uploaded.media : null
      const media=cached || (typeof file==='string'
        ? await backend.uploadPath(file,id,kind,duration,purpose==='cry'?'cry_analysis':undefined)
        : await backend.uploadBlob(file,id,kind,duration,purpose==='cry'?'cry_analysis':undefined))
      if(!active())return false
      uploaded={file,kind,purpose,babyId:id,media}
      if(purpose==='chat') {const result=await backend.transcribe(media.id);return active()?result.transcript:false}
      if(purpose==='cry') {
        const result=await backend.analyzeCry(id,media.id)
        if(!active())return false
        state.cry=result;state.cryHistory=[result,...state.cryHistory.filter(r=>r.id!==result.id)]
      } else {
        const result=await backend.draftFromMedia(kind==='audio'?'voice':'photo',id,media.id)
        if(!active())return false
        state.draft=result
      }
      return true
    }catch(error){if(active())state.captureError=errorText(error);return false}
    finally{if(active())state.busy.capture=false}
  }
  async function loadCryHistory(more=false) {
    if(state.busy.history)return
    const current=epoch,id=babyId();state.busy.history=true;state.historyError=''
    try {
      const result=await backend.cryHistory(id,more?state.cryHistory.length:0)
      if(current!==epoch)return
      state.cryHistory=more ? [...state.cryHistory,...result.filter(row=>!state.cryHistory.some(old=>old.id===row.id))] : result
    }catch(error){if(current===epoch)state.historyError=errorText(error)}
    finally{if(current===epoch)state.busy.history=false}
  }
  async function switchFamily(id:string,invite=false) {
    if(busy())return false
    clear();state.busy.switch=true
    try {if(invite)await backend.acceptInvite(id);else await backend.switchFamily(id)}
    catch(error){state.error=errorText(error);state.busy.switch=false;return false}
    await load();return state.ready
  }
  return {state,load,clear,busy,saveRecord,removeRecord,restoreRecord,saveBaby,loadChat,sendChat,newChat,capture,cancelCapture,loadCryHistory,switchFamily}
}
