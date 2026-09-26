export const RECORD_TYPES = [
  { value: 'feeding', label: '喂奶', icon: '🍼' },
  { value: 'complementary_food', label: '辅食', icon: '🥣' },
  { value: 'vitamin_ad', label: '维生素AD', icon: '💧' },
  { value: 'sleep', label: '睡眠', icon: '☾' },
  { value: 'stool', label: '排便', icon: '●' },
  { value: 'diaper', label: '尿布', icon: '▱' },
  { value: 'crying', label: '哭闹', icon: '◌' },
  { value: 'growth', label: '身高体重', icon: '↗' },
  { value: 'vaccine', label: '疫苗', icon: '✚' },
  { value: 'medication', label: '用药', icon: '＋' },
  { value: 'custom', label: '自定义', icon: '✎' },
] as const

export type RecordType = (typeof RECORD_TYPES)[number]['value']
export type RecordSource = 'manual' | 'voice' | 'photo' | 'system'
export type Payload = Record<string, unknown> & { kind: RecordType }

export interface Baby {
  id: string
  nickname: string
  birth_date: string | null
  gender: 'male' | 'female' | 'unknown'
  created_at?: string
  updated_at?: string
}

export interface RecordItem {
  created_by_name?: string | null
  id: string
  baby_id: string
  record_type: RecordType
  occurred_at: string
  source: RecordSource
  payload: Payload
  note?: string | null
  transcript?: string | null
  recognition_warnings?: string[]
  media?: MediaAsset[]
  created_at?: string
  updated_at?: string
}

export interface RecordDraft {
  id: string
  status: 'captured' | 'processing' | 'draft' | 'confirmed' | 'saved'
  baby_id: string
  record_type: RecordType | null
  occurred_at: string | null
  payload: Record<string, unknown>
  note?: string | null
  source: 'voice' | 'photo' | 'manual'
  transcript?: string | null
  missing_fields: string[]
  recognition_warnings: string[]
  media_id?: string | null
}

export interface DailySummary {
  feeding_ml: number
  sleep_minutes: number
  diaper_count: number
  complementary_food_count: number
}

export interface RecordInput {
  record_type: RecordType
  occurred_at: string
  payload: Payload
  note: string | null
}

/** 识别没给出类型时，草稿仍要能确认保存：自定义标题兜底，避免表单卡在空标题。 */
export const draftFormInitial = (draft: RecordDraft): Partial<RecordInput> => {
  const recordType = draft.record_type || 'custom'
  const payload: Payload = { kind: recordType, ...draft.payload }
  if (recordType === 'feeding' && !present(payload.feeding_type)) {
    payload.feeding_type = 'unknown'
  }
  if (recordType === 'custom' && !String(payload.title ?? '').trim()) {
    payload.title = draft.source === 'photo' ? '拍照记录' : '语音记录'
    if (!payload.details) {
      const details = (draft.transcript || draft.recognition_warnings[0] || '').trim()
      payload.details = details || null
    }
  }
  return {
    record_type: recordType,
    occurred_at: draft.occurred_at || undefined,
    payload,
    note: draft.note,
  }
}

/** 快速记录：把草稿收成可直接 confirm 的完整输入。 */
export function draftQuickInput(draft: RecordDraft): RecordInput {
  const initial = draftFormInitial(draft)
  const recordType = initial.record_type ?? 'custom'
  const parts = nowParts()
  return {
    record_type: recordType,
    occurred_at: initial.occurred_at || toIsoDateTime(parts.date, parts.time),
    payload: (initial.payload ?? { kind: recordType }) as Payload,
    note: initial.note ?? null,
  }
}

/** 快速确认卡上的一行摘要。 */
export function draftQuickSummary(draft: RecordDraft): string {
  const input = draftQuickInput(draft)
  return recordWhatText({ record_type: input.record_type, payload: input.payload })
}

/** 缺关键字段时不能一键保存，需要展开表单。 */
export function draftNeedsEdit(draft: RecordDraft): boolean {
  const input = draftQuickInput(draft)
  return validatePayload(input.record_type, input.payload) !== null
}

export interface MediaAsset {
  id: string
  baby_id: string
  media_type: 'audio' | 'image'
  mime_type: string
  size_bytes: number
  duration_ms?: number | null
  url: string
}

export const typeMeta = (type: RecordType) =>
  RECORD_TYPES.find((item) => item.value === type) ?? RECORD_TYPES[RECORD_TYPES.length - 1]!

/** 首页「每日记录」快捷四项（原型：喝奶 / 辅食 / 维生素AD / 排便）。 */
export const HOME_QUICK_TYPES = [
  { value: 'feeding' as const, label: '喝奶', icon: '🍼' },
  { value: 'complementary_food' as const, label: '辅食', icon: '🥣' },
  { value: 'vitamin_ad' as const, label: '维生素AD', icon: '💧' },
  { value: 'stool' as const, label: '排便', icon: '💩' },
]

/** @deprecated 用 HOME_QUICK_TYPES；保留别名避免旧引用短暂报错。 */
export const QUICK_RECORD_TYPES = HOME_QUICK_TYPES

/** 只读展示用：未填的档案项统一显示「待完善」，不留空白。 */
export const orPending = (value?: string | null) => (value && value.trim() ? value.trim() : '待完善')

/** 首页等处的宝宝称呼：空昵称按原型显示「宝宝」。 */
export const babyDisplayName = (nickname?: string | null) => {
  const name = nickname?.trim()
  return name || '宝宝'
}

export const genderText = (gender: Baby['gender']) => ({ male: '男宝', female: '女宝', unknown: '待完善' })[gender]

export const nowParts = () => {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString()
  return { date: local.slice(0, 10), time: local.slice(11, 16) }
}

const pad2 = (value: number) => String(value).padStart(2, '0')

/** 记录按家长所在时区归日：时间戳解析不了时返回空串，不落到「今天」。 */
export const dateOf = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString().slice(0, 10)
}

/** 日期加减：用本地零点算，跨月、跨年都对。 */
export const shiftDate = (date: string, days: number) => {
  const [year, month, day] = date.split('-').map(Number)
  if (!year || !month || !day) return date
  const shifted = new Date(year, month - 1, day + days)
  return `${shifted.getFullYear()}-${pad2(shifted.getMonth() + 1)}-${pad2(shifted.getDate())}`
}

/** 日期条上的短标签：今天 / 昨天 / 周X。 */
export const dayLabel = (date: string, today = nowParts().date) => {
  if (date === today) return '今天'
  if (date === shiftDate(today, -1)) return '昨天'
  const [year, month, day] = date.split('-').map(Number)
  if (!year || !month || !day) return date
  return `周${'日一二三四五六'[new Date(year, month - 1, day).getDay()]}`
}

/** uni `picker` 的 change 事件取值：H5 与小程序都把选中的日期放在 `detail.value`。 */
export const pickerValue = (event: unknown) =>
  String((event as { detail?: { value?: string } })?.detail?.value ?? '')

/** 原型记录页日期条：只标周几（日一二…），不写成「今天/昨天」。 */
export const weekdayChar = (date: string) => {
  const [year, month, day] = date.split('-').map(Number)
  if (!year || !month || !day) return ''
  return '日一二三四五六'[new Date(year, month - 1, day).getDay()] ?? ''
}

/** 记录页顶部日期条：`days` 天，最后一天就是 `anchor`（默认今天）。 */
export function buildDateStrip(days: number, anchor = nowParts().date) {
  const today = nowParts().date
  return Array.from({ length: days }, (_, index) => {
    const date = shiftDate(anchor, index - days + 1)
    return { date, day: String(Number(date.split('-')[2])), label: dayLabel(date, today), weekday: weekdayChar(date) }
  })
}

/** 完整记录页筛选：对齐原型 全部/喂奶/辅食/维生素AD/睡眠/排便/尿布。 */
export const RECORD_FILTERS: { value: RecordType | 'all'; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'feeding', label: '喂奶' },
  { value: 'complementary_food', label: '辅食' },
  { value: 'vitamin_ad', label: '维生素AD' },
  { value: 'sleep', label: '睡眠' },
  { value: 'stool', label: '排便' },
  { value: 'diaper', label: '尿布' },
]

/** 时间线只显示选中的那一天：记录接口没有 from/to，按客户端本地日期过滤。 */
export const recordsOnDay = <T extends { occurred_at: string }>(records: T[], date: string) =>
  records.filter((item) => dateOf(item.occurred_at) === date)

export const dateTimeParts = (value?: string | null) => {
  if (!value) return nowParts()
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return nowParts()
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000).toISOString()
  return { date: local.slice(0, 10), time: local.slice(11, 16) }
}

export const toIsoDateTime = (date: string, time: string) =>
  new Date(`${date}T${time || '00:00'}:00`).toISOString()

const present = (value: unknown) => value !== undefined && value !== null && String(value).trim() !== ''
const positive = (value: unknown) => present(value) && Number(value) > 0

export function validatePayload(type: RecordType, payload: Record<string, unknown>): string | null {
  switch (type) {
    case 'feeding':
      return present(payload.feeding_type) ? null : '请选择喂养方式'
    case 'complementary_food':
      return present(payload.food_name) ? null : '请填写食物名称'
    case 'sleep':
      return positive(payload.duration_minutes) ? null : '请填写睡眠时长'
    case 'stool':
      return present(payload.color) && present(payload.consistency) ? null : '请选择颜色和性状'
    case 'diaper':
      return present(payload.content) ? null : '请填写记录内容'
    case 'crying':
      return null
    case 'growth':
      return positive(payload.height_cm) || positive(payload.weight_kg) ? null : '身高或体重至少填写一项'
    case 'vaccine':
      return present(payload.name) ? null : '请填写疫苗名称'
    case 'vitamin_ad':
      return null
    case 'medication':
      return present(payload.name) ? null : '请填写药品名称'
    case 'custom':
      return present(payload.title) ? null : '请填写标题'
  }
}

export interface BabyProfileInput {
  nickname: string
  birth_date: string
  gender: Baby['gender']
}

/**
 * 建档与编辑共用同一套校验。
 *
 * 生日允许稍后补充（空串通过）；填了则校验格式且不能是未来。
 * `today` 可注入，好让用例把「今天」钉死；不注入就是设备本地日期。
 */
export function validateBabyProfile(input: BabyProfileInput, today = nowParts().date): string | null {
  if (!input.nickname.trim()) return '请填写宝宝昵称'
  if (!input.birth_date) return null
  if (!/^\d{4}-\d{2}-\d{2}$/.test(input.birth_date) || dateOf(`${input.birth_date}T00:00:00`) !== input.birth_date) return '生日格式不正确'
  if (input.birth_date > today) return '生日不能是未来的日期'
  return null
}

const numberText = (value: unknown) => {
  const number = Number(value)
  return Number.isFinite(number) ? String(number) : ''
}

export function describeRecord(record: Pick<RecordItem, 'record_type' | 'payload'>): string {
  const payload = record.payload
  switch (record.record_type) {
    case 'feeding':
      return payload.amount_ml ? `${numberText(payload.amount_ml)} ml` : '已记录喂奶'
    case 'complementary_food':
      return [payload.food_name, payload.amount_text].filter(present).join(' · ') || '已记录辅食'
    case 'sleep': {
      const minutes = Number(payload.duration_minutes || 0)
      if (minutes) return minutes >= 60 ? `${Math.floor(minutes / 60)} 小时 ${minutes % 60} 分钟` : `${minutes} 分钟`
      return payload.start_at && payload.end_at ? '已记录起止时间' : '已记录睡眠'
    }
    case 'stool':
      return [payload.color, payload.consistency].filter(present).join(' · ') || '已记录排便'
    case 'diaper':
      return ({ wet: '尿湿', stool: '排便', both: '尿湿和排便' } as Record<string, string>)[String(payload.content)] || String(payload.content ?? '').trim() || '已更换尿布'
    case 'crying':
      return [payload.duration_minutes ? `${numberText(payload.duration_minutes)} 分钟` : '', payload.description].filter(present).join(' · ') || '已记录哭闹'
    case 'growth':
      return [payload.height_cm ? `身高 ${numberText(payload.height_cm)} cm` : '', payload.weight_kg ? `体重 ${numberText(payload.weight_kg)} kg` : ''].filter(present).join(' · ')
    case 'vaccine':
      return [payload.name, payload.dose].filter(present).join(' · ')
    case 'vitamin_ad':
      return present(payload.dose_text) ? `已吃 · ${String(payload.dose_text)}` : '已记录维生素AD'
    case 'medication':
      return [payload.name, payload.dosage_text].filter(present).join(' · ')
    case 'custom':
      return String(payload.title || '自定义记录')
  }
}

/**
 * 语音/拍照确认保存后的短摘要：类型 · 数量（若有），供提示框与 AI 会话留痕共用。
 */
export function recordWhatText(record: Pick<RecordItem, 'record_type' | 'payload'>): string {
  const label = typeMeta(record.record_type).label
  const detail = describeRecord(record).trim()
  if (!detail || detail === `已记录${label}` || detail.startsWith('已记录')) return label
  return `${label} · ${detail}`
}

/**
 * 提示框正文：写明已进今日记录（不是问懂宝）。
 */
export function savedRecordAck(record: Pick<RecordItem, 'record_type' | 'payload'>): string {
  return `已写入今日记录：${recordWhatText(record)}`
}

export function showSavedRecordAck(record: Pick<RecordItem, 'record_type' | 'payload'>) {
  uni.showModal({
    title: '记好了',
    content: savedRecordAck(record),
    showCancel: false,
    confirmText: '知道了',
  })
}

export function normalizeSummary(value: Partial<DailySummary> & Record<string, unknown>): DailySummary {
  return {
    feeding_ml: Number(value.feeding_ml ?? value.milk_ml ?? 0),
    sleep_minutes: Number(value.sleep_minutes ?? 0),
    diaper_count: Number(value.diaper_count ?? 0),
    complementary_food_count: Number(value.complementary_food_count ?? value.food_count ?? 0),
  }
}

/** 首页与记录页共用的时间文案：本地时区的「M月D日 HH:MM」，解析不了就原样返回。 */
export const recordTimeText = (value: string) => {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return `${date.getMonth() + 1}月${date.getDate()}日 ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`
}

/** 首页问候语：只看本地小时，覆盖 0-23。 */
export function greetingFor(hour: number) {
  if (hour < 5 || hour >= 23) return '夜深了，早点休息'
  if (hour < 11) return '早上好，陪宝宝慢慢长大'
  if (hour < 14) return '中午好，记得吃饭'
  if (hour < 18) return '下午好，陪宝宝慢慢长大'
  return '晚上好，今天也辛苦啦'
}

/**
 * 给 `daily-summary` 的时区名。服务端默认就是 Asia/Shanghai，两边保持一致：
 * 小程序逻辑层没有 Intl，取不到时区时退回同一个默认值，与不带参数时的行为相同。
 */
export const timeZoneName = (resolved?: string | null) =>
  resolved && resolved.trim() ? resolved.trim() : 'Asia/Shanghai'

export const detectTimeZone = () => {
  try {
    return timeZoneName(Intl.DateTimeFormat().resolvedOptions().timeZone)
  } catch {
    return timeZoneName(null)
  }
}

export const ageText = (birthDate?: string | null) => {
  if (!birthDate) return '生日待完善'
  const birth = new Date(`${birthDate}T00:00:00`)
  const now = new Date()
  if (Number.isNaN(birth.getTime()) || birth > now) return '生日待完善'
  let months = (now.getFullYear() - birth.getFullYear()) * 12 + now.getMonth() - birth.getMonth()
  if (now.getDate() < birth.getDate()) months -= 1
  return months < 1 ? '未满 1 个月' : `${months} 个月`
}
