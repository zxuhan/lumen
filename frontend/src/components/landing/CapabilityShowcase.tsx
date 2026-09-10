import type { ReactNode } from 'react'

import { CandidatesPreview, ExportsPreview, LayersPreview, SelectionPreview } from './previews'

const CAPABILITIES: { title: string; desc: string; preview: ReactNode }[] = [
  {
    title: 'Generate from one sentence',
    desc: 'No upload needed: describe what you want and get 4 candidate directions. The one you pick goes straight into the editor.',
    preview: <CandidatesPreview />,
  },
  {
    title: 'Object-level editing',
    desc: 'Click any object in the image, then give an instruction. Changes stay inside the selection and never spill into other areas.',
    preview: <SelectionPreview />,
  },
  {
    title: 'Semantic layers',
    desc: 'Subject, background, and text are split into layers automatically, any object can get its own layer, and you can return to the previous version anytime.',
    preview: <LayersPreview />,
  },
  {
    title: 'Ready-to-ship asset packs',
    desc: 'Export selling-point callouts plus 1:1, 4:5, and 9:16 sizes in one go, subject never cropped, ready to list and advertise.',
    preview: <ExportsPreview />,
  },
]

export default function CapabilityShowcase() {
  return (
    <section className="mx-auto max-w-5xl px-6 py-16">
      <header className="max-w-xl">
        <p className="text-brand-strong text-sm font-medium">Capabilities</p>
        <h2 className="text-ink mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">
          More than just a pretty picture
        </h2>
        <p className="text-muted mt-3 leading-relaxed">
          From candidate directions to detailed touch-ups, layering, and multi-size delivery, the whole pipeline lives in a single workspace.
        </p>
      </header>

      <div className="mt-10 grid gap-5 sm:grid-cols-2">
        {CAPABILITIES.map((item) => (
          <article
            key={item.title}
            className="border-line bg-paper rounded-card hover:shadow-lift border p-6 transition-shadow"
          >
            <div className="bg-soft border-line/70 mb-6 flex h-44 items-center justify-center overflow-hidden rounded-[14px] border px-5 py-4">
              {item.preview}
            </div>
            <h3 className="text-ink font-medium">{item.title}</h3>
            <p className="text-muted mt-2 text-sm leading-relaxed">{item.desc}</p>
          </article>
        ))}
      </div>
    </section>
  )
}
