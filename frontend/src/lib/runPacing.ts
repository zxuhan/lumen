/**
 * Typical duration of each tool, in seconds. The server reports only a few discrete steps and
 * may stay silent for the whole remote generation, so estimated durations smooth the gaps into
 * continuous progress. Purely for display; never used in any business decision.
 */
const SECONDS: Record<string, number> = {
  crop_canvas: 0.8,
  flip_layer: 0.8,
  rotate_layer: 0.8,
  move_layer: 0.8,
  scale_layer: 0.8,
  set_layer_opacity: 0.8,
  set_layer_visible: 0.8,
  set_layer_text: 0.8,
  reorder_layer: 0.8,
  adjust_image: 2,
  prepare_delivery_sizes: 8,
  remove_background: 10,
  generate_image: 40,
  erase_region: 40,
  replace_region: 40,
  promote_object_to_layer: 40,
  replace_background: 45,
  expand_canvas: 45,
  upscale_image: 45,
  generate_marketing: 45,
  batch_process: 60,
  split_layers: 70,
}

const FALLBACK = 25
// Reaches ~88% at the estimated duration, then keeps approaching the ceiling, so it never fully stalls
const SHAPE = 2.2

/** Display ceiling while running; the last step is reserved for actual completion. */
export const PROGRESS_CEILING = 99

export function pacingSeconds(tool: string | undefined) {
  if (!tool) return FALLBACK
  return SECONDS[tool] ?? FALLBACK
}

export function pacedProgress(elapsedMs: number, seconds: number) {
  const tau = (seconds / SHAPE) * 1000
  return PROGRESS_CEILING * (1 - Math.exp(-elapsedMs / tau))
}
