import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import type { Asset } from '@/api/assets'
import ProgressBar from '@/components/ui/ProgressBar'
import { useRun } from '@/hooks/useRun'
import { useCreateSession } from '@/hooks/useSessions'

export default function CandidatesPage() {
  const { runId = '' } = useParams()
  const navigate = useNavigate()
  const [picked, setPicked] = useState<string | null>(null)
  const { status, progress, stage, error, prompt, candidates, notFound } = useRun(runId || null)
  const createSession = useCreateSession()

  // Using one opens it in the editor; the other candidates from the same batch come along into the session's image wall
  const adopt = () =>
    picked &&
    createSession.mutate(
      {
        current_asset_id: picked,
        asset_ids: candidates.map((asset) => asset.id),
        title: prompt ?? undefined,
      },
      { onSuccess: (session) => navigate(`/editor/${session.id}`) },
    )

  if (notFound) {
    return <Centered title="Task not found" hint="The link may have expired. Go back to the Create page and start over." />
  }

  if (status === 'failed' || status === 'canceled') {
    return (
      <Centered title="Generation failed" hint={error ?? 'Unknown reason'}>
        <Link
          to="/create"
          className="bg-ink hover:bg-dark rounded-control mt-5 px-4 py-2 text-sm font-medium text-white"
        >
          Go back and retry
        </Link>
      </Centered>
    )
  }

  if (status !== 'succeeded') {
    return <Progress percent={progress} stage={stage} />
  }

  return (
    <div className="mx-auto max-w-5xl px-8 py-10">
      <header className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-ink text-2xl font-semibold tracking-tight">Pick one</h1>
          <p className="text-muted mt-1 text-sm">
            Choose the one you like to start editing. The other candidates stay on the session image wall, so you can switch back anytime.
          </p>
        </div>
        <button
          type="button"
          disabled={!picked || createSession.isPending}
          onClick={adopt}
          className="bg-ink hover:bg-dark rounded-control shrink-0 px-4 py-2 text-sm font-medium text-white transition-all duration-150 active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40 disabled:active:scale-100"
        >
          {createSession.isPending ? 'Opening…' : picked ? 'Open in editor' : 'Pick one first'}
        </button>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {candidates.map((asset, index) => (
          <Candidate
            key={asset.id}
            asset={asset}
            index={index}
            selected={picked === asset.id}
            onSelect={() => setPicked(asset.id)}
          />
        ))}
      </div>
    </div>
  )
}

function Candidate({
  asset,
  index,
  selected,
  onSelect,
}: {
  asset: Asset
  index: number
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`rounded-panel group relative block overflow-hidden border-2 bg-white transition-all duration-200 ${
        selected
          ? 'border-brand shadow-lift'
          : 'border-line hover:border-brand hover:-translate-y-0.5 hover:shadow-lift'
      }`}
    >
      <img
        src={asset.url}
        alt={`Candidate ${index + 1}`}
        loading="lazy"
        className="block max-h-[52vh] w-full object-contain transition-transform duration-300 group-hover:scale-[1.01]"
      />
      <span className="text-muted bg-paper/90 absolute top-2 left-2 rounded-full px-2 py-0.5 text-xs font-medium backdrop-blur">
        {index + 1}
      </span>
      {selected && (
        <span className="bg-brand absolute top-2 right-2 rounded-full px-2 py-0.5 text-xs font-medium text-white">
          Selected
        </span>
      )}
    </button>
  )
}

function Progress({ percent, stage }: { percent: number; stage: string }) {
  return (
    <Centered title="Generating" hint={stage || 'Task submitted, waiting in the queue'}>
      <ProgressBar value={percent} className="mt-6 h-1 w-64 rounded-full" />
      <p className="text-faint mt-2 text-xs tabular-nums">{percent}%</p>
    </Centered>
  )
}

function Centered({
  title,
  hint,
  children,
}: {
  title: string
  hint: string
  children?: React.ReactNode
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-8 text-center">
      <h1 className="text-ink text-xl font-semibold">{title}</h1>
      <p className="text-muted mt-1 max-w-md text-sm">{hint}</p>
      {children}
    </div>
  )
}
