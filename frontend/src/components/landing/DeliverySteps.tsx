const STEPS = [
  { title: 'Describe it', desc: 'Name the product, scene, and size in one sentence.' },
  { title: 'Pick a direction', desc: 'Choose the best of 4 candidates.' },
  { title: 'Refine details', desc: 'Click the subject, give instructions, and iterate until you are happy.' },
  { title: 'Export assets', desc: 'Export every size for each ad channel at once.' },
]

export default function DeliverySteps() {
  return (
    <section className="mx-auto max-w-5xl px-6 pb-16">
      <ol className="border-line bg-paper rounded-card divide-line grid divide-y border sm:grid-cols-4 sm:divide-x sm:divide-y-0">
        {STEPS.map((step, index) => (
          <li key={step.title} className="p-6">
            <span className="bg-brand-soft text-brand-strong grid size-7 place-items-center rounded-full text-xs font-semibold">
              {index + 1}
            </span>
            <h3 className="text-ink mt-4 text-sm font-medium">{step.title}</h3>
            <p className="text-muted mt-1.5 text-sm leading-relaxed">{step.desc}</p>
          </li>
        ))}
      </ol>
    </section>
  )
}
