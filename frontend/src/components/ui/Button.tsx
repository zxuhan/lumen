import type { ReactNode } from 'react'

import { buttonClass, type ButtonLook } from '@/components/ui/buttonStyles'

/**
 * Site-wide press feedback. When progress is passed, the button itself becomes the progress
 * indicator, so "the one running is the one I clicked" no longer has to be shown by dimming the
 * whole row.
 */
export default function Button({
  children,
  onClick,
  title,
  disabled,
  active,
  variant = 'ghost',
  size = 'md',
  block,
  progress = null,
  className,
}: ButtonLook & {
  children: ReactNode
  onClick: () => void
  title?: string
  disabled?: boolean
  progress?: number | null
  className?: string
}) {
  const running = progress !== null
  const filled = Math.max(0, Math.min(100, progress ?? 0))

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-pressed={active}
      aria-busy={running || undefined}
      className={[buttonClass({ variant, size, active: active || running, block }), className]
        .filter(Boolean)
        .join(' ')}
    >
      {running && variant !== 'icon' ? (
        <span className="flex items-center justify-center gap-1.5">
          {children}
          <span className="tabular-nums opacity-70">{Math.round(filled)}%</span>
        </span>
      ) : (
        children
      )}
      {running && (
        <span
          className="bg-brand-strong/60 absolute bottom-0 left-0 h-[2px]"
          style={{ width: `${Math.max(filled, 4)}%` }}
        />
      )}
    </button>
  )
}
