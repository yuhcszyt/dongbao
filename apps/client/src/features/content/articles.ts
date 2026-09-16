/**
 * 推荐文章与收藏：当前无内容接口，本地静态示例 + 本机收藏。
 * UI 必须标明「内容示例 / 演示」，不伪装成已审核专业内容。
 */
import { reactive } from 'vue'

export interface Article {
  id: number
  title: string
  category: string
  why: string
  emoji: string
  color: string
  intro: string
  body: string
  sub: string
  detail: string
  minutes: number
}

export const ARTICLES: Article[] = [
  {
    id: 0,
    title: '读懂宝宝的睡眠节奏',
    category: '睡眠',
    why: '与你关注的睡眠记录相关',
    emoji: '☾',
    color: '#e5ece8',
    intro: '先记录，再了解',
    body: '把入睡、睡醒和夜间醒来的时间记下来，帮助回顾宝宝每天的变化。',
    sub: '让记录更完整',
    detail: '记录白天的小睡，也可以备注当时的环境、入睡方式以及醒来后的表现。本文仅为演示阅读体验。',
    minutes: 3,
  },
  {
    id: 1,
    title: '辅食日记，怎么记更轻松？',
    category: '喂养',
    why: '适合当前辅食记录阶段',
    emoji: '🥣',
    color: '#f4e8d9',
    intro: '把每一次尝试记下来',
    body: '记录食物名称、时间和大致份量，也可以补充宝宝当时的接受情况。',
    sub: '从简单开始',
    detail: '不必把记录写成任务清单。先记下最容易遗漏的信息，之后再慢慢补充。',
    minutes: 4,
  },
  {
    id: 2,
    title: '开始爬行，家里准备好了吗？',
    category: '发育',
    why: '关注宝宝的探索阶段',
    emoji: '🧸',
    color: '#ede8dc',
    intro: '跟着宝宝的视角看一看',
    body: '从宝宝活动的高度，观察家中日常空间，并记下需要进一步检查的地方。',
    sub: '和家人一起准备',
    detail: '把观察到的问题分享给共同照顾宝宝的家人。正式内容将展示专业资料来源及审核信息。',
    minutes: 5,
  },
]

const FAVORITES_KEY = 'dongbao.favorites'

const readFavorites = (): number[] => {
  try {
    const raw = uni.getStorageSync(FAVORITES_KEY)
    if (!raw) return []
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    return Array.isArray(parsed) ? parsed.filter((id) => typeof id === 'number') : []
  } catch {
    return []
  }
}

const state = reactive({ favorites: readFavorites() })

const persist = () => {
  try {
    uni.setStorageSync(FAVORITES_KEY, JSON.stringify(state.favorites))
  } catch {
    // 本机存储失败时仍保留内存态，下次冷启动可能丢失收藏。
  }
}

export const contentStore = {
  state,
  articles: ARTICLES,
  article(id: number) {
    return ARTICLES.find((item) => item.id === id) ?? ARTICLES[0]!
  },
  isFavorite(id: number) {
    return state.favorites.includes(id)
  },
  toggleFavorite(id: number) {
    const index = state.favorites.indexOf(id)
    if (index < 0) state.favorites.push(id)
    else state.favorites.splice(index, 1)
    persist()
    return index < 0
  },
  favoriteArticles() {
    return ARTICLES.filter((item) => state.favorites.includes(item.id))
  },
  clear() {
    state.favorites = []
    persist()
  },
}
