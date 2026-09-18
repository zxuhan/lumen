import { useEffect, useState } from 'react'

import type { Asset } from '@/api/assets'
import { ACTION_LABELS, type Layer, type SessionDetail } from '@/api/sessions'
import { BackgroundForm, ExpandForm, ReplaceForm } from '@/components/editor/GenerateEdits'
import Button from '@/components/ui/Button'
import { useSessionHistory, type SessionTools } from '@/hooks/useSessions'
import { formatBytes, formatDateTime } from '@/lib/format'
import { wallOnly } from '@/lib/layers'
import { useEditorUi, type Panel } from '@/stores/editorUi'

const ADJUST_FIELDS: { key: string; label: string; min?: number }[] = [
  { key: 'brightness', label: 'Brightness' },
  { key: 'contrast', label: 'Contrast' },
  { key: 'highlights', label: 'Highlights' },
  { key: 'shadows', label: 'Shadows' },
  { key: 'temperature', label: 'Temperature' },
  { key: 'tint', label: 'Tint' },
  { key: 'saturation', label: 'Saturation' },
  { key: 'vibrance', label: 'Vibrance' },
  { key: 'sharpness', label: 'Sharpness' },
  { key: 'clarity', label: 'Clarity' },
  { key: 'vignette', label: 'Vignette', min: 0 },
]

const REORDER_LABELS = {
  top: 'Top',
  up: 'Up',
  down: 'Down',
  bottom: 'Bottom',
} as const

export default function LayerPanel({
  session,
  tools,
  panel,
}: {
  session: SessionDetail
  tools: SessionTools
  // Passed in from outside so the original form still renders during the close animation instead of collapsing halfway first
  panel: Panel
}) {
  const current = session.assets.find((asset) => asset.id === session.current_asset_id)
  const { data: history = [] } = useSessionHistory(session.id)
  const selectedLayerId = useEditorUi((state) => state.selectedLayerId)
  const selectLayer = useEditorUi((state) => state.selectLayer)
  const selection = useEditorUi((state) => state.selection)
  const includeText = useEditorUi((state) => state.splitIncludeText)
  const setIncludeText = useEditorUi((state) => state.setSplitIncludeText)
  const selected =
    session.document.layers.find((layer) => layer.id === selectedLayerId) ??
    session.document.layers.at(-1)
  const onlyToWall = wallOnly(session.document)

  return (
    <aside className="border-line bg-paper scrollbar-slim h-full w-72 shrink-0 overflow-y-auto border-l">
      {panel === 'adjust' && (
        <AdjustForm
          disabled={tools.busy}
          onApply={(params) =>
            tools.invoke('adjust_image', { ...params, layer_id: selectedLayerId })
          }
        />
      )}
      {panel === 'background' && (
        <BackgroundForm
          disabled={tools.busy}
          wallOnly={onlyToWall}
          onApply={(params) => tools.invoke('replace_background', params)}
        />
      )}
      {panel === 'expand' && (
        <ExpandForm
          disabled={tools.busy}
          wallOnly={onlyToWall}
          onApply={(params) => tools.invoke('expand_canvas', params)}
        />
      )}
      {panel === 'replace' && (
        <ReplaceForm
          disabled={tools.busy || !selection}
          onApply={(params) =>
            tools.invoke('replace_region', {
              ...params,
              mask_asset_id: selection?.maskId,
              revision: session.revision,
              layer_id: selectedLayerId,
            })
          }
        />
      )}

      <Section title="Layers">
        <label className="text-muted mb-2 flex items-center gap-1.5 text-[11px]">
          <input
            type="checkbox"
            checked={includeText}
            disabled={tools.busy}
            onChange={(event) => setIncludeText(event.target.checked)}
          />
          Also split out text
        </label>
        <div className="mb-2.5 flex gap-1">
          <Button
            variant="outline"
            size="sm"
            block
            disabled={tools.busy}
            progress={tools.isRunning('split_layers') ? tools.pendingProgress : null}
            title={includeText ? 'Split into background, subject, and text (can be undone)' : 'Split into background and subject (can be undone)'}
            onClick={() => tools.invoke('split_layers', { include_text: includeText })}
          >
            Split layers
          </Button>
          <Button
            variant="outline"
            size="sm"
            block
            disabled={tools.busy || !selection}
            progress={tools.isRunning('promote_object_to_layer') ? tools.pendingProgress : null}
            title={selection ? 'Extract the selection to its own layer (can be undone)' : 'Click or paint a selection first'}
            onClick={() =>
              tools.invoke('promote_object_to_layer', {
                mask_asset_id: selection?.maskId,
                revision: session.revision,
              })
            }
          >
            To layer
          </Button>
        </div>
        <ul className="space-y-1">
          {[...session.document.layers].reverse().map((layer) => (
            <LayerRow
              key={layer.id}
              layer={layer}
              active={selected?.id === layer.id}
              disabled={tools.busy}
              thumb={layer.asset_id ? session.assets.find((asset) => asset.id === layer.asset_id) : undefined}
              onSelect={() => selectLayer(layer.id)}
              onToggleVisible={() =>
                tools.invoke('set_layer_visible', {
                  layer_id: layer.id,
                  visible: !layer.visible,
                })
              }
            />
          ))}
        </ul>
      </Section>

      {selected?.kind === 'text' && (
        <Section title="Text">
          <p className="text-faint mb-2.5 text-[11px] leading-relaxed">
            Edit the copy, font size, or color. Changes are saved when the field loses focus and can be undone with ⌘Z. You can also double-click a text layer on the canvas to edit it.
          </p>
          <TextForm
            layer={selected}
            disabled={tools.busy}
            onCommit={(params) =>
              tools.invoke('set_layer_text', { layer_id: selected.id, ...params })
            }
          />
        </Section>
      )}

      {selected && (
        <Section title="Transform">
          <p className="text-faint mb-2.5 text-[11px] leading-relaxed">
            With a layer selected, drag a corner to scale it and drag on the canvas to move it. The sliders work too; changes are saved on release and can be undone with ⌘Z.
          </p>
          <LayerControls
            layer={selected}
            disabled={tools.busy}
            onOpacity={(opacity) =>
              tools.invoke('set_layer_opacity', {
                layer_id: selected.id,
                opacity,
              })
            }
            onScale={(scale) =>
              tools.invoke('scale_layer', {
                layer_id: selected.id,
                scale_x: scale,
                scale_y: scale,
              })
            }
            onRotate={(rotation) =>
              tools.invoke('rotate_layer', { layer_id: selected.id, rotation })
            }
            onReorder={(place) => tools.invoke('reorder_layer', { layer_id: selected.id, place })}
          />
        </Section>
      )}

      <Section title="Properties">
        <Properties document={session.document} current={current} revision={session.revision} />
      </Section>

      <Section title="Edit history">
        {history.length === 0 ? (
          <p className="text-faint text-xs">No history yet</p>
        ) : (
          <ol className="space-y-1.5">
            {history.map((entry) => (
              <li key={entry.seq} className="flex items-baseline justify-between gap-2 text-xs">
                <span className="text-ink">{ACTION_LABELS[entry.action] ?? entry.action}</span>
                <span className="text-faint shrink-0 tabular-nums">
                  {formatDateTime(entry.created_at)}
                </span>
              </li>
            ))}
          </ol>
        )}
      </Section>
    </aside>
  )
}

function LayerRow({
  layer,
  active,
  disabled,
  thumb,
  onSelect,
  onToggleVisible,
}: {
  layer: Layer
  active: boolean
  disabled: boolean
  thumb?: Asset
  onSelect: () => void
  onToggleVisible: () => void
}) {
  return (
    <li
      className={`rounded-control flex items-center border transition-all duration-150 ${
        active ? 'border-brand bg-brand-soft' : 'border-line hover:border-line-strong hover:bg-soft'
      } ${layer.visible ? '' : 'opacity-50'}`}
    >
      <button
        type="button"
        onClick={onSelect}
        className="flex min-w-0 flex-1 items-center gap-2 px-2 py-1.5 text-left"
      >
        <span className="bg-canvas border-line rounded-chip size-8 shrink-0 overflow-hidden border">
          {thumb ? (
            <img src={thumb.url} alt="" className="size-full object-cover" />
          ) : (
            <span className="text-faint grid size-full place-items-center text-[10px]">
              {layer.kind === 'text' ? 'T' : ''}
            </span>
          )}
        </span>
        <span className="min-w-0 flex-1">
          <span className="text-ink block truncate text-xs font-medium">{layer.name}</span>
          <span className="text-faint block truncate text-[10px]">
            {layer.kind === 'text'
              ? layer.text || 'Text'
              : layer.locked
                ? 'Locked'
                : 'Image'}
          </span>
        </span>
        <span className="text-faint shrink-0 text-[10px] tabular-nums">
          {Math.round(layer.opacity * 100)}%
        </span>
      </button>
      <Button
        variant="icon"
        size="sm"
        disabled={disabled}
        title={layer.visible ? 'Hide layer' : 'Show layer'}
        onClick={onToggleVisible}
        className="mr-1.5 shrink-0"
      >
        <EyeIcon open={layer.visible} />
      </Button>
    </li>
  )
}

function EyeIcon({ open }: { open: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
      <path
        d="M1.5 8s2.4-4.5 6.5-4.5S14.5 8 14.5 8 12.1 12.5 8 12.5 1.5 8 1.5 8Z"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinejoin="round"
      />
      {open ? (
        <circle cx="8" cy="8" r="1.7" fill="currentColor" />
      ) : (
        <path d="M3 13 13 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
      )}
    </svg>
  )
}

const TEXT_FIELD =
  'border-line text-ink placeholder:text-faint rounded-control focus:border-line-strong w-full resize-none border px-2.5 py-1.5 text-xs leading-relaxed outline-none'

function toHex6(value: string) {
  const raw = value.replace('#', '')
  if (raw.length === 3) return `#${[...raw].map((ch) => ch + ch).join('')}`
  return `#${raw.padEnd(6, '0')}`.slice(0, 7)
}

function TextForm({
  layer,
  disabled,
  onCommit,
}: {
  layer: Layer
  disabled: boolean
  onCommit: (params: { text: string; font_size: number; fill: string }) => void
}) {
  const [text, setText] = useState(layer.text || '')
  const [fontSize, setFontSize] = useState(layer.font_size ?? 24)
  const [fill, setFill] = useState(toHex6(layer.fill ?? '#141414'))
  const setLayerPreview = useEditorUi((state) => state.setLayerPreview)

  useEffect(() => {
    setText(layer.text || '')
    setFontSize(layer.font_size ?? 24)
    setFill(toHex6(layer.fill ?? '#141414'))
  }, [layer.id, layer.text, layer.font_size, layer.fill])

  const current = {
    text: layer.text || '',
    font_size: layer.font_size ?? 24,
    fill: toHex6(layer.fill ?? '#141414'),
  }

  const commit = (next: { text: string; font_size: number; fill: string }) => {
    if (
      next.text === current.text &&
      next.font_size === current.font_size &&
      next.fill.toLowerCase() === current.fill.toLowerCase()
    ) {
      return
    }
    onCommit(next)
  }

  return (
    <div className="space-y-3">
      <textarea
        rows={3}
        value={text}
        disabled={disabled}
        className={TEXT_FIELD}
        onChange={(event) => {
          const next = event.target.value
          setText(next)
          setLayerPreview({ id: layer.id, text: next })
        }}
        onBlur={() => commit({ text, font_size: fontSize, fill })}
        onKeyDown={(event) => {
          if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
            event.preventDefault()
            commit({ text, font_size: fontSize, fill })
          }
        }}
      />
      <SliderField
        label="Font size"
        value={fontSize}
        origin={layer.font_size ?? 24}
        min={8}
        max={120}
        step={1}
        format={(value) => `${Math.round(value)}`}
        disabled={disabled}
        onInput={(value) => {
          setFontSize(value)
          setLayerPreview({ id: layer.id, font_size: value })
        }}
        onCommit={(value) => {
          setFontSize(value)
          commit({ text, font_size: value, fill })
        }}
      />
      <label className="flex items-center justify-between gap-2 text-[11px]">
        <span className="text-muted">Color</span>
        <input
          type="color"
          value={fill}
          disabled={disabled}
          className="border-line h-7 w-12 cursor-pointer rounded border bg-transparent p-0"
          onChange={(event) => {
            const next = event.target.value
            setFill(next)
            setLayerPreview({ id: layer.id, fill: next })
            commit({ text, font_size: fontSize, fill: next })
          }}
        />
      </label>
    </div>
  )
}

function LayerControls({
  layer,
  disabled,
  onOpacity,
  onScale,
  onRotate,
  onReorder,
}: {
  layer: Layer
  disabled: boolean
  onOpacity: (value: number) => void
  onScale: (value: number) => void
  onRotate: (value: number) => void
  onReorder: (place: 'top' | 'bottom' | 'up' | 'down') => void
}) {
  const preview = useEditorUi((state) => state.layerPreview)
  const setLayerPreview = useEditorUi((state) => state.setLayerPreview)
  const scale = Math.abs(layer.transform.scale_x)

  // Drop the preview only after the document catches up, so selecting/writing back doesn't snap the layer to its old position
  useEffect(() => {
    if (!preview || preview.id !== layer.id) return
    const same =
      (preview.opacity === undefined || preview.opacity === layer.opacity) &&
      (preview.scale === undefined || Math.abs(preview.scale - scale) < 0.001) &&
      (preview.rotation === undefined || preview.rotation === layer.transform.rotation) &&
      (preview.x === undefined || Math.abs(preview.x - layer.transform.x) < 0.5) &&
      (preview.y === undefined || Math.abs(preview.y - layer.transform.y) < 0.5) &&
      (preview.text === undefined || preview.text === (layer.text || '')) &&
      (preview.font_size === undefined || preview.font_size === (layer.font_size ?? 24)) &&
      (preview.fill === undefined ||
        preview.fill.toLowerCase() === (layer.fill ?? '#141414').toLowerCase())
    if (same) setLayerPreview(null)
  }, [
    preview,
    scale,
    setLayerPreview,
    layer.id,
    layer.opacity,
    layer.transform.scale_x,
    layer.transform.rotation,
    layer.transform.x,
    layer.transform.y,
  ])

  useEffect(() => () => setLayerPreview(null), [setLayerPreview])

  return (
    <div className="space-y-3">
      <SliderField
        label="Opacity"
        value={layer.opacity}
        origin={1}
        min={0}
        max={1}
        step={0.01}
        format={(value) => `${Math.round(value * 100)}%`}
        disabled={disabled}
        onInput={(opacity) => setLayerPreview({ id: layer.id, opacity })}
        onCommit={onOpacity}
      />
      <SliderField
        label="Layer scale"
        value={scale}
        origin={1}
        min={0.1}
        max={3}
        step={0.05}
        format={(value) => `${Math.round(value * 100)}%`}
        disabled={disabled}
        onInput={(value) => setLayerPreview({ id: layer.id, scale: value })}
        onCommit={onScale}
      />
      <SliderField
        label="Rotation"
        value={layer.transform.rotation}
        origin={0}
        min={-180}
        max={180}
        step={1}
        format={(value) => `${Math.round(value)}°`}
        disabled={disabled}
        onInput={(rotation) => setLayerPreview({ id: layer.id, rotation })}
        onCommit={onRotate}
      />
      <div className="grid grid-cols-4 gap-1">
        {(['top', 'up', 'down', 'bottom'] as const).map((place) => (
          <Button
            key={place}
            variant="outline"
            size="sm"
            block
            disabled={disabled}
            onClick={() => onReorder(place)}
          >
            {REORDER_LABELS[place]}
          </Button>
        ))}
      </div>
    </div>
  )
}

function AdjustForm({
  disabled,
  onApply,
}: {
  disabled: boolean
  onApply: (params: Record<string, number>) => void
}) {
  const [values, setValues] = useState<Record<string, number>>({})
  const setAdjustPreview = useEditorUi((state) => state.setAdjustPreview)
  const touched = Object.keys(values).length > 0

  useEffect(() => () => setAdjustPreview(null), [setAdjustPreview])

  const clear = () => {
    setValues({})
    setAdjustPreview(null)
  }

  return (
    <Section title="Adjust colors">
      <p className="text-faint mb-2.5 text-[11px] leading-relaxed">
        Dragging previews on the canvas; sharpness and clarity only show after applying. Apply saves a new version, which can be undone.
      </p>
      <div className="space-y-2.5">
        {ADJUST_FIELDS.map((field) => (
          <SliderField
            key={field.key}
            label={field.label}
            value={values[field.key] ?? 0}
            origin={0}
            min={field.min ?? -1}
            max={1}
            step={0.05}
            format={(value) => value.toFixed(2)}
            disabled={disabled}
            onInput={(value) => setAdjustPreview({ ...values, [field.key]: value })}
            onCommit={(value) => {
              const next = { ...values, [field.key]: value }
              setValues(next)
              setAdjustPreview(next)
            }}
          />
        ))}
        <div className="flex gap-2">
          <Button variant="outline" block disabled={disabled || !touched} onClick={clear}>
            Reset
          </Button>
          <Button
            variant="solid"
            block
            disabled={disabled || !touched}
            title={touched ? 'Apply the current adjustments (can be undone)' : 'Drag a slider before applying'}
            onClick={() => {
              onApply(values)
              clear()
            }}
          >
            Apply
          </Button>
        </div>
      </div>
    </Section>
  )
}

function SliderField({
  label,
  value,
  origin,
  min,
  max,
  step,
  format,
  disabled,
  onInput,
  onCommit,
}: {
  label: string
  value: number
  origin: number
  min: number
  max: number
  step: number
  format: (value: number) => string
  disabled: boolean
  onInput: (value: number) => void
  onCommit: (value: number) => void
}) {
  const [draft, setDraft] = useState<number | null>(null)

  const commit = () => {
    if (draft !== null && draft !== value) onCommit(draft)
    setDraft(null)
  }

  return (
    <label
      className="block select-none"
      title="Double-click to reset"
      onDoubleClick={() => {
        setDraft(null)
        if (value !== origin) onCommit(origin)
      }}
    >
      <span className="mb-1 flex justify-between text-[11px]">
        <span className="text-muted">{label}</span>
        <span className="text-ink tabular-nums">{format(draft ?? value)}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        value={draft ?? value}
        onChange={(event) => {
          const next = Number(event.target.value)
          setDraft(next)
          onInput(next)
        }}
        onPointerDown={(event) => event.currentTarget.setPointerCapture(event.pointerId)}
        onPointerUp={commit}
        onLostPointerCapture={commit}
      />
    </label>
  )
}

function Properties({
  document,
  current,
  revision,
}: {
  document: { width: number; height: number }
  current: Asset | undefined
  revision: number
}) {
  const rows: [string, string][] = [
    ['Canvas', `${document.width} × ${document.height}`],
    ['Revision', String(revision)],
  ]
  if (current) {
    rows.push(['Format', current.image_format])
    rows.push(['Size', formatBytes(current.size_bytes)])
    rows.push(['Alpha channel', current.has_alpha ? 'Yes' : 'No'])
  }

  return (
    <dl className="space-y-1.5 text-xs">
      {rows.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-2">
          <dt className="text-muted">{label}</dt>
          <dd className="text-ink tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-line border-b px-4 py-4 last:border-b-0">
      <h2 className="text-muted mb-2.5 text-xs font-medium">{title}</h2>
      {children}
    </section>
  )
}
