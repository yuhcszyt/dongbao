// Only actual measurements; no invented standards or percentile bands.
export function chartSource(input: {date:string;value:number}[]): string {
  const data=input.filter(p=>Number.isFinite(p.value)&&p.value>0).slice(-30)
  if(!data.length)return ''
  const values=data.map(p=>p.value),min=Math.min(...values),max=Math.max(...values)
  const margin=Math.max((max-min)*0.15,0.5),low=min-margin,high=max+margin
  const first=Date.parse(data[0]!.date),last=Date.parse(data[data.length-1]!.date)
  const series=data.map(p=>({x:last===first?180:45+(Date.parse(p.date)-first)/(last-first)*275,y:180-(p.value-low)/(high-low)*150}))
  const points=series.map(p=>`${p.x},${p.y}`).join(' ')
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="360" height="210" viewBox="0 0 360 210"><rect width="360" height="210" fill="white"/>${[0,1,2,3].map(i=>`<path d="M40 ${30+i*50}H340" stroke="#edf0f6"/><text x="2" y="${34+i*50}" font-size="10" fill="#7b8098">${(high-i*(high-low)/3).toFixed(1)}</text>`).join('')}<polyline points="${points}" fill="none" stroke="#6759f6" stroke-width="3"/>${series.map(p=>`<circle cx="${p.x}" cy="${p.y}" r="4" fill="#6759f6"/>`).join('')}<text x="40" y="205" font-size="11" fill="#7b8098">${data[0]!.date}</text><text x="260" y="205" font-size="11" fill="#7b8098">${data[data.length-1]!.date}</text></svg>`
  return `data:image/svg+xml;base64,${asciiBase64(svg)}`
}

function asciiBase64(value: string): string {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
  let result = ''
  for (let i = 0; i < value.length; i += 3) {
    const a=value.charCodeAt(i), b=value.charCodeAt(i+1)||0, c=value.charCodeAt(i+2)||0
    const bits=(a<<16)|(b<<8)|c
    result += chars[(bits>>18)&63]! + chars[(bits>>12)&63]!
      + (i+1<value.length ? chars[(bits>>6)&63] : '=')
      + (i+2<value.length ? chars[bits&63] : '=')
  }
  return result
}
