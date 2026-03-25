import React, { useState, FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Eye, EyeOff, Shield, AlertCircle, CheckCircle } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'

interface PasswordStrength {
  score:  0 | 1 | 2 | 3 | 4
  label:  string
  color:  string
}

function checkPasswordStrength(password: string): PasswordStrength {
  let score = 0
  if (password.length >= 8)                    score++
  if (/[A-Z]/.test(password))                 score++
  if (/[0-9]/.test(password))                 score++
  if (/[^A-Za-z0-9]/.test(password))          score++

  const levels: PasswordStrength[] = [
    { score: 0, label: 'Too short',  color: 'bg-slate-600' },
    { score: 1, label: 'Weak',       color: 'bg-red-600'   },
    { score: 2, label: 'Fair',       color: 'bg-amber-500' },
    { score: 3, label: 'Good',       color: 'bg-blue-500'  },
    { score: 4, label: 'Strong',     color: 'bg-green-500' },
  ]
  return levels[score] as PasswordStrength
}

export default function Register(): React.ReactElement {
  const { register, isLoading, error, clearError } = useAuth()

  const [username, setUsername]   = useState('')
  const [email,    setEmail]      = useState('')
  const [password, setPassword]   = useState('')
  const [confirm,  setConfirm]    = useState('')
  const [showPass, setShowPass]   = useState(false)
  const [localErr, setLocalErr]   = useState<string | null>(null)

  const displayError  = error ?? localErr
  const strength      = checkPasswordStrength(password)
  const passwordsMatch = password && confirm && password === confirm

  async function handleSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault()
    setLocalErr(null)
    clearError()

    if (!username.trim() || !email.trim() || !password || !confirm) {
      setLocalErr('Please fill in all fields.')
      return
    }
    if (username.trim().length < 3) {
      setLocalErr('Username must be at least 3 characters.')
      return
    }
    if (password.length < 8) {
      setLocalErr('Password must be at least 8 characters.')
      return
    }
    if (password !== confirm) {
      setLocalErr('Passwords do not match.')
      return
    }

    try {
      await register(username.trim(), email.trim(), password)
    } catch {
      // Error stored in hook state
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 bg-dungeon-texture opacity-30 pointer-events-none" />
      <div className="absolute top-0 right-0 w-96 h-96 bg-amber-900/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-96 h-96 bg-purple-900/10 rounded-full blur-3xl pointer-events-none" />

      <div className="relative w-full max-w-md">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <div className="w-16 h-16 bg-amber-600/20 rounded-full flex items-center justify-center border-2 border-amber-600/40 shadow-amber">
              <Shield className="w-8 h-8 text-amber-500" />
            </div>
          </div>
          <h1 className="text-3xl font-serif text-amber-400 tracking-wider text-shadow-amber">
            RPG-IA
          </h1>
          <p className="text-slate-400 mt-1 text-sm italic font-serif">
            Forge your legend
          </p>
        </div>

        {/* Card */}
        <div className="card-rune p-8">
          <h2 className="text-xl font-serif text-slate-100 mb-6 text-center tracking-wide">
            Create Your Hero
          </h2>

          {/* Error banner */}
          {displayError && (
            <div className="flex items-start gap-2 bg-red-900/40 border border-red-700/60 rounded-md px-4 py-3 mb-5 text-red-300 text-sm animate-fade-in">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{displayError}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4" noValidate>
            {/* Username */}
            <div>
              <label htmlFor="username" className="label-rune">
                Hero Name
              </label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Thorin Stoneblade"
                className="input-dark"
                disabled={isLoading}
                minLength={3}
                maxLength={50}
              />
            </div>

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
                placeholder="hero@realm.io"
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
                  autoComplete="new-password"
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

              {/* Password strength bar */}
              {password && (
                <div className="mt-2 space-y-1">
                  <div className="flex gap-1">
                    {[1, 2, 3, 4].map((i) => (
                      <div
                        key={i}
                        className={`h-1 flex-1 rounded-full transition-all duration-300 ${
                          i <= strength.score ? strength.color : 'bg-slate-700'
                        }`}
                      />
                    ))}
                  </div>
                  <p className="text-xs text-slate-500">{strength.label}</p>
                </div>
              )}
            </div>

            {/* Confirm password */}
            <div>
              <label htmlFor="confirm" className="label-rune">
                Confirm Password
              </label>
              <div className="relative">
                <input
                  id="confirm"
                  type={showPass ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="••••••••"
                  className={`input-dark pr-10 ${
                    confirm && !passwordsMatch
                      ? 'border-red-600 focus:border-red-500'
                      : ''
                  }`}
                  disabled={isLoading}
                />
                {passwordsMatch && (
                  <CheckCircle className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-green-500" />
                )}
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
                  Creating hero…
                </>
              ) : (
                <>
                  <Shield className="w-4 h-4" />
                  Begin Your Adventure
                </>
              )}
            </button>
          </form>

          {/* Divider */}
          <div className="divider-rune mt-6">
            <span>or</span>
          </div>

          {/* Login link */}
          <p className="text-center text-slate-400 text-sm mt-4">
            Already a hero?{' '}
            <Link
              to="/login"
              className="text-amber-400 hover:text-amber-300 underline underline-offset-2 transition-colors"
            >
              Sign in here
            </Link>
          </p>
        </div>

        <p className="text-center text-slate-600 text-xs mt-6 font-serif italic">
          Powered by Artificial Dungeon Master Intelligence
        </p>
      </div>
    </div>
  )
}
