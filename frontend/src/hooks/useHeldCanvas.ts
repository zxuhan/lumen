import { useEffect, useState } from 'react'

import type { LayerDocument } from '@/api/sessions'
import { preloadCanvasImage } from '@/hooks/useCanvasImage'

export type HeldCanvas = { document: LayerDocument; urls: Map<string, string> }

/**
 * Decides whether the image changed using only the canvas size and layer assets. Signed URLs
 * change on every write-back and must be left out; otherwise scaling or moving would also count
 * as switching images, briefly flashing the old zoom level before fading out.
 */
export function canvasStamp(document: LayerDocument) {
  const layers = document.layers.map((layer) => `${layer.id}:${layer.asset_id ?? ''}`).join('|')
  return `${document.width}x${document.height}:${layers}`
}

function needed(document: LayerDocument, urls: Map<string, string>) {
  return document.layers.flatMap((layer) => {
    if (!layer.visible || layer.kind !== 'image' || !layer.asset_id) return []
    const url = urls.get(layer.asset_id)
    return url ? [url] : []
  })
}

/** Keeps drawing the current frame until the next image has preloaded, so switching images doesn't blank a layer and then pop it back in. */
export function useHeldCanvas(document: LayerDocument, urls: Map<string, string>): HeldCanvas {
  const incomingKey = canvasStamp(document)
  const [held, setHeld] = useState<HeldCanvas & { key: string }>({
    document,
    urls,
    key: incomingKey,
  })

  useEffect(() => {
    const next = { document, urls, key: incomingKey }
    if (incomingKey === held.key) {
      setHeld((current) =>
        current.document === document && current.urls === urls ? current : next,
      )
      return
    }

    let cancelled = false
    const apply = () => {
      if (!cancelled) setHeld(next)
    }
    const urlsToLoad = needed(document, urls)
    if (urlsToLoad.length === 0) {
      apply()
      return
    }
    const loaded = Promise.all(urlsToLoad.map(preloadCanvasImage))
    const timeout = new Promise((resolve) => setTimeout(resolve, 4000))
    void Promise.race([loaded, timeout]).then(apply)
    return () => {
      cancelled = true
    }
  }, [incomingKey, held.key, document, urls])

  // Same set of layers: transforms and refreshed signed URLs apply immediately, no need to wait for preloading
  if (incomingKey === held.key) return { document, urls }
  return { document: held.document, urls: held.urls }
}
