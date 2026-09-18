import { useState } from 'react'
import { Link, NavLink } from 'react-router-dom'

import AgentConversation from '@/components/editor/AgentConversation'
import MessageComposer from '@/components/editor/MessageComposer'
import Button from '@/components/ui/Button'
import { buttonClass } from '@/components/ui/buttonStyles'
import { useSendMessage, useTurns } from '@/hooks/useAgent'
import { errorMessage } from '@/hooks/useAuth'
import { useSessions } from '@/hooks/useSessions'
import { formatDateTime } from '@/lib/format'

export default function SessionSidebar({ activeId }: { activeId: string }) {
  // History is collapsed by default to leave as much vertical space as possible for the current conversation
  const [historyOpen, setHistoryOpen] = useState(false)

  return (
    <aside className="border-line bg-paper flex w-72 shrink-0 flex-col border-r">
      <div className="border-line flex items-center gap-2 border-b p-3">
        <Link
          to="/create"
          className={`${buttonClass({ variant: 'outline' })} flex-1 py-2 text-center text-sm`}
        >
          New chat
        </Link>
        <Button
          active={historyOpen}
          className="px-3 py-2"
          onClick={() => setHistoryOpen((open) => !open)}
        >
          History
        </Button>
      </div>

      {historyOpen && <SessionList activeId={activeId} />}

      {activeId ? (
        <Conversation sessionId={activeId} />
      ) : (
        <p className="text-faint min-h-0 flex-1 px-4 py-4 text-xs leading-relaxed">
          Open a past conversation, or go back to the Create page to start a new image.
        </p>
      )}
    </aside>
  )
}

function Conversation({ sessionId }: { sessionId: string }) {
  const send = useSendMessage(sessionId)
  const { data: turns = [] } = useTurns(sessionId)
  const planActive = turns.some((turn) => turn.status === 'queued' || turn.status === 'running')

  return (
    <>
      <AgentConversation sessionId={sessionId} />
      <MessageComposer
        pending={send.isPending || planActive}
        error={send.isError ? errorMessage(send.error) : null}
        placeholder={
          planActive
            ? 'A plan is in progress. Confirm, cancel, or wait for it to finish before sending'
            : 'Describe the change, e.g. remove the background, then flip horizontally. Enter to send'
        }
        onSend={(text) => send.mutate(text)}
      />
    </>
  )
}

function SessionList({ activeId }: { activeId: string }) {
  const { data: sessions = [], isPending } = useSessions()

  if (isPending) {
    return <p className="text-faint border-line border-b px-4 py-3 text-xs">Loading…</p>
  }

  if (sessions.length === 0) {
    return <p className="text-faint border-line border-b px-4 py-3 text-xs">No conversations yet</p>
  }

  return (
    <ul className="border-line scrollbar-slim animate-fade-in max-h-52 shrink-0 space-y-0.5 overflow-y-auto border-b p-2">
      {sessions.map((session) => (
        <li key={session.id}>
          <NavLink
            to={`/editor/${session.id}`}
            className={`rounded-chip block px-2.5 py-2 transition-colors duration-150 ${
              session.id === activeId
                ? 'bg-brand-soft text-brand-strong'
                : 'text-muted hover:bg-soft hover:text-ink'
            }`}
          >
            <span className="block truncate text-xs font-medium">{session.title}</span>
            <span className="text-faint block text-[10px] tabular-nums">
              {formatDateTime(session.updated_at)}
            </span>
          </NavLink>
        </li>
      ))}
    </ul>
  )
}
