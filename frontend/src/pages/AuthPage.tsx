import { useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'

import BrandMark from '@/components/BrandMark'
import { errorMessage, useAuthActions, useCurrentUser } from '@/hooks/useAuth'

type Mode = 'login' | 'register'
type Rules = { minLength?: number; maxLength?: number; pattern?: string; title?: string }

const COPY: Record<Mode, { title: string; submit: string; switchTo: Mode; switchHint: string }> = {
  login: { title: 'Sign in', submit: 'Sign in', switchTo: 'register', switchHint: 'No account yet? Sign up' },
  register: {
    title: 'Create account',
    submit: 'Sign up and continue',
    switchTo: 'login',
    switchHint: 'Already have an account? Sign in',
  },
}

// Matches the backend's Credentials, so sign-up is validated in the browser without a round trip. Sign-in has no length limits, so older accounts can still get in.
const RULES: Record<Mode, { username: Rules; password: Rules }> = {
  login: { username: {}, password: {} },
  register: {
    username: {
      minLength: 3,
      maxLength: 32,
      pattern: '[\\p{L}\\p{N}_]{3,32}',
      title: '3–32 letters, digits, or underscores',
    },
    password: { minLength: 6, maxLength: 64, title: '6–64 characters' },
  },
}

export default function AuthPage() {
  const [params, setParams] = useSearchParams()
  const mode: Mode = params.get('mode') === 'register' ? 'register' : 'login'
  const copy = COPY[mode]

  const navigate = useNavigate()
  const { user, isLoading } = useCurrentUser()
  const { login, register } = useAuthActions()
  const action = mode === 'login' ? login : register

  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  if (!isLoading && user) return <Navigate to="/create" replace />

  const submit = (event: React.FormEvent) => {
    event.preventDefault()
    action.mutate({ username, password }, { onSuccess: () => navigate('/create', { replace: true }) })
  }

  const switchMode = () => {
    action.reset()
    setParams({ mode: copy.switchTo })
  }

  return (
    <div className="relative isolate flex min-h-screen items-center justify-center px-6 py-12">
      <div className="bg-glow absolute inset-x-0 top-0 h-[420px]" aria-hidden />

      <div className="relative w-full max-w-sm">
        <Link to="/" className="text-muted hover:text-ink mb-6 inline-flex items-center gap-2 text-sm">
          <span aria-hidden>←</span> Back to home
        </Link>

        <div className="border-line bg-paper rounded-panel shadow-panel border p-8">
          <BrandMark size="sm">
            <span className="text-ink text-sm font-semibold">Lumen</span>
          </BrandMark>

          <h1 className="text-ink mt-6 text-2xl font-semibold tracking-tight">{copy.title}</h1>

          <form onSubmit={submit} className="mt-6 space-y-4">
            <Field
              label="Username"
              value={username}
              onChange={setUsername}
              autoComplete="username"
              placeholder="3–32 letters, digits, or underscores"
              rules={RULES[mode].username}
            />
            <Field
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
              placeholder="At least 6 characters"
              rules={RULES[mode].password}
            />

            {action.isError && <p className="text-danger text-sm">{errorMessage(action.error)}</p>}

            <button
              type="submit"
              disabled={action.isPending}
              className="bg-ink hover:bg-dark rounded-control w-full py-2.5 text-sm font-medium text-white transition-colors disabled:opacity-50"
            >
              {action.isPending ? 'Processing…' : copy.submit}
            </button>
          </form>

          <button
            type="button"
            onClick={switchMode}
            className="text-muted hover:text-brand-strong mt-5 text-sm transition-colors"
          >
            {copy.switchHint}
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({
  label,
  value,
  onChange,
  type = 'text',
  autoComplete,
  placeholder,
  rules,
}: {
  label: string
  value: string
  onChange: (value: string) => void
  type?: string
  autoComplete?: string
  placeholder?: string
  rules?: Rules
}) {
  return (
    <label className="block">
      <span className="text-muted mb-1.5 block text-sm">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete={autoComplete}
        placeholder={placeholder}
        required
        {...rules}
        className="border-line bg-paper text-ink placeholder:text-faint focus:border-brand rounded-control w-full border px-3.5 py-2.5 text-sm outline-none transition-colors"
      />
    </label>
  )
}
