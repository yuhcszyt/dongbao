export const RECORD_TYPES = [
  { value: 'feeding', label: '喂奶', icon: '🍼' },
  { value: 'complementary_food', label: '辅食', icon: '🥣' },
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
  birth_date: string
  gender: 'male' | 'female' | 'unknown'
  created_at?: string
  updated_at?: string
}

export interface RecordItem {
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
  RECORD_TYPES.find((item) => item.value === type) ?? RECORD_TYPES[9]

export const nowParts = () => {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60_000).toISOString()
  return { date: local.slice(0, 10), time: local.slice(11, 16) }
}

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
      return present(payload.content) ? null : '请选择尿布情况'
    case 'crying':
      return null
    case 'growth':
      return positive(payload.height_cm) || positive(payload.weight_kg) ? null : '身高或体重至少填写一项'
    case 'vaccine':
      return present(payload.name) ? null : '请填写疫苗名称'
    case 'medication':
      return present(payload.name) ? null : '请填写药品名称'
    case 'custom':
      return present(payload.title) ? null : '请填写标题'
  }
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
      return ({ wet: '尿湿', stool: '排便', both: '尿湿和排便' } as Record<string, string>)[String(payload.content)] || '已更换尿布'
    case 'crying':
      return [payload.duration_minutes ? `${numberText(payload.duration_minutes)} 分钟` : '', payload.description].filter(present).join(' · ') || '已记录哭闹'
    case 'growth':
      return [payload.height_cm ? `身高 ${numberText(payload.height_cm)} cm` : '', payload.weight_kg ? `体重 ${numberText(payload.weight_kg)} kg` : ''].filter(present).join(' · ')
    case 'vaccine':
      return [payload.name, payload.dose].filter(present).join(' · ')
    case 'medication':
      return [payload.name, payload.dosage_text].filter(present).join(' · ')
    case 'custom':
      return String(payload.title || '自定义记录')
  }
}

export function normalizeSummary(value: Partial<DailySummary> & Record<string, unknown>): DailySummary {
  return {
    feeding_ml: Number(value.feeding_ml ?? value.milk_ml ?? 0),
    sleep_minutes: Number(value.sleep_minutes ?? 0),
    diaper_count: Number(value.diaper_count ?? 0),
    complementary_food_count: Number(value.complementary_food_count ?? value.food_count ?? 0),
  }
}

export const ageText = (birthDate: string) => {
  const birth = new Date(`${birthDate}T00:00:00`)
  const now = new Date()
  if (Number.isNaN(birth.getTime()) || birth > now) return '生日待完善'
  let months = (now.getFullYear() - birth.getFullYear()) * 12 + now.getMonth() - birth.getMonth()
  if (now.getDate() < birth.getDate()) months -= 1
  return months < 1 ? '未满 1 个月' : `${months} 个月`
}
