<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { onHide, onPageScroll } from '@dcloudio/uni-app'
import { api, session } from '@/services/api'
import { API_BASE } from '@/services/config'
import RecordForm from '@/components/RecordForm.vue'
import { ageText, genderText, draftFormInitial, nowParts, toIsoDateTime, validateBabyProfile, RECORD_TYPES, type RecordInput, type RecordItem, type RecordType, type Baby } from '@/features/record/domain'
import { createVoiceCapture } from '@/features/record/voiceCapture'
import RecordTimeline from '../../components/RecordTimeline.vue'
import FamilyPanel from '../../components/FamilyPanel.vue'
import DiscoverPanel from '../../components/DiscoverPanel.vue'
import BabyMetrics from '../../components/BabyMetrics.vue'
import GrowthPanel from '../../components/GrowthPanel.vue'
import { articleTopics } from '../../domain/articleTopics'
import { createWorkspace, answerText, errorText } from '../../domain/workspace'
import { recordView, growthPoints } from '../../domain/presentation'
import { dateKey, rangeLabel, exportRecords, recordStats, selectRecords, shiftDateKey, type Range } from '../../domain/model'

const workspace=createWorkspace(api), state=workspace.state
const page=ref('home'),modal=ref(''),infoTitle=ref(''),infoText=ref('')
const range=ref<Range>('day'),selectedDate=ref(dateKey()),recordFilter=ref('全部')
const chatInput=ref(''),recordInitial=ref<Partial<RecordInput>>({}),editId=ref(''),deletedId=ref('')
const capturePurpose=ref<'record'|'chat'|'cry'>('record'),recording=ref(false),starting=ref(false),captureSeconds=ref(0),photo=ref('')
const exportFormat=ref<'CSV'|'JSON'>('CSV')
const homeQuickTypes=['feeding','sleep','complementary_food','stool','diaper','growth','medication'].map(type=>({...RECORD_TYPES.find(item=>item.value===type)!,icon:({feeding:'🍼',sleep:'🌙',complementary_food:'🥣',stool:'💩',diaper:'🩲',growth:'📈',medication:'💊'} as Record<string,string>)[type]}))
const quickClasses:Record<string,string>={feeding:'i-feed',sleep:'i-sleep',complementary_food:'i-food',stool:'i-poop',diaper:'i-diaper',growth:'i-height',medication:'i-med'}
const babyForm=reactive({nickname:'',birth_date:'',gender:'unknown' as Baby['gender']})
const localError=ref(''),inviteBusy=ref(false),familyBusy=ref(false)
const toast=(title:string)=>uni.showToast({title,icon:'none'})
const canManage=computed(()=>state.family?.role==='owner'||state.family?.role==='admin')
const views=computed(()=>state.records.map(recordView))
const todayRecords=computed(()=>selectRecords(views.value,dateKey(),'day'))
const visibleRecords=computed(()=>selectRecords(views.value,selectedDate.value,range.value,recordFilter.value))
const stats=computed(()=>recordStats(selectRecords(views.value,selectedDate.value,range.value)))
const filters=['全部',...RECORD_TYPES.map(r=>r.label)]
const dateLabel=computed(()=>rangeLabel(selectedDate.value,range.value))
const heightPoints=computed(()=>growthPoints(state.records,'height_cm')),weightPoints=computed(()=>growthPoints(state.records,'weight_kg'))
const height=computed(()=>heightPoints.value.at(-1)?.value),weight=computed(()=>weightPoints.value.at(-1)?.value)
const exportText=computed(()=>exportFormat.value==='JSON' ? JSON.stringify(state.records,null,2) : exportRecords(views.value,'CSV'))
const actionBusy=computed(()=>workspace.busy() || inviteBusy.value || familyBusy.value || recording.value || starting.value)
let timer: ReturnType<typeof setInterval>|undefined
let homeScrollTop=0
onPageScroll(({scrollTop})=>{if(page.value==='home')homeScrollTop=scrollTop})
let mediaRevision=0
let pendingMedia: {file:string|Blob;kind:'audio'|'image';duration?:number;purpose:'record'|'chat'|'cry'}|null=null

function info(title:string,text:string){infoTitle.value=title;infoText.value=text;modal.value='info'}
function unavailable(title:string){info(title,'此功能暂未开放。当前版本没有对应服务，暂不支持保存或提交。')}
function requireBaby(){if(!state.ready){toast('请先连接服务并完成登录');return false}if(!state.baby){openBaby();return false}return true}
function clearTimer(){if(timer)clearInterval(timer);timer=undefined;recording.value=false;starting.value=false}
const voice=createVoiceCapture({
  started(){starting.value=false;recording.value=true;captureSeconds.value=0;timer=setInterval(()=>{captureSeconds.value++;if(captureSeconds.value>=30)voice.stop()},1000)},
  stopped(file,duration){clearTimer();pendingMedia={file,kind:'audio',duration,purpose:capturePurpose.value};void processMedia()},
  failed(message,stillRecording){if(!stillRecording)clearTimer();localError.value=message},
},{minimumMs:2000})
function cancelMedia(){mediaRevision++;voice.cancel();clearTimer();workspace.cancelCapture();pendingMedia=null;photo.value=''}
function closeModal(){if(state.busy.save||inviteBusy.value||familyBusy.value)return;cancelMedia();modal.value='';localError.value='';state.error=''}
function navigate(destination:string){
  if(state.busy.save||state.busy.switch||inviteBusy.value||familyBusy.value)return
  const scrollTop=page.value==='discover'&&destination==='home'?homeScrollTop:0
  cancelMedia();modal.value='';page.value=destination;localError.value=''
  void nextTick(()=>{if(page.value===destination)uni.pageScrollTo({scrollTop,duration:0})})
  if(destination==='ai'&&state.baby)void workspace.loadChat()
}
function shiftDate(direction:number){selectedDate.value=shiftDateKey(selectedDate.value,direction,range.value)}
function selectFilter(event:unknown){recordFilter.value=filters[Number((event as {detail:{value:string}}).detail.value)]||'全部'}
function quickRecord(type:RecordType){
  if(!requireBaby())return
  cancelMedia();editId.value='';state.error='';localError.value=''
  recordInitial.value={record_type:type,payload:{kind:type},occurred_at:toIsoDateTime(page.value==='record'?selectedDate.value:nowParts().date,nowParts().time)}
  modal.value='record'
}
function moreRecord(title:string){
  quickRecord(title==='疫苗'?'vaccine':'custom')
  if(modal.value==='record'&&title!=='疫苗'&&title!=='自定义')recordInitial.value={...recordInitial.value,payload:{kind:'custom',title}}
}
function editRecord(id:string){
  if(!requireBaby())return
  const record=state.records.find(row=>row.id===id);if(!record)return
  cancelMedia();editId.value=id;recordInitial.value={...record};state.error='';modal.value='record'
}
async function saveRecord(input:RecordInput){
  if(await workspace.saveRecord(input,editId.value||undefined)){modal.value='';pendingMedia=null;toast('记录已保存')}
}
function deleteRecord(){const id=editId.value;if(!id)return;uni.showModal({title:'删除这条记录？',content:'删除后可在当前页面撤销。',success:async result=>{if(result.confirm&&await workspace.removeRecord(id)){deletedId.value=id;modal.value='';toast('已删除，可撤销')}}})}
async function restoreRecord(){if(await workspace.restoreRecord(deletedId.value)){deletedId.value='';toast('已恢复')}}
function openBaby(){
  if(!state.ready)return toast('请先重试连接服务')
  if(!canManage.value)return info('宝宝档案','请联系家庭创建者或管理员建立、修改宝宝档案。')
  Object.assign(babyForm,{nickname:state.baby?.nickname||'',birth_date:state.baby?.birth_date||'',gender:state.baby?.gender||'unknown'});localError.value='';modal.value='baby'
}
async function saveBaby(){const error=validateBabyProfile(babyForm);if(error){localError.value=error;return}if(await workspace.saveBaby({...babyForm,birth_date:babyForm.birth_date||null})){modal.value='';toast('宝宝档案已保存')}}
function changeBirthday(event:unknown){babyForm.birth_date=String((event as {detail:{value:string}}).detail.value)}
function changeGender(event:unknown){babyForm.gender=(['unknown','male','female'] as const)[Number((event as {detail:{value:string}}).detail.value)]||'unknown'}
function startVoice(purpose:'record'|'chat'|'cry'){
  if(!requireBaby()||state.busy.save||starting.value||recording.value||state.busy.capture)return
  cancelMedia();captureSeconds.value=0;capturePurpose.value=purpose;localError.value='';modal.value=purpose==='cry'?'':'voice';if(purpose==='cry'){page.value='cry';state.cry=null}starting.value=true;void voice.start()
}
function startPhoto(){if(!requireBaby())return;cancelMedia();capturePurpose.value='record';localError.value='';modal.value='photo'}
function choosePhoto(source:'camera'|'album'){
  const revision=++mediaRevision
  localError.value=''
  uni.chooseImage({count:1,sizeType:['compressed'],sourceType:[source],success(result){if(revision!==mediaRevision)return;photo.value=result.tempFilePaths[0]||''},fail(){if(revision===mediaRevision)localError.value='未选择图片，请重试或检查权限'}})
}
async function processMedia(){
  if(!pendingMedia||state.busy.capture)return
  const revision=mediaRevision,media=pendingMedia;localError.value='';modal.value=media.purpose==='cry'?'':'processing'
  const result=await workspace.capture(media.file,media.kind,media.purpose,media.duration)
  if(revision!==mediaRevision)return
  if(result===false)return
  if(media.purpose==='chat'){chatInput.value=String(result);modal.value='';page.value='ai'}
  else if(media.purpose==='cry'){modal.value='';page.value='cry'}
  else if(state.draft){recordInitial.value=draftFormInitial(state.draft);editId.value='';modal.value='record'}
  pendingMedia=null
}
function submitPhoto(){if(!photo.value)return;pendingMedia={file:photo.value,kind:'image',purpose:'record'};void processMedia()}
async function sendChat(question?:string){if(!requireBaby())return;const text=(question||chatInput.value).trim();if(!text)return;chatInput.value=text;if(await workspace.sendChat(text)){if(chatInput.value===text)chatInput.value=''}}
function observe(){navigate('ai');chatInput.value='请根据宝宝最近几天的记录，总结喂养和睡眠情况，并说明需要关注的变化。'}
async function showCryHistory(){if(!requireBaby())return;modal.value='cryHistory';await workspace.loadCryHistory()}
async function explainCry(){if(!state.cry||state.busy.explain)return;const id=state.cry.id;state.busy.explain=true;localError.value='';try{const result=await api.explainCry(id);if(state.cry?.id===id)state.cry.explanation=result.answer}catch(e){localError.value=errorText(e)}finally{state.busy.explain=false}}
function clearInputs(){chatInput.value='';recordInitial.value={};editId.value='';deletedId.value='';localError.value='';Object.assign(babyForm,{nickname:'',birth_date:'',gender:'unknown'})}
async function switchFamily(id:string,invite=false){if(actionBusy.value)return;cancelMedia();clearInputs();modal.value='';page.value='home';await workspace.switchFamily(id,invite)}
async function refresh(){if(actionBusy.value)return;cancelMedia();clearInputs();await workspace.load()}
async function familyChanged(){inviteBusy.value=true;try{state.family=await api.family()}catch(e){state.error=errorText(e)}finally{inviteBusy.value=false}}
function copyExport(){uni.setClipboardData({data:exportText.value,success(){toast('已复制真实记录')},fail(){toast('复制失败，请重试')}})}
function copySource(url:string){uni.setClipboardData({data:url})}
function recordRelated(ids:string[]){navigate('record');if(ids.length){const item=state.records.find(r=>r.id===ids[0]);if(item)selectedDate.value=recordView(item).date;range.value='day';recordFilter.value='全部'}}
function deleteAccount(){uni.showModal({title:'注销账号',content:'注销会永久删除你的账号，相关数据按家庭成员规则清理，无法撤销。',confirmText:'确认注销',success:async result=>{if(!result.confirm)return;inviteBusy.value=true;try{await api.deleteAccount();session.logout();cancelMedia();workspace.clear();state.error='账号已注销，请重新进入小程序';modal.value=''}catch(e){state.error=errorText(e)}finally{inviteBusy.value=false}}})}
function suspend(){if(recording.value||starting.value){cancelMedia();modal.value=''} }
onHide(suspend)
onUnmounted(()=>{cancelMedia();workspace.clear()})
onMounted(()=>void workspace.load())
</script>

<template>
  <view class="phone">
    <view v-if="!state.ready" class="content connection-state">
      <view class="brand">懂宝</view><view class="tagline">用 AI 陪伴每一个小小的成长</view>
      <view class="card"><view>{{ state.busy.load || state.busy.switch ? '正在登录并读取家庭数据…' : '暂时无法连接服务' }}</view><view v-if="state.error" class="error-box">{{ state.error }}</view><button class="primary-btn wide" :disabled="actionBusy" @tap="refresh">重新连接</button><text class="small" selectable>{{ API_BASE }}</text></view>
    </view>
    <view v-else class="main">
      <view v-if="state.error && !modal" class="error-box">{{ state.error }}</view>
      <view v-if="!state.baby" class="content"><view class="card"><view class="card-title">先为宝宝建立档案</view><view class="small">{{ canManage ? '填写昵称、生日和性别后，就可以记录成长了。' : '请联系家庭管理员建立宝宝档案。' }}</view><button v-if="canManage" class="primary-btn wide" @tap="openBaby">建立宝宝档案</button></view></view>
      <view v-if="page === 'home'" class="page">
        <view class="header"><view><view class="brand">懂宝</view><view class="tagline">用 AI 陪伴每一个小小的成长</view></view><button class="icon-btn circle-add" @tap="requireBaby() && (modal = 'chooser')">＋</button></view>
        <view class="content">
          <view class="hero" @tap="navigate('profile')"><view class="avatar">👶🏻</view><view><view class="h3">{{ state.baby?.nickname || '我的宝宝' }}</view><view class="p">{{ ageText(state.baby?.birth_date) }} · {{ state.baby ? genderText(state.baby.gender) : '待建档' }}</view><view class="small">今天也要开心呀 ❤</view></view></view>
          <view class="card observe"><view class="card-title">💡 AI 今日观察</view><view class="p">结合宝宝的真实记录，向懂宝询问近期喂养、睡眠和成长变化。</view><button class="primary-btn wide" @tap="observe">查看详细分析 →</button></view>
          <view class="section-title">记一笔</view><view class="capture-row"><button class="capture-btn voice" @tap="startVoice('record')"><text class="cap-ico">🎙</text><text class="b">语音记录</text><text class="span">说一句，AI 帮你填</text></button><button class="capture-btn photo" @tap="startPhoto"><text class="cap-ico">📷</text><text class="b">拍照记录</text><text class="span">拍奶瓶 / 辅食 / 便便</text></button></view>
          <view class="section-title">手动快捷</view><view class="quick-grid"><button v-for="item in homeQuickTypes" :key="item.value" class="quick-item" @tap="quickRecord(item.value)"><view class="quick-icon" :class="quickClasses[item.value]">{{ item.icon }}</view><text class="span">{{ item.label }}</text></button><button class="quick-item" @tap="requireBaby() && (modal = 'more')"><view class="quick-icon i-more">•••</view><text class="span">更多</text></button></view>
          <view class="card cry-card"><view><view class="card-title">宝宝哭了？</view><view class="small">辅助了解哭声特征</view><button class="primary-btn" @tap="navigate('cry')">开始哭声分析 →</button></view><view class="cry-whale">🐳</view></view>
          <view class="section-title">今天 · {{ dateKey() }}<button class="link" @tap="navigate('record')">{{ todayRecords.length }} 条记录</button></view><view class="card"><RecordTimeline :records="todayRecords" @select="editRecord" /></view>
          <view class="section-title">为你推荐</view>
          <view class="card home-recommendations">
            <view v-for="item in articleTopics.slice(0,2)" :key="item.title" class="article" @tap="unavailable(item.title)"><view class="thumb">{{ item.emoji }}</view><view><text class="b">{{ item.title }}</text><view class="p">{{ item.intro }}</view><text class="small">内容暂未开放</text></view></view>
            <button class="primary-btn wide" @tap="navigate('discover')">推荐文章 →</button>
          </view>
        </view>
      </view>
      <view v-else-if="page === 'ai'" class="page">
        <view class="header"><button class="icon-btn" @tap="navigate('home')">‹</button><view class="ai-heading"><view class="header-title">懂宝 AI</view><view class="tagline">基于宝宝数据的专属育儿助手</view></view><button class="link" :disabled="state.busy.chat || !state.baby" @tap="workspace.newChat">新对话</button></view>
        <view class="chat-wrap"><view v-if="!state.messages.length" class="empty">你好，有什么育儿问题想问懂宝？</view><view v-for="message in state.messages" :key="message.id" class="bubble-row" :class="message.role === 'user' ? 'me' : 'bot'"><view class="bubble history-text">{{ message.structured_payload?.summary ? answerText(message.structured_payload) : message.content }}<view v-if="message.structured_payload?.related_record_ids?.length" class="bubble-actions"><button @tap="recordRelated(message.structured_payload.related_record_ids)">查看相关记录</button></view><view v-for="source in message.structured_payload?.sources || []" :key="source.title" class="source"><text>{{ source.title }} · {{ source.publisher }}</text><button v-if="source.source_url" class="link" @tap="copySource(source.source_url)">复制资料链接</button></view></view></view><view v-if="state.busy.chat" class="small">正在处理…</view><view v-if="state.chatError" class="error-box">{{ state.chatError }}<button class="link" :disabled="state.busy.chat" @tap="workspace.loadChat">刷新会话</button></view></view>
        <view class="suggests"><view class="small">你可能还想问</view><button v-for="question in ['宝宝最近的奶量怎么样？','宝宝最近为什么夜醒？','怎样记录辅食更清楚？']" :key="question" class="chip" :disabled="state.busy.chat" @tap="sendChat(question)">{{ question }}</button></view>
        <view class="composer"><input v-model="chatInput" :maxlength="2000" placeholder="有什么育儿问题都可以问我…" confirm-type="send" @confirm="sendChat()" /><button class="mic" :disabled="state.busy.chat" @tap="startVoice('chat')">🎙</button><button class="send" :disabled="state.busy.chat" @tap="sendChat()">➤</button></view>
      </view>
      <view v-else-if="page === 'record'" class="page">
        <view class="header"><button class="icon-btn" @tap="navigate('home')">‹</button><view class="header-title">记录</view><button class="icon-btn" @tap="requireBaby() && (modal = 'chooser')">＋</button></view>
        <view class="seg"><button v-for="item in [{key:'day',name:'日'},{key:'week',name:'周'},{key:'month',name:'月'}]" :key="item.key" :class="{active:range === item.key}" @tap="range = item.key as Range">{{ item.name }}</button></view>
        <view class="datebar"><button @tap="shiftDate(-1)">‹</button><text>{{ dateLabel }}</text><button @tap="shiftDate(1)">›</button></view>
        <view class="content"><view class="card"><view class="stats-grid"><view v-for="stat in stats" :key="stat.name" class="stat"><text class="b">{{ stat.icon }} {{ stat.name }}</text><text class="span">{{ stat.value }}</text><text class="small">{{ stat.count }} 次</text></view></view><view class="capture-row record-cta"><button class="capture-btn voice" @tap="startVoice('record')"><text class="cap-ico">🎙</text><text class="b">语音</text><text class="span">说完自动识别</text></button><button class="capture-btn photo" @tap="startPhoto"><text class="cap-ico">📷</text><text class="b">拍照</text><text class="span">看图帮你填</text></button></view><button class="soft-btn wide" @tap="requireBaby() && (modal = 'chooser')">手动选择类型</button></view><view class="section-title">记录时间线<picker :range="filters" @change="selectFilter"><text class="link">{{ recordFilter }} ▾</text></picker></view><button v-if="deletedId" class="soft-btn wide" :disabled="state.busy.save" @tap="restoreRecord">撤销刚才的删除</button><view class="timeline"><RecordTimeline :records="visibleRecords" @select="editRecord" /></view></view>
      </view>
      <view v-else-if="page === 'cry'" class="page cry-page">
        <view class="header"><button class="icon-btn" @tap="navigate('home')">‹</button><view class="header-title">哭声分析</view><button class="link" :disabled="actionBusy" @tap="showCryHistory">历史</button></view>
        <view class="cry-stage"><view class="baby-circle"><view class="wave"><text>≋</text><text>≋</text></view>😭</view><view class="h3">{{ starting ? '等待麦克风授权…' : recording ? '正在聆听…' : state.busy.capture ? '正在分析…' : state.cry ? '分析完成' : '点击开始监听' }}</view><view class="p">{{ recording ? '请保持手机靠近宝宝，环境尽量安静' : '请在安静环境下录制，建议 10–30 秒。此功能仅作辅助判断。' }}</view><button class="record-btn" :disabled="starting || state.busy.capture" @tap="recording ? voice.stop() : startVoice('cry')">{{ recording ? '■' : '●' }}</button><view class="record-time">00:{{ String(captureSeconds).padStart(2,'0') }} / 00:30</view></view>
        <view v-if="state.captureError" class="error-box">{{ state.captureError }}<button class="link" :disabled="state.busy.capture" @tap="processMedia">重试分析</button></view>
        <view v-if="state.cry" class="analysis-card"><view class="card-title">{{ state.cry.status === 'uncertain' ? '暂不能确定' : '哭声特征分析' }}</view><view class="p">{{ state.cry.summary }}</view><view v-for="(item,index) in state.cry.candidates" :key="item.category" class="reason"><text>{{ index+1 }}.</text><view>{{ item.label }}<view class="bar"><view class="fill" :style="{width:Math.max(0,Math.min(100,item.score*100))+'%'}" /></view></view><text>{{ item.possibility }}</text></view><view class="disclaimer">{{ state.cry.disclaimer }} · 匹配度不是实际哭闹原因概率。</view><view class="small">分析已保存至历史</view><view class="row-btns"><button class="outline-btn" @tap="startVoice('cry')">重新录制</button><button class="primary-btn" @tap="showCryHistory">查看历史</button></view><button class="soft-btn wide" :disabled="state.busy.explain" @tap="explainCry">{{ state.busy.explain ? '正在解释…' : 'AI 解读' }}</button><view v-if="state.cry.explanation" class="history-text">{{ answerText(state.cry.explanation) }}</view></view><view v-else class="analysis-card"><view class="card-title">分析结果</view><view class="empty">{{ state.busy.capture ? '正在处理录音，请稍候…' : '完成录音后展示分析结果' }}</view></view><view v-if="localError" class="error-box">{{ localError }}</view>
      </view>
      <GrowthPanel v-else-if="page === 'growth'" :records="state.records" :age="ageText(state.baby?.birth_date)" @create="quickRecord('growth')" @select="editRecord" />
      <DiscoverPanel v-else-if="page === 'discover'" :age="ageText(state.baby?.birth_date)" @back="navigate('home')" @unavailable="unavailable" />
      <view v-else-if="page === 'profile'" class="page"><view class="header"><button class="icon-btn" @tap="navigate('home')">‹</button><view class="header-title">宝宝档案</view><button v-if="canManage" class="link" @tap="openBaby">编辑</button></view><view class="profile-head"><view class="baby-profile"><view class="avatar">👶🏻</view><view><view class="h3">{{ state.baby?.nickname || '待建档' }}</view><view class="p">{{ ageText(state.baby?.birth_date) }} · {{ state.baby ? genderText(state.baby.gender) : '' }}</view><view class="p">{{ state.baby?.birth_date || '生日待完善' }}</view></view></view><BabyMetrics :height="height" :weight="weight" /></view><view class="settings-list"><view class="setting-row" @tap="openBaby"><view class="setting-ico">👤</view><text class="b">基本信息</text><text>›</text></view><view class="setting-row" @tap="navigate('growth')"><view class="setting-ico">📈</view><text class="b">生长发育</text><text>›</text></view><view v-for="name in ['喂养偏好','睡眠习惯','过敏信息']" :key="name" class="setting-row" @tap="unavailable(name)"><view class="setting-ico">{{ ({喂养偏好:'🛡',睡眠习惯:'🌙',过敏信息:'📍'} as Record<string,string>)[name] }}</view><text class="b">{{ name }}</text><text class="small">暂未开放</text></view><view class="setting-row" @tap="quickRecord('vaccine')"><view class="setting-ico">💉</view><text class="b">疫苗接种</text><text>记录 ›</text></view><view class="setting-row" @tap="modal = 'family'"><view class="setting-ico">👨‍👩‍👧</view><text class="b">家人信息</text><text>›</text></view><view class="setting-row" @tap="quickRecord('medication')"><view class="setting-ico">🧾</view><text class="b">用药记录</text><text>记录 ›</text></view></view></view>
      <view v-else-if="page === 'me'" class="page"><view class="header"><view class="header-title">我的</view><button class="icon-btn" @tap="modal = 'settings'">⚙</button></view><view class="me-head"><view class="me-card"><view class="person"><view class="person-avatar">👤</view><view><view class="h3">{{ state.family?.display_name || '家人' }}</view><view class="p">{{ state.family?.name }}</view></view></view><view class="membership"><text>懂宝会员 · 暂未开放</text><button class="member-btn" @tap="unavailable('会员')">了解更多</button></view><view class="icon-grid"><view class="gitem" @tap="unavailable('收藏')"><view class="gico">⭐</view>收藏</view><view class="gitem" @tap="navigate('ai')"><view class="gico">💬</view>历史对话</view><view class="gitem" @tap="navigate('profile')"><view class="gico">👶</view>我的宝宝</view><view class="gitem" @tap="unavailable('消息')"><view class="gico">🔔</view>消息</view></view></view></view><view class="settings-list"><view class="setting-row" @tap="modal = 'family'"><view class="setting-ico">👥</view><text class="b">家庭成员管理</text><text>›</text></view><view class="setting-row" @tap="modal = 'export'"><view class="setting-ico">⇩</view><text class="b">数据导出</text><text>›</text></view><view class="setting-row" @tap="info('使用帮助','先建立宝宝档案，再添加记录。语音和照片会上传至当前家庭的后端，识别后请核对并确认保存。哭声结果自动进入历史。网络失败会显示错误，不生成模拟结果。')"><view class="setting-ico">?</view><text class="b">使用帮助</text><text>›</text></view><view class="setting-row" @tap="unavailable('意见反馈')"><view class="setting-ico">✉</view><text class="b">意见反馈</text><text class="small">暂未开放</text></view><view class="setting-row" @tap="modal = 'settings'"><view class="setting-ico">⚙</view><text class="b">设置</text><text>›</text></view></view><view class="banner"><view>每一个小小的成长<br />都值得被认真记录 ❤</view><text class="art">🤱🏻</text></view></view>
    </view>
    <view class="nav"><button v-for="item in [{key:'home',name:'首页',icon:'⌂'},{key:'ai',name:'AI',icon:'◉'},{key:'record',name:'记录',icon:'▣'},{key:'me',name:'我的',icon:'♙'}]" :key="item.key" :class="{active:(page === 'discover' ? 'home' : page) === item.key}" @tap="navigate(item.key)"><text class="n-ico">{{ item.icon }}</text><text>{{ item.name }}</text></button></view>
    <view v-if="modal" class="modal-mask" @tap="closeModal"><scroll-view scroll-y class="sheet" @tap.stop><view class="grab" /><view class="close-row"><text class="sheet-title">{{ modal === 'record' ? (state.draft ? '识别完成，请确认' : (editId ? '编辑 · ' : '记录 · ')+(recordInitial.payload?.title || RECORD_TYPES.find(item=>item.value===recordInitial.record_type)?.label || '自定义')) : modal === 'baby' ? '宝宝基本信息' : modal === 'family' ? '家庭成员管理' : modal === 'voice' ? '正在录音' : modal === 'photo' ? '拍照记录' : modal === 'processing' ? '上传与识别' : modal === 'export' ? '数据导出' : modal === 'cryHistory' ? '哭声历史' : modal === 'settings' ? '设置' : modal === 'chooser' ? '记一笔' : modal === 'more' ? '更多记录' : infoTitle }}</text><button class="icon-btn" :disabled="state.busy.save || inviteBusy" @tap="closeModal">×</button></view>
      <view v-if="localError || state.error" class="error-box">{{ localError || state.error }}</view>
      <view v-if="modal === 'chooser' || modal === 'more'"><view class="capture-row"><button class="capture-btn voice" @tap="startVoice('record')"><text class="cap-ico">🎙</text><text class="b">语音</text><text class="span">说完自动识别</text></button><button class="capture-btn photo" @tap="startPhoto"><text class="cap-ico">📷</text><text class="b">拍照</text><text class="span">看图帮你填</text></button></view><view v-if="modal === 'chooser'" class="quick-grid chooser-grid"><button v-for="item in homeQuickTypes" :key="item.value" class="quick-item" @tap="quickRecord(item.value)"><view class="quick-icon" :class="quickClasses[item.value]">{{ item.icon }}</view><text class="span">{{ item.label }}</text></button><button class="quick-item" @tap="modal = 'more'"><view class="quick-icon i-more">•••</view><text class="span">更多</text></button></view><view v-else class="quick-grid chooser-grid"><button v-for="item in [{title:'体温',icon:'🌡'},{title:'不适',icon:'🤒'},{title:'疫苗',icon:'💉'},{title:'自定义',icon:'📝'}]" :key="item.title" class="quick-item" @tap="moreRecord(item.title)"><view class="quick-icon i-more">{{ item.icon }}</view><text class="span">{{ item.title }}</text></button></view><view v-if="modal === 'more'" class="small">体温、不适使用自定义记录保存，可在内容中填写测量值和症状。</view></view>
      <view v-else-if="modal === 'record'"><image v-if="state.draft?.source === 'photo' && photo" class="photo-preview" :src="photo" mode="aspectFit" /><view v-if="state.draft" class="draft-preview"><view class="tag">{{ state.draft.source === 'voice' ? '语音识别' : '拍照识别' }}</view><view v-if="state.draft.transcript">转写：{{ state.draft.transcript }}</view><view v-for="warning in state.draft.recognition_warnings" :key="warning">{{ warning }}</view><view v-if="state.draft.missing_fields.length">待补充：{{ state.draft.missing_fields.join('、') }}</view><button class="link" @tap="state.draft?.source === 'voice' ? startVoice('record') : startPhoto()">重新采集</button></view><RecordForm :initial="recordInitial" :submitting="state.busy.save" :lock-type="!state.draft" :submit-text="state.draft ? '确认保存' : '保存记录'" @submit="saveRecord" /><button v-if="editId" class="danger-btn wide" :disabled="state.busy.save" @tap="deleteRecord">删除记录</button></view>
      <view v-else-if="modal === 'baby'"><view class="form-row"><text>昵称</text><input v-model="babyForm.nickname" maxlength="30" placeholder="宝宝昵称" /></view><view class="form-row"><text>生日</text><picker mode="date" :value="babyForm.birth_date" :end="dateKey()" @change="changeBirthday"><view class="choice">{{ babyForm.birth_date || '请选择（可选）' }}</view></picker></view><view class="form-row"><text>性别</text><picker :range="['未填写','男宝宝','女宝宝']" @change="changeGender"><view class="choice">{{ genderText(babyForm.gender) }}</view></picker></view><button class="primary-btn wide" :disabled="state.busy.save" @tap="saveBaby">{{ state.busy.save ? '正在保存…' : '保存档案' }}</button></view>
      <view v-else-if="modal === 'voice'" class="listen-panel"><view class="listen-orb" :class="{pulse:recording}">🎙</view><view>{{ starting ? '等待麦克风授权…' : recording ? '正在听你说…' : '录音未开始' }}</view><view class="record-time">{{ captureSeconds }} 秒</view><view class="small">{{ capturePurpose === 'cry' ? '建议录制 10–30 秒宝宝哭声。' : '说完后结束录音，上传识别。' }}</view><button class="primary-btn wide" :disabled="!recording" @tap="voice.stop">说完了，结束录音</button><button v-if="!starting && !recording" class="outline-btn wide" @tap="startVoice(capturePurpose)">重试录音</button></view>
      <view v-else-if="modal === 'photo'"><image v-if="photo" class="photo-preview" :src="photo" mode="aspectFit" /><view v-else class="photo-slot" @tap="choosePhoto('camera')">点击拍照 / 选图</view><view class="row-btns"><button class="outline-btn" @tap="choosePhoto('camera')">拍照</button><button class="outline-btn" @tap="choosePhoto('album')">从相册选择</button></view><view class="small">确认后上传至后端识别，请核对生成的草稿。</view><button class="primary-btn wide" :disabled="!photo" @tap="submitPhoto">上传识别</button></view>
      <view v-else-if="modal === 'processing'"><view class="listen-panel">{{ state.busy.capture ? '正在上传并处理，请稍候…' : '处理未完成' }}</view><view v-if="state.captureError" class="error-box">{{ state.captureError }}</view><button v-if="!state.busy.capture" class="primary-btn wide" @tap="processMedia">重试</button><view class="small">关闭可停止等待；已上传的媒体由后端管理。草稿未经确认不会成为日常记录。</view></view>
      <FamilyPanel v-else-if="modal === 'family' && state.family" :family="state.family" @busy="familyBusy = $event" @changed="familyChanged" @switch="switchFamily($event)" @join="switchFamily($event,true)" />
      <view v-else-if="modal === 'cryHistory'"><view v-if="state.historyError" class="error-box">{{ state.historyError }}<button class="link" @tap="workspace.loadCryHistory()">重试</button></view><view v-for="result in state.cryHistory" :key="result.id" class="card" @tap="state.cry = result; modal = ''; page = 'cry'"><view>{{ result.summary }}</view><view class="small">{{ result.created_at }} · {{ result.status === 'uncertain' ? '不确定' : '特征匹配' }}</view></view><view v-if="!state.cryHistory.length && !state.busy.history" class="empty">暂无分析记录</view><button class="soft-btn wide" :disabled="state.busy.history" @tap="workspace.loadCryHistory(true)">{{ state.busy.history ? '加载中…' : '加载更多' }}</button></view>
      <view v-else-if="modal === 'export'"><view class="small">导出当前家庭宝宝的 {{ state.records.length }} 条真实记录</view><view class="row-btns"><button class="outline-btn" @tap="exportFormat = 'CSV'">CSV</button><button class="outline-btn" @tap="exportFormat = 'JSON'">JSON</button></view><textarea :value="exportText" disabled /><button class="primary-btn wide" @tap="copyExport">复制 {{ exportFormat }} 内容</button></view>
      <view v-else-if="modal === 'settings'"><view class="small">通知与个性化偏好暂未开放。</view><button class="soft-btn wide" :disabled="actionBusy" @tap="closeModal(); refresh()">重新读取服务端数据</button><button class="danger-btn wide" :disabled="actionBusy" @tap="deleteAccount">注销账号</button></view>
      <view v-else class="history-text">{{ infoText }}</view>
    </scroll-view></view>
  </view>
</template>
