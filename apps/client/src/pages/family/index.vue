<script setup lang="ts">
import { computed, ref, onBeforeUnmount } from 'vue'
import { onLoad, onShow, onShareAppMessage } from '@dcloudio/uni-app'
import { api } from '@/services/api'
import { recordStore, errorText } from '@/features/record/store'
import { roleName, auditName, canRemoveMember, type FamilyOverview, type FamilyAudit } from '@/features/content/family'

const family = ref<FamilyOverview | null>(null)
const busy = ref(false)
const error = ref('')
const familyName = ref('')
const displayName = ref('')
const token = ref('')
const preview = ref<{ family_name: string; expires_at: string } | null>(null)
const invitation = ref<{ id: string; token: string; expires_at: string } | null>(null)
const logs = ref<FamilyAudit[]>([])
const manager = computed(() => family.value?.role === 'owner' || family.value?.role === 'admin')
let generation = 0
let alive = true

async function load() {
  const current = ++generation
  try {
    const result = await api.family()
    if (!alive || current !== generation) return
    family.value = result
    familyName.value = result.name
    displayName.value = result.display_name
    logs.value = []
  } catch (reason) { if (alive && current === generation) error.value = errorText(reason) }
}
async function run(work: () => Promise<unknown>, changesFamily = false) {
  if (busy.value) return
  busy.value = true
  error.value = ''
  try {
    await work()
    if (!alive) return
    if (changesFamily) {
      recordStore.reset()
      invitation.value = null
      preview.value = null
      token.value = ''
      await recordStore.load()
    }
    await load()
  } catch (reason) { if (alive) error.value = errorText(reason) }
  finally { if (alive) busy.value = false }
}
async function checkInvite() {
  preview.value = null
  await run(async () => { preview.value = await api.previewInvite(token.value.trim()) })
}
function confirm(title: string, content: string, work: () => Promise<unknown>, changesFamily = false) {
  uni.showModal({ title, content, success: (result) => { if (result.confirm && alive) void run(work, changesFamily) } })
}
function copyInvite() { if (invitation.value) uni.setClipboardData({ data: invitation.value.token }) }
async function showAudit() {
  if (busy.value) return
  busy.value = true
  try { logs.value = await api.familyAudit() } catch (reason) { error.value = errorText(reason) }
  finally { busy.value = false }
}
onLoad((query) => { if (query?.invite) token.value = String(query.invite) })
onShow(() => void load())
onBeforeUnmount(() => { alive = false; generation++ })
onShareAppMessage(() => ({ title: '一起记录宝宝的成长', path: `/pages/family/index?invite=${encodeURIComponent(invitation.value?.token || '')}` }))
</script>

<template>
  <view class="page">
    <text class="title">我的家庭</text>
    <text class="hint">和家人一起记录，切换家庭后只查看该家庭的数据。</text>
    <view v-if="error" class="error"><text>{{ error }}</text><button :disabled="busy" @click="load">重新加载</button></view>
    <text v-if="!family && !error" class="hint">正在加载家庭…</text>
    <template v-if="family">
      <view class="card">
        <text class="subtitle">{{ family.name }} · {{ roleName(family.role) }}</text>
        <text class="hint">家人看到的称呼</text>
        <input v-model="displayName" maxlength="30" placeholder="例如：妈妈、爸爸、奶奶" :disabled="busy" />
        <button :disabled="busy || !displayName.trim()" @click="run(() => api.familyProfile(displayName.trim()))">保存称呼</button>
        <template v-if="manager">
          <text class="hint">家庭名称</text>
          <input v-model="familyName" maxlength="30" :disabled="busy" />
          <button :disabled="busy || !familyName.trim()" @click="run(() => api.renameFamily(familyName.trim()))">保存家庭名称</button>
        </template>
      </view>
      <view v-if="family.families.length > 1" class="card">
        <text class="subtitle">切换家庭</text>
        <button v-for="item in family.families" :key="item.id" :disabled="busy || item.id === family.id" @click="run(() => api.switchFamily(item.id), true)">{{ item.name }}{{ item.id === family.id ? '（当前）' : '' }}</button>
      </view>
      <view class="card">
        <text class="subtitle">家庭成员</text>
        <view v-for="member in family.members" :key="member.user_id" class="member">
          <text>{{ member.name }} · {{ roleName(member.role) }}{{ member.user_id === family.user_id ? '（我）' : '' }}</text>
          <view v-if="family.role === 'owner' && member.user_id !== family.user_id" class="actions">
            <button :disabled="busy" @click="run(() => api.familyRole(member.user_id, member.role === 'admin' ? 'member' : 'admin'))">{{ member.role === 'admin' ? '设为家人' : '设为管理员' }}</button>
            <button :disabled="busy" @click="confirm('转交家庭管理？', '对方将成为创建者，你会成为管理员。', () => api.transferFamily(member.user_id))">转交管理</button>
          </view>
          <button v-if="member.user_id !== family.user_id && canRemoveMember(family.role, member.role)" class="danger" :disabled="busy" @click="confirm('移除这位成员？', '对方将无法继续查看这个家庭，共同记录会保留。', () => api.removeFamilyMember(member.user_id))">移除成员</button>
        </view>
        <button v-if="family.role !== 'owner'" class="danger" :disabled="busy" @click="confirm('退出这个家庭？', '共同记录会保留给家人，你将回到自己的其他家庭。', () => api.removeFamilyMember(family!.user_id), true)">退出家庭</button>
      </view>
      <view v-if="manager" class="card">
        <text class="subtitle">邀请家人</text>
        <text class="hint">邀请 48 小时有效，只能使用一次。新加入的家人可以共同查看和记录。</text>
        <button :disabled="busy" @click="run(async () => { invitation = await api.createInvite() })">创建邀请</button>
        <template v-if="invitation">
          <button @click="copyInvite">复制邀请码</button>
          <!-- #ifdef MP-WEIXIN -->
          <button open-type="share">发送邀请给家人</button>
          <!-- #endif -->
        </template>
        <view v-for="item in family.invites" :key="item.id" class="member">
          <text class="hint">有效至 {{ new Date(item.expires_at).toLocaleString('zh-CN') }}</text>
          <button :disabled="busy" @click="run(async () => { await api.revokeInvite(item.id); if (invitation?.id === item.id) invitation = null })">撤销邀请</button>
        </view>
      </view>
      <view class="card">
        <text class="subtitle">加入家人的家庭</text>
        <input v-model="token" maxlength="100" placeholder="粘贴家人发来的邀请码" :disabled="busy" @input="preview = null" />
        <button :disabled="busy || !token.trim()" @click="checkInvite">查看邀请</button>
        <template v-if="preview">
          <text class="hint">将以家人身份加入「{{ preview.family_name }}」。原家庭和数据会保留。</text>
          <button :disabled="busy" @click="run(() => api.acceptInvite(token.trim()), true)">确认加入</button>
        </template>
      </view>
      <view v-if="manager" class="card">
        <button :disabled="busy" @click="showAudit">查看家庭管理记录</button>
        <text v-for="item in logs" :key="item.id" class="hint">{{ new Date(item.created_at).toLocaleString('zh-CN') }} · {{ auditName(item.action) }}</text>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page { padding: 20px 18px calc(32px + env(safe-area-inset-bottom)); color: var(--db-text); }
.title { display: block; font-size: 24px; font-weight: 700; }
.subtitle { display: block; font-size: 18px; font-weight: 700; }
.hint { display: block; margin: 10px 0; font-size: 15px; color: var(--db-muted); line-height: 1.65; }
.card { margin-top: 18px; padding: 18px; border: 1px solid var(--db-border); border-radius: 18px; background: var(--db-surface); }
input { min-height: 48px; margin: 10px 0; padding: 10px; border-radius: 10px; background: var(--db-soft); font-size: 16px; }
button { margin-top: 10px; min-height: 48px; padding: 10px 14px; border-radius: 12px; background: var(--db-soft); color: var(--db-primary); font-size: 16px; line-height: 1.6; }
.member { padding: 14px 0; border-bottom: 1px solid var(--db-border); }
.actions { display: flex; flex-wrap: wrap; gap: 8px; }
.danger, .error { color: #9a4c3e; }
.error { margin-top: 12px; padding: 12px; border-radius: 12px; background: #fff0ec; }
</style>
