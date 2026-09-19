export interface AiSourceRef {
  title: string
  source_url?: string | null
  publisher: string
  published_at?: string | null
  chunk_id?: string | null
}

export interface ParentingAnswer {
  summary: string
  reasons: string[]
  baby_context: string[]
  actions: string[]
  watch_for: string[]
  sources: AiSourceRef[]
  related_record_ids: string[]
  medical_disclaimer?: string | null
}

export interface AiChatResponse {
  conversation_id: string
  message_id: string
  answer: ParentingAnswer
}

export interface AiActiveConversation {
  conversation_id: string | null
  messages: Array<{
    id: string
    role: string
    content: string
    structured_payload?: ParentingAnswer | null
    created_at: string
  }>
}
