<script setup lang="ts">
/**
 * 宝宝档案表单：建档与编辑共用同一套字段与校验（票 07 起编辑走这里，规则不会两边打架）。
 * 校验先在本地挡住并给中文提示，不把「必填项缺失」当成一次失败的提交。
 */
import { computed, reactive, ref } from 'vue'
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
// 计算属性而不是快照：小程序常驻，过了午夜还能选到当天。
const today = computed(() => nowParts().date)

function submit() {
  // 建档与编辑共用 domain 里那一条校验，本地先挡住，不让「必填项缺失」走成一趟失败请求。
  const problem = validateBabyProfile({
    nickname: profile.nickname,
    birth_date: profile.birth_date,
    gender: profile.gender,
  })
  if (problem) {
    localError.value = problem
    return
  }
  localError.value = ''
  emit('submit', {
    nickname: profile.nickname.trim() || '宝宝',
    birth_date: profile.birth_date,
    gender: profile.gender,
  })
}
</script>

<template>
  <view class="profile-form">
    <label><text class="label">宝宝昵称</text><input v-model="profile.nickname" class="input" maxlength="30" placeholder="例如 安安" /></label>
    <label>
      <text class="label">生日（可稍后补充）</text>
      <picker mode="date" :end="today" @change="profile.birth_date = pickerValue($event)">
        <view class="input">{{ profile.birth_date || '待完善 · 点击选择' }}</view>
      </picker>
      <button v-if="profile.birth_date" class="clear-birth" type="button" @click="profile.birth_date = ''">清除生日</button>
    </label>
    <text class="label">性别</text>
    <!-- 「暂不填」是选项本身的名字（票据 07：性别可选男宝 / 女宝 / 暂不填）；
         只读展示里同一份数据是「未填成的字段」，由 `genderText()` 显示为「待完善」。 -->
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
.input { display: block; min-height: 54px; width: 100%; border: 1px solid var(--db-border); border-radius: 14px; background: var(--db-surface); padding: 14px; font-size: 17px; color: var(--db-text); }
.gender-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 9px; }
.gender-row button { min-height: 48px; border: 1px solid var(--db-border); border-radius: 13px; background: var(--db-surface); color: var(--db-muted); }
.selected { border-color: var(--db-primary) !important; background: var(--db-soft) !important; color: var(--db-primary) !important; font-weight: 700; }
.error { margin: 12px 0; border-radius: 12px; background: #fff0ec; padding: 12px; color: #9a4c3e; }
.error .retry { margin-top: 10px; min-height: 44px; border-radius: 10px; background: var(--db-surface); color: #9a4c3e; font-weight: 700; }
.primary { width: 100%; min-height: 54px; margin-top: 24px; border-radius: 15px; background: var(--db-primary); color: white; font-size: 17px; font-weight: 750; }
.clear-birth { margin-top: 8px; min-height: 44px; padding: 0 8px; background: transparent; color: var(--db-primary); font-size: 14px; text-align: left; }
</style>
