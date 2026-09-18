import { useEffect, useState } from 'react'

/** safe means the bitmap's pixels can be read; live filters can only run on the canvas when it is true. */
export type CanvasImage = { element: HTMLImageElement; safe: boolean; url: string }

const LIMIT = 16
const cache = new Map<string, CanvasImage>()

function remember(image: CanvasImage) {
  cache.delete(image.url)
  cache.set(image.url, image)
  while (cache.size > LIMIT) {
    const oldest = cache.keys().next().value
    if (!oldest || oldest === image.url) break
    cache.delete(oldest)
  }
}

function read(url: string) {
  return cache.get(url) ?? null
}

function decode(url: string, safe: boolean) {
  return new Promise<CanvasImage>((resolve, reject) => {
    const element = new Image()
    if (safe) element.crossOrigin = 'anonymous'
    element.onload = () => resolve({ element, safe, url })
    element.onerror = () => reject(new Error('image'))
    element.src = url
  })
}

export function preloadCanvasImage(url: string) {
  const hit = read(url)
  if (hit) return Promise.resolve(hit)
  return decode(url, true)
    .catch(() => decode(url, false))
    .then((image) => {
      remember(image)
      return image
    })
    .catch(() => null)
}

/** Decodes a URL into a bitmap Konva can draw directly. Keeps the previous image while the source changes so the canvas doesn't flash white. */
export function useCanvasImage(url: string | undefined) {
  const [image, setImage] = useState<CanvasImage | null>(() => (url ? read(url) : null))

  useEffect(() => {
    if (!url) return

    const hit = read(url)
    if (hit) {
      setImage(hit)
      return
    }

    let cancelled = false
    void preloadCanvasImage(url).then((next) => {
      if (!cancelled && next) setImage(next)
    })
    return () => {
      cancelled = true
    }
  }, [url])

  return (url && read(url)) || image
}
