export type Range = 'day' | 'week' | 'month'
export interface BabyRecord { id: string; date: string; time: string; type: string; value: string; note: string; source: string }
export interface Message { role: 'me' | 'bot'; text: string }
export interface AppState {
  version: 1; records: BabyRecord[]; babyName: string
  profile: Record<string, { value: string; note: string }>
  settings: { notifications: boolean; sharing: boolean; personalized: boolean }
  messages: Message[]; milestones: string[]; feedback: string[]; favorites: string[]
}
export const STORAGE_KEY = 'dongbao.client-v13.v1'
export function dateKey(date = new Date()): string {
  return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`
}
export function shiftDateKey(key: string, direction: number, range: Range): string {
  const date = new Date(`${key}T12:00:00`)
  if (range === 'month') { date.setDate(1); date.setMonth(date.getMonth()+direction) }
  else date.setDate(date.getDate()+direction*(range === 'week' ? 7 : 1))
  return dateKey(date)
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
export function validateRecord(record: Pick<BabyRecord,'type'|'value'|'time'>): string {
  if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(record.time)) return '请选择有效时间'
  if (!record.value.trim()) return '请填写记录内容'
  if (['喂奶','睡眠','体温'].includes(record.type) && (!/^\d+(\.\d+)?$/.test(record.value) || Number(record.value) <= 0)) return '请输入大于 0 的数值'
  if (record.value.length > 300) return '记录内容最多 300 字'
  return ''
}
export function recordStats(records: BabyRecord[]) {
  return ['喂奶','睡眠','辅食','尿布','排便','用药'].map(type => {
    const rows = records.filter(r=>r.type===type)
    const total = rows.reduce((sum,r)=>sum+(Number(r.value)||0),0)
    return { name:type, count:rows.length, value:type==='喂奶'?`${total} ml`:type==='睡眠'?`${Math.floor(total/60)}h${total%60}m`:`${rows.length} 次` }
  })
}
export function seedState(today = dateKey()): AppState {
  return { version:1, babyName:'小米粥', profile:{}, settings:{notifications:true,sharing:true,personalized:true},
    records:[['08:00','喂奶','150','配方奶'],['10:30','辅食','鸡肉蔬菜粥 · 半碗',''],['13:00','睡眠','80','午睡'],['15:20','喂奶','180','配方奶'],['18:00','辅食','南瓜泥 50g','']].map((row,i)=>({id:`sample-${i}`,date:today,time:row[0]!,type:row[1]!,value:row[2]!,note:row[3]!,source:'示例'})),
    messages:[{role:'bot',text:'你好，我是懂宝。这里可以体验育儿对话流程；当前回答为演示，不会调用真实 AI。你也可以先记录宝宝的喂养、睡眠和成长。'}],
    milestones:['会爬','扶站','会叫爸爸妈妈'], feedback:[],favorites:[] }
}
export function decodeState(raw: unknown): AppState | null {
  try {
    const value = typeof raw === 'string' ? JSON.parse(raw) : raw
    if (!value || value.version !== 1 || typeof value.babyName !== 'string' || !value.babyName.trim()) return null
    if (!Array.isArray(value.records) || !value.records.every((r: BabyRecord)=>r && ['id','date','time','type','value','note','source'].every(k=>typeof r[k as keyof BabyRecord]==='string') && /^\d{4}-\d{2}-\d{2}$/.test(r.date) && !validateRecord(r))) return null
    if (!Array.isArray(value.messages) || !value.messages.every((m: Message)=>m && ['me','bot'].includes(m.role) && typeof m.text==='string')) return null
    if (!value.settings || !['notifications','sharing','personalized'].every(k=>typeof value.settings[k]==='boolean')) return null
    if (!value.profile || typeof value.profile!=='object' || Array.isArray(value.profile) || !Object.values(value.profile).every((p: unknown)=>p && typeof p==='object' && typeof (p as {value?:unknown}).value==='string' && typeof (p as {note?:unknown}).note==='string')) return null
    if (!['milestones','feedback','favorites'].every(k=>Array.isArray(value[k]) && value[k].every((s:unknown)=>typeof s==='string'))) return null
    return value as AppState
  } catch { return null }
}
export function exportRecords(records: BabyRecord[], format: 'CSV'|'JSON'): string {
  if (format === 'JSON') return JSON.stringify(records,null,2)
  // Spreadsheet formula injection must remain inert even when a user enters a leading operator.
  const cell=(s:string)=>`"${(/^[\s]*[=+@-]/.test(s)?"'"+s:s).replace(/"/g,'""')}"`
  return '\ufeff日期,时间,类型,内容,备注,来源\r\n'+records.map(r=>[r.date,r.time,r.type,r.value,r.note,r.source].map(cell).join(',')).join('\r\n')
}
export function articleMatches(category: string, search: string, articleCategory: string, title: string): boolean {
  return (['推荐','当月'].includes(category) || category===articleCategory) && title.includes(search.trim())
}
