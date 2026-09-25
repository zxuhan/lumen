import { useState } from 'react'

import type { Ratio } from '@/api/runs'
import Button from '@/components/ui/Button'

const RATIOS: { value: Ratio; label: string }[] = [
  { value: '1:1', label: '1:1' },
  { value: '4:5', label: '4:5' },
  { value: '3:4', label: '3:4' },
  { value: '9:16', label: '9:16' },
  { value: '16:9', label: '16:9' },
]

const FIELD =
  'border-line text-ink placeholder:text-faint rounded-control focus:border-line-strong w-full resize-none border px-3 py-2 text-xs leading-relaxed outline-none transition-colors duration-150'

export function BackgroundForm({
  disabled,
  wallOnly,
  onApply,
}: {
  disabled: boolean
  wallOnly: boolean
  onApply: (params: { prompt: string; count: number }) => void
}) {
  const [prompt, setPrompt] = useState('')
  const [count, setCount] = useState(1)
  const ready = prompt.trim().length > 0

  return (
    <section className="border-line border-b px-4 py-4">
      <h2 className="text-muted mb-2.5 text-xs font-medium">Replace background</h2>
      <p className="text-faint mb-2.5 text-[11px] leading-relaxed">
        {wallOnly
          ? 'Describe the new background. The image is split into layers, so the result is flattened and only added to the image wall; click it to use it. The canvas and layers stay unchanged.'
          : 'Describe the new background. A single result goes straight onto the canvas; multiple results go to the image wall, where you click one to use it.'}
      </p>
      <textarea
        rows={3}
        value={prompt}
        disabled={disabled}
        onChange={(event) => setPrompt(event.target.value)}
        placeholder="e.g. light wood tabletop, morning light from the left"
        className={FIELD}
      />
      <div className="mt-2 flex gap-1">
        {[1, 2, 4].map((value) => (
          <Button
            key={value}
            variant="outline"
            size="sm"
            block
            active={count === value}
            disabled={disabled}
            onClick={() => setCount(value)}
          >
            ×{value}
          </Button>
        ))}
      </div>
      <Button
        variant="solid"
        block
        className="mt-3"
        disabled={disabled || !ready}
        onClick={() => {
          onApply({ prompt: prompt.trim(), count })
          setPrompt('')
        }}
      >
        Generate
      </Button>
    </section>
  )
}

export function ExpandForm({
  disabled,
  wallOnly,
  onApply,
}: {
  disabled: boolean
  wallOnly: boolean
  onApply: (params: { ratio: Ratio }) => void
}) {
  const [ratio, setRatio] = useState<Ratio>('16:9')

  return (
    <section className="border-line border-b px-4 py-4">
      <h2 className="text-muted mb-2.5 text-xs font-medium">Expand image</h2>
      <p className="text-faint mb-2.5 text-[11px] leading-relaxed">
        {wallOnly
          ? 'Extends the image to the target ratio, keeping the subject in frame. The image is split into layers, so the result only goes to the image wall; click it to use it. The canvas and layers stay unchanged.'
          : 'Extends the image to the target ratio, keeping the subject in frame, then writes the result back to the canvas.'}
      </p>
      <div className="grid grid-cols-5 gap-1">
        {RATIOS.map((item) => (
          <Button
            key={item.value}
            variant="outline"
            size="sm"
            block
            active={ratio === item.value}
            disabled={disabled}
            onClick={() => setRatio(item.value)}
          >
            {item.label}
          </Button>
        ))}
      </div>
      <Button
        variant="solid"
        block
        className="mt-3"
        disabled={disabled}
        onClick={() => onApply({ ratio })}
      >
        Expand
      </Button>
    </section>
  )
}

export function ReplaceForm({
  disabled,
  onApply,
}: {
  disabled: boolean
  onApply: (params: { prompt: string }) => void
}) {
  const [prompt, setPrompt] = useState('')
  const ready = prompt.trim().length > 0

  return (
    <section className="border-line border-b px-4 py-4">
      <h2 className="text-muted mb-2.5 text-xs font-medium">Replace region</h2>
      <p className="text-faint mb-2.5 text-[11px] leading-relaxed">
        Only the current selection changes. Everything outside it stays as is.
      </p>
      <textarea
        rows={3}
        value={prompt}
        disabled={disabled}
        onChange={(event) => setPrompt(event.target.value)}
        placeholder="e.g. turn the cup into a ceramic mug"
        className={FIELD}
      />
      <Button
        variant="solid"
        block
        className="mt-3"
        disabled={disabled || !ready}
        onClick={() => {
          onApply({ prompt: prompt.trim() })
          setPrompt('')
        }}
      >
        Replace
      </Button>
    </section>
  )
}
