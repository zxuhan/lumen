import { useRef, useState } from 'react'

import PromptComposer from './PromptComposer'

const SCENARIOS = [
  {
    label: 'Product shot',
    prompt: 'Place this product on a pure white background, centered, with soft top lighting and clean edges. Output a 1:1 main image.',
  },
  {
    label: 'Lifestyle scene',
    prompt: 'Put the product on a warm wooden tabletop with side/back lighting and shallow depth of field, keeping its original materials and colors.',
  },
  {
    label: 'On model',
    prompt: 'Generate a half-body shot of a model holding this product, with a clean indoor background, natural light, and clearly visible product details.',
  },
  {
    label: 'Promo poster',
    prompt: 'Make a sale poster: headline "New Arrival", subheading "20% Off, Limited Time". Feature the product and leave room for text on the right.',
  },
  {
    label: 'Multi-size assets',
    prompt: 'Create a set of ad assets from this product image in three sizes, 1:1, 4:5, and 9:16, without cropping the subject.',
  },
]

const FACTS = ['No design experience needed', 'Supports JPG / PNG / WebP', 'Export 1:1 / 4:5 / 9:16 at once']

export default function LandingHero({
  initialPrompt,
  submitLabel,
  onStart,
}: {
  initialPrompt: string
  submitLabel: string
  onStart: (prompt: string) => void
}) {
  const [prompt, setPrompt] = useState(initialPrompt)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  const pick = (text: string) => {
    setPrompt(text)
    inputRef.current?.focus()
  }

  return (
    <section className="relative isolate overflow-hidden">
      <div className="bg-glow absolute inset-x-0 -top-24 h-[560px]" aria-hidden />
      <div className="bg-grid absolute inset-x-0 -top-24 h-[560px]" aria-hidden />

      {/* The container is 4xl, sized so the original 14-character Chinese headline fit on one line on desktop; body text and input are each narrower */}
      <div className="relative mx-auto max-w-4xl px-6 pt-16 pb-14 text-center sm:pt-24">
        <p
          className="border-line bg-paper/80 text-muted animate-rise inline-flex items-center gap-2 rounded-full border px-3.5 py-1.5 text-xs backdrop-blur"
          style={{ animationDelay: '40ms' }}
        >
          <span className="bg-accent size-1.5 rounded-full" aria-hidden />
          For e-commerce teams and content creators
        </p>

        <h1
          className="text-ink animate-rise mt-6 text-[2rem] leading-[1.2] font-semibold tracking-tight text-balance sm:text-[2.7rem] lg:text-[3.25rem]"
          style={{ animationDelay: '120ms' }}
        >
          Turn one sentence into <span className="relative mx-1 whitespace-nowrap">
            {/* CJK glyphs fill the whole em box, so the highlight must cover the full glyph height to read as a marker rather than a strikethrough */}
            <span
              className="bg-accent/55 absolute inset-x-[-7px] top-[14%] bottom-[8%] -skew-x-6 rounded-[3px]"
              aria-hidden
            />
            <span className="relative">shelf-ready</span>
          </span> product assets
        </h1>

        <p
          className="text-muted animate-rise mx-auto mt-5 max-w-xl leading-relaxed"
          style={{ animationDelay: '200ms' }}
        >
          Describe what you need to generate from scratch, or upload a product photo to keep editing. Cutouts, background swaps, detailed touch-ups, outpainting, layer splitting, and multi-size export are all orchestrated by the agent.
        </p>

        <div className="animate-rise mx-auto mt-9 max-w-3xl" style={{ animationDelay: '280ms' }}>
          <PromptComposer
            value={prompt}
            onChange={setPrompt}
            onSubmit={() => onStart(prompt)}
            onAttach={() => onStart(prompt)}
            submitLabel={submitLabel}
            placeholder="Describe the product image you want, e.g. put these running shoes on a city street at dawn, side/back light, output a 1:1 main image and a 9:16 vertical…"
            inputRef={inputRef}
          />
        </div>

        <div
          className="animate-rise mt-5 flex flex-wrap justify-center gap-2"
          style={{ animationDelay: '360ms' }}
        >
          {SCENARIOS.map((scenario) => (
            <button
              key={scenario.label}
              type="button"
              onClick={() => pick(scenario.prompt)}
              className="border-line bg-paper/70 text-muted hover:border-brand hover:text-brand-strong rounded-full border px-3.5 py-1.5 text-xs transition-colors"
            >
              {scenario.label}
            </button>
          ))}
        </div>

        <ul
          className="text-faint animate-rise mt-10 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-xs"
          style={{ animationDelay: '440ms' }}
        >
          {FACTS.map((fact) => (
            <li key={fact} className="flex items-center gap-1.5">
              <span className="bg-line-strong size-1 rounded-full" aria-hidden />
              {fact}
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
