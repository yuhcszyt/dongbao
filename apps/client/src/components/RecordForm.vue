<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import {
  RECORD_TYPES,
  dateTimeParts,
  nowParts,
  toIsoDateTime,
  validatePayload,
  type Payload,
  type RecordInput,
  type RecordType,
} from '@/features/record/domain'

const props = withDefaults(
  defineProps<{
    initial?: Partial<RecordInput> | null
    submitting?: boolean
    submitText?: string
    lockType?: boolean
  }>(),
  { initial: null, submitting: false, submitText: '保存记录', lockType: false },
)

const emit = defineEmits<{
  submit: [input: RecordInput]
}>()

type FormValues = {
  feeding_type: string
  amount_ml: string
  food_name: string
  amount_text: string
  duration_minutes: string
  color: string
  consistency: string
  content: string
  description: string
  height_cm: string
  weight_kg: string
  vaccine_name: string
  dose: string
  medication_name: string
  dosage_text: string
  vitamin_dose: string
  title: string
  details: string
}

const emptyValues = (): FormValues => ({
  feeding_type: 'formula',
  amount_ml: '',
  food_name: '',
  amount_text: '',
  duration_minutes: '',
  color: '',
  consistency: '',
  content: '',
  description: '',
  height_cm: '',
  weight_kg: '',
  vaccine_name: '',
  dose: '',
  medication_name: '',
  dosage_text: '',
  vitamin_dose: '',
  title: '',
  details: '',
})

const recordType = ref<RecordType>('feeding')
const date = ref(nowParts().date)
const time = ref(nowParts().time)
const note = ref('')
const error = ref('')
const values = reactive<FormValues>(emptyValues())

const textValue = (payload: Record<string, unknown>, key: keyof FormValues) => {
  const value = payload[key]
  return value === undefined || value === null ? '' : String(value)
}

watch(
  () => props.initial,
  (initial) => {
    const payload: Record<string, unknown> = initial?.payload ?? {}
    recordType.value = initial?.record_type ?? (typeof payload.kind === 'string' ? payload.kind as RecordType : 'feeding')
    const parts = dateTimeParts(initial?.occurred_at)
    date.value = parts.date
    time.value = parts.time
    note.value = initial?.note ?? ''
    const fresh = emptyValues()
    for (const key of Object.keys(fresh) as (keyof FormValues)[]) fresh[key] = textValue(payload, key) || fresh[key]
    if (recordType.value === 'vaccine') fresh.vaccine_name = String(payload.name ?? '')
    if (recordType.value === 'medication') fresh.medication_name = String(payload.name ?? '')
    if (recordType.value === 'vitamin_ad') fresh.vitamin_dose = String(payload.dose_text ?? '')
    Object.assign(values, fresh)
    error.value = ''
  },
  { immediate: true, deep: true },
)

const optionalNumber = (value: string) => value.trim() === '' ? null : Number(value)

function buildPayload(): Payload {
  switch (recordType.value) {
    case 'feeding':
      return { kind: 'feeding', feeding_type: values.feeding_type, amount_ml: optionalNumber(values.amount_ml) }
    case 'complementary_food':
      return { kind: 'complementary_food', food_name: values.food_name.trim(), amount_text: values.amount_text.trim() || null }
    case 'sleep':
      return { kind: 'sleep', start_at: null, end_at: null, duration_minutes: optionalNumber(values.duration_minutes) }
    case 'stool':
      return { kind: 'stool', color: values.color.trim(), consistency: values.consistency.trim() }
    case 'diaper':
      return { kind: 'diaper', content: values.content }
    case 'crying':
      return { kind: 'crying', duration_minutes: optionalNumber(values.duration_minutes), description: values.description.trim() || null }
    case 'growth':
      return { kind: 'growth', height_cm: optionalNumber(values.height_cm), weight_kg: optionalNumber(values.weight_kg) }
    case 'vaccine':
      return { kind: 'vaccine', name: values.vaccine_name.trim(), dose: values.dose.trim() || null }
    case 'vitamin_ad':
      return { kind: 'vitamin_ad', dose_text: values.vitamin_dose.trim() || null }
    case 'medication':
      return { kind: 'medication', name: values.medication_name.trim(), dosage_text: values.dosage_text.trim() || null }
    case 'custom':
      return { kind: 'custom', title: values.title.trim(), details: values.details.trim() || null }
  }
}

const eventIndex = (event: unknown) => {
  const value = (event as { detail?: { value?: string | number } })?.detail?.value
  return Number(value ?? 0)
}
const eventValue = (event: unknown) => String((event as { detail?: { value?: string } })?.detail?.value ?? '')

const feedingOptions = [
  { label: '配方奶', value: 'formula' },
  { label: '母乳', value: 'breast' },
  { label: '未注明', value: 'unknown' },
]
const stoolColors = ['黄色', '绿色', '棕色', '黑色', '其他']
const stoolConsistency = ['稀便', '软便', '成形', '干硬', '其他']

const optionLabel = (options: readonly { label: string; value: string }[], current: string) =>
  options.find((item) => item.value === current)?.label ?? options[0]?.label ?? ''

function submit() {
  error.value = ''
  const payload = buildPayload()
  const validation = validatePayload(recordType.value, payload)
  if (validation) {
    error.value = validation
    return
  }
  emit('submit', {
    record_type: recordType.value,
    occurred_at: toIsoDateTime(date.value, time.value),
    payload,
    note: note.value.trim() || null,
  })
}
</script>

<template>
  <view class="record-form">
    <text class="field-title">记录类型</text>
    <view class="type-grid">
      <button
        v-for="item in RECORD_TYPES"
        :key="item.value"
        class="type-option"
        :class="{ selected: recordType === item.value, 'is-disabled': lockType }"
        :disabled="lockType"
        @click="recordType = item.value"
      >
        <text class="type-icon">{{ item.icon }}</text>
        <text>{{ item.label }}</text>
      </button>
    </view>

    <view v-if="recordType === 'feeding'" class="fields">
      <label>
        <text class="field-title">喂养方式</text>
        <picker :range="feedingOptions" range-key="label" @change="values.feeding_type = feedingOptions[eventIndex($event)]?.value || 'formula'">
          <view class="picker-field">{{ optionLabel(feedingOptions, values.feeding_type) }} <text>⌄</text></view>
        </picker>
      </label>
      <label>
        <text class="field-title">奶量（ml，选填）</text>
        <input v-model="values.amount_ml" class="input" type="number" placeholder="例如 180" maxlength="4" />
      </label>
    </view>

    <view v-else-if="recordType === 'complementary_food'" class="fields">
      <label>
        <text class="field-title">吃了什么</text>
        <input v-model="values.food_name" class="input" placeholder="例如 米糊" maxlength="40" />
      </label>
      <label>
        <text class="field-title">份量（选填）</text>
        <input v-model="values.amount_text" class="input" placeholder="例如 半碗、3 勺" maxlength="30" />
      </label>
    </view>

    <view v-else-if="recordType === 'sleep'" class="fields">
      <label>
        <text class="field-title">睡眠时长（分钟）</text>
        <input v-model="values.duration_minutes" class="input" type="number" placeholder="例如 90" maxlength="4" />
      </label>
    </view>

    <view v-else-if="recordType === 'stool'" class="fields two-columns">
      <label>
        <text class="field-title">颜色</text>
        <picker :range="stoolColors" @change="values.color = stoolColors[eventIndex($event)] || ''">
          <view class="picker-field">{{ values.color || '请选择' }} <text>⌄</text></view>
        </picker>
      </label>
      <label>
        <text class="field-title">性状</text>
        <picker :range="stoolConsistency" @change="values.consistency = stoolConsistency[eventIndex($event)] || ''">
          <view class="picker-field">{{ values.consistency || '请选择' }} <text>⌄</text></view>
        </picker>
      </label>
    </view>

    <view v-else-if="recordType === 'diaper'" class="fields">
      <label>
        <text class="field-title">记录内容</text>
        <input v-model="values.content" class="input" placeholder="例如 更换尿布" maxlength="100" />
      </label>
    </view>

    <view v-else-if="recordType === 'crying'" class="fields">
      <label>
        <text class="field-title">持续时长（分钟，选填）</text>
        <input v-model="values.duration_minutes" class="input" type="number" placeholder="例如 10" maxlength="4" />
      </label>
      <label>
        <text class="field-title">描述（选填）</text>
        <textarea v-model="values.description" class="textarea" placeholder="记录当时的情况" maxlength="200" />
      </label>
    </view>

    <view v-else-if="recordType === 'growth'" class="fields two-columns">
      <label>
        <text class="field-title">身高（cm）</text>
        <input v-model="values.height_cm" class="input" type="digit" placeholder="选填" maxlength="5" />
      </label>
      <label>
        <text class="field-title">体重（kg）</text>
        <input v-model="values.weight_kg" class="input" type="digit" placeholder="选填" maxlength="5" />
      </label>
    </view>

    <view v-else-if="recordType === 'vaccine'" class="fields">
      <label>
        <text class="field-title">疫苗名称</text>
        <input v-model="values.vaccine_name" class="input" placeholder="填写疫苗名称" maxlength="60" />
      </label>
      <label>
        <text class="field-title">剂次（选填）</text>
        <input v-model="values.dose" class="input" placeholder="例如 第 2 剂" maxlength="30" />
      </label>
    </view>

    <view v-else-if="recordType === 'vitamin_ad'" class="fields">
      <label>
        <text class="field-title">剂量（选填）</text>
        <input v-model="values.vitamin_dose" class="input" placeholder="例如 1 滴" maxlength="40" />
      </label>
      <text class="field-hint">点保存即可记一笔「今天吃过维生素AD」。</text>
    </view>

    <view v-else-if="recordType === 'medication'" class="fields">
      <label>
        <text class="field-title">药品名称</text>
        <input v-model="values.medication_name" class="input" placeholder="填写药品名称" maxlength="60" />
      </label>
      <label>
        <text class="field-title">剂量（选填）</text>
        <input v-model="values.dosage_text" class="input" placeholder="请按医嘱原样填写" maxlength="60" />
      </label>
    </view>

    <view v-else class="fields">
      <label>
        <text class="field-title">标题</text>
        <input v-model="values.title" class="input" placeholder="这次想记录什么" maxlength="50" />
      </label>
      <label>
        <text class="field-title">详情（选填）</text>
        <textarea v-model="values.details" class="textarea" placeholder="补充一些细节" maxlength="300" />
      </label>
    </view>

    <view class="fields two-columns">
      <label>
        <text class="field-title">日期</text>
        <picker mode="date" :value="date" @change="date = eventValue($event)">
          <view class="picker-field">{{ date }}</view>
        </picker>
      </label>
      <label>
        <text class="field-title">时间</text>
        <picker mode="time" :value="time" @change="time = eventValue($event)">
          <view class="picker-field">{{ time }}</view>
        </picker>
      </label>
    </view>

    <label>
      <text class="field-title">备注（选填）</text>
      <textarea v-model="note" class="textarea note" placeholder="还有什么想记下的" maxlength="300" />
    </label>

    <view v-if="error" class="error" role="alert">{{ error }}</view>
    <button class="submit" :class="{ 'is-disabled': submitting }" :disabled="submitting" @click="submit">
      {{ submitting ? '正在保存…' : submitText }}
    </button>
  </view>
</template>

<style scoped>
.record-form { padding-bottom: 12px; }
.field-title { display: block; margin: 17px 0 7px; color: #385d6b; font-size: 16px; font-weight: 600; }
.field-hint { display: block; margin-top: 8px; color: #71858b; font-size: 13px; line-height: 1.5; }

.type-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 7px; }
.type-option { min-height: 65px; padding: 7px 2px; border: 1px solid #e0e9e9; border-radius: 12px; background: #fff; color: #526c74; font-size: 12px; line-height: 1.25; }
.type-option.selected { border-color: #328da9; background: #edf6f8; color: #236f87; font-weight: 700; }
.type-option.is-disabled:not(.selected) { opacity: .42; }
.type-icon { display: block; margin-bottom: 3px; font-size: 20px; }
.fields { display: grid; grid-template-columns: 1fr; gap: 3px 12px; }
.two-columns { grid-template-columns: 1fr 1fr; }
.input, .picker-field, .textarea { width: 100%; min-height: 52px; border: 1px solid #dfe8e9; border-radius: 13px; background: #fff; padding: 13px 14px; color: #203f4a; font-size: 17px; }
.picker-field { display: flex; align-items: center; justify-content: space-between; }
.textarea { height: 92px; line-height: 1.6; }
.textarea.note { height: 78px; }
.error { margin-top: 14px; border-radius: 10px; background: #fff0ec; padding: 10px 12px; color: #a04e3d; font-size: 14px; }
.submit { width: 100%; min-height: 54px; margin-top: 20px; border-radius: 15px; background: #328da9; color: #fff; font-size: 18px; font-weight: 700; }
.submit.is-disabled { opacity: .55; }
@media (max-width: 360px) {
  .type-grid { grid-template-columns: repeat(4, 1fr); }
}
</style>
