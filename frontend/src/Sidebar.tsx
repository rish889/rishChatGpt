import type { ConversationSummary } from './api'

interface SidebarProps {
  conversations: ConversationSummary[]
  currentConversationId: number | null
  onSelect: (id: number) => void
  onNewChat: () => void
  onLogOut: () => void
}

function Sidebar({
  conversations,
  currentConversationId,
  onSelect,
  onNewChat,
  onLogOut,
}: SidebarProps) {
  return (
    <aside className="w-64 shrink-0 border-r border-neutral-200 dark:border-neutral-800 flex flex-col">
      <div className="p-3">
        <button
          type="button"
          className="w-full rounded-xl border border-neutral-300 dark:border-neutral-700 px-3 py-2 text-sm font-medium hover:bg-neutral-100 dark:hover:bg-neutral-800"
          onClick={onNewChat}
        >
          + New chat
        </button>
      </div>
      <nav className="flex-1 overflow-y-auto px-2 space-y-1">
        {conversations.map((c) => (
          <button
            key={c.id}
            type="button"
            className={`w-full truncate rounded-lg px-3 py-2 text-left text-sm ${
              c.id === currentConversationId
                ? 'bg-emerald-600/10 text-emerald-700 dark:text-emerald-400'
                : 'text-neutral-700 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800'
            }`}
            onClick={() => onSelect(c.id)}
          >
            {c.title || 'New chat'}
          </button>
        ))}
      </nav>
      <div className="p-3 border-t border-neutral-200 dark:border-neutral-800">
        <button
          type="button"
          className="w-full rounded-xl px-3 py-2 text-left text-sm text-neutral-500 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800"
          onClick={onLogOut}
        >
          Log out
        </button>
      </div>
    </aside>
  )
}

export default Sidebar
