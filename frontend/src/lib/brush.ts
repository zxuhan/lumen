/** Brush radius as a fraction of the canvas's short side. The frontend sends this same value explicitly so the preview and the server-side mask match in width. */
export const BRUSH_RADIUS = 0.03

export function brushWidth(canvas: { width: number; height: number }) {
  return Math.max(2, Math.min(canvas.width, canvas.height) * BRUSH_RADIUS)
}
