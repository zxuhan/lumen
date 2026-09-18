import type { Asset, AssetKind } from '@/api/assets'

const KIND_LABELS: Record<AssetKind, string> = {
  original: 'Original',
  generated: 'Generated',
  subject: 'Subject',
  background: 'Background',
  mask: 'Mask',
  marketing: 'Marketing',
  export: 'Export',
}

/** Every image in the session, including unused candidates. Clicking one switches the canvas's current image without overwriting any existing result. */
export default function ImageWall({
  assets,
  currentId,
  disabled,
  onPick,
}: {
  assets: Asset[]
  currentId: string
  disabled: boolean
  onPick: (assetId: string) => void
}) {
  return (
    <div className="border-line bg-paper shrink-0 border-t">
      <div className="scrollbar-slim flex scroll-px-4 items-center gap-2 overflow-x-auto px-4 py-3">
        {assets
          .filter((asset) => asset.kind !== 'mask')
          .filter(
            (asset) =>
              asset.id === currentId || (asset.kind !== 'subject' && asset.kind !== 'background'),
          )
          .map((asset) => {
          const active = asset.id === currentId
          return (
            <button
              key={asset.id}
              type="button"
              disabled={disabled || active}
              onClick={() => onPick(asset.id)}
              title={
                active
                  ? `Current canvas · ${KIND_LABELS[asset.kind]}`
                  : `Use this image · ${KIND_LABELS[asset.kind]} ${asset.width}×${asset.height}`
              }
              className={`bg-canvas group rounded-chip relative size-16 shrink-0 overflow-hidden border-2 transition-all duration-150 disabled:cursor-default ${
                active
                  ? 'border-brand shadow-control'
                  : 'border-line hover:border-brand hover:shadow-control active:scale-[0.97]'
              }`}
            >
              <img
                src={asset.url}
                alt=""
                loading="lazy"
                className="size-full object-contain transition-transform duration-150 group-hover:scale-[1.03]"
              />
              <span className="bg-ink/70 absolute right-0 bottom-0 left-0 py-0.5 text-[10px] text-white">
                {KIND_LABELS[asset.kind]}
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
