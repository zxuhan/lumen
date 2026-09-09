import { useLayoutEffect, useRef, useState } from 'react'

/** Observes an element's actual size, for components such as the Konva Stage that need an explicit width and height. */
export function useElementSize<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [size, setSize] = useState({ width: 0, height: 0 })

  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return

    // Keep the previous size when a measurement is 0: ResizeObserver only fires after the first
    // frame, and opening/closing panels can briefly report 0. A stage starting at 0×0 draws
    // nothing, and the view can't fit the canvas.
    const measure = (width: number, height: number) =>
      setSize((current) =>
        !width || !height || (current.width === width && current.height === height)
          ? current
          : { width, height },
      )

    measure(element.clientWidth, element.clientHeight)
    const observer = new ResizeObserver(([entry]) =>
      measure(Math.round(entry.contentRect.width), Math.round(entry.contentRect.height)),
    )
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return [ref, size] as const
}
