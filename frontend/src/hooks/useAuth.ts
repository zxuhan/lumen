import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { authApi, type Credentials, type User } from '@/api/auth'
import { ApiError } from '@/api/client'

const ME_KEY = ['auth', 'me']

/** The server-side cookie is the source of truth for the login session; the frontend holds no token and only caches the current user. */
export function useCurrentUser() {
  const { data, isPending } = useQuery({
    queryKey: ME_KEY,
    queryFn: () => authApi.me(),
    retry: false,
    staleTime: Infinity,
    // Being signed out is a normal state, not an error to throw
    throwOnError: false,
  })
  return { user: data ?? null, isLoading: isPending }
}

export function useAuthActions() {
  const queryClient = useQueryClient()
  const cacheUser = (user: User) => queryClient.setQueryData(ME_KEY, user)

  const login = useMutation({
    mutationFn: (body: Credentials) => authApi.login(body),
    onSuccess: cacheUser,
  })
  const register = useMutation({
    mutationFn: (body: Credentials) => authApi.register(body),
    onSuccess: cacheUser,
  })
  const logout = useMutation({
    mutationFn: () => authApi.logout(),
    onSuccess: () => queryClient.clear(),
  })

  return { login, register, logout }
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return error instanceof Error ? error.message : 'Request failed. Please try again later.'
}
