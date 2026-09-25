import { useState } from 'react'

import Button from '@/components/ui/Button'

export default function MessageComposer({
  pending,
  error,
  placeholder = 'Describe the change, e.g. remove background, flip horizontally. Enter to send',
  onSend,
}: {
  pending: boolean
  error?: string | null
  placeholder?: string
  onSend: (text: string) => void
}) {
  const [text, setText] = useState('')
  const canSend = text.trim().length > 0 && !pending

  const submit = () => {
    if (!canSend) return
    onSend(text.trim())
    setText('')
  }

  return (
    <div className="border-line shrink-0 border-t p-3">
      <textarea
        rows={2}
        value={text}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault()
            submit()
          }
        }}
        placeholder={placeholder}
        aria-label="Editing instruction"
        className="border-line text-ink placeholder:text-faint rounded-control focus:border-line-strong w-full resize-none border px-3 py-2 text-xs leading-relaxed outline-none transition-colors"
      />
      <Button variant="solid" block className="mt-2 py-2" disabled={!canSend} onClick={submit}>
        {pending ? 'Thinking…' : 'Send'}
      </Button>
      {error && <p className="text-danger mt-2 text-[11px] leading-relaxed">{error}</p>}
    </div>
  )
}
