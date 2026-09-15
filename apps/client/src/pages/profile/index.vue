<script setup lang="ts">
import { ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AccountGone from '@/components/AccountGone.vue'
import ProfileForm from '@/components/ProfileForm.vue'
import { ageText, genderText, orPending, type Baby } from '@/features/record/domain'
import { recordStore } from '@/features/record/store'

const { state } = recordStore
const formOpen = ref(false)
/** 注销的二次确认：误触只会关掉这个浮层，不会碰到服务端。 */
const confirmingDelete = ref(false)

/**
 * 建档与编辑是同一条路：`recordStore.saveBaby` 按「家里有没有宝宝」决定调哪个接口，
 * 校验与字段来自同一个 `ProfileForm`，所以两边的规则不会漂移。
 * 保存失败时这里什么都不做——中文提示由 store 给出，表单与输入都留在原地，可以直接重试。
 */
async function save(input: Pick<Baby, 'nickname' | 'birth_date' | 'gender'>) {
  const creating = !state.baby
  if (!(await recordStore.saveBaby(input))) return
  formOpen.value = false
  uni.showToast({ title: creating ? '建档完成' : '已保存', icon: 'success' })
}

onShow(() => void recordStore.load())

/**
 * 二次确认之后才真正调注销接口；失败时只关浮层——中文提示由 store 给出，
 * 本地状态与登录态都原样留着，可以直接再试。
 */
async function confirmDelete() {
  const done = await recordStore.deleteAccount()
  confirmingDelete.value = false
  if (done) uni.showToast({ title: '账号已注销', icon: 'success' })
}
</script>

<template>
  <view class="page">
    <view v-if="state.loading" class="state">正在加载…</view>

    <AccountGone v-else-if="state.accountDeleted" />

    <view v-else-if="!state.baby" class="onboarding">
      <view class="baby-mark">👶🏻</view>
      <text class="eyebrow">欢迎来到懂宝</text>
      <text class="page-title">先认识一下宝宝</text>
      <text class="muted">只需三项，之后就可以开始记录。</text>
      <ProfileForm :submitting="state.saving" submit-text="创建宝宝档案" :error="state.error" :retryable="state.retryable" @submit="save" @retry="recordStore.retrySession" />
    </view>

    <template v-else>
      <view class="head">
        <view class="avatar">👶🏻</view>
        <text class="page-title">{{ orPending(state.baby.nickname) }}</text>
        <text class="muted">{{ ageText(state.baby.birth_date) }} · {{ genderText(state.baby.gender) }}</text>
      </view>

      <view class="card">
        <view class="card-head"><text class="card-title">基础信息</text><button class="link" @click="formOpen = true">编辑</button></view>
        <view class="row"><text class="row-key">昵称</text><text class="row-value">{{ orPending(state.baby.nickname) }}</text></view>
        <view class="row"><text class="row-key">生日</text><text class="row-value">{{ orPending(state.baby.birth_date) }}</text></view>
        <view class="row"><text class="row-key">性别</text><text class="row-value">{{ genderText(state.baby.gender) }}</text></view>
      </view>

      <view v-if="state.error" class="error"><text>{{ state.error }}</text><button v-if="state.retryable" class="retry" @click="recordStore.retrySession">重试</button></view>
    </template>

    <view v-if="!state.loading && !state.accountDeleted" class="danger">
      <text class="danger-title">注销账号</text>
      <text class="muted">注销后宝宝档案、全部记录、语音和照片会被永久删除，且不可恢复。</text>
      <button class="danger-button" @click="confirmingDelete = true">注销账号</button>
    </view>

    <view v-if="confirmingDelete" class="overlay" @click.self="confirmingDelete = false">
      <view class="sheet">
        <text class="card-title">确认注销账号？</text>
        <text class="muted">确认后会立即删除，且不可恢复：</text>
        <view class="danger-list">
          <text>· 宝宝档案（昵称、生日、性别）</text>
          <text>· 全部记录（喂奶、辅食、睡眠、排便、尿布等十类，含手动补记）</text>
          <text>· 已上传的语音和照片</text>
        </view>
        <button class="primary delete" :disabled="state.saving" @click="confirmDelete">{{ state.saving ? '正在注销…' : '确认注销，永久删除' }}</button>
        <button class="cancel" :disabled="state.saving" @click="confirmingDelete = false">取消</button>
      </view>
    </view>

    <view v-if="formOpen && state.baby" class="overlay" @click.self="formOpen = false">
      <view class="sheet">
        <view class="sheet-head"><text class="card-title">编辑宝宝档案</text><button aria-label="关闭" @click="formOpen = false">×</button></view>
        <ProfileForm :key="state.baby.updated_at ?? state.baby.id" :initial="state.baby" :submitting="state.saving" submit-text="保存修改" :error="state.error" :retryable="state.retryable" @submit="save" @retry="recordStore.retrySession" />
      </view>
    </view>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 22px 18px 120px; background: #fbfaf7; color: #203f4a; }
.state { padding: 80px 20px; text-align: center; color: #70858c; }
.onboarding { max-width: 520px; margin: 0 auto; padding-top: 34px; }
.baby-mark, .avatar { display: grid; place-items: center; background: #f2e8d8; border-radius: 50%; }
.baby-mark { width: 82px; height: 82px; margin: 0 auto 22px; font-size: 45px; }
.avatar { width: 76px; height: 76px; margin: 0 auto; font-size: 44px; }
.head { text-align: center; margin-bottom: 20px; }
.eyebrow, .page-title, .muted { display: block; }
.eyebrow { color: #328da9; font-size: 13px; font-weight: 750; letter-spacing: 1px; }
.head .page-title { margin: 10px 0 4px; }
.page-title { margin: 5px 0; font-size: 27px; font-weight: 800; line-height: 1.25; }
.muted { color: #71858b; font-size: 14px; line-height: 1.55; }
.card { max-width: 760px; margin: 18px auto; border: 1px solid #e6eceb; border-radius: 19px; background: white; box-shadow: 0 7px 24px rgba(43, 75, 83, .06); padding: 18px; }
.card-head { display: flex; align-items: center; justify-content: space-between; }
.card-title { font-size: 20px; font-weight: 800; }
.link { min-height: 48px; padding: 0 8px; background: transparent; color: #2d8098; font-size: 16px; }
.row { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 54px; border-bottom: 1px solid #eef2f1; }
.row:last-child { border-bottom: 0; }
.row-key { color: #71858b; font-size: 16px; }
.row-value { font-size: 17px; font-weight: 700; }
.error { max-width: 760px; margin: 12px auto; border-radius: 12px; background: #fff0ec; padding: 12px; color: #9a4c3e; }
.error .retry { margin-top: 10px; min-height: 44px; border-radius: 10px; background: #fff; color: #9a4c3e; font-weight: 700; }
.overlay { position: fixed; z-index: 20; inset: 0; display: flex; align-items: flex-end; justify-content: center; background: rgba(25, 47, 52, .46); }
.sheet { width: 100%; max-width: 720px; max-height: 92vh; overflow-y: auto; border-radius: 24px 24px 0 0; background: #fbfaf7; padding: 21px 18px calc(22px + env(safe-area-inset-bottom)); }
.sheet-head { display: flex; align-items: center; justify-content: space-between; }
.sheet-head button { width: 48px; height: 48px; border-radius: 50%; background: #eef2f1; font-size: 27px; }
.danger { max-width: 760px; margin: 26px auto 0; border: 1px solid #f0dcd6; border-radius: 19px; background: #fff8f6; padding: 17px; }
.danger-title { display: block; font-size: 17px; font-weight: 800; }
.danger .muted { margin-top: 5px; }
.danger-button { width: 100%; min-height: 52px; margin-top: 12px; border-radius: 14px; background: #fff; color: #b04a35; font-size: 16px; font-weight: 700; border: 1px solid #eccfc7; }
.danger-list { display: block; margin: 12px 0 4px; color: #7c5b53; font-size: 15px; line-height: 1.7; }
.danger-list text { display: block; }
.sheet .delete { margin-top: 16px; background: #c0503a; }
.sheet .cancel { width: 100%; min-height: 50px; margin-top: 10px; border-radius: 14px; background: white; color: #566d75; }
</style>
