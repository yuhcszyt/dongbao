import { describe, expect, it } from 'vitest'
import { describeRecord, detectTimeZone, greetingFor, normalizeSummary, recordTimeText, timeZoneName, validateBabyProfile, validatePayload } from './domain'

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

  it('昵称与生日齐全且生日不是未来时通过', () => {
    expect(validateBabyProfile({ nickname: '安安', birth_date: '2024-03-05', gender: 'female' }, today)).toBeNull()
    expect(validateBabyProfile({ nickname: '安安', birth_date: today, gender: 'unknown' }, today)).toBeNull()
  })

  it('缺昵称、缺生日、生日在未来时都给中文提示', () => {
    expect(validateBabyProfile({ nickname: '  ', birth_date: '2024-03-05', gender: 'male' }, today)).toBe('请填写宝宝昵称')
    expect(validateBabyProfile({ nickname: '安安', birth_date: '', gender: 'male' }, today)).toBe('请填写宝宝生日')
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
