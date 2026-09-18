import type { LayerDocument } from '@/api/sessions'

const BASE = 'base'
const SUBJECT = 'subject'
const BACKGROUND = 'background'

/**
 * Mirrors the backend's `_layered`: once the image is split into layers, or has several image
 * layers, whole-image generation (replace background, expand, upscale) only adds its result to
 * the image wall instead of writing it back to the canvas. The UI uses this to explain where
 * the result went.
 */
export function wallOnly(document: LayerDocument): boolean {
  if (document.layers.filter((layer) => layer.kind === 'image').length > 1) return true
  const ids = new Set(document.layers.map((layer) => layer.id))
  if (ids.has(BACKGROUND) && ids.has(SUBJECT)) return true
  return ids.has(BACKGROUND) && !ids.has(BASE)
}
