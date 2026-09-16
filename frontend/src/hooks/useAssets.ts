import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ACCEPTED_TYPES, MAX_UPLOAD_BYTES, assetsApi } from '@/api/assets'

const ASSETS_KEY = ['assets']

/** Validate type and size up front so obviously invalid files don't waste a network request. */
export function checkFile(file: File): string | null {
  if (!ACCEPTED_TYPES.includes(file.type)) return 'Only JPG, PNG, and WebP are supported'
  if (file.size > MAX_UPLOAD_BYTES) return 'File exceeds the 20 MB limit'
  return null
}

export function useAssets(limit?: number) {
  return useQuery({ queryKey: ASSETS_KEY, queryFn: () => assetsApi.list(limit) })
}

export function useAssetLibrary(limit?: number) {
  return useQuery({ queryKey: [...ASSETS_KEY, 'library'], queryFn: () => assetsApi.library(limit) })
}

export function useUploadAsset() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file: File) => assetsApi.upload(file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ASSETS_KEY }),
  })
}
