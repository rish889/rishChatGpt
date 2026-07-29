export const API_BASE = 'http://127.0.0.1:8000'

export type Role = 'user' | 'assistant'

export interface Message {
  role: Role
  content: string
}

export interface ConversationSummary {
  id: number
  title: string | null
  created_at: string
}

export async function fetchConversations(): Promise<ConversationSummary[]> {
  const res = await fetch(`${API_BASE}/conversations`)
  if (!res.ok) throw new Error('Failed to load conversations')
  return res.json()
}

export async function createConversation(): Promise<ConversationSummary> {
  const res = await fetch(`${API_BASE}/conversations`, { method: 'POST' })
  if (!res.ok) throw new Error('Failed to create conversation')
  return res.json()
}

export async function fetchMessages(conversationId: number): Promise<Message[]> {
  const res = await fetch(`${API_BASE}/conversations/${conversationId}/messages`)
  if (!res.ok) throw new Error('Failed to load messages')
  return res.json()
}

export async function streamChat(
  conversationId: number,
  message: string,
  onChunk: (chunk: string) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId, message }),
  })
  if (!res.ok || !res.body) throw new Error('Failed to reach the backend')

  const reader = res.body.getReader()
  const decoder = new TextDecoder()

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    onChunk(decoder.decode(value, { stream: true }))
  }
}
