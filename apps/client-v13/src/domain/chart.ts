// Local illustrative asset: no remote image requests and no browser DOM / canvas dependency.
export const curveNames = ['身高曲线','体重曲线','头围曲线']
export function chartSource(mode: number): string {
  const series = [[160,145,125,105,90,78,69],[174,152,129,112,99,89,82],[152,126,107,92,80,72,65]][mode] || []
  const points = series.map((y,i)=>`${30+i*50},${y}`).join(' ')
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="360" height="210" viewBox="0 0 360 210"><rect width="360" height="210" fill="white"/>${[45,80,115,150,185].map(y=>`<path d="M28 ${y}H340" stroke="#edf0f6"/>`).join('')}<polyline points="30,185 80,171 130,159 180,146 230,135 280,126 330,118" fill="none" stroke="#ffae43" stroke-width="2"/><polyline points="30,178 80,162 130,146 180,133 230,120 280,110 330,102" fill="none" stroke="#6bb8ff" stroke-width="2"/><polyline points="${points}" fill="none" stroke="#6759f6" stroke-width="3"/>${series.map((y,i)=>`<circle cx="${30+i*50}" cy="${y}" r="4" fill="#6759f6"/>`).join('')}${[0,2,4,6,8,10,12].map((m,i)=>`<text x="${27+i*50}" y="205" font-size="11" fill="#7b8098">${m}</text>`).join('')}</svg>`
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
