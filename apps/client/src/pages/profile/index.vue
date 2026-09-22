<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AccountGone from '@/components/AccountGone.vue'
import ProfileForm from '@/components/ProfileForm.vue'
import { ageText, babyDisplayName, genderText, orPending, type Baby } from '@/features/record/domain'
import { recordStore } from '@/features/record/store'

const { state } = recordStore
const formOpen = ref(false)
const logoutOpen = ref(false)
const deleteStep = ref<0 | 1 | 2>(0)
const deleteWord = ref('')
const babyName = computed(() => babyDisplayName(state.baby?.nickname))

async function save(input: Pick<Baby, 'nickname' | 'birth_date' | 'gender'>) {
  if (!(await recordStore.saveBaby(input))) return
  formOpen.value = false
  uni.showToast({ title: '已保存', icon: 'success' })
}

function openStats() {
  uni.navigateTo({ url: '/pages/stats/index' })
}

function openRecords() {
  uni.switchTab({ url: '/pages/record/index' })
}

function openFavorites() {
  uni.navigateTo({ url: '/pages/favorites/index' })
}

function confirmLogout() {
  logoutOpen.value = false
  recordStore.logoutSession()
  uni.showToast({ title: '已退出登录', icon: 'none' })
  // 清凭证后重新拉会话：会静默重登（开发码 / 微信码）
  void recordStore.load()
}

async function confirmDelete() {
  if (deleteWord.value.trim() !== '注销') {
    uni.showToast({ title: '请输入「注销」', icon: 'none' })
    return
  }
  const done = await recordStore.deleteAccount()
  if (!done) {
    uni.showToast({ title: state.error || '注销失败，请稍后重试', icon: 'none' })
    return
  }
  deleteStep.value = 0
  deleteWord.value = ''
  uni.showToast({ title: '账号已注销', icon: 'success' })
}

onShow(() => void recordStore.load())
</script>

<template>
  <view class="page">
    <view v-if="state.loading" class="state">正在加载…</view>
    <AccountGone v-else-if="state.accountDeleted" />

    <template v-else>
      <view class="head">
        <view class="avatar">👶🏻</view>
        <text class="page-title">{{ babyName }}</text>
        <text class="muted">{{ ageText(state.baby?.birth_date) }} · {{ genderText(state.baby?.gender ?? 'unknown') }}</text>
      </view>

      <view class="card">
        <view class="card-head">
          <text class="card-title">宝宝档案</text>
          <button class="link" @click="formOpen = true">编辑</button>
        </view>
        <view class="row"><text class="row-key">昵称</text><text class="row-value">{{ orPending(state.baby?.nickname) }}</text></view>
        <view class="row"><text class="row-key">生日</text><text class="row-value">{{ orPending(state.baby?.birth_date) }}</text></view>
        <view class="row"><text class="row-key">性别</text><text class="row-value">{{ genderText(state.baby?.gender ?? 'unknown') }}</text></view>
      </view>

      <view class="card">
        <button class="menu-row" @click="openStats"><text>数据统计</text><text class="chev">›</text></button>
        <button class="menu-row" @click="openRecords"><text>成长时间线</text><text class="chev">›</text></button>
        <button class="menu-row" @click="openFavorites"><text>我的收藏</text><text class="chev">›</text></button>
      </view>

      <view class="card account">
        <text class="card-title">账号</text>
        <button class="menu-row" @click="logoutOpen = true"><text>退出登录</text><text class="chev">›</text></button>
        <button class="menu-row danger" @click="deleteStep = 1"><text>注销账号</text><text class="chev">›</text></button>
        <text class="account-note">退出登录不会删除宝宝档案和数据；注销账号属于不可逆操作。</text>
      </view>

      <view v-if="state.error" class="error">
        <text>{{ state.error }}</text>
        <button v-if="state.retryable" class="retry" @click="() => recordStore.retrySession()">重试</button>
      </view>
    </template>

    <view v-if="logoutOpen" class="overlay" @click="logoutOpen = false">
      <view class="sheet" @click.stop>
        <view class="sheet-head"><text class="card-title">退出登录</text><button @click="logoutOpen = false">×</button></view>
        <text class="muted">退出后将结束当前账号在本机的登录状态。</text>
        <view class="warn">宝宝档案和云端数据不会因为退出登录而删除。</view>
        <button class="primary" @click="confirmLogout">确认退出</button>
        <button class="cancel" @click="logoutOpen = false">取消</button>
      </view>
    </view>

    <view v-if="deleteStep === 1" class="overlay" @click="deleteStep = 0">
      <view class="sheet" @click.stop>
        <view class="sheet-head"><text class="card-title">注销账号</text><button @click="deleteStep = 0">×</button></view>
        <text class="muted">注销后将无法继续使用当前账号。</text>
        <view class="warn">会永久删除宝宝档案、全部记录、语音和照片，且不可恢复。</view>
        <button class="outline danger-btn" @click="deleteStep = 2">继续注销</button>
        <button class="cancel" @click="deleteStep = 0">暂不注销</button>
      </view>
    </view>

    <view v-if="deleteStep === 2" class="overlay" @click="deleteStep = 0">
      <view class="sheet" @click.stop>
        <view class="sheet-head"><text class="card-title">最后确认</text><button @click="deleteStep = 0">×</button></view>
        <text class="muted">请输入「注销」确认你理解此操作会终止当前账号。</text>
        <input v-model="deleteWord" class="confirm-word" maxlength="2" placeholder="请输入：注销" />
        <button class="outline danger-btn" :disabled="state.saving" @click="confirmDelete">
          {{ state.saving ? '正在注销…' : '确认申请注销' }}
        </button>
        <button class="cancel" :disabled="state.saving" @click="deleteStep = 0">取消</button>
      </view>
    </view>

    <view v-if="formOpen" class="overlay" @click="formOpen = false">
      <view class="sheet" @click.stop>
        <view class="sheet-head"><text class="card-title">编辑宝宝档案</text><button @click="formOpen = false">×</button></view>
        <ProfileForm
          :key="state.baby?.updated_at ?? state.baby?.id ?? 'new'"
          :initial="state.baby ?? { nickname: '宝宝', birth_date: '', gender: 'unknown' }"
          :submitting="state.saving"
          submit-text="保存档案"
          :error="state.error"
          :retryable="state.retryable"
          @submit="save"
          @retry="recordStore.retrySession"
        />
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 22px 18px 120px; background: #fbfaf7; color: #203f4a; }
.state { padding: 80px 20px; text-align: center; color: #70858c; }
.avatar { display: grid; place-items: center; width: 76px; height: 76px; margin: 0 auto; border-radius: 50%; background: #f2e8d8; font-size: 44px; }
.head { text-align: center; margin-bottom: 20px; }
.page-title { display: block; margin: 10px 0 4px; font-size: 27px; font-weight: 800; }
.muted { display: block; color: #71858b; font-size: 14px; line-height: 1.55; }
.card { margin: 14px 0; border: 1px solid #e6eceb; border-radius: 19px; background: white; box-shadow: 0 7px 24px rgba(43, 75, 83, .06); padding: 16px; }
.card-head { display: flex; align-items: center; justify-content: space-between; }
.card-title { font-size: 18px; font-weight: 800; }
.link { min-height: 44px; padding: 0 8px; background: transparent; color: #2d8098; font-size: 15px; }
.row, .menu-row { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 54px; border-bottom: 1px solid #eef2f1; width: 100%; background: transparent; text-align: left; color: inherit; font-size: 15px; padding: 0; }
.row:last-child, .menu-row:last-child { border-bottom: 0; }
.row-key { color: #71858b; }
.row-value { font-weight: 700; }
.chev { color: #91a1a6; }
.account .card-title { display: block; margin-bottom: 4px; }
.account-note { display: block; margin-top: 12px; color: #8b9c9f; font-size: 11px; line-height: 1.7; }
.danger { color: #b86e62; }
.error { margin: 12px 0; border-radius: 12px; background: #fff0ec; padding: 12px; color: #9a4c3e; }
.error .retry { margin-top: 10px; min-height: 44px; border-radius: 10px; background: #fff; color: #9a4c3e; font-weight: 700; }
.overlay { position: fixed; z-index: 20; inset: 0; display: flex; align-items: flex-end; justify-content: center; background: rgba(25, 47, 52, .46); }
.sheet { width: 100%; max-width: 720px; max-height: 92vh; overflow-y: auto; border-radius: 24px 24px 0 0; background: #fbfaf7; padding: 21px 18px calc(22px + env(safe-area-inset-bottom)); }
.sheet-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.sheet-head button { width: 48px; height: 48px; border-radius: 50%; background: #eef2f1; font-size: 27px; }
.warn { margin: 12px 0; border-radius: 12px; background: #fff0df; color: #b88346; padding: 10px 12px; font-size: 13px; line-height: 1.6; }
.primary { width: 100%; min-height: 52px; margin-top: 14px; border-radius: 14px; background: #328da9; color: white; font-weight: 700; }
.outline { width: 100%; min-height: 50px; margin-top: 12px; border-radius: 14px; border: 1px solid #bedbe4; background: white; color: #328da9; }
.danger-btn { color: #b86e62; border-color: #eccfc7; }
.cancel { width: 100%; min-height: 50px; margin-top: 10px; border-radius: 14px; background: white; color: #566d75; }
.confirm-word { width: 100%; margin-top: 12px; padding: 12px; border: 1px solid #e0eaed; border-radius: 10px; background: white; font-size: 16px; }
</style>
