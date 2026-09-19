import { describe, expect, it } from 'vitest'
import {
  buildDateStrip,
  dateOf,
  dayLabel,
  describeRecord,
  detectTimeZone,
  greetingFor,
  normalizeSummary,
  pickerValue,
  recordTimeText,
  recordsOnDay,
  shiftDate,
  timeZoneName,
  validateBabyProfile,
  validatePayload,
} from './domain'

describe('记录领域契约', () => {
  it('与后端字段一致并允许不填奶量', () => {
    expect(validatePayload('feeding', { kind: 'feeding', feeding_type: 'breast', amount_ml: null })).toBeNull()
    expect(validatePayload('crying', { kind: 'crying', duration_minutes: null, description: null })).toBeNull()
    expect(validatePayload('diaper', { kind: 'diaper', content: '更换尿布' })).toBeNull()
    expect(describeRecord({ record_type: 'diaper', payload: { kind: 'diaper', content: '更换尿布' } })).toBe('更换尿布')
    expect(describeRecord({ record_type: 'vaccine', payload: { kind: 'vaccine', name: '乙肝疫苗' } })).toBe('乙肝疫苗')
    expect(normalizeSummary({ feeding_ml: 180 })).toEqual({ feeding_ml: 180, sleep_minutes: 0, diaper_count: 0, complementary_food_count: 0 })
  })
})

describe('宝宝档案校验（建档与编辑共用同一套规则）', () => {
  const today = '2026-09-16'

  it('昵称齐全即可；生日可稍后补充', () => {
    expect(validateBabyProfile({ nickname: '安安', birth_date: '2024-03-05', gender: 'female' }, today)).toBeNull()
    expect(validateBabyProfile({ nickname: '安安', birth_date: today, gender: 'unknown' }, today)).toBeNull()
    expect(validateBabyProfile({ nickname: '宝宝', birth_date: '', gender: 'unknown' }, today)).toBeNull()
  })

  it('缺昵称、生日格式错、生日在未来时给中文提示', () => {
    expect(validateBabyProfile({ nickname: '  ', birth_date: '2024-03-05', gender: 'male' }, today)).toBe('请填写宝宝昵称')
    expect(validateBabyProfile({ nickname: '安安', birth_date: '不是日期', gender: 'male' }, today)).toBe('生日格式不正确')
    expect(validateBabyProfile({ nickname: '安安', birth_date: '2026-09-17', gender: 'male' }, today)).toBe('生日不能是未来的日期')
  })

  it('建档与编辑走同一个函数，性别不参与必填（可暂不填）', () => {
    const profile = { nickname: '安安', birth_date: '2025-01-02', gender: 'unknown' as const }
    expect(validateBabyProfile(profile, today)).toBe(validateBabyProfile({ ...profile, gender: 'male' }, today))
  })
})

describe('首页展示用的时间文案（票 08）', () => {
  it('记录时间按本地时间显示成「M月D日 HH:MM」，解析不了就原样返回', () => {
    expect(recordTimeText('2026-03-05T09:07:00')).toBe('3月5日 09:07')
    expect(recordTimeText('2026-11-20T23:05:00')).toBe('11月20日 23:05')
    expect(recordTimeText('不是时间')).toBe('不是时间')
  })

  it('问候语按时段给中文，覆盖整天', () => {
    expect(greetingFor(5)).toBe('早上好，陪宝宝慢慢长大')
    expect(greetingFor(10)).toBe('早上好，陪宝宝慢慢长大')
    expect(greetingFor(12)).toBe('中午好，记得吃饭')
    expect(greetingFor(15)).toBe('下午好，陪宝宝慢慢长大')
    expect(greetingFor(20)).toBe('晚上好，今天也辛苦啦')
    expect(greetingFor(23)).toBe('夜深了，早点休息')
    expect(greetingFor(3)).toBe('夜深了，早点休息')
  })

  it('时区名用于 daily-summary 参数：拿不到就退回服务端默认时区', () => {
    expect(timeZoneName('Asia/Shanghai')).toBe('Asia/Shanghai')
    expect(timeZoneName(' America/New_York ')).toBe('America/New_York')
    expect(timeZoneName(null)).toBe('Asia/Shanghai')
    expect(timeZoneName('')).toBe('Asia/Shanghai')
    expect(detectTimeZone()).toBeTruthy()
  })
})

describe('记录页的日期归日与日期条（票 09）', () => {
  const today = '2026-09-16'

  it('时间戳按本地日期归入某一天，解析不了不落到今天', () => {
    expect(dateOf('2026-03-05T09:07:00')).toBe('2026-03-05')
    expect(dateOf('2026-11-20T23:59:00')).toBe('2026-11-20')
    expect(dateOf('不是时间')).toBe('')
  })

  it('日期加减跳月、跳年都是对的', () => {
    expect(shiftDate('2026-03-01', -1)).toBe('2026-02-28')
    expect(shiftDate('2026-01-01', -1)).toBe('2025-12-31')
    expect(shiftDate('2026-02-28', 1)).toBe('2026-03-01')
    expect(shiftDate('不是日期', 1)).toBe('不是日期')
  })

  it('日期条标签：今天 / 昨天 / 周X', () => {
    expect(dayLabel(today, today)).toBe('今天')
    expect(dayLabel('2026-09-15', today)).toBe('昨天')
    expect(dayLabel('2026-09-13', today)).toBe('周日')
  })

  it('7 天日期条以选中日结尾，选中日就是最后一天', () => {
    const strip = buildDateStrip(7, today)
    expect(strip).toHaveLength(7)
    expect(strip[0]?.date).toBe('2026-09-10')
    expect(strip[6]?.date).toBe(today)
    // label 相对设备「今天」：锚定历史日时显示周几，不是「今天」
    expect(strip[6]?.label).toBe(dayLabel(today))
    expect(strip[6]?.weekday).toBe('三')
  })

  it('时间线只显示选中那一天（按客户端本地日期过滤）', () => {
    const records = [
      { id: 'a', occurred_at: '2026-09-16T08:00:00' },
      { id: 'b', occurred_at: '2026-09-15T22:30:00' },
      { id: 'c', occurred_at: '不是时间' },
    ]
    expect(recordsOnDay(records, '2026-09-16').map((item) => item.id)).toEqual(['a'])
    expect(recordsOnDay(records, '2026-09-15').map((item) => item.id)).toEqual(['b'])
    expect(recordsOnDay(records, '2026-09-14')).toEqual([])
  })

  it('日期选择器取值：两端口径一致，取不到就当没选', () => {
    expect(pickerValue({ detail: { value: '2026-09-10' } })).toBe('2026-09-10')
    expect(pickerValue({ detail: {} })).toBe('')
    expect(pickerValue(undefined)).toBe('')
  })
})
