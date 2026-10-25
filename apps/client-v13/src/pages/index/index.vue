<script setup lang="ts">
import { computed, onUnmounted, reactive, ref } from 'vue'
import { onHide } from '@dcloudio/uni-app'
import RecordTimeline from '../../components/RecordTimeline.vue'
import { articleMatches, dateKey, decodeState, exportRecords, recordStats, seedState, selectRecords, shiftDateKey, STORAGE_KEY, validateRecord, type Range } from '../../domain/model'
import { chartSource, curveNames } from '../../domain/chart'

const toast = (title: string) => uni.showToast({ title, icon:'none' })
let initial = seedState()
try {
  const saved: unknown = uni.getStorageSync(STORAGE_KEY)
  if (saved) {
    const restored = decodeState(saved)
    if (restored) initial = restored
    else toast('本地数据格式异常，已加载演示数据')
  }
} catch { toast('暂时无法读取本地数据') }
const state = reactive(initial)
function persist(): boolean {
  try { uni.setStorageSync(STORAGE_KEY, JSON.stringify(state)); return true }
  catch { toast('本地保存失败，请导出备份后重试'); return false }
}
const page = ref('home')
const modal = ref('')
const article = ref('')
const modalTitle = ref('')
const modalText = ref('')
const range = ref<Range>('day')
const selectedDate = ref(dateKey())
const recordFilter = ref('全部')
const recordTypes = ['喂奶','睡眠','辅食','排便','尿布','身高体重','用药','体温','不适','疫苗','自定义']
const recordFilters = ['全部',...recordTypes,'哭声分析']
const growthTab = ref('data')
const category = ref('推荐')
const search = ref('')
const chatInput = ref('')
const curveMode = ref(0)
const chartUrl = computed(()=>chartSource(curveMode.value))
const todayLabel = computed(()=>dateKey().slice(5).replace('-','月')+'日')
const todayRecords = computed(()=>selectRecords(state.records,dateKey(),'day'))
const rangeRecords = computed(()=>selectRecords(state.records,selectedDate.value,range.value))
const visibleRecords = computed(()=>selectRecords(state.records,selectedDate.value,range.value,recordFilter.value))
const stats = computed(()=>recordStats(rangeRecords.value))
const dateLabel = computed(()=>range.value==='month'?selectedDate.value.slice(0,7):range.value==='week'?`${selectedDate.value} 所在周`:selectedDate.value)
function changeRecordFilter(e: { detail: { value: unknown } }) { recordFilter.value=recordFilters[Number(e.detail.value)] || '全部' }
function navigate(destination:string) { stopCapture(); resetCry(); modal.value='';article.value='';page.value=destination;uni.pageScrollTo({scrollTop:0,duration:0}) }
function setRange(value:string) { range.value=value as Range }
function shiftDate(direction:string) { selectedDate.value=shiftDateKey(selectedDate.value,Number(direction),range.value) }
function setGrowthTab(value:string) { growthTab.value=value }
function setCategory(value:string) { category.value=value }
const hasMatchingArticle = computed(()=>[['喂养','8个月宝宝辅食添加指南'],['睡眠','宝宝夜醒的常见原因与应对方法'],['发育','出牙期护理全攻略'],['喂养','宝宝便便颜色对照表']].some(([cat,title])=>articleMatches(category.value,search.value,cat!,title!)))
function matchesArticle(cat:string,title:string) { return articleMatches(category.value,search.value,cat,title) }
function toggleMilestone(name:string) { const index=state.milestones.indexOf(name); if(index<0)state.milestones.push(name);else state.milestones.splice(index,1);persist() }

const draft = reactive({ type:'喂奶',date:dateKey(),time:'',value:'',note:'',source:'手动记录' })
const defaults: Record<string,string> = { 喂奶:'180',睡眠:'60',辅食:'南瓜泥 50g',排便:'正常',尿布:'已更换',身高体重:'70cm / 8.2kg',用药:'',体温:'36.5' }
function quickRecord(type:string, source='手动记录') {
  stopCapture()
  Object.assign(draft,{type,date:page.value==='record'?selectedDate.value:dateKey(),time:new Date().toTimeString().slice(0,5),value:defaults[type]||'',note:'',source})
  modal.value='record'
}
function saveRecord() {
  const error=validateRecord(draft)
  if(error) return toast(error)
  state.records.push({...draft,id:`${Date.now()}-${Math.random().toString(36).slice(2)}`})
  if (!persist()) {state.records.pop();return}
  modal.value='';toast('记录已保存到本机')
}
function changeDraftDate(e:{detail:{value:string}}){draft.date=e.detail.value}
function changeDraftTime(e:{detail:{value:string}}){draft.time=e.detail.value}
let captureTimer: ReturnType<typeof setInterval> | undefined
const captureSeconds = ref(0)
const voicePurpose = ref<'record'|'chat'>('record')
const photo = ref('')
function stopCapture(){ if(captureTimer)clearInterval(captureTimer);captureTimer=undefined }
function closeModal(){stopCapture();modal.value=''}
function startVoice(){voicePurpose.value='record';beginVoice()}
function beginVoice(){stopCapture();captureSeconds.value=0;modal.value='voice';captureTimer=setInterval(()=>{captureSeconds.value++;if(captureSeconds.value>=8)finishVoice()},1000)}
function finishVoice(){stopCapture();if(voicePurpose.value==='chat'){chatInput.value='宝宝最近为什么晚上总醒？';closeModal();return}quickRecord('喂奶','语音演示');draft.note='演示转写：喂了 180 毫升配方奶，请核对';modal.value='record'}
function startPhoto(){photo.value='';modal.value='photo'}
function choosePhoto(source:'camera'|'album') {
  uni.chooseImage({count:1,sizeType:['compressed'],sourceType:[source],success(result){photo.value=result.tempFilePaths[0]||''},fail(){toast('未选择图片，可使用示例体验')}})
}
function photoDraft(){quickRecord('喂奶','拍照演示');draft.value='160';draft.note='示例草稿：请手动核对实际奶量（未进行图像识别）'}
const cryRunning=ref(false),cryReady=ref(false),crySeconds=ref(0),crySaved=ref(false)
let cryTimer: ReturnType<typeof setInterval> | undefined
function resetCry(){if(cryTimer)clearInterval(cryTimer);cryTimer=undefined;cryRunning.value=false;cryReady.value=false;crySeconds.value=0;crySaved.value=false}
function finishCry(){if(cryTimer)clearInterval(cryTimer);cryTimer=undefined;cryRunning.value=false;cryReady.value=true}
function toggleCry(){if(cryRunning.value)return finishCry();resetCry();cryRunning.value=true;cryTimer=setInterval(()=>{crySeconds.value++;if(crySeconds.value>=30)finishCry()},1000)}
function saveCry(){
  if(!cryReady.value)return toast('请先完成一次演示分析')
  if(crySaved.value)return toast('本次结果已保存')
  state.records.push({id:`cry-${Date.now()}`,date:dateKey(),time:new Date().toTimeString().slice(0,5),type:'哭声分析',value:'演示结果：饥饿 42% · 困倦 28% · 胀气 20% · 不适 10%',note:'模拟数据，不代表真实分析',source:'哭声演示'})
  if(!persist()){state.records.pop();return}crySaved.value=true;toast('演示结果已保存')
}
function sendChat(question?: string){
  const text=(question||chatInput.value).trim();if(!text)return
  state.messages.push({role:'me',text},{role:'bot',text:`【演示回复】已收到“${text}”。你已记录 ${todayRecords.value.length} 条今日数据。正式 AI 问答尚未接入，此处仅用于体验对话交互。`})
  chatInput.value='';persist()
}
const articleTitles:Record<string,string>={'sleep-guide':'8个月宝宝睡眠全攻略','feeding-guide':'8个月宝宝辅食添加指南','night-wake':'宝宝夜醒的常见原因与应对方法','teething':'出牙期护理全攻略','poop':'宝宝便便颜色对照表'}
const articleBodies:Record<string,string>={
  'sleep-guide':'观察宝宝睡眠时，可以记录入睡时间、夜醒次数和白天小睡时长，把连续几天的记录放在一起查看。\n\n本页为原型阅读内容示例，不是个性化医疗建议。',
  'feeding-guide':'记录每次辅食的食材、份量以及宝宝的反应，方便家人了解当天的喂养情况。\n\n本页为阅读交互示例，正式内容需经过专业审核。',
  'night-wake':'可以先记录夜醒的时间、次数和安抚过程，方便回看作息变化。\n\n本页展示文章阅读交互，不提供诊断。',
  'teething':'可以在宝宝档案中补充出牙期的观察记录，并在需要时向专业人员咨询。\n\n本页为内容示例。',
  'poop':'记录颜色、性状、次数和观察时间，帮助照护者交接信息。\n\n本页为内容示例，不作健康判断。'
}
function openArticle(key:string){article.value=key}
function favoriteArticle(){const index=state.favorites.indexOf(article.value);if(index<0)state.favorites.push(article.value);else state.favorites.splice(index,1);persist()}
const profileForm=reactive({value:'',note:''})
function editProfile(name:string){modalTitle.value=name;Object.assign(profileForm,state.profile[name]||{value:name==='基本信息'?state.babyName:'',note:''});modal.value='profile'}
function saveProfile(){if(!profileForm.value.trim())return toast('请填写信息');if(modalTitle.value==='基本信息')state.babyName=profileForm.value.trim();state.profile[modalTitle.value]={...profileForm};if(persist()){closeModal();toast('档案已保存')}}
const settingsDraft=reactive({...state.settings})
function setSetting(key: keyof typeof settingsDraft, event: unknown) {
  const value = (event as { detail?: { value?: unknown } })?.detail?.value
  if (typeof value === 'boolean') settingsDraft[key] = value
}
function saveSettings(){Object.assign(state.settings,settingsDraft);if(persist()){closeModal();toast('设置已保存在本机')}}
const feedback = ref('')
function saveFeedback(){if(!feedback.value.trim())return toast('请填写反馈内容');state.feedback.push(feedback.value.trim());if(persist()){feedback.value='';closeModal();toast('反馈已暂存本机，尚未发送')}}
const exportFormat=ref<'CSV'|'JSON'>('CSV')
const exportText=computed(()=>exportRecords(state.records,exportFormat.value))
function copyExport(){uni.setClipboardData({data:exportText.value,success(){toast('全部记录已复制，可粘贴保存')},fail(){toast('复制失败，请重试')}})}
function info(title:string,text:string){modalTitle.value=title;modalText.value=text;modal.value='info'}
function action(name:string,message=''){
  switch(name){
    case 'open-record':case 'open-more': modal.value='chooser';break
    case 'capture-voice':startVoice();break
    case 'voice':voicePurpose.value='chat';beginVoice();break
    case 'capture-photo':startPhoto();break
    case 'send-chat':sendChat();break
    case 'cry-toggle':toggleCry();break
    case 'cry-reset':resetCry();break
    case 'save-cry':saveCry();break
    case 'switch-curve':curveMode.value=(curveMode.value+1)%3;break
    case 'open-growth-detail':modal.value='chart';break
    case 'open-growth-record':quickRecord('身高体重');break
    case 'shuffle-articles':category.value=['推荐','喂养','睡眠','发育'][(Math.max(0,['推荐','喂养','睡眠','发育'].indexOf(category.value))+1)%4]!;search.value='';break
    case 'article-sleep':openArticle('sleep-guide');break
    case 'edit-profile':editProfile('基本信息');break
    case 'family':modal.value='family';break
    case 'export':modal.value='export';break
    case 'feedback':modal.value='feedback';break
    case 'settings':Object.assign(settingsDraft,state.settings);modal.value='settings';break
    case 'upgrade':info('懂宝 Pro','会员权益演示：更长对话上下文、成长报告和家庭协作。支付尚未接入，不会产生扣费。');break
    case 'toast':
      if(message==='设置已打开') action('settings')
      else if(message==='收藏夹')modal.value='favorites'
      else if(message==='历史对话')navigate('ai')
      else if(message==='使用帮助')info('使用帮助','在首页选择记录类型填写内容，确认后保存。语音、拍照和哭声功能为演示。记录与设置只保存在当前设备，可通过“数据导出”复制备份。')
      else if(message==='暂无历史分析')info('哭声分析历史',state.records.filter(r=>r.type==='哭声分析').map(r=>`${r.date} ${r.time}\n${r.value}`).join('\n\n')||'还没有保存分析结果')
      else toast(message||'暂无新消息')
      break
  }
}
function suspend(){stopCapture();if(modal.value==='voice')modal.value='';if(cryRunning.value)resetCry()}
onHide(suspend)
onUnmounted(suspend)
</script>

<template>
<view>

<view class="stage">
  <view class="phone" id="app"><view class="demo-banner">交互演示 · 数据保存在本机 · AI / 识别结果为示例</view>
    <view class="main">

      <view class="page" v-if="page === 'home'">
        <view class="header">
          <view><view class="brand">懂宝</view><view class="tagline">用 AI 陪伴每一个小小的成长</view></view>
          <view style="display:flex;gap:8px"><button class="icon-btn" @tap="action('toast', '暂无新通知')">🔔</button><button class="icon-btn circle-add" @tap="action('open-record', '')">＋</button></view>
        </view>
        <view class="content">
          <view class="hero" @tap="navigate('profile')">
            <view class="avatar">👶🏻</view>
            <view style="flex:1"><view class="h3">{{ state.babyName }} <text style="color:#ff69a8" class="span">♀</text></view><view class="p">8个月12天</view><view class="p">“今天也要开心呀～” <text class="tiny-heart span">❤</text></view></view>
          </view>

          <view class="card observe">
            <view class="card-title">💡 AI 今日观察</view>
            <view class="small">基于最近 5 天的记录</view>
            <view class="p">宝宝昨晚睡眠时间略有减少，夜醒 3 次；可能与出牙或白天睡眠不足有关。整体状态正常，建议关注白天小睡时长。</view>
            <button class="primary-btn wide" @tap="navigate('ai')">查看详细分析 →</button>
          </view>

          <view class="section-title">记一笔</view>
          <view class="capture-row">
            <button class="capture-btn voice" @tap="action('capture-voice', '')"><text class="cap-ico span">🎙</text><text class="b">语音记录</text><text class="span">说一句，AI 帮你填</text></button>
            <button class="capture-btn photo" @tap="action('capture-photo', '')"><text class="cap-ico span">📷</text><text class="b">拍照记录</text><text class="span">拍奶瓶 / 辅食 / 便便</text></button>
          </view>
          <view class="section-title">手动快捷</view>
          <view class="quick-grid">
            <button class="quick-item" @tap="quickRecord('喂奶')"><view class="quick-icon i-feed">🍼</view><text class="span">喂奶</text></button>
            <button class="quick-item" @tap="quickRecord('睡眠')"><view class="quick-icon i-sleep">🌙</view><text class="span">睡眠</text></button>
            <button class="quick-item" @tap="quickRecord('辅食')"><view class="quick-icon i-food">🥣</view><text class="span">辅食</text></button>
            <button class="quick-item" @tap="quickRecord('排便')"><view class="quick-icon i-poop">💩</view><text class="span">排便</text></button>
            <button class="quick-item" @tap="quickRecord('尿布')"><view class="quick-icon i-diaper">🩲</view><text class="span">尿布</text></button>
            <button class="quick-item" @tap="quickRecord('身高体重')"><view class="quick-icon i-height">📈</view><text class="span">身高体重</text></button>
            <button class="quick-item" @tap="quickRecord('用药')"><view class="quick-icon i-med">💊</view><text class="span">用药</text></button>
            <button class="quick-item" @tap="action('open-more', '')"><view class="quick-icon i-more">•••</view><text class="span">更多</text></button>
          </view>

          <view class="card cry-card">
            <view><view class="card-title">宝宝哭了？</view><view class="small" style="margin:4px 0 10px">AI 陪你分辨哭声，找出可能原因</view><button class="primary-btn" @tap="navigate('cry')">开始哭声分析 →</button></view>
            <view class="cry-whale">🐳</view>
          </view>

          <view class="section-title">今天 · {{ todayLabel }} <button class="link" @tap="navigate('record')">{{ todayRecords.length }} 条记录</button></view>
          <view class="card" style="margin-top:0">
            <view class="timeline" id="homeTimeline"><RecordTimeline :records="todayRecords" /></view>
          </view>
        </view>
      </view>


      <view class="page" v-if="page === 'ai'">
        <view class="header"><button class="icon-btn" @tap="navigate('home')">‹</button><view style="text-align:center;flex:1"><view class="header-title" style="justify-content:center">懂宝 AI</view><view class="tagline">基于宝宝数据的专属育儿助手</view></view><view style="width:38px"></view></view>
        <view class="chat-wrap" id="chatList"><view v-for="(message, i) in state.messages" :key="i" class="bubble-row" :class="message.role"><view class="bubble history-text">{{ message.text }}</view></view></view>
        <view class="suggests"><view class="h4">你可能还想问</view>
          <button class="chip" @tap="sendChat('8个月宝宝一天应该喝多少奶？')">8个月宝宝一天应该喝多少奶？</button>
          <button class="chip" @tap="sendChat('如何判断宝宝是否出牙？')">如何判断宝宝是否出牙？</button>
          <button class="chip" @tap="sendChat('宝宝睡眠倒退一般持续多久？')">宝宝睡眠倒退一般持续多久？</button>
        </view>
        <view class="composer"><input id="chatInput" placeholder="有什么育儿问题都可以问我…" v-model="chatInput" @confirm="sendChat()" confirm-type="send"></input><button class="mic" @tap="action('voice', '')">🎙</button><button class="send" @tap="action('send-chat', '')">➤</button></view>
      </view>


      <view class="page" v-if="page === 'record'">
        <view class="header"><button class="icon-btn" @tap="navigate('home')">‹</button><view class="header-title">记录</view><view style="width:38px"></view></view>
        <view class="seg"><button class="" @tap="setRange('day')" :class="{ active: range === 'day' }">日</button><button @tap="setRange('week')" :class="{ active: range === 'week' }" class="">周</button><button @tap="setRange('month')" :class="{ active: range === 'month' }" class="">月</button></view>
        <view class="datebar"><button @tap="shiftDate('-1')">‹</button><text id="recordDateLabel" class="span">{{ dateLabel }}</text><button @tap="shiftDate('1')">›</button></view>
        <view class="content">
          <view class="card" style="margin-top:10px"><view class="stats-grid"><view v-for="stat in stats" :key="stat.name" class="stat"><text class="b">{{ stat.name }}</text><text class="span">{{ stat.value }}</text><text class="small">{{ stat.count }} 次</text></view></view>
            <view class="capture-row record-cta">
              <button class="capture-btn voice" @tap="action('capture-voice', '')"><text class="cap-ico span">🎙</text><text class="b">语音</text><text class="span">说完自动识别</text></button>
              <button class="capture-btn photo" @tap="action('capture-photo', '')"><text class="cap-ico span">📷</text><text class="b">拍照</text><text class="span">看图帮你填</text></button>
            </view>
            <button class="soft-btn wide" style="margin-top:10px" @tap="action('open-record', '')">手动选择类型</button>
          </view>
          <view class="section-title">记录时间线 <picker :range="recordFilters" @change="changeRecordFilter"><text class="link">{{ recordFilter }} ▾</text></picker></view>
          <view class="timeline" id="recordTimeline"><RecordTimeline :records="visibleRecords" /></view>
        </view>
      </view>


      <view class="page cry-page" v-if="page === 'cry'">
        <view class="header"><button class="icon-btn" @tap="navigate('home')">‹</button><view class="header-title">哭声分析</view><button class="link" @tap="action('toast', '暂无历史分析')">历史</button></view>
        <view class="cry-stage">
          <view class="baby-circle"><view class="wave"><text class="span">≋</text><text class="span">≋</text></view>😭</view>
          <view id="cryStatus" class="h3">{{ cryRunning ? '正在演示监听…' : cryReady ? '演示分析完成' : '点击体验哭声分析' }}</view><view id="cryTip" class="p">演示模式，不会采集或分析真实哭声。</view>
          <button class="record-btn" id="cryBtn" @tap="action('cry-toggle', '')">{{ cryRunning ? '■' : '●' }}</button>
          <view class="record-time" id="cryTimer">00:{{ String(crySeconds).padStart(2, '0') }} / 00:30</view>
        </view>
        <view class="analysis-card">
          <view class="card-title">分析结果 <text class="small span" id="crySample">（演示数据）</text></view>
          <view id="reasonList">
            <view class="reason"><text class="span">1.</text><view>饥饿<view class="bar"><view class="fill" style="width:42%"></view></view></view><text class="b">42%</text></view>
            <view class="reason"><text class="span">2.</text><view>困倦<view class="bar"><view class="fill" style="width:28%"></view></view></view><text class="b">28%</text></view>
            <view class="reason"><text class="span">3.</text><view>胀肚气<view class="bar"><view class="fill" style="width:20%"></view></view></view><text class="b">20%</text></view>
            <view class="reason"><text class="span">4.</text><view>不适<view class="bar"><view class="fill" style="width:10%"></view></view></view><text class="b">10%</text></view>
          </view>
          <view class="disclaimer">AI 分析仅供参考，如宝宝持续哭闹或伴随其他异常症状，建议及时咨询医生。</view>
          <view class="row-btns"><button class="outline-btn" @tap="action('cry-reset', '')">重新录制</button><button class="primary-btn" @tap="action('save-cry', '')">保存结果</button></view>
        </view>
      </view>


      <view class="page" v-if="page === 'growth'">
        <view class="header"><view class="header-title">成长</view><button class="icon-btn" @tap="action('open-growth-record', '')">＋</button></view>
        <view class="growth-top"><view class="growth-tabs"><button class="" @tap="setGrowthTab('data')" :class="{ active: growthTab === 'data' }">数据</button><button @tap="setGrowthTab('timeline')" :class="{ active: growthTab === 'timeline' }" class="">时间线</button><button @tap="setGrowthTab('milestone')" :class="{ active: growthTab === 'milestone' }" class="">里程碑</button></view></view>
        <view class="content" id="growthData" v-if="growthTab === 'data'">
          <view class="section-title" style="margin-top:12px">生长发育</view>
          <view class="card" style="margin-top:0">
            <view style="display:flex;justify-content:space-between;align-items:center"><view><text style="font-size:18px" class="b">8个月12天</text><view class="small">矫正月龄：8个月12天</view></view><button class="outline-btn" @tap="action('switch-curve', '')">切换曲线</button></view>
            <view class="metrics" style="margin-top:12px"><view class="metric"><text class="span">体重</text><text class="b">8.2 kg</text><view class="ok">P60 正常</view></view><view class="metric"><text class="span">身高</text><text class="b">70 cm</text><view class="ok">P55 正常</view></view><view class="metric"><text class="span">头围</text><text class="b">43.2 cm</text><view class="ok">P58 正常</view></view></view>
            <view class="chart-wrap" id="chartArea"><image class="chart-image" :src="chartUrl" mode="aspectFit" /><view class="small">{{ curveNames[curveMode] }} · 原型示意，非医学标准曲线</view></view>
            <view class="legend"><text style="color:#6d5cf7" class="span">身高</text><text style="color:#73b7ff" class="span">体重</text><text style="color:#ffad55" class="span">头围</text></view>
            <button class="link wide" style="margin-top:7px" @tap="action('open-growth-detail', '')">查看详细生长曲线 →</button>
          </view>
          <view class="section-title">发育里程碑 <button class="link" @tap="setGrowthTab('milestone')">全部 ›</button></view>
          <view class="card" style="margin-top:0">
            <view class="milestone" @tap="toggleMilestone('会爬')"><view class="m-check">{{ state.milestones.includes('会爬') ? '✓' : '○' }}</view><view><text class="b">会爬</text><text class="span">通常 7–10 个月</text></view></view>
            <view class="milestone" @tap="toggleMilestone('扶站')"><view class="m-check">{{ state.milestones.includes('扶站') ? '✓' : '○' }}</view><view><text class="b">扶站</text><text class="span">通常 8–12 个月</text></view></view>
            <view class="milestone" @tap="toggleMilestone('会叫爸爸妈妈')"><view class="m-check">{{ state.milestones.includes('会叫爸爸妈妈') ? '✓' : '○' }}</view><view><text class="b">会叫爸爸妈妈</text><text class="span">通常 9–12 个月</text></view></view>
          </view>
        </view>
        <view class="content" id="growthTimelinePanel" v-if="growthTab === 'timeline'"><RecordTimeline :records="state.records.filter(record => record.type === '身高体重')" /><view class="card"><view class="section-title" style="margin-top:0">成长时间线</view><view class="timeline"><view class="t-row"><view class="dot" style="color:#3bc879"></view><view class="t-time">9/14</view><view class="t-main"><text class="strong">身高 70cm</text><view class="t-sub">体重 8.2kg · 头围 43.2cm</view></view></view><view class="t-row"><view class="dot" style="color:#6d5cf7"></view><view class="t-time">8/12</view><view class="t-main"><text class="strong">第一次独立爬行</text><view class="t-sub">成长里程碑</view></view></view></view></view></view>
        <view class="content" id="growthMilestonePanel" v-if="growthTab === 'milestone'"><view class="card"><view class="section-title" style="margin-top:0">里程碑</view><view class="milestone" @tap="toggleMilestone('会爬')"><view class="m-check">{{ state.milestones.includes('会爬') ? '✓' : '○' }}</view><view><text class="b">会爬</text><text class="span">{{ state.milestones.includes('会爬') ? '已完成' : '待观察' }}</text></view></view><view class="milestone" @tap="toggleMilestone('扶站')"><view class="m-check">{{ state.milestones.includes('扶站') ? '✓' : '○' }}</view><view><text class="b">扶站</text><text class="span">{{ state.milestones.includes('扶站') ? '已完成' : '待观察' }}</text></view></view><view class="milestone" @tap="toggleMilestone('独立站立')"><view class="m-check">{{ state.milestones.includes('独立站立') ? '✓' : '○' }}</view><view><text class="b">独立站立</text><text class="span">{{ state.milestones.includes('独立站立') ? '已完成' : '待观察' }}</text></view></view></view></view>
      </view>


      <view class="page" v-if="page === 'discover'">
        <view class="header"><view class="header-title">发现</view><view style="width:38px"></view></view>
        <view class="searchbar">⌕ <input id="articleSearch" placeholder="搜索育儿知识、文章、问题…" v-model="search"></input></view>
        <view class="rec-tabs"><button class="" @tap="setCategory('推荐')" :class="{ active: category === '推荐' }">为你推荐</button><button @tap="setCategory('当月')" :class="{ active: category === '当月' }" class="">当月月龄</button><button @tap="setCategory('喂养')" :class="{ active: category === '喂养' }" class="">喂养</button><button @tap="setCategory('睡眠')" :class="{ active: category === '睡眠' }" class="">睡眠</button><button @tap="setCategory('发育')" :class="{ active: category === '发育' }" class="">发育</button></view>
        <view class="discover-hero"><view><view class="h3">8个月宝宝<text>
</text>睡眠全攻略</view><view class="p">如何应对夜醒、睡眠倒退？</view><button class="primary-btn" @tap="openArticle('sleep-guide')">立即阅读</button></view><view class="sleep-ill">😴</view></view>
        <view class="section-title" style="padding:0 14px;margin-top:0">猜你喜欢 <button class="link" @tap="action('shuffle-articles', '')">换一批</button></view>
        <view class="article-list" id="articleList"><view v-if="!hasMatchingArticle" class="empty">没有匹配的文章，试试其他关键词或分类</view>
          <view class="article" @tap="openArticle('feeding-guide')" v-show="matchesArticle('喂养', '8个月宝宝辅食添加指南')"><view class="thumb">🥗</view><view><text class="b">8个月宝宝辅食添加指南</text><view class="p">从泥糊到小块，怎么吃更科学？</view><text class="small">12.3k 阅读 · 专业医生</text></view></view>
          <view class="article" @tap="openArticle('night-wake')" v-show="matchesArticle('睡眠', '宝宝夜醒的常见原因与应对方法')"><view class="thumb">👶</view><view><text class="b">宝宝夜醒的常见原因与应对方法</text><view class="p">陪伴睡眠训练的关键步骤</view><text class="small">8.7k 阅读 · 儿科医生</text></view></view>
          <view class="article" @tap="openArticle('teething')" v-show="matchesArticle('发育', '出牙期护理全攻略')"><view class="thumb">🦷</view><view><text class="b">出牙期护理全攻略</text><view class="p">如何缓解宝宝出牙不适</view><text class="small">6.5k 阅读 · 育儿专家</text></view></view>
          <view class="article" @tap="openArticle('poop')" v-show="matchesArticle('喂养', '宝宝便便颜色对照表')"><view class="thumb">🥣</view><view><text class="b">宝宝便便颜色对照表</text><view class="p">一张图看懂正常与异常</view><text class="small">9.1k 阅读 · 专业医生</text></view></view>
        </view>
      </view>


      <view class="page" v-if="page === 'profile'">
        <view class="header"><button class="icon-btn" @tap="navigate('home')">‹</button><view class="header-title">宝宝档案</view><button class="link" @tap="action('edit-profile', '')">编辑</button></view>
        <view class="profile-head"><view class="baby-profile"><view class="avatar">👶🏻</view><view><view class="h3">{{ state.babyName }} <text style="color:#ff6da8" class="span">♀</text></view><view class="p">8个月12天 · 女宝宝</view><view class="p">2026年1月6日出生</view></view></view>
          <view class="mini-metrics"><view class="metric"><text class="span">身高</text><text class="b">70 cm</text><text class="small">(8月龄 P55)</text></view><view class="metric"><text class="span">体重</text><text class="b">8.2 kg</text><text class="small">(8月龄 P60)</text></view><view class="metric"><text class="span">头围</text><text class="b">43.2 cm</text><text class="small">(8月龄 P58)</text></view></view></view>
        <view class="settings-list">
          <view class="setting-row" @tap="editProfile('基本信息')"><view class="setting-ico">👤</view><text class="b">基本信息</text><text class="chev span">›</text></view>
          <view class="setting-row" @tap="navigate('growth')"><view class="setting-ico">📈</view><text class="b">生长发育</text><text class="chev span">›</text></view>
          <view class="setting-row" @tap="editProfile('喂养偏好')"><view class="setting-ico">🛡</view><text class="b">喂养偏好</text><text class="small">{{ state.profile['喂养偏好']?.value || '配方奶 · 无特殊忌口' }}</text><text class="chev span">›</text></view>
          <view class="setting-row" @tap="editProfile('睡眠习惯')"><view class="setting-ico">🌙</view><text class="b">睡眠习惯</text><text class="small">{{ state.profile['睡眠习惯']?.value || '通常 20:30 入睡' }}</text><text class="chev span">›</text></view>
          <view class="setting-row" @tap="editProfile('过敏信息')"><view class="setting-ico">📍</view><text class="b">过敏信息</text><text class="small">{{ state.profile['过敏信息']?.value || '无已知过敏' }}</text><text class="chev span">›</text></view>
          <view class="setting-row" @tap="editProfile('疫苗接种')"><view class="setting-ico">💉</view><text class="b">疫苗接种</text><text class="small">{{ state.profile['疫苗接种']?.value || '按计划接种' }}</text><text class="chev span">›</text></view>
          <view class="setting-row" @tap="editProfile('家人信息')"><view class="setting-ico">👨‍👩‍👧</view><text class="b">家人信息</text><text class="small">{{ state.profile['家人信息']?.value || '爸爸、妈妈、爷爷奶奶' }}</text><text class="chev span">›</text></view>
          <view class="setting-row" @tap="editProfile('医疗记录')"><view class="setting-ico">🧾</view><text class="b">医疗记录</text><text class="small">{{ state.profile['医疗记录']?.value || '体检、用药、病史' }}</text><text class="chev span">›</text></view>
        </view>
      </view>


      <view class="page" v-if="page === 'me'">
        <view class="header"><view class="header-title"></view><button class="icon-btn" @tap="action('toast', '设置已打开')">⚙</button></view>
        <view class="me-head"><view class="me-card"><view class="person"><view class="person-avatar">👨🏻</view><view style="flex:1"><view class="h3">余海昌</view><view class="p">陪伴{{ state.babyName }}成长的第 251 天</view></view></view><view class="membership"><view><text class="b">♛ 普通会员</text><view class="small">升级会员，解锁更多 AI 能力</view></view><button class="member-btn" @tap="action('upgrade', '')">立即升级</button></view><view class="icon-grid"><view class="gitem" @tap="action('toast', '收藏夹')"><view class="gico">⭐</view>收藏</view><view class="gitem" @tap="action('toast', '历史对话')"><view class="gico">💬</view>历史对话</view><view class="gitem" @tap="navigate('profile')"><view class="gico">👶</view>我的宝宝</view><view class="gitem" @tap="action('toast', '暂无新消息')"><view class="gico">🔔</view>消息</view></view></view></view>
        <view class="settings-list">
          <view class="setting-row" @tap="action('family', '')"><view class="setting-ico">👥</view><text class="b">家庭成员管理</text><text class="chev span">›</text></view>
          <view class="setting-row" @tap="action('export', '')"><view class="setting-ico">⇩</view><text class="b">数据导出</text><text class="chev span">›</text></view>
          <view class="setting-row" @tap="action('toast', '使用帮助')"><view class="setting-ico">?</view><text class="b">使用帮助</text><text class="chev span">›</text></view>
          <view class="setting-row" @tap="action('feedback', '')"><view class="setting-ico">✉</view><text class="b">意见反馈</text><text class="chev span">›</text></view>
          <view class="setting-row" @tap="action('settings', '')"><view class="setting-ico">⚙</view><text class="b">设置</text><text class="chev span">›</text></view>
        </view>
        <view class="banner"><text class="span">每一个小小的成长<text>
</text>都值得被认真记录 ❤</text><text class="art span">🤱🏻</text></view>
      </view>
    </view>

    <view class="nav">
      <button class="" @tap="navigate('home')" :class="{ active: page === 'home' }"><text class="n-ico span">⌂</text><text class="span">首页</text></button>
      <button @tap="navigate('ai')" :class="{ active: page === 'ai' }" class=""><text class="n-ico span">◉</text><text class="span">AI</text></button>
      <button @tap="navigate('record')" :class="{ active: page === 'record' }" class=""><text class="n-ico span">▣</text><text class="span">记录</text></button>
      <button @tap="navigate('discover')" :class="{ active: page === 'discover' }" class=""><text class="n-ico span">◌</text><text class="span">发现</text></button>
      <button @tap="navigate('me')" :class="{ active: page === 'me' }" class=""><text class="n-ico span">♙</text><text class="span">我的</text></button>
    </view>
  </view>
</view>

  <view v-if="modal" class="modal-mask" @tap="closeModal">
    <scroll-view scroll-y class="sheet" @tap.stop>
      <view class="close-row"><text class="sheet-title">{{ modal === 'record' ? '记录 · ' + draft.type : modal === 'chooser' ? '记一笔' : modal === 'voice' ? '语音记录 · 演示' : modal === 'photo' ? '拍照记录' : modal === 'settings' ? '设置' : modal === 'export' ? '数据导出' : modal === 'feedback' ? '意见反馈' : modal === 'family' ? '家庭成员' : modal === 'favorites' ? '我的收藏' : modal === 'chart' ? '详细生长曲线' : modalTitle }}</text><button class="icon-btn" @tap="closeModal">×</button></view>
      <view v-if="modal === 'chooser'">
        <view class="capture-row"><button class="capture-btn voice" @tap="startVoice">🎙 语音记录</button><button class="capture-btn photo" @tap="startPhoto">📷 拍照记录</button></view>
        <view class="quick-grid"><button v-for="type in recordTypes" :key="type" class="quick-item" @tap="quickRecord(type)">{{ type }}</button></view>
      </view>
      <view v-else-if="modal === 'record'">
        <view v-if="draft.source !== '手动记录'" class="draft-preview">{{ draft.source }}草稿 · 请核对后确认保存，尚未进行真实识别。</view>
        <view class="form-row"><text class="label">日期</text><picker mode="date" :value="draft.date" @change="changeDraftDate"><view class="choice">{{ draft.date }}</view></picker></view>
        <view class="form-row"><text class="label">时间</text><picker mode="time" :value="draft.time" @change="changeDraftTime"><view class="choice">{{ draft.time }}</view></picker></view>
        <view class="form-row"><text class="label">{{ draft.type === '喂奶' ? '奶量 (ml)' : draft.type === '睡眠' ? '时长 (分)' : draft.type === '体温' ? '体温 (℃)' : '内容' }}</text><input v-model="draft.value" :type="['喂奶','睡眠','体温'].includes(draft.type) ? 'digit' : 'text'" :maxlength="300" placeholder="请填写记录内容" /></view>
        <view class="form-row"><text class="label">备注</text><textarea v-model="draft.note" :maxlength="500" placeholder="可选" /></view>
        <view class="row-btns"><button class="outline-btn" @tap="draft.source === '语音演示' ? startVoice() : draft.source === '拍照演示' ? startPhoto() : closeModal()">{{ draft.source === '手动记录' ? '取消' : '重新采集' }}</button><button class="primary-btn" @tap="saveRecord">确认保存</button></view>
      </view>
      <view v-else-if="modal === 'voice'" class="listen-panel"><view class="listen-orb pulse">🎙</view><view>模拟聆听 {{ captureSeconds }} 秒</view><view class="small">不调用麦克风，演示转写为“{{ voicePurpose === 'chat' ? '宝宝最近为什么晚上总醒？' : '喂了 180 毫升配方奶' }}”。</view><button class="primary-btn wide" @tap="finishVoice">结束演示，确认内容</button></view>
      <view v-else-if="modal === 'photo'"><image v-if="photo" class="photo-preview" :src="photo" mode="aspectFit" /><view v-else class="photo-slot">📷 拍摄或选择图片</view><view class="small">图片仅在本次预览，不上传。下一步生成固定示例草稿，请手动核对。</view><view class="row-btns"><button class="outline-btn" @tap="choosePhoto('camera')">拍照</button><button class="outline-btn" @tap="choosePhoto('album')">从相册选择</button></view><button class="primary-btn wide" @tap="photoDraft">{{ photo ? '查看示例草稿' : '使用示例体验' }}</button></view>
      <view v-else-if="modal === 'profile'"><view class="form-row"><text class="label">{{ modalTitle === '基本信息' ? '宝宝昵称' : '当前状态' }}</text><input v-model="profileForm.value" :maxlength="80" placeholder="填写信息" /></view><view class="form-row"><text class="label">备注</text><textarea v-model="profileForm.note" :maxlength="500" placeholder="补充信息" /></view><button class="primary-btn wide" @tap="saveProfile">保存</button></view>
      <view v-else-if="modal === 'settings'"><view class="small">这些是本机偏好，通知推送、家庭同步和 AI 个性化服务尚未接入。</view><view class="setting-row"><text>通知偏好</text><switch :checked="settingsDraft.notifications" @change="setSetting('notifications', $event)" /></view><view class="setting-row"><text>家庭共享偏好</text><switch :checked="settingsDraft.sharing" @change="setSetting('sharing', $event)" /></view><view class="setting-row"><text>AI 个性化偏好</text><switch :checked="settingsDraft.personalized" @change="setSetting('personalized', $event)" /></view><button class="primary-btn wide" @tap="saveSettings">保存设置</button></view>
      <view v-else-if="modal === 'feedback'"><view class="small">反馈暂存本机，尚未接入发送服务。</view><textarea v-model="feedback" :maxlength="1000" placeholder="告诉我们哪里还可以做得更好…" /><button class="primary-btn wide" @tap="saveFeedback">保存反馈</button></view>
      <view v-else-if="modal === 'family'"><view v-for="member in ['👨🏻 爸爸 · 管理员','👩🏻 妈妈 · 管理员','👵🏻 奶奶 · 可记录']" :key="member" class="setting-row">{{ member }}</view><view class="small">以上为原型家庭示例，尚未连接真实家庭账号。</view><button class="primary-btn wide" @tap="info('邀请家庭成员','家庭邀请需要接入账号与家庭服务，当前仅展示交互流程。')">＋ 邀请家庭成员</button></view>
      <view v-else-if="modal === 'export'"><view class="small">导出本机全部 {{ state.records.length }} 条记录。选择格式后复制为文本保存。</view><view class="row-btns"><button :class="exportFormat === 'CSV' ? 'primary-btn' : 'outline-btn'" @tap="exportFormat = 'CSV'">CSV</button><button :class="exportFormat === 'JSON' ? 'primary-btn' : 'outline-btn'" @tap="exportFormat = 'JSON'">JSON</button></view><textarea :value="exportText" disabled /><button class="primary-btn wide" @tap="copyExport">复制导出内容</button></view>
      <view v-else-if="modal === 'favorites'"><view v-if="!state.favorites.length" class="empty">暂无收藏，在文章中点击收藏即可添加。</view><button v-for="key in state.favorites" :key="key" class="soft-btn wide" @tap="closeModal(); openArticle(key)">{{ articleTitles[key] }}</button></view>
      <view v-else-if="modal === 'chart'"><image class="chart-image" :src="chartUrl" mode="aspectFit" /><view class="small">{{ curveNames[curveMode] }} · 示例曲线，不代表真实百分位。</view><button class="soft-btn wide" @tap="action('switch-curve')">切换曲线</button></view>
      <view v-else class="history-text">{{ modalText }}</view>
    </scroll-view>
  </view>
  <view v-if="article" class="overlay-view"><view class="overlay-head"><button class="icon-btn" @tap="article = ''">‹</button><text class="h3">{{ articleTitles[article] }}</text></view><view class="overlay-body"><view class="history-text">{{ articleBodies[article] }}</view><button class="primary-btn wide" @tap="favoriteArticle">{{ state.favorites.includes(article) ? '取消收藏' : '收藏文章' }}</button></view></view>

</view>
</template>
