import { useEffect, useState } from 'react'
import {
  type ConversationSummary,
  type Message,
  createConversation,
  fetchConversations,
  fetchMessages,
  streamChat,
} from './api'
import Sidebar from './Sidebar'

function App() {
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [currentConversationId, setCurrentConversationId] = useState<number | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)

  useEffect(() => {
    fetchConversations().then(setConversations).catch(() => {})
  }, [])

  async function selectConversation(id: number) {
    setCurrentConversationId(id)
    setMessages(await fetchMessages(id))
  }

  function startNewChat() {
    setCurrentConversationId(null)
    setMessages([])
  }

  async function sendMessage() {
    const text = input.trim()
    if (!text || isStreaming) return

    setInput('')
    setIsStreaming(true)

    try {
      let conversationId = currentConversationId
      if (conversationId === null) {
        const conversation = await createConversation()
        conversationId = conversation.id
        setCurrentConversationId(conversationId)
        setConversations((prev) => [conversation, ...prev])
      }

      setMessages((prev) => [
        ...prev,
        { role: 'user', content: text },
        { role: 'assistant', content: '' },
      ])

      await streamChat(conversationId, text, (chunk) => {
        setMessages((prev) => {
          const next = [...prev]
          next[next.length - 1] = {
            role: 'assistant',
            content: next[next.length - 1].content + chunk,
          }
          return next
        })
      })

      fetchConversations().then(setConversations).catch(() => {})
    } catch {
      setMessages((prev) => {
        const next = [...prev]
        next[next.length - 1] = {
          role: 'assistant',
          content: 'Error: failed to reach the backend.',
        }
        return next
      })
    } finally {
      setIsStreaming(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="flex h-svh w-full">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelect={selectConversation}
        onNewChat={startNewChat}
      />

      <div className="flex flex-1 flex-col max-w-2xl mx-auto px-4">
        <header className="py-4 border-b border-neutral-200 dark:border-neutral-800">
          <h1 className="text-lg font-medium text-neutral-900 dark:text-neutral-100">
            Build Your Own ChatGPT
          </h1>
        </header>

        <div className="flex-1 overflow-y-auto py-4 space-y-4">
          {messages.length === 0 && (
            <p className="text-neutral-500 dark:text-neutral-400 text-sm">
              Say something to get started.
            </p>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2 whitespace-pre-wrap ${
                  m.role === 'user'
                    ? 'bg-emerald-600 text-white'
                    : 'bg-neutral-100 dark:bg-neutral-800 text-neutral-900 dark:text-neutral-100'
                }`}
              >
                {m.content ||
                  (m.role === 'assistant' && isStreaming && i === messages.length - 1
                    ? '…'
                    : '')}
              </div>
            </div>
          ))}
        </div>

        <div className="py-4 border-t border-neutral-200 dark:border-neutral-800">
          <div className="flex items-end gap-2">
            <textarea
              className="flex-1 resize-none rounded-xl border border-neutral-300 dark:border-neutral-700 bg-transparent px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-600"
              rows={1}
              placeholder="Message..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
            />
            <button
              type="button"
              className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
              disabled={isStreaming || !input.trim()}
              onClick={sendMessage}
            >
              Send
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default App
