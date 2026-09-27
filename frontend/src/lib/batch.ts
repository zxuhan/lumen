import type { Ratio } from '@/api/runs'

export type BatchTool =
  | 'remove_background'
  | 'replace_background'
  | 'adjust_image'
  | 'upscale_image'
  | 'expand_canvas'
  | 'prepare_delivery_sizes'

export type BatchOp = {
  tool: BatchTool
  params: Record<string, unknown>
}

export const BATCH_STEPS: { id: BatchTool; label: string; hint: string }[] = [
  { id: 'remove_background', label: 'Remove background', hint: 'Remove the background, keep the subject' },
  { id: 'replace_background', label: 'Replace background', hint: 'Replace the background from a description' },
  { id: 'adjust_image', label: 'Adjust colors', hint: 'Brightness, contrast, saturation' },
  { id: 'upscale_image', label: 'Upscale', hint: 'Increase resolution' },
  { id: 'expand_canvas', label: 'Expand image', hint: 'Extend to a chosen ratio' },
  { id: 'prepare_delivery_sizes', label: 'Ad sizes', hint: 'Fit fully into 1:1 / 4:5 / 9:16' },
]

export const EXPAND_RATIOS: Ratio[] = ['1:1', '4:5', '9:16', '16:9']

export type BatchDraft = {
  selected: BatchTool[]
  prompt: string
  brightness: number
  contrast: number
  saturation: number
  scale: 2 | 4
  expandRatio: Ratio
  delivery: Ratio[]
  formats: Array<'png' | 'jpg'>
}

export const EMPTY_DRAFT: BatchDraft = {
  selected: ['remove_background'],
  prompt: '',
  brightness: 0,
  contrast: 0,
  saturation: 0,
  scale: 2,
  expandRatio: '16:9',
  delivery: ['1:1', '4:5', '9:16'],
  formats: ['png'],
}

export function operationsOf(draft: BatchDraft): BatchOp[] {
  return draft.selected.map((tool) => {
    if (tool === 'replace_background') return { tool, params: { prompt: draft.prompt.trim() } }
    if (tool === 'adjust_image') {
      return {
        tool,
        params: {
          brightness: draft.brightness,
          contrast: draft.contrast,
          saturation: draft.saturation,
        },
      }
    }
    if (tool === 'upscale_image') return { tool, params: { scale: draft.scale } }
    if (tool === 'expand_canvas') return { tool, params: { ratio: draft.expandRatio } }
    if (tool === 'prepare_delivery_sizes') return { tool, params: { ratios: draft.delivery } }
    return { tool, params: {} }
  })
}

export function draftReady(draft: BatchDraft, assetCount: number): string | null {
  if (assetCount === 0) return 'Select at least one image first'
  if (draft.selected.length === 0) return 'Check at least one processing step first'
  if (draft.selected.includes('replace_background') && !draft.prompt.trim()) {
    return 'Replace background needs a description'
  }
  if (draft.selected.includes('prepare_delivery_sizes') && draft.delivery.length === 0) {
    return 'Pick at least one ratio for ad sizes'
  }
  if (draft.formats.length === 0) return 'Choose at least one export format'
  return null
}
