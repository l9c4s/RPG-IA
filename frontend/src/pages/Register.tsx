import React, { useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { Eye, EyeOff, Shield, AlertCircle, CheckCircle } from 'lucide-react'
import { useAuth } from '../hooks/useAuth'
import { AuthLayout } from '../components/layout/AuthLayout'
import { Button } from '../components/ui/Button'
import { Input } from '../components/ui/Input'

interface PasswordStrength {
  score: 0 | 1 | 2 | 3 | 4
  label: string
  color: string
}

function checkPasswordStrength(password: string): PasswordStrength {
  let score = 0
  if (password.length >= 8)           score++
  if (/[A-Z]/.test(password))         score++
  if (/[0-9]/.test(password))         score++
  if (/[^A-Za-z0-9]/.test(password))  score++

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

  const [username, setUsername] = useState('')
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [confirm,  setConfirm]  = useState('')
  const [showPass, setShowPass] = useState(false)
  const [localErr, setLocalErr] = useState<string | null>(null)

  const displayError   = error ?? localErr
  const strength       = checkPasswordStrength(password)
  const passwordsMatch = password && confirm && password === confirm

  async function handleSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault()
    setLocalErr(null)
    clearError()

    if (!username.trim() || !email.trim() || !password || !confirm) {
      setLocalErr('Por favor, preencha todos os campos.')
      return
    }
    if (username.trim().length < 3) {
      setLocalErr('O nome de usuário deve ter pelo menos 3 caracteres.')
      return
    }
    if (password.length < 8) {
      setLocalErr('A senha deve ter pelo menos 8 caracteres.')
      return
    }
    if (password !== confirm) {
      setLocalErr('As senhas não coincidem.')
      return
    }

    try {
      await register(username.trim(), email.trim(), password)
    } catch {
      // Error stored in hook state
    }
  }

  return (
    <AuthLayout subtitle="Forge your legend" icon={<Shield className="w-8 h-8 text-amber-500" />}>
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
          <Input
            id="username"
            type="text"
            label="Hero Name"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Thorin Stoneblade"
            disabled={isLoading}
            minLength={3}
            maxLength={50}
          />

          <Input
            id="email"
            type="email"
            label="Email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="hero@realm.io"
            disabled={isLoading}
          />

          <div>
            <Input
              id="password"
              type={showPass ? 'text' : 'password'}
              label="Password"
              autoComplete="new-password"
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

          <div>
            <Input
              id="confirm"
              type={showPass ? 'text' : 'password'}
              label="Confirm Password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="••••••••"
              disabled={isLoading}
              className={confirm && !passwordsMatch ? 'border-red-600 focus:border-red-500' : ''}
              rightElement={
                passwordsMatch ? (
                  <CheckCircle className="w-4 h-4 text-green-500 pointer-events-none" />
                ) : undefined
              }
            />
          </div>

          <Button
            type="submit"
            variant="primary"
            size="md"
            isLoading={isLoading}
            leftIcon={<Shield className="w-4 h-4" />}
            className="w-full justify-center mt-2"
          >
            {isLoading ? 'Creating hero…' : 'Begin Your Adventure'}
          </Button>
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
    </AuthLayout>
  )
}
