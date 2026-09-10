/**
 * Illustrations for the capability cards: the product UI is mocked up purely with styles, with no
 * image assets. Everything here is decorative and hidden from assistive technology.
 */

const TILES = [
  'bg-[linear-gradient(145deg,#dbe9ee,#f4f6f3)]',
  'bg-[linear-gradient(145deg,#e7f0d4,#f4f6f3)]',
  'bg-[linear-gradient(145deg,#f0e3d3,#f4f6f3)]',
  'bg-[linear-gradient(145deg,#e0e5dd,#f4f6f3)]',
]

/** Generate from one sentence: four candidate directions, one of them selected. */
export function CandidatesPreview() {
  return (
    <div className="grid aspect-square h-full grid-cols-2 gap-2 p-1" aria-hidden>
      {TILES.map((tone, index) => (
        <div
          key={tone}
          className={`relative grid place-items-center rounded-[10px] ${tone} ${
            index === 1 ? 'ring-brand ring-2' : 'border-line border'
          }`}
        >
          <span className="bg-ink/12 h-5 w-4 rounded-[3px]" />
          {index === 1 && (
            <span className="bg-brand absolute top-1 right-1 grid size-3.5 place-items-center rounded-full">
              <svg viewBox="0 0 24 24" fill="none" className="size-2">
                <path d="M5 13l4.5 4.5L19 7" stroke="#fff" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
          )}
        </div>
      ))}
    </div>
  )
}

/** Object-level editing: a selection frames the subject and the instruction applies only inside it. */
export function SelectionPreview() {
  return (
    <div
      className="border-line relative aspect-[4/3] h-full max-h-full w-auto overflow-hidden rounded-[13px] border bg-[linear-gradient(160deg,#e4eef1,#f4f6f3)]"
      aria-hidden
    >
      <div className="border-brand absolute top-[18%] left-[22%] h-[54%] w-[38%] rounded-[6px] border-2 border-dashed">
        <span className="bg-ink/12 absolute inset-1.5 rounded-[4px]" />
        {['-top-1 -left-1', '-top-1 -right-1', '-bottom-1 -left-1', '-bottom-1 -right-1'].map((pos) => (
          <span key={pos} className={`bg-paper border-brand absolute size-2 rounded-full border-2 ${pos}`} />
        ))}
      </div>
      <p className="bg-ink/90 absolute bottom-2.5 left-2.5 rounded-full px-2.5 py-1 text-[10px] text-white">
        Change the background to beige linen
      </p>
    </div>
  )
}

const LAYERS = [
  { name: 'Text · Selling points', tone: 'bg-accent/70', indent: 'ml-0' },
  { name: 'Subject · Product', tone: 'bg-brand/60', indent: 'ml-3' },
  { name: 'Background · Scene', tone: 'bg-line-strong', indent: 'ml-6' },
]

/** Semantic layers: subject, background, and text separated automatically. */
export function LayersPreview() {
  return (
    <div className="w-full max-w-[210px] space-y-1.5" aria-hidden>
      {LAYERS.map((layer) => (
        <div
          key={layer.name}
          className={`border-line bg-paper shadow-control flex items-center gap-2.5 rounded-[10px] border px-2.5 py-2 ${layer.indent}`}
        >
          <span className={`size-4 shrink-0 rounded-[4px] ${layer.tone}`} />
          <span className="text-muted flex-1 truncate text-[11px]">{layer.name}</span>
          <svg viewBox="0 0 24 24" fill="none" className="text-faint size-3.5">
            <path d="M2.5 12S6 6 12 6s9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6z" stroke="currentColor" strokeWidth="1.8" />
            <circle cx="12" cy="12" r="2.5" stroke="currentColor" strokeWidth="1.8" />
          </svg>
        </div>
      ))}
    </div>
  )
}

const RATIOS = [
  { label: '1:1', frame: 'h-[62px] w-[62px]' },
  { label: '4:5', frame: 'h-[70px] w-[56px]' },
  { label: '9:16', frame: 'h-[78px] w-[44px]' },
]

/** Asset pack delivery: export several ad sizes at once. */
export function ExportsPreview() {
  return (
    <div className="flex items-end gap-3" aria-hidden>
      {RATIOS.map((ratio) => (
        <div key={ratio.label} className="flex flex-col items-center gap-1.5">
          <div
            className={`border-line grid place-items-center rounded-[9px] border bg-[linear-gradient(150deg,#e4eef1,#f4f6f3)] ${ratio.frame}`}
          >
            <span className="bg-ink/15 h-2/5 w-1/3 rounded-[3px]" />
          </div>
          <span className="text-faint text-[10px]">{ratio.label}</span>
        </div>
      ))}
    </div>
  )
}
