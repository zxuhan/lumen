import { useRef, useState } from 'react'

import { ACCEPTED_TYPES } from '@/api/assets'
import { checkFile } from '@/hooks/useAssets'

type Props = {
  onFile: (file: File) => void
  disabled?: boolean
  hint?: string
  multiple?: boolean
}

export default function ImageDropzone({ onFile, disabled, hint, multiple }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const accept = (file: File | undefined) => {
    if (!file) return
    const problem = checkFile(file)
    setError(problem)
    if (!problem) onFile(file)
  }

  return (
    <div>
      <button
        type="button"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          const files = Array.from(event.dataTransfer.files)
          if (multiple) files.forEach((file) => accept(file))
          else accept(files[0])
        }}
        className={`flex w-full flex-col items-center gap-1.5 rounded-[18px] border border-dashed px-6 py-10 transition-colors disabled:opacity-50 ${
          dragging ? 'border-brand bg-brand-soft' : 'border-line-strong bg-paper hover:border-brand'
        }`}
      >
        <span className="text-ink text-sm font-medium">
          {disabled ? 'Uploading…' : multiple ? 'Drop images here, or click to choose' : 'Drop an image here, or click to choose'}
        </span>
        <span className="text-faint text-xs">{hint ?? 'JPG / PNG / WebP, up to 20 MB each'}</span>
      </button>

      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED_TYPES.join(',')}
        multiple={multiple}
        hidden
        onChange={(event) => {
          const files = Array.from(event.target.files ?? [])
          if (multiple) files.forEach((file) => accept(file))
          else accept(files[0])
          event.target.value = ''
        }}
      />

      {error && <p className="text-danger mt-2 text-sm">{error}</p>}
    </div>
  )
}
