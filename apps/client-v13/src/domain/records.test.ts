import { expect, it } from 'vitest'
import { dateKey, rangeLabel, exportRecords, inRange, recordStats, selectRecords, shiftDateKey, type BabyRecord } from './model'
const rows:BabyRecord[]=[{id:'a',date:'2026-10-25',time:'10:30',type:'喂奶',value:'180',note:'',source:'手动'},{id:'b',date:'2026-10-25',time:'11:00',type:'睡眠',value:'80',note:'',source:'语音'}]
it('按真实记录统计，不填默认奶量',()=>{expect(recordStats(rows)[0]?.value).toBe('180 ml');expect(recordStats([]).every(r=>r.count===0)).toBe(true)})
it('分类筛选与日期共同生效，保持时间倒序',()=>{expect(selectRecords(rows,'2026-10-25','day')[0]?.id).toBe('b');expect(selectRecords(rows,'2026-10-25','day','喂奶')).toHaveLength(1);expect(selectRecords(rows,'2026-10-24','day')).toEqual([])})
it('本地日期键不被UTC改变',()=>expect(dateKey(new Date(2026,0,1,0,1))).toBe('2026-01-01'))
it('跨月、跨年、闰年切换正确',()=>{expect(shiftDateKey('2026-12-31',1,'day')).toBe('2027-01-01');expect(shiftDateKey('2024-02-28',1,'day')).toBe('2024-02-29');expect(shiftDateKey('2026-01-31',1,'month')).toBe('2026-02-01');expect(shiftDateKey('2026-12-28',1,'week')).toBe('2027-01-04')})
it('跨年周一到周日，月范围独立',()=>{expect(inRange('2025-12-29','2026-01-01','week')).toBe(true);expect(inRange('2026-01-04','2026-01-01','week')).toBe(true);expect(inRange('2026-01-05','2026-01-01','week')).toBe(false);expect(inRange('2026-02-01','2026-01-31','month')).toBe(false)})
it('CSV保留引号换行并阻断表格公式，JSON可回读',()=>{const records=[{...rows[0]!,note:' =HYPERLINK("bad")\n下一行'}];expect(JSON.parse(exportRecords(records,'JSON'))).toEqual(records);expect(exportRecords(records,'CSV')).toContain('"\' =HYPERLINK(""bad"")\n下一行"')})

it('日期标题与实际筛选范围一致，跨年周显示年份',()=>{
  expect(rangeLabel('2026-10-29','day')).toBe('10月29日　周四')
  expect(rangeLabel('2026-10-29','month')).toBe('2026年10月')
  expect(rangeLabel('2026-10-29','week')).toBe('10月26日 - 11月1日')
  expect(rangeLabel('2026-01-01','week')).toBe('2025年12月29日 - 2026年1月4日')
})
