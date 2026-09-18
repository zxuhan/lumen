import { ACTION_LABELS } from '@/api/sessions'

/**
 * Operations whose results are hard to revert by hand. Instead of a confirmation prompt,
 * the completion toast offers an Undo action: lighter to use, yet still reversible.
 * Casual, easily changed edits like layer transforms and visibility skip the toast.
 */
const UNDOABLE = new Set([
  'split_layers',
  'promote_object_to_layer',
  'remove_background',
  'replace_background',
  'expand_canvas',
  'upscale_image',
  'erase_region',
  'replace_region',
  'adjust_image',
  'crop_canvas',
  'flip_layer',
])

export function toolLabel(tool: string | undefined) {
  if (!tool) return ''
  return ACTION_LABELS[tool] ?? ''
}

export function offersUndo(tool: string | undefined) {
  return Boolean(tool && UNDOABLE.has(tool))
}
