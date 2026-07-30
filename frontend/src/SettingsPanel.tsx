import type { ConversationSettings } from './api'

interface SettingsPanelProps {
  settings: ConversationSettings
  availableModels: string[]
  onChange: (patch: Partial<ConversationSettings>) => void
  onClose: () => void
}

function SettingsPanel({ settings, availableModels, onChange, onClose }: SettingsPanelProps) {
  return (
    <div className="absolute right-0 top-12 z-10 w-80 space-y-4 rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900 p-4 shadow-lg">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-neutral-900 dark:text-neutral-100">
          Conversation settings
        </h2>
        <button
          type="button"
          className="text-sm text-neutral-500 dark:text-neutral-400 hover:underline"
          onClick={onClose}
        >
          Close
        </button>
      </div>

      <div className="space-y-1">
        <label className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
          Model
        </label>
        <select
          className="w-full rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-2 py-1.5 text-sm"
          value={settings.model ?? ''}
          onChange={(e) => onChange({ model: e.target.value || null })}
        >
          <option value="">Default</option>
          {availableModels.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1">
        <label className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
          Temperature: {(settings.temperature ?? 1.0).toFixed(1)}
        </label>
        <input
          type="range"
          min={0}
          max={2}
          step={0.1}
          value={settings.temperature ?? 1.0}
          onChange={(e) => onChange({ temperature: Number(e.target.value) })}
          className="w-full"
        />
      </div>

      <div className="space-y-1">
        <label className="text-xs font-medium text-neutral-500 dark:text-neutral-400">
          System prompt
        </label>
        <textarea
          className="w-full resize-none rounded-lg border border-neutral-300 dark:border-neutral-700 bg-transparent px-2 py-1.5 text-sm"
          rows={4}
          placeholder="e.g. You are a terse, no-nonsense assistant."
          value={settings.system_prompt ?? ''}
          onChange={(e) => onChange({ system_prompt: e.target.value || null })}
        />
      </div>
    </div>
  )
}

export default SettingsPanel
