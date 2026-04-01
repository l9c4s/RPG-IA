import React, { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Eye, EyeOff, Sword, AlertCircle } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { AuthLayout } from '../components/layout/AuthLayout'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'

export default function Login(): React.ReactElement {
  const { login, isLoading, error, clearError } = useAuth()

  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [showPass, setShowPass] = useState(false)
  const [localErr, setLocalErr] = useState<string | null>(null)

  const displayError = error ?? localErr

  async function handleSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault()
    setLocalErr(null)
    clearError()

    if (!email.trim() || !password) {
      setLocalErr('Por favor, preencha todos os campos.')
      return
    }

    try {
      await login(email.trim(), password)
    } catch {
      // Error already stored in auth state
    }
  }

  return (
    <AuthLayout subtitle="Enter the realm of legends">
      <div className="card-rune p-8">
        <h2 className="text-xl font-serif text-slate-100 mb-6 text-center tracking-wide">
          Sign In
        </h2>

        {/* Error banner */}
        {displayError && (
          <div className="flex items-start gap-2 bg-red-900/40 border border-red-700/60 rounded-md px-4 py-3 mb-5 text-red-300 text-sm animate-fade-in">
            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
            <span>{displayError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5" noValidate>
          <Input
            id="email"
            type="email"
            label="Email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="adventurer@realm.io"
            disabled={isLoading}
          />

          <div>
            <Input
              id="password"
              type={showPass ? 'text' : 'password'}
              label="Password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              disabled={isLoading}
              rightElement={
                <button
                  type="button"
                  onClick={() => setShowPass((v) => !v)}
                  className="text-slate-500 hover:text-amber-400 transition-colors"
                  aria-label={showPass ? 'Hide password' : 'Show password'}
                >
                  {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              }
            />
          </div>

          <Button
            type="submit"
            variant="primary"
            size="md"
            isLoading={isLoading}
            leftIcon={<Sword className="w-4 h-4" />}
            className="w-full justify-center mt-2"
          >
            {isLoading ? 'Entering the realm…' : 'Enter the Realm'}
          </Button>
        </form>

        {/* Divider */}
        <div className="divider-rune mt-6">
          <span>or</span>
        </div>

        {/* Register link */}
        <p className="text-center text-slate-400 text-sm mt-4">
          No account yet?{' '}
          <Link
            to="/register"
            className="text-amber-400 hover:text-amber-300 underline underline-offset-2 transition-colors"
          >
            Create your hero
          </Link>
        </p>
      </div>
    </AuthLayout>
  )
}
