import { useState } from 'react'
import { Link } from 'react-router-dom'

import type { SessionDetail } from '@/api/sessions'
import Button from '@/components/ui/Button'
import { buttonClass } from '@/components/ui/buttonStyles'
import type { SessionSelection } from '@/hooks/useSelection'
import type { SessionTools } from '@/hooks/useSessions'
import { wallOnly } from '@/lib/layers'
import { ZOOM_STEP, useCanvasView } from '@/stores/canvasView'
import { useEditorUi, type CropRatio } from '@/stores/editorUi'

const CROP_RATIOS: { value: CropRatio; label: string }[] = [
  { value: 'free', label: 'Free' },
  { value: '1:1', label: '1:1' },
  { value: '4:5', label: '4:5' },
  { value: '9:16', label: '9:16' },
  { value: '16:9', label: '16:9' },
]

export default function EditorToolbar({
  session,
  tools,
  picking,
  onRename,
}: {
  session: SessionDetail
  tools: SessionTools
  picking: SessionSelection
  onRename: (title: string) => void
}) {
  const scale = useCanvasView((state) => state.scale)
  const fit = useCanvasView((state) => state.fit)
  const stepZoom = useCanvasView((state) => state.stepZoom)
  const zoomTo = useCanvasView((state) => state.zoomTo)
  const ui = useEditorUi()

  // Only the button that started the run shows a percentage; the other buttons are simply disabled
  const running = (tool: string, match?: (params: Record<string, unknown>) => boolean) =>
    tools.isRunning(tool, match) ? tools.pendingProgress : null

  const confirmCrop = () => {
    if (!ui.cropRect) return
    tools.invoke('crop_canvas', {
      rect: {
        x: ui.cropRect.x / session.document.width,
        y: ui.cropRect.y / session.document.height,
        width: ui.cropRect.width / session.document.width,
        height: ui.cropRect.height / session.document.height,
      },
    })
    ui.closeCrop()
  }

  return (
    <header className="border-line bg-paper scrollbar-slim flex h-14 shrink-0 items-center gap-2 overflow-x-auto border-b px-3">
      <TitleField value={session.title} onCommit={onRename} />

      <span className="text-faint hidden shrink-0 text-xs tabular-nums sm:block">
        {session.document.width} × {session.document.height}
      </span>

      <div className="ml-1 flex shrink-0 items-center gap-1">
        {ui.selectMode ? (
          <>
            <Button
              active={ui.selectMode === 'point'}
              title="Click an object to select it"
              onClick={() => ui.setSelectMode(ui.selectMode === 'point' ? null : 'point')}
            >
              Select
            </Button>
            <Button
              active={ui.selectMode === 'brush'}
              title="Paint a selection"
              onClick={() => ui.setSelectMode(ui.selectMode === 'brush' ? null : 'brush')}
            >
              Brush
            </Button>
            <Button
              disabled={tools.busy || picking.busy || !picking.selection}
              progress={running('erase_region')}
              title={picking.selection ? 'Erase the selected area' : 'Click or paint a selection first'}
              onClick={() =>
                tools.invoke('erase_region', {
                  mask_asset_id: picking.selection?.maskId,
                  revision: session.revision,
                  layer_id: ui.selectedLayerId,
                })
              }
            >
              Erase
            </Button>
            <Button
              disabled={!picking.selection}
              active={ui.panel === 'replace'}
              title={picking.selection ? 'Replace the selection from a description' : 'Click or paint a selection first'}
              onClick={() => ui.setPanel(ui.panel === 'replace' ? null : 'replace')}
            >
              Replace
            </Button>
            <Button
              disabled={tools.busy || picking.busy || !picking.selection}
              progress={running('promote_object_to_layer')}
              title={picking.selection ? 'Extract the selection to its own layer (can be undone)' : 'Click or paint a selection first'}
              onClick={() =>
                tools.invoke('promote_object_to_layer', {
                  mask_asset_id: picking.selection?.maskId,
                  revision: session.revision,
                })
              }
            >
              To layer
            </Button>
            <Button
              disabled={!picking.selection || picking.busy}
              title="Clear the current selection"
              onClick={picking.clear}
            >
              Clear
            </Button>
            <Button title="Exit selection (Esc)" onClick={() => ui.setSelectMode(null)}>
              Done
            </Button>
          </>
        ) : ui.cropOpen ? (
          <>
            {CROP_RATIOS.map((item) => (
              <Button
                key={item.value}
                active={ui.cropRatio === item.value}
                title={item.value === 'free' ? 'Free crop' : `Crop to ${item.label}`}
                onClick={() => ui.setCropRatio(item.value, session.document)}
              >
                {item.label}
              </Button>
            ))}
            <Button title="Crop the canvas to the current box (can be undone)" onClick={confirmCrop}>
              Apply
            </Button>
            <Button title="Exit crop (Esc)" onClick={ui.closeCrop}>
              Cancel
            </Button>
          </>
        ) : (
          <>
            <Button
              disabled={tools.busy}
              active={ui.cropOpen}
              title="Crop the canvas to a ratio"
              onClick={() => ui.openCrop(session.document)}
            >
              Crop
            </Button>
            <Button
              disabled={tools.busy}
              progress={running('flip_layer', (params) => params.direction === 'horizontal')}
              title="Flip the current layer horizontally"
              onClick={() =>
                tools.invoke('flip_layer', {
                  direction: 'horizontal',
                  layer_id: ui.selectedLayerId,
                })
              }
            >
              Flip H
            </Button>
            <Button
              disabled={tools.busy}
              progress={running('flip_layer', (params) => params.direction === 'vertical')}
              title="Flip the current layer vertically"
              onClick={() =>
                tools.invoke('flip_layer', {
                  direction: 'vertical',
                  layer_id: ui.selectedLayerId,
                })
              }
            >
              Flip V
            </Button>
            <Button
              disabled={tools.busy}
              progress={running('remove_background')}
              title="Cut out the subject and make the background transparent"
              onClick={() => tools.invoke('remove_background', { layer_id: ui.selectedLayerId })}
            >
              Remove BG
            </Button>
            <Button
              disabled={tools.busy}
              active={ui.panel === 'background'}
              title="Replace the background from a description"
              onClick={() => ui.setPanel(ui.panel === 'background' ? null : 'background')}
            >
              Replace BG
            </Button>
            <Button
              disabled={tools.busy}
              active={ui.panel === 'expand'}
              title="Expand the canvas to a new ratio"
              onClick={() => ui.setPanel(ui.panel === 'expand' ? null : 'expand')}
            >
              Expand
            </Button>
            <Button
              disabled={tools.busy}
              progress={running('upscale_image')}
              title={
                wallOnly(session.document)
                  ? 'Upscale 2×. The image is split into layers, so the result only goes to the image wall'
                  : 'Upscale the current canvas 2×'
              }
              onClick={() => tools.invoke('upscale_image', { scale: 2 })}
            >
              Upscale
            </Button>
            <Button
              active={ui.panel === 'adjust'}
              title="Adjust brightness, contrast, and color"
              onClick={() => ui.setPanel(ui.panel === 'adjust' ? null : 'adjust')}
            >
              Adjust
            </Button>
            <Button
              disabled={tools.busy}
              progress={running('split_layers')}
              title="Split into background and subject; to include text, check it in the Layers panel (can be undone)"
              onClick={() => tools.invoke('split_layers', { include_text: ui.splitIncludeText })}
            >
              Split
            </Button>
            <Button
              disabled={tools.busy}
              title="Click an object to make a selection"
              onClick={() => ui.setSelectMode('point')}
            >
              Select
            </Button>
            <Button
              disabled={tools.busy}
              title="Paint to make a selection"
              onClick={() => ui.setSelectMode('brush')}
            >
              Brush
            </Button>
          </>
        )}
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-1">
        <Button
          disabled={tools.busy || picking.busy || !(picking.canUndo || session.can_undo)}
          title={
            picking.canUndo
              ? 'Undo selection ⌘Z'
              : session.can_undo
                ? 'Undo last step ⌘Z'
                : 'Nothing to undo'
          }
          onClick={() => (picking.canUndo ? picking.undo() : tools.undo())}
        >
          Undo
        </Button>
        <Button
          disabled={tools.busy || picking.busy || !(picking.canRedo || session.can_redo)}
          title={
            picking.canRedo
              ? 'Redo selection ⌘⇧Z'
              : session.can_redo
                ? 'Redo ⌘⇧Z'
                : 'Nothing to redo'
          }
          onClick={() => (picking.canRedo ? picking.redo() : tools.redo())}
        >
          Redo
        </Button>
        <Button
          active={ui.compareOpen}
          disabled={!session.previous_document}
          title={session.previous_document ? 'Compare with the previous version' : 'No previous version yet'}
          onClick={() => ui.setCompareOpen(!ui.compareOpen)}
        >
          Compare
        </Button>

        <div className="border-line rounded-control ml-1 flex items-center gap-0.5 border p-0.5">
          <Button
            variant="icon"
            size="sm"
            title="Zoom out -"
            onClick={() => stepZoom(1 / ZOOM_STEP)}
          >
            −
          </Button>
          <Button
            size="sm"
            title="Actual pixels · press 1"
            className="w-12 tabular-nums"
            onClick={() => zoomTo(1)}
          >
            {Math.round(scale * 100)}%
          </Button>
          <Button variant="icon" size="sm" title="Zoom in +" onClick={() => stepZoom(ZOOM_STEP)}>
            +
          </Button>
          <Button
            size="sm"
            title="Fit to window · press 0, or double-click the canvas"
            onClick={() => fit(session.document)}
          >
            Fit
          </Button>
        </div>

        <Link to={`/marketing/${session.id}`} title="Export marketing images and ad sizes" className={buttonClass()}>
          Export
        </Link>
        <Button
          active={ui.panel === 'layers'}
          title="Layers, transforms, and edit history"
          onClick={() => ui.setPanel(ui.panel === 'layers' ? null : 'layers')}
        >
          Layers
        </Button>
      </div>
    </header>
  )
}

function TitleField({ value, onCommit }: { value: string; onCommit: (title: string) => void }) {
  const [draft, setDraft] = useState<string | null>(null)

  const commit = () => {
    const next = draft?.trim()
    setDraft(null)
    if (next && next !== value) onCommit(next)
  }

  return (
    <input
      value={draft ?? value}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === 'Enter') event.currentTarget.blur()
        if (event.key === 'Escape') setDraft(null)
      }}
      aria-label="Session title"
      className="text-ink hover:bg-soft focus:bg-soft rounded-chip w-28 shrink-0 px-2 py-1 text-sm font-medium transition-colors duration-150 outline-none sm:w-40"
    />
  )
}
