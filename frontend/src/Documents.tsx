import { useRef, useState } from 'react'
import type { DocumentSummary } from './api'

interface DocumentsProps {
  documents: DocumentSummary[]
  onUpload: (file: File) => Promise<void>
  onDelete: (documentId: number) => void
}

export default function Documents({ documents, onUpload, onDelete }: DocumentsProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return

    setUploading(true)
    setError(null)
    try {
      await onUpload(file)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 py-2 text-xs">
      {documents.map((doc) => (
        <span
          key={doc.id}
          className="flex items-center gap-1 rounded-full bg-neutral-100 dark:bg-neutral-800 px-2 py-1 text-neutral-700 dark:text-neutral-300"
        >
          {doc.filename}
          <button
            type="button"
            className="text-neutral-400 hover:text-neutral-700 dark:hover:text-neutral-100"
            onClick={() => onDelete(doc.id)}
            aria-label={`Remove ${doc.filename}`}
          >
            ×
          </button>
        </span>
      ))}

      <button
        type="button"
        className="rounded-full border border-dashed border-neutral-300 dark:border-neutral-700 px-2 py-1 text-neutral-500 dark:text-neutral-400 hover:bg-neutral-100 dark:hover:bg-neutral-800 disabled:opacity-50"
        onClick={() => inputRef.current?.click()}
        disabled={uploading}
      >
        {uploading ? 'Uploading…' : '+ Attach file'}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".txt,.md,.pdf"
        className="hidden"
        onChange={handleFileChange}
      />

      {error && <span className="text-red-500">{error}</span>}
    </div>
  )
}
