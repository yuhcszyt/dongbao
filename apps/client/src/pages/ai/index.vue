<script setup lang="ts">
import { computed, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AccountGone from '@/components/AccountGone.vue'
import { aiDemoStore } from '@/features/content/aiDemo'
import { babyDisplayName, nowParts } from '@/features/record/domain'
import { recordStore } from '@/features/record/store'

const { state } = recordStore
const question = ref('')
const babyName = computed(() => babyDisplayName(state.baby?.nickname))
const today = computed(() => nowParts().date)
const summary = computed(() => recordStore.summaryFor(today.value))

const prompts = ['帮我看看最近的睡眠记录', '今天一共喝了多少奶？', '怎么记录辅食？']

function ask(text?: string) {
  const q = (text ?? question.value).trim()
  if (!q) return
  aiDemoStore.ask(q, state.baby, state.records, summary.value, today.value)
  question.value = ''
}

function clearChat() {
  if (!aiDemoStore.state.messages.length) {
    uni.showToast({ title: '还没有对话记录', icon: 'none' })
    return
  }
  uni.showModal({
    title: '清空演示对话？',
    content: '宝宝档案和日常记录会保留。',
    success: ({ confirm }) => {
      if (confirm) aiDemoStore.clear()
    },
  })
}

function openCry() {
  uni.navigateTo({ url: '/pages/cry/index' })
}

onShow(() => void recordStore.load(today.value))
</script>

<template>
  <view class="page">
    <AccountGone v-if="state.accountDeleted" />
    <template v-else>
      <view class="head">
        <view class="brand">
          <text class="cloud">•ᴗ•</text>
          <view>
            <text class="title">懂宝 AI</text>
            <text class="muted">正在结合{{ babyName }}的近期记录</text>
          </view>
        </view>
        <button class="link" @click="clearChat">清空</button>
      </view>

      <view class="warn">演示对话 · 未连接大模型，不提供真实分析</view>

      <view v-if="!aiDemoStore.state.messages.length" class="welcome">
        <text class="title">今天有什么想和我聊聊？</text>
        <text class="muted">我会从{{ babyName }}的日常记录出发。</text>
        <view class="card">
          <text class="card-title">从这些问题开始</text>
          <button v-for="item in prompts" :key="item" class="outline" @click="ask(item)">{{ item }}</button>
        </view>
        <button class="outline" @click="openCry">▥ 进入哭声监测</button>
      </view>

      <view v-for="(msg, index) in aiDemoStore.state.messages" :key="index" class="thread">
        <view class="user">{{ msg.q }}</view>
        <view class="answer">
          <text class="card-title">一起看看{{ babyName }}的记录</text>
          <view class="evidence">{{ msg.a }}</view>
          <text class="muted">这是交互示例。真实服务接入后，会结合宝宝档案与专业资料继续回答。</text>
          <text class="notice">专业来源：尚未接入知识库，不生成虚构引用。</text>
        </view>
      </view>

      <view class="composer">
        <input v-model="question" class="input" maxlength="500" placeholder="继续问懂宝…" confirm-type="send" @confirm="ask()" />
        <button class="send" @click="ask()">↑</button>
      </view>
    </template>
  </view>
</template>

<style scoped>
.page { min-height: 100vh; padding: 14px 19px calc(120px + env(safe-area-inset-bottom)); background: #fbfaf7; color: #203f4a; }
.head { display: flex; justify-content: space-between; align-items: center; gap: 10px; }
.brand { display: flex; gap: 10px; align-items: center; }
.cloud { width: 40px; height: 32px; border-radius: 50%; background: #b7e4f5; color: #25516a; font-size: 16px; letter-spacing: 3px; text-align: center; line-height: 32px; }
.title { display: block; font-size: 18px; font-weight: 800; }
.muted { display: block; color: #71858b; font-size: 13px; line-height: 1.5; margin-top: 4px; }
.link { background: transparent; color: #2d8098; font-size: 12px; }
.warn { margin: 14px 0; border-radius: 12px; background: #fff0df; color: #b88346; padding: 10px 12px; font-size: 12px; }
.welcome { margin-top: 18px; }
.welcome .title { font-size: 23px; }
.card { margin-top: 16px; border-radius: 19px; background: white; border: 1px solid #eef1ef; padding: 16px; }
.card-title { display: block; font-size: 16px; font-weight: 800; margin-bottom: 8px; }
.outline { display: block; width: 100%; margin-top: 10px; min-height: 48px; border-radius: 14px; border: 1px solid #bedbe4; background: white; color: #328da9; font-size: 14px; }
.user { margin: 18px 0 12px 28px; padding: 12px 15px; border-radius: 17px 17px 4px 17px; background: #d8edf4; font-size: 14px; }
.answer { margin: 12px 0; padding: 16px; border-radius: 4px 18px 18px 18px; background: white; border: 1px solid #eef1ef; }
.evidence { margin: 10px 0; padding: 12px; border-radius: 12px; background: #edf6f8; font-size: 13px; line-height: 1.7; }
.notice { display: block; margin-top: 10px; color: #8b9c9f; font-size: 11px; }
.composer { position: fixed; left: 0; right: 0; bottom: calc(50px + env(safe-area-inset-bottom)); display: flex; align-items: center; gap: 8px; padding: 10px 15px; background: white; border-top: 1px solid #e9eff0; }
.input { flex: 1; min-width: 0; height: 44px; line-height: 44px; border-radius: 22px; background: #f3f7f8; padding: 0 15px; font-size: 15px; }
.send { width: 40px; height: 40px; flex-shrink: 0; border-radius: 50%; background: #328da9; color: white; font-size: 18px; line-height: 40px; }
</style>
