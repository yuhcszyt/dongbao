import { expect, it } from 'vitest'
import { chartSource } from './chart'
it('小程序图表使用完整的本地 base64 SVG，不依赖 DOM 或网络',()=>{
  for(const value of [70,8.2,45]) {
    const source=chartSource([{date:'2026-10-25',value}])
    expect(source.startsWith('data:image/svg+xml;base64,')).toBe(true)
    const svg=Buffer.from(source.split(',')[1]!, 'base64').toString('utf8')
    expect(svg.startsWith('<svg xmlns="http://www.w3.org/2000/svg"')).toBe(true)
    expect(svg.endsWith('</svg>')).toBe(true)
    expect(svg.match(/<circle /g)).toHaveLength(1)
    expect(svg).not.toContain('NaN')
  }
})
it('无测量数据不生成虚构曲线',()=>expect(chartSource([])).toBe(''))
