import React, { Suspense, lazy } from 'react'
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  Outlet,
} from 'react-router-dom'
import { AuthProvider } from './contexts/AuthContext'
import { ErrorBoundary } from './components/ErrorBoundary'
import { useAuth } from './hooks/useAuth'

// ── Lazy page imports ──────────────────────────────────────────────────────
const Login          = lazy(() => import('./pages/Login'))
const Register       = lazy(() => import('./pages/Register'))
const Dashboard      = lazy(() => import('./pages/Dashboard'))
const Lobby          = lazy(() => import('./pages/Lobby'))
const GameSession    = lazy(() => import('./components/GameSession'))
const CharacterSheet = lazy(() => import('./components/CharacterSheet'))
const KnowledgeGate  = lazy(() => import('./components/KnowledgeGate'))

// ── Full-screen loading spinner ───────────────────────────────────────────
function PageLoader(): React.ReactElement {
  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 border-4 border-amber-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-amber-500 font-serif text-sm tracking-widest animate-pulse">
          Summoning the realm…
        </p>
      </div>
    </div>
  )
}

// ── Protected route wrapper ────────────────────────────────────────────────
function RequireAuth(): React.ReactElement {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) return <PageLoader />
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <Outlet />
}

// ── Public-only wrapper (redirect authed users away from login/register) ───
function PublicOnly(): React.ReactElement {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) return <PageLoader />
  if (isAuthenticated) return <Navigate to="/dashboard" replace />
  return <Outlet />
}

// ── Root redirect ──────────────────────────────────────────────────────────
function RootRedirect(): React.ReactElement {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) return <PageLoader />
  return <Navigate to={isAuthenticated ? '/dashboard' : '/login'} replace />
}

// ── App shell ──────────────────────────────────────────────────────────────
function AppRoutes(): React.ReactElement {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        {/* Root */}
        <Route path="/" element={<RootRedirect />} />

        {/* Public-only routes */}
        <Route element={<PublicOnly />}>
          <Route path="/login"    element={<Login />} />
          <Route path="/register" element={<Register />} />
        </Route>

        {/* Protected routes */}
        <Route element={<RequireAuth />}>
          <Route path="/dashboard"                      element={<Dashboard />} />
          <Route path="/lobby/:id"                      element={<Lobby />} />
          <Route path="/campaign/:id"                   element={<GameSession />} />
          <Route path="/campaign/:id/characters"        element={<CharacterSheet />} />
          <Route path="/knowledge"                      element={<KnowledgeGate />} />
        </Route>

        {/* 404 fallback */}
        <Route
          path="*"
          element={
            <div className="min-h-screen bg-slate-900 flex flex-col items-center justify-center gap-6 p-8">
              <h1 className="text-6xl font-serif text-amber-500 text-shadow-amber">404</h1>
              <p className="text-slate-300 text-lg font-serif italic">
                This page was lost in the dungeon.
              </p>
              <a
                href="/dashboard"
                className="btn-primary"
              >
                Return to the Keep
              </a>
            </div>
          }
        />
      </Routes>
    </Suspense>
  )
}

// ── Root App ───────────────────────────────────────────────────────────────
export default function App(): React.ReactElement {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </BrowserRouter>
    </ErrorBoundary>
  )
}
