import { getToken } from './auth'

export const API_BASE = 'http://127.0.0.1:8000'

export type Role = 'user' | 'assistant'

export interface Message {
  role: Role
  content: string
}

export interface ConversationSettings {
  system_prompt: string | null
  model: string | null
  temperature: number | null
}

export interface ConversationSummary extends ConversationSettings {
  id: number
  title: string | null
  created_at: string
}

export interface AuthResponse {
  access_token: string
  token_type: string
}

export class UnauthorizedError extends Error {}

function authHeaders(): Record<string, string> {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...(init.headers ?? {}) },
  })
  if (res.status === 401) throw new UnauthorizedError('Session expired')
  return res
}

async function extractError(res: Response, fallback: string): Promise<never> {
  const body = await res.json().catch(() => null)
  throw new Error(body?.detail ?? fallback)
}

export async function signup(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) return extractError(res, 'Signup failed')
  return res.json()
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
  if (!res.ok) return extractError(res, 'Login failed')
  return res.json()
}

export async function fetchConversations(): Promise<ConversationSummary[]> {
  const res = await apiFetch('/conversations')
  if (!res.ok) throw new Error('Failed to load conversations')
  return res.json()
}

export async function createConversation(
  settings: Partial<ConversationSettings> = {},
): Promise<ConversationSummary> {
  const res = await apiFetch('/conversations', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
  if (!res.ok) throw new Error('Failed to create conversation')
  return res.json()
}

export async function updateConversationSettings(
  conversationId: number,
  settings: Partial<ConversationSettings>,
): Promise<ConversationSummary> {
  const res = await apiFetch(`/conversations/${conversationId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(settings),
  })
  if (!res.ok) throw new Error('Failed to update conversation settings')
  return res.json()
}

export async function fetchModels(): Promise<string[]> {
  const res = await apiFetch('/models')
  if (!res.ok) throw new Error('Failed to load models')
  return res.json()
}

export async function fetchMessages(conversationId: number): Promise<Message[]> {
  const res = await apiFetch(`/conversations/${conversationId}/messages`)
  if (!res.ok) throw new Error('Failed to load messages')
  return res.json()
}

export async function streamChat(
  conversationId: number,
  message: string,
  onChunk: (chunk: string) => void,
): Promise<void> {
  const res = await apiFetch('/chat/stream', {
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
