/**
 * 微信小程序里，fixed 遮罩用 v-show 经常「关不掉 / 一进来就在」。
 * 统一要求：带 class="overlay" 的节点必须用 v-if 控制显隐，禁止 v-show。
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

const srcRoot = join(process.cwd(), 'src')

function walkVue(dir: string): string[] {
  const out: string[] = []
  for (const name of readdirSync(dir)) {
    const path = join(dir, name)
    const stat = statSync(path)
    if (stat.isDirectory()) out.push(...walkVue(path))
    else if (name.endsWith('.vue')) out.push(path)
  }
  return out
}

describe('overlay visibility guard', () => {
  it('forbids v-show on fixed overlay sheets', () => {
    const offenders: string[] = []
    for (const file of walkVue(srcRoot)) {
      const text = readFileSync(file, 'utf8')
      const lines = text.split('\n')
      lines.forEach((line, index) => {
        if (line.includes('class="overlay"') && line.includes('v-show')) {
          offenders.push(`${file.replace(`${srcRoot}/`, 'src/')}:${index + 1}: ${line.trim()}`)
        }
      })
    }
    expect(offenders).toEqual([])
  })

  it('home/record capture overlays use v-if with open state', () => {
    const home = readFileSync(join(srcRoot, 'pages/home/index.vue'), 'utf8')
    const record = readFileSync(join(srcRoot, 'pages/record/index.vue'), 'utf8')
    expect(home).toMatch(/v-if="state\.baby && captureOpen"/)
    expect(home).not.toMatch(/v-show="captureOpen"/)
    expect(record).toMatch(/v-if="state\.baby && panel"/)
    expect(record).not.toMatch(/v-show="panel"/)
  })
})
