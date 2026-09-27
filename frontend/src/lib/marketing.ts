import type { Asset, AssetKind } from '@/api/assets'
import type { Ratio } from '@/api/runs'

export type MarketingKind = 'product' | 'scene' | 'model' | 'poster'

export const MARKETING_KINDS: {
  id: MarketingKind
  label: string
  hint: string
}[] = [
  { id: 'product', label: 'Product shot', hint: 'Centered on white, ideal as a listing main image' },
  { id: 'scene', label: 'Lifestyle scene', hint: 'Real setting, side/back light, shallow depth of field' },
  { id: 'model', label: 'On model', hint: 'Held or worn by a model' },
  { id: 'poster', label: 'Promo poster', hint: 'Product front and center, room left for copy' },
]

export const DELIVERY_RATIOS: { value: Ratio; label: string; size: string }[] = [
  { value: '1:1', label: '1:1', size: '1080×1080' },
  { value: '4:5', label: '4:5', size: '1080×1350' },
  { value: '9:16', label: '9:16', size: '1080×1920' },
]

const DELIVERY_SIZES: Record<string, string> = {
  '1080x1080': '1:1',
  '1080x1350': '4:5',
  '1080x1920': '9:16',
}

export const KIND_LABELS: Record<AssetKind, string> = {
  original: 'Original',
  generated: 'Generated',
  subject: 'Subject',
  background: 'Background',
  mask: 'Mask',
  marketing: 'Marketing',
  export: 'Export',
}

export function ratioLabel(width: number, height: number): string {
  return DELIVERY_SIZES[`${width}x${height}`] ?? `${width}×${height}`
}

export function packable(asset: Asset, currentId: string): boolean {
  if (asset.kind === 'mask') return false
  if (asset.kind === 'subject' || asset.kind === 'background') return asset.id === currentId
  return true
}

export function defaultSelected(assets: Asset[], currentId: string): string[] {
  const ready = assets.filter((asset) => asset.kind === 'marketing' || asset.kind === 'export')
  if (ready.length) return ready.map((asset) => asset.id)
  return assets.some((asset) => asset.id === currentId) ? [currentId] : []
}
