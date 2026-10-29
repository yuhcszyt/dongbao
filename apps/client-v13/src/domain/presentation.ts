import { dateTimeParts, describeRecord, typeMeta, type RecordItem } from '@/features/record/domain'
import type { BabyRecord } from './model'

export function recordView(record: RecordItem): BabyRecord {
  const parts=dateTimeParts(record.occurred_at)
  return {id:record.id,date:parts.date,time:parts.time,type:typeMeta(record.record_type).label,
    value:record.record_type==='feeding' ? String(record.payload.amount_ml ?? '')
      : record.record_type==='sleep' ? String(record.payload.duration_minutes ?? duration(record)) : describeRecord(record),
    note:record.note || '',source:({manual:'手动',voice:'语音',photo:'拍照',system:'系统'})[record.source]}
}
function duration(record:RecordItem) {
  if(!record.payload.start_at || !record.payload.end_at)return 0
  return Math.max(0,Math.round((Date.parse(String(record.payload.end_at))-Date.parse(String(record.payload.start_at)))/60000))
}
export function growthPoints(records:RecordItem[],key:'height_cm'|'weight_kg') {
  return records.filter(r=>r.record_type==='growth' && Number(r.payload[key])>0)
    .sort((a,b)=>Date.parse(a.occurred_at)-Date.parse(b.occurred_at))
    .map(r=>({date:dateTimeParts(r.occurred_at).date,value:Number(r.payload[key])}))
}

export function recordTitle(record: BabyRecord): string {
  if (record.type === '喂奶') return `喂奶 ${record.value ? record.value+' ml' : '奶量未填写'}`
  if (record.type === '睡眠') return `睡眠 ${record.value ? record.value+' 分钟' : '时长未填写'}`
  return `${record.type} ${record.value}`.trim()
}
