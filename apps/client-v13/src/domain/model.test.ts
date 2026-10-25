import { describe, expect, it } from 'vitest'
import { articleMatches, dateKey, decodeState, exportRecords, inRange, recordStats, seedState, selectRecords, shiftDateKey, validateRecord } from './model'

describe('本地记录闭环',()=>{
  it('保存后的状态可以恢复，包括设置和档案',()=>{
    const state=seedState('2026-10-25')
    state.records.push({id:'new',date:'2026-10-25',time:'23:59',type:'喂奶',value:'200',note:'睡前',source:'手动记录'})
    state.profile['基本信息']={value:'豆豆',note:'宝宝'}
    state.babyName='豆豆';state.settings.notifications=false
    expect(decodeState(JSON.stringify(state))).toEqual(state)
    expect(recordStats(state.records)[0]).toEqual({name:'喂奶',count:3,value:'530 ml'})
    expect(selectRecords(state.records,'2026-10-25','day')[0]?.id).toBe('new')
  })
  it('损坏、版本不兼容和嵌套字段错误不能进入页面状态',()=>{
    expect(decodeState('{')).toBeNull()
    expect(decodeState({...seedState(),version:2})).toBeNull()
    expect(decodeState({...seedState(),settings:{}})).toBeNull()
    expect(decodeState({...seedState(),profile:{bad:null}})).toBeNull()
    expect(decodeState({...seedState(),messages:[{role:'other',text:'x'}]})).toBeNull()
    expect(decodeState({...seedState(),records:[null]})).toBeNull()
  })
  it.each(['','0','-1','abc','12ml','Infinity','NaN'])('拒绝非法奶量 %s',value=>{
    expect(validateRecord({type:'喂奶',value,time:'10:30'})).not.toBe('')
  })
  it('允许小数数值及手动文本，拒绝非法时间',()=>{
    expect(validateRecord({type:'体温',value:'36.5',time:'10:30'})).toBe('')
    expect(validateRecord({type:'辅食',value:'南瓜粥',time:'10:30'})).toBe('')
    expect(validateRecord({type:'辅食',value:'南瓜粥',time:'24:00'})).not.toBe('')
  })
  it('空列表统计为零，分类筛选不改变原始记录',()=>{
    const state=seedState('2026-10-25')
    expect(selectRecords(state.records,'2026-10-24','day')).toEqual([])
    expect(selectRecords(state.records,'2026-10-25','day','喂奶')).toHaveLength(2)
    expect(state.records).toHaveLength(5)
    expect(recordStats([]).every(s=>s.count===0)).toBe(true)
  })
})
describe('日周月边界',()=>{
  it('按本地日期生成日期键',()=>expect(dateKey(new Date(2026,0,1,0,1))).toBe('2026-01-01'))
  it('跨月、闰年和跨年切换',()=>{
    expect(shiftDateKey('2026-12-31',1,'day')).toBe('2027-01-01')
    expect(shiftDateKey('2024-02-28',1,'day')).toBe('2024-02-29')
    expect(shiftDateKey('2026-01-31',1,'month')).toBe('2026-02-01')
    expect(shiftDateKey('2026-12-28',1,'week')).toBe('2027-01-04')
  })
  it('周一到周日且可以跨年',()=>{
    expect(inRange('2025-12-29','2026-01-01','week')).toBe(true)
    expect(inRange('2026-01-04','2026-01-01','week')).toBe(true)
    expect(inRange('2026-01-05','2026-01-01','week')).toBe(false)
    expect(inRange('2026-02-01','2026-01-31','month')).toBe(false)
  })
})
describe('发现与导出',()=>{
  it('分类与搜索叠加生效',()=>{
    expect(articleMatches('睡眠','宝宝','喂养','宝宝辅食')).toBe(false)
    expect(articleMatches('睡眠','宝宝','睡眠','宝宝夜醒')).toBe(true)
    expect(articleMatches('推荐','不存在','睡眠','宝宝夜醒')).toBe(false)
  })
  it('JSON 可以回读，CSV 转义引号换行并阻断公式执行',()=>{
    const records=seedState().records
    records[0]!.note=' =HYPERLINK("bad")\n下一行'
    expect(JSON.parse(exportRecords(records,'JSON'))).toEqual(records)
    const csv=exportRecords(records,'CSV')
    expect(csv).toContain('"\' =HYPERLINK(""bad"")\n下一行"')
    expect(csv.startsWith('\ufeff日期,时间')).toBe(true)
  })
})
