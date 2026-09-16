/**
 * 懂宝 AI 演示对话：用本地模板汇总已有记录，不调用大模型，不生成专业判断。
 */
import { reactive } from 'vue'
import { babyDisplayName, dateOf, describeRecord, type Baby, type DailySummary, type RecordItem } from '@/features/record/domain'

export interface ChatMessage {
  q: string
  a: string
}

const CHAT_KEY = 'dongbao.ai.demo.messages'

const readMessages = (): ChatMessage[] => {
  try {
    const raw = uni.getStorageSync(CHAT_KEY)
    if (!raw) return []
    const parsed = typeof raw === 'string' ? JSON.parse(raw) : raw
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

const state = reactive({ messages: readMessages() })

const persist = () => {
  try {
    uni.setStorageSync(CHAT_KEY, JSON.stringify(state.messages))
  } catch {
    // ignore
  }
}

export function demoAnswer(
  question: string,
  baby: Baby | null,
  records: RecordItem[],
  summary: DailySummary | null,
  today: string,
): string {
  const name = babyDisplayName(baby?.nickname)
  const q = question.trim()
  const todayRecords = records.filter((item) => dateOf(item.occurred_at) === today)
  const milkCount = todayRecords.filter((item) => item.record_type === 'feeding').length
  const milkMl = summary?.feeding_ml ?? 0
  const sleepMin = summary?.sleep_minutes ?? 0
  const foodCount = summary?.complementary_food_count ?? 0

  if (/奶|喂养|喝奶/.test(q)) {
    return `今天已有 ${milkCount} 条喝奶记录，总量 ${milkMl} ml（仅统计已录入数据）。这是演示汇总，不代表全天实际摄入，也不构成喂养建议。`
  }
  if (/睡/.test(q)) {
    return `今天已记录睡眠 ${Math.floor(sleepMin / 60)} 小时 ${sleepMin % 60} 分。当前为演示模式，不会判断睡眠原因。`
  }
  if (/辅食/.test(q)) {
    return `今天已有 ${foodCount} 条辅食记录。可在首页点「辅食」填写后确认保存。演示模式不会给出辅食添加建议。`
  }
  const sample = todayRecords.slice(0, 3).map((item) => `${item.record_type}：${describeRecord(item)}`).join('；')
  return `已收到「${q}」。当前为演示对话，未连接大模型。已载入 ${name} 的档案与 ${records.length} 条记录。${sample ? `今日片段：${sample}。` : ''}正式服务接入后，会结合档案与近期记录作答。`
}

export const aiDemoStore = {
  state,
  ask(q: string, baby: Baby | null, records: RecordItem[], summary: DailySummary | null, today: string) {
    const question = q.trim()
    if (!question) return
    state.messages.push({ q: question, a: demoAnswer(question, baby, records, summary, today) })
    persist()
  },
  clear() {
    state.messages = []
    persist()
  },
}
