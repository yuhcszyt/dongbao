import { expect, it } from 'vitest'
import { chartSource } from './chart'
it('小程序图表使用完整的本地 base64 SVG，不依赖 DOM 或网络',()=>{
  for(let mode=0;mode<3;mode++) {
    const source=chartSource(mode)
    expect(source.startsWith('data:image/svg+xml;base64,')).toBe(true)
    const svg=Buffer.from(source.split(',')[1]!, 'base64').toString('utf8')
    expect(svg.startsWith('<svg xmlns="http://www.w3.org/2000/svg"')).toBe(true)
    expect(svg.endsWith('</svg>')).toBe(true)
    expect(svg.match(/<circle /g)).toHaveLength(7)
  }
})
it('三种曲线有各自的数据',()=>expect(new Set([0,1,2].map(chartSource)).size).toBe(3))
