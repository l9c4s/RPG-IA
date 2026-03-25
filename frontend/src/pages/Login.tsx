import React, { useState, FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Eye, EyeOff, Sword, AlertCircle } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'

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
      setLocalErr('Please fill in all fields.')
      return
    }

    try {
      await login(email.trim(), password)
    } catch {
      // Error already stored in useAuth state
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background decorative elements */}
      <div className="absolute inset-0 bg-dungeon-texture opacity-30 pointer-events-none" />
      <div className="absolute top-0 left-0 w-96 h-96 bg-amber-900/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 right-0 w-96 h-96 bg-red-900/10 rounded-full blur-3xl pointer-events-none" />

      <div className="relative w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <div className="w-16 h-16 bg-amber-600/20 rounded-full flex items-center justify-center border-2 border-amber-600/40 shadow-amber">
              <Sword className="w-8 h-8 text-amber-500" />
            </div>
          </div>
          <h1 className="text-3xl font-serif text-amber-400 tracking-wider text-shadow-amber">
            RPG-IA
          </h1>
          <p className="text-slate-400 mt-1 text-sm italic font-serif">
            Enter the realm of legends
          </p>
        </div>

        {/* Card */}
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
            {/* Email */}
            <div>
              <label htmlFor="email" className="label-rune">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="adventurer@realm.io"
                className="input-dark"
                disabled={isLoading}
              />
            </div>

            {/* Password */}
            <div>
              <label htmlFor="password" className="label-rune">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPass ? 'text' : 'password'}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="input-dark pr-10"
                  disabled={isLoading}
                />
                <button
                  type="button"
                  onClick={() => setShowPass((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-amber-400 transition-colors"
                  aria-label={showPass ? 'Hide password' : 'Show password'}
                >
                  {showPass ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              className="btn-primary w-full justify-center mt-2"
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <span className="w-4 h-4 border-2 border-slate-900 border-t-transparent rounded-full animate-spin" />
                  Entering the realm…
                </>
              ) : (
                <>
                  <Sword className="w-4 h-4" />
                  Enter the Realm
                </>
              )}
            </button>
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

        {/* Footer */}
        <p className="text-center text-slate-600 text-xs mt-6 font-serif italic">
          Powered by Artificial Dungeon Master Intelligence
        </p>
      </div>
    </div>
  )
}
