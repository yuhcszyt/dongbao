<script setup lang="ts">
import { ref, watch } from 'vue'
import { api } from '@/services/api'
import { roleName, canRemoveMember, type FamilyOverview } from '@/features/content/family'
import { errorText } from '../domain/workspace'
const props=defineProps<{ family:FamilyOverview }>()
const emit=defineEmits<{ changed:[]; switch:[id:string]; join:[token:string]; busy:[value:boolean] }>()
const busy=ref(false),error=ref(''),token=ref(''),preview=ref(''),name=ref(props.family.name),displayName=ref(props.family.display_name)
const invite=ref('')
const previewToken=ref('')
watch(busy,value=>emit('busy',value),{flush:'sync'})
async function run(task:()=>Promise<unknown>,refresh=true){
  if(busy.value)return
  busy.value=true;error.value=''
  try{await task();if(refresh)emit('changed')}
  catch(e){error.value=errorText(e)}finally{busy.value=false}
}
function createInvite(){void run(async()=>{const result=await api.createInvite();invite.value=result.token},false)}
function copyInvite(){uni.setClipboardData({data:invite.value,fail(){error.value='邀请码复制失败，请重试'}})}
function previewInvite(){
  const requestedToken=token.value.trim();preview.value='';previewToken.value=''
  void run(async()=>{
    const result=await api.previewInvite(requestedToken)
    if(token.value.trim()!==requestedToken)return
    previewToken.value=requestedToken;preview.value=result.family_name
  },false)
}
function confirmAction(title:string,task:()=>Promise<unknown>){uni.showModal({title,content:'请确认此项家庭管理操作。',success(result){if(result.confirm)void run(task)}})}
</script>
<template>
  <view class="family-panel">
    <view class="small">{{ family.name }} · {{ roleName(family.role) }}</view>
    <view v-if="error" class="error-box">{{ error }}</view>
    <view class="form-row"><text>我的称呼</text><input v-model="displayName" maxlength="40" /></view>
    <button class="soft-btn wide" :disabled="busy" @tap="run(()=>api.familyProfile(displayName))">保存称呼</button>
    <view v-if="family.role !== 'member'" class="form-row"><text>家庭名称</text><input v-model="name" maxlength="40" /></view>
    <button v-if="family.role !== 'member'" class="soft-btn wide" :disabled="busy" @tap="run(()=>api.renameFamily(name))">修改家庭名称</button>
    <view v-for="member in family.members" :key="member.user_id" class="card">
      <view>{{ member.name }} · {{ roleName(member.role) }}{{ member.user_id === family.user_id ? '（我）' : '' }}</view>
      <view v-if="member.user_id !== family.user_id" class="button-row">
        <button v-if="family.role === 'owner' && member.role !== 'owner'" class="soft-btn" :disabled="busy" @tap="confirmAction('修改成员权限',()=>api.familyRole(member.user_id,member.role === 'admin' ? 'member' : 'admin'))">{{ member.role === 'admin' ? '设为家人' : '设为管理员' }}</button>
        <button v-if="family.role === 'owner'" class="outline-btn" :disabled="busy" @tap="confirmAction('转交家庭管理',()=>api.transferFamily(member.user_id))">转交</button>
        <button v-if="canRemoveMember(family.role,member.role)" class="danger-btn" :disabled="busy" @tap="confirmAction('移除成员',()=>api.removeFamilyMember(member.user_id))">移除</button>
      </view>
    </view>
    <button v-if="family.role !== 'member'" class="primary-btn wide" :disabled="busy" @tap="createInvite">生成真实邀请码</button>
    <view v-if="invite" class="draft-preview"><text selectable>{{ invite }}</text><button class="soft-btn" @tap="copyInvite">复制邀请码</button></view>
    <view v-for="item in family.invites" :key="item.id" class="card"><text>邀请有效至 {{ item.expires_at }}</text><button class="danger-btn" :disabled="busy" @tap="run(()=>api.revokeInvite(item.id))">撤销邀请</button></view>
    <view class="section-title">加入家庭</view>
    <input v-model="token" class="choice" :disabled="busy" placeholder="粘贴家人分享的邀请码" @input="preview = ''; previewToken = ''" />
    <button class="outline-btn wide" :disabled="busy || !token.trim()" @tap="previewInvite">查看邀请</button>
    <view v-if="preview && previewToken === token.trim()" class="card">即将加入：{{ preview }}<button class="primary-btn wide" :disabled="busy" @tap="emit('join',previewToken)">确认加入</button></view>
    <view class="section-title">切换家庭</view>
    <button v-for="item in family.families" :key="item.id" class="soft-btn wide" :disabled="busy || item.id === family.id" @tap="emit('switch',item.id)">{{ item.name }}{{ item.id === family.id ? '（当前）' : '' }}</button>
  </view>
</template>
