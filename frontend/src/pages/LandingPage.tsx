import { useNavigate } from 'react-router-dom'

import CapabilityShowcase from '@/components/landing/CapabilityShowcase'
import DeliverySteps from '@/components/landing/DeliverySteps'
import LandingFooter from '@/components/landing/LandingFooter'
import LandingHeader from '@/components/landing/LandingHeader'
import LandingHero from '@/components/landing/LandingHero'
import StartBanner from '@/components/landing/StartBanner'
import { useCurrentUser } from '@/hooks/useAuth'
import { readPromptDraft, savePromptDraft } from '@/lib/promptDraft'

export default function LandingPage() {
  const navigate = useNavigate()
  const { user } = useCurrentUser()

  // Signed-out users always go to the sign-in page first; signed-in users go straight to the workspace
  const entry = user ? { label: 'Open workspace', to: '/create' } : { label: 'Start for free', to: '/auth' }

  const start = (prompt: string) => {
    savePromptDraft(prompt)
    navigate(entry.to)
  }

  return (
    <div className="flex min-h-screen flex-col">
      <LandingHeader account={user?.username ?? null} />

      <main className="flex-1">
        <LandingHero
          initialPrompt={readPromptDraft()}
          submitLabel={entry.label}
          onStart={start}
        />
        <CapabilityShowcase />
        <DeliverySteps />
        <StartBanner label={entry.label} to={entry.to} />
      </main>

      <LandingFooter />
    </div>
  )
}
