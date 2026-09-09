/**
 * The progress value is already animated frame by frame, so the bar gets no CSS transition;
 * stacking two layers of interpolation would cause ghosting.
 */
export default function ProgressBar({
  value,
  tone = 'ink',
  className = 'h-0.5',
}: {
  value: number
  tone?: 'ink' | 'brand'
  className?: string
}) {
  const clamped = Math.max(0, Math.min(100, value))

  return (
    <div
      role="progressbar"
      aria-valuenow={Math.round(clamped)}
      aria-valuemin={0}
      aria-valuemax={100}
      className={`bg-line overflow-hidden ${className}`}
    >
      <div
        className={`h-full ${tone === 'brand' ? 'bg-brand-strong' : 'bg-ink'}`}
        style={{ width: `${Math.max(clamped, 2)}%` }}
      />
    </div>
  )
}
