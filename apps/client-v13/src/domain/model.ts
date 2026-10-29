export type Range = 'day' | 'week' | 'month'
export interface BabyRecord { id: string; date: string; time: string; type: string; value: string; note: string; source: string }
export interface Message { role: 'me' | 'bot'; text: string }
export function dateKey(date = new Date()): string {
  return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`
}
export function shiftDateKey(key: string, direction: number, range: Range): string {
  const date = new Date(`${key}T12:00:00`)
  if (range === 'month') { date.setDate(1); date.setMonth(date.getMonth()+direction) }
  else date.setDate(date.getDate()+direction*(range === 'week' ? 7 : 1))
  return dateKey(date)
}
export function rangeLabel(selected: string, range: Range): string {
  const date = new Date(`${selected}T12:00:00`)
  if (range === 'month') return `${date.getFullYear()}年${date.getMonth()+1}月`
  if (range === 'day') return `${date.getMonth()+1}月${date.getDate()}日　${['周日','周一','周二','周三','周四','周五','周六'][date.getDay()]}`
  const start = new Date(date); start.setDate(start.getDate()-(start.getDay()+6)%7)
  const end = new Date(start); end.setDate(end.getDate()+6)
  const format = (value: Date) => `${start.getFullYear() !== end.getFullYear() ? value.getFullYear()+'年' : ''}${value.getMonth()+1}月${value.getDate()}日`
  return `${format(start)} - ${format(end)}`
}
export function inRange(key: string, selected: string, range: Range): boolean {
  if (range === 'day') return key === selected
  if (range === 'month') return key.slice(0,7) === selected.slice(0,7)
  const start = new Date(`${selected}T12:00:00`)
  start.setDate(start.getDate() - (start.getDay()+6)%7)
  const end = new Date(start); end.setDate(end.getDate()+6)
  return key >= dateKey(start) && key <= dateKey(end)
}
export function selectRecords(records: BabyRecord[], selected: string, range: Range, type = '全部'): BabyRecord[] {
  return records.filter(r => inRange(r.date,selected,range) && (type === '全部' || r.type === type))
    .sort((a,b) => `${b.date} ${b.time}`.localeCompare(`${a.date} ${a.time}`))
}
export function recordStats(records: BabyRecord[]) {
  return ['喂奶','睡眠','辅食','尿布','排便','用药'].map(type => {
    const rows = records.filter(r=>r.type===type)
    const total = rows.reduce((sum,r)=>sum+(Number(r.value)||0),0)
    return { name:type, icon:({'喂奶':'🍼','睡眠':'🌙','辅食':'🥣','尿布':'🩲','排便':'💩','用药':'💊'} as Record<string,string>)[type], count:rows.length, value:type==='喂奶'?`${total} ml`:type==='睡眠'?`${Math.floor(total/60)}h${total%60}m`:`${rows.length} 次` }
  })
}
export function exportRecords(records: BabyRecord[], format: 'CSV'|'JSON'): string {
  if (format === 'JSON') return JSON.stringify(records,null,2)
  // Spreadsheet formula injection must remain inert even when a user enters a leading operator.
  const cell=(s:string)=>`"${(/^[\s]*[=+@-]/.test(s)?"'"+s:s).replace(/"/g,'""')}"`
  return '\ufeff日期,时间,类型,内容,备注,来源\r\n'+records.map(r=>[r.date,r.time,r.type,r.value,r.note,r.source].map(cell).join(',')).join('\r\n')
}
