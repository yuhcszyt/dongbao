import { describe, expect, it } from 'vitest'
import { describeRecord, normalizeSummary, validateBabyProfile, validatePayload } from './domain'

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
