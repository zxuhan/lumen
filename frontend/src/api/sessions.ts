import type { Asset } from '@/api/assets'
import { api, apiError } from '@/api/client'
import type { Run } from '@/api/runs'

export type LayerKind = 'image' | 'text' | 'shape'

export type Transform = {
  x: number
  y: number
  scale_x: number
  scale_y: number
  rotation: number
}

export type Layer = {
  id: string
  kind: LayerKind
  name: string
  width: number
  height: number
  asset_id: string | null
  transform: Transform
  opacity: number
  visible: boolean
  locked: boolean
  source_hash?: string | null
  text?: string | null
  font_size?: number
  fill?: string
}

export type LayerDocument = {
  width: number
  height: number
  layers: Layer[]
}

export type Session = {
  id: string
  title: string
  revision: number
  history_seq: number
  original_asset_id: string
  current_asset_id: string
  created_at: string
  updated_at: string
}

export type SessionDetail = Session & {
  document: LayerDocument
  previous_document: LayerDocument | null
  assets: Asset[]
  can_undo: boolean
  can_redo: boolean
}

export type HistoryEntry = {
  seq: number
  action: string
  params: Record<string, unknown>
  result: Record<string, unknown>
  created_at: string
}

export type SessionCreateInput = {
  current_asset_id: string
  asset_ids?: string[]
  title?: string
}

export type SessionPatchInput = {
  title?: string
  current_asset_id?: string
}

export type ToolInvoke = {
  run: Run
  session: SessionDetail
}

export const ACTION_LABELS: Record<string, string> = {
  create_session: 'New session',
  switch_current: 'Switch image',
  generate_image: 'Generate image',
  replace_background: 'Replace background',
  expand_canvas: 'Expand image',
  upscale_image: 'Upscale',
  remove_background: 'Remove background',
  adjust_image: 'Adjust colors',
  erase_region: 'Erase region',
  replace_region: 'Replace region',
  crop_canvas: 'Crop',
  flip_layer: 'Flip',
  set_layer_opacity: 'Opacity',
  set_layer_visible: 'Visibility',
  set_layer_text: 'Edit text',
  reorder_layer: 'Layer order',
  scale_layer: 'Scale',
  rotate_layer: 'Rotate',
  move_layer: 'Move',
  split_layers: 'Split layers',
  promote_object_to_layer: 'Extract to layer',
  generate_marketing: 'Marketing image',
  prepare_delivery_sizes: 'Ad sizes',
}

export type ExportPack = {
  blob: Blob
  filename: string
}

export type Marker = { index: number; x: number; y: number }

export type Selection = {
  revision: number
  mask: Asset
  markers: Marker[]
}

export type SelectInput = {
  revision: number
  points?: { x: number; y: number }[]
  strokes?: { x: number; y: number }[][]
  radius?: number
  append?: boolean
}

export const sessionsApi = {
  create: (input: SessionCreateInput) => api.post<SessionDetail>('/sessions', input),
  list: () => api.get<Session[]>('/sessions'),
  get: (id: string) => api.get<SessionDetail>(`/sessions/${id}`),
  patch: (id: string, input: SessionPatchInput) =>
    api.patch<SessionDetail>(`/sessions/${id}`, input),
  history: (id: string) => api.get<HistoryEntry[]>(`/sessions/${id}/history`),
  invoke: (id: string, tool: string, params: Record<string, unknown> = {}) =>
    api.post<ToolInvoke>(`/sessions/${id}/tools`, { tool, params }),
  undo: (id: string) => api.post<SessionDetail>(`/sessions/${id}/undo`),
  redo: (id: string) => api.post<SessionDetail>(`/sessions/${id}/redo`),
  select: (id: string, input: SelectInput) => api.post<Selection>(`/sessions/${id}/selection`, input),
  prepareSelection: (id: string) => api.post<void>(`/sessions/${id}/selection/prepare`),
  getSelection: (id: string) => api.get<Selection | null>(`/sessions/${id}/selection`),
  clearSelection: (id: string) => api.delete<void>(`/sessions/${id}/selection`),
  export: (id: string, asset_ids: string[] = []) => downloadExport(id, asset_ids),
}

async function downloadExport(id: string, asset_ids: string[]): Promise<ExportPack> {
  const response = await fetch(`/api/sessions/${id}/exports`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ asset_ids }),
  })
  if (!response.ok) throw await apiError(response, 'Export failed')
  return { blob: await response.blob(), filename: filenameOf(response.headers.get('Content-Disposition')) }
}

function filenameOf(header: string | null): string {
  if (!header) return 'assets.zip'
  const encoded = /filename\*=(?:UTF-8'')?([^;]+)/i.exec(header)
  if (encoded) return decodeURIComponent(encoded[1])
  const plain = /filename="?([^"]+)"?/i.exec(header)
  return plain?.[1] ?? 'assets.zip'
}
