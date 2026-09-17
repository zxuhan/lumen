import { useEffect, useRef, useState } from 'react'

import { isTerminal, type RunStatus } from '@/api/runs'
import { PROGRESS_CEILING, pacedProgress, pacingSeconds } from '@/lib/runPacing'

// When the server jumps ahead, ease to catch up instead of snapping
const CATCH_UP_S = 0.35
// Time scale for settling to 100 after completion
const SETTLE_S = 0.25
// Minimum advance per second, so no phase ever looks completely stalled
const CREEP_PER_S = 0.12
// Changes smaller than this don't trigger a re-render
const EPSILON = 0.4

/**
 * Server progress arrives in a few discrete steps and goes quiet during long waits. This smooths
 * it into a continuous value based on each tool's estimated duration.
 *
 * Displayed progress never goes backwards: it resets only when the run changes (token changes),
 * and stays where it is on failure or cancellation.
 */
export function useSmoothedProgress({
  reported,
  status,
  tool,
  token,
}: {
  reported: number
  status: RunStatus | undefined
  tool: string | undefined
  token: string | null
}) {
  const [shown, setShown] = useState(0)
  const current = useRef(0)
  const emitted = useRef(0)
  const startedAt = useRef(0)

  useEffect(() => {
    current.current = 0
    emitted.current = 0
    startedAt.current = performance.now()
    setShown(0)
  }, [token])

  const done = Boolean(status && isTerminal(status))
  const succeeded = status === 'succeeded' || reported >= 100
  const seconds = pacingSeconds(tool)

  useEffect(() => {
    // Failed or canceled: hold the current value, neither resetting to 0 nor jumping to 100
    if (!token || (done && !succeeded)) return

    let frame = 0
    let last = performance.now()

    const tick = (now: number) => {
      const dt = Math.min(0.25, (now - last) / 1000)
      last = now
      const from = current.current
      let next: number

      if (succeeded) {
        next = from + (100 - from) * Math.min(1, dt / SETTLE_S)
        if (next > 99.5) next = 100
      } else {
        const paced = pacedProgress(now - startedAt.current, seconds)
        const target = Math.min(PROGRESS_CEILING, Math.max(reported, paced))
        const eased = from + (target - from) * (1 - Math.exp(-dt / CATCH_UP_S))
        const creep = Math.min(PROGRESS_CEILING, from + CREEP_PER_S * dt)
        next = Math.max(from, eased, creep)
      }

      current.current = next
      if (Math.abs(next - emitted.current) >= EPSILON || (next === 100 && emitted.current !== 100)) {
        emitted.current = next
        setShown(next)
      }

      if (next < 100) frame = requestAnimationFrame(tick)
    }

    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [token, reported, done, succeeded, seconds])

  return Math.round(shown)
}
