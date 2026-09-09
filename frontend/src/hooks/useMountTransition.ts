import { useEffect, useState } from 'react'

/**
 * After closing, stays in the tree until the exit animation has played, then unmounts. Returns
 * null once it can actually be removed; while exiting is true, the caller applies the exit animation.
 */
export function useMountTransition<T>(
  value: T | null,
  exitMs: number,
): { value: T; exiting: boolean } | null {
  const [held, setHeld] = useState(value)
  const [exiting, setExiting] = useState(false)

  useEffect(() => {
    if (value !== null) {
      setHeld(value)
      setExiting(false)
      return
    }
    if (held === null) return
    setExiting(true)
    const timer = window.setTimeout(() => {
      setHeld(null)
      setExiting(false)
    }, exitMs)
    return () => window.clearTimeout(timer)
  }, [value, held, exitMs])

  if (held === null) return null
  return { value: held, exiting }
}
