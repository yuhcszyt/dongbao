<script setup lang="ts">
/**
 * 宝宝档案表单：建档与编辑共用同一套字段与校验（票 07 起编辑走这里，规则不会两边打架）。
 * 校验先在本地挡住并给中文提示，不把「必填项缺失」当成一次失败的提交。
 */
import { reactive, ref } from 'vue'
import { nowParts, pickerValue, validateBabyProfile, type Baby } from '@/features/record/domain'

const props = withDefaults(
  defineProps<{
    initial?: Partial<Pick<Baby, 'nickname' | 'birth_date' | 'gender'>> | null
    submitting?: boolean
    submitText?: string
    /** 页面带上来的错误（保存失败 / 需要重试）；本地校验错误由本组件自己显示。 */
    error?: string
    retryable?: boolean
  }>(),
  { initial: null, submitting: false, submitText: '保存', error: '', retryable: false },
)

const emit = defineEmits<{
  submit: [input: Pick<Baby, 'nickname' | 'birth_date' | 'gender'>]
  retry: []
}>()

const profile = reactive({
  nickname: props.initial?.nickname ?? '',
  birth_date: props.initial?.birth_date ?? '',
  gender: (props.initial?.gender ?? 'unknown') as Baby['gender'],
})
const localError = ref('')
const today = nowParts().date

function submit() {
  // 建档与编辑共用 domain 里那一条校验，本地先挡住，不让「必填项缺失」走成一趟失败请求。
  const problem = validateBabyProfile(profile)
  if (problem) {
    localError.value = problem
    return
  }
  localError.value = ''
  emit('submit', { nickname: profile.nickname.trim(), birth_date: profile.birth_date, gender: profile.gender })
}
</script>

<template>
  <view class="profile-form">
    <label><text class="label">宝宝昵称</text><input v-model="profile.nickname" class="input" maxlength="30" placeholder="例如 安安" /></label>
    <label><text class="label">生日</text><picker mode="date" :end="today" @change="profile.birth_date = pickerValue($event)"><view class="input">{{ profile.birth_date || '请选择生日' }}</view></picker></label>
    <text class="label">性别</text>
    <view class="gender-row">
      <button v-for="item in [{ v: 'male', t: '男宝' }, { v: 'female', t: '女宝' }, { v: 'unknown', t: '暂不填' }]" :key="item.v" :class="{ selected: profile.gender === item.v }" @click="profile.gender = item.v as Baby['gender']">{{ item.t }}</button>
    </view>
    <view v-if="localError || props.error" class="error">
      <text>{{ localError || props.error }}</text>
      <button v-if="props.retryable" class="retry" @click="emit('retry')">重试</button>
    </view>
    <button class="primary" :disabled="submitting" @click="submit">{{ submitting ? '正在保存…' : props.submitText }}</button>
  </view>
</template>

<style scoped>
.profile-form { display: block; }
.label { display: block; margin: 20px 0 8px; font-weight: 650; }
.input { display: block; min-height: 54px; width: 100%; border: 1px solid #dfe7e7; border-radius: 14px; background: white; padding: 14px; font-size: 17px; color: #203f4a; }
.gender-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 9px; }
.gender-row button { min-height: 48px; border: 1px solid #dde7e8; border-radius: 13px; background: white; color: #49646d; }
.selected { border-color: #328da9 !important; background: #edf6f8 !important; color: #236f87 !important; font-weight: 700; }
.error { margin: 12px 0; border-radius: 12px; background: #fff0ec; padding: 12px; color: #9a4c3e; }
.error .retry { margin-top: 10px; min-height: 44px; border-radius: 10px; background: #fff; color: #9a4c3e; font-weight: 700; }
.primary { width: 100%; min-height: 54px; margin-top: 24px; border-radius: 15px; background: #328da9; color: white; font-size: 17px; font-weight: 750; }
</style>
