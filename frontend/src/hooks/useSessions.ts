import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { isTerminal } from '@/api/runs'
import {
  sessionsApi,
  type SessionCreateInput,
  type SessionDetail,
  type SessionPatchInput,
} from '@/api/sessions'
import { errorMessage } from '@/hooks/useAuth'
import { useRun } from '@/hooks/useRun'
import { offersUndo, toolLabel } from '@/lib/tools'
import { toast } from '@/stores/toasts'

const LIST_KEY = ['sessions']
const detailKey = (id: string) => ['session', id]
const historyKey = (id: string) => ['session', id, 'history']

export function useSessions() {
  return useQuery({ queryKey: LIST_KEY, queryFn: sessionsApi.list })
}

export function useSession(id: string | null) {
  return useQuery({
    queryKey: detailKey(id ?? ''),
    queryFn: () => sessionsApi.get(id as string),
    enabled: Boolean(id),
  })
}

export function useSessionHistory(id: string | null) {
  return useQuery({
    queryKey: historyKey(id ?? ''),
    queryFn: () => sessionsApi.history(id as string),
    enabled: Boolean(id),
  })
}

function useCacheSession(id: string) {
  const queryClient = useQueryClient()
  return (detail: SessionDetail) => {
    queryClient.setQueryData(detailKey(id), detail)
    void queryClient.invalidateQueries({ queryKey: LIST_KEY })
    void queryClient.invalidateQueries({ queryKey: historyKey(id) })
  }
}

export function useCreateSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: SessionCreateInput) => sessionsApi.create(input),
    onSuccess: (detail) => {
      queryClient.setQueryData(detailKey(detail.id), detail)
      void queryClient.invalidateQueries({ queryKey: LIST_KEY })
    },
  })
}

export function usePatchSession(id: string) {
  const cache = useCacheSession(id)
  return useMutation({
    mutationFn: (input: SessionPatchInput) => sessionsApi.patch(id, input),
    onSuccess: cache,
  })
}

export function useExportPack(id: string) {
  return useMutation({
    mutationFn: (assetIds: string[]) => sessionsApi.export(id, assetIds),
    onError: (error) => toast(errorMessage(error), 'danger'),
  })
}

export function useSessionTools(id: string) {
  const queryClient = useQueryClient()
  const cache = useCacheSession(id)
  const [pendingRunId, setPendingRunId] = useState<string | null>(null)
  const live = useRun(pendingRunId)

  const invoke = useMutation({
    mutationFn: ({ tool, params }: { tool: string; params?: Record<string, unknown> }) =>
      sessionsApi.invoke(id, tool, params),
    onSuccess: (body) => {
      cache(body.session)
      if (!isTerminal(body.run.status)) setPendingRunId(body.run.id)
    },
    onError: (error) => toast(errorMessage(error), 'danger'),
  })

  const historyLock = useRef(false)
  const unlockHistory = () => {
    historyLock.current = false
  }

  const undo = useMutation({
    mutationFn: () => sessionsApi.undo(id),
    onSuccess: cache,
    onError: (error) => toast(errorMessage(error), 'danger'),
    onSettled: unlockHistory,
  })
  const redo = useMutation({
    mutationFn: () => sessionsApi.redo(id),
    onSuccess: cache,
    onError: (error) => toast(errorMessage(error), 'danger'),
    onSettled: unlockHistory,
  })

  const waiting = Boolean(pendingRunId && (!live.status || !isTerminal(live.status)))
  const busy = invoke.isPending || undo.isPending || redo.isPending || waiting

  // The toast's Undo must use the mutation as of completion; read the latest one through a ref instead of adding it to the effect deps
  const undoRef = useRef(() => undo.mutate())
  undoRef.current = () => undo.mutate()
  const pendingTool = invoke.variables?.tool
  // Announce each run only once; later dependency changes won't show the toast again
  const announced = useRef<string | null>(null)

  useEffect(() => {
    if (!pendingRunId || !live.status || !isTerminal(live.status)) return
    if (announced.current === pendingRunId) return
    announced.current = pendingRunId
    void queryClient.invalidateQueries({ queryKey: detailKey(id) })
    void queryClient.invalidateQueries({ queryKey: historyKey(id) })
    if (live.status === 'failed') {
      toast(live.error || 'Processing failed', 'danger')
      return
    }
    const label = toolLabel(pendingTool)
    toast(
      label ? `${label} complete` : live.stage || 'Done',
      'ok',
      offersUndo(pendingTool)
        ? { action: { label: 'Undo', run: () => undoRef.current() } }
        : undefined,
    )
  }, [pendingRunId, live.status, live.error, live.stage, pendingTool, id, queryClient])

  /**
   * Whether the run in progress came from this particular call. The tool layer runs one task at
   * a time, so only the button that started it switches to progress text; the other buttons are
   * disabled as well, but don't look like they are generating too.
   */
  const isRunning = (tool: string, match?: (params: Record<string, unknown>) => boolean) => {
    const pending = invoke.isPending || waiting ? invoke.variables : undefined
    if (pending?.tool !== tool) return false
    return match ? match(pending.params ?? {}) : true
  }

  const runHistory = (action: () => void) => {
    if (historyLock.current || busy) return
    historyLock.current = true
    action()
  }

  return {
    invoke: (tool: string, params?: Record<string, unknown>) => invoke.mutate({ tool, params }),
    undo: () => runHistory(() => undo.mutate()),
    redo: () => runHistory(() => redo.mutate()),
    busy,
    isRunning,
    pending: waiting,
    pendingStage: waiting ? live.stage : '',
    pendingProgress: waiting ? live.progress : 0,
  }
}

export type SessionTools = ReturnType<typeof useSessionTools>
