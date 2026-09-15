import { describe, expect, it } from 'vitest'
import { describeRecord, normalizeSummary, validatePayload } from './domain'

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
