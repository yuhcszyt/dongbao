import { expect, it } from 'vitest'
import { recordView, growthPoints, recordTitle } from './presentation'
import type { RecordItem } from '@/features/record/domain'
const record:RecordItem={id:'a',baby_id:'baby',record_type:'growth',source:'manual',occurred_at:'2026-10-29T10:00:00Z',payload:{kind:'growth',height_cm:'70.5'}}
it('真实增长数据按时间排序，缺失体重不补默认值',()=>{
  expect(growthPoints([record],'weight_kg')).toEqual([])
  expect(growthPoints([record],'height_cm')[0]?.value).toBe(70.5)
})
it('记录展示保留服务端ID、来源和测量值',()=>{
  expect(recordView(record)).toMatchObject({id:'a',type:'身高体重',source:'手动'})
  expect(recordView(record).value).toContain('70.5')
})

it('未填写奶量不会展示孤立单位或虚构数值',()=>{
  const feeding:RecordItem={...record,record_type:'feeding',payload:{kind:'feeding',feeding_type:'breast',amount_ml:null}}
  expect(recordTitle(recordView(feeding))).toBe('喂奶 奶量未填写')
  expect(recordTitle(recordView({...feeding,payload:{...feeding.payload,amount_ml:180}}))).toBe('喂奶 180 ml')
})
