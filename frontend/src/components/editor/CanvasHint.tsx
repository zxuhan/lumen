export default function CanvasHint({ mode, text }: { mode: string; text: string | null }) {
  if (!text) return null

  return (
    <p
      // Key by mode: switching modes replays the entrance animation, while percentage updates within a mode don't interrupt it
      key={mode}
      className="bg-ink/80 shadow-control animate-pop pointer-events-none absolute top-3 left-1/2 z-10 -translate-x-1/2 rounded-full px-3 py-1 text-[11px] text-white backdrop-blur"
    >
      {text}
    </p>
  )
}
