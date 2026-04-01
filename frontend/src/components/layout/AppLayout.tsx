import React, { type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { Sword, BookOpen, LogOut } from 'lucide-react'
import { useAuth } from '../../hooks/useAuth'

interface AppLayoutProps {
  children: ReactNode
  title?:   string
}

export function AppLayout({ children, title }: AppLayoutProps): React.ReactElement {
  const { user, logout } = useAuth()

  return (
    <div className="min-h-screen bg-slate-900 bg-dungeon-texture">
      {/* Navbar */}
      <nav className="sticky top-0 z-40 bg-slate-900/95 backdrop-blur border-b border-amber-700/30 px-4 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          {/* Brand */}
          <Link to="/dashboard" className="flex items-center gap-3 group">
            <div className="w-8 h-8 bg-amber-600/20 rounded-full flex items-center justify-center border border-amber-600/40 group-hover:border-amber-600/70 transition-colors">
              <Sword className="w-4 h-4 text-amber-500" />
            </div>
            <span className="font-serif text-amber-400 text-lg tracking-wide group-hover:text-amber-300 transition-colors">
              RPG·IA
            </span>
          </Link>

          {/* Actions */}
          <div className="flex items-center gap-3">
            <Link to="/knowledge" className="btn-ghost py-1.5 text-xs">
              <BookOpen className="w-3.5 h-3.5" />
              Knowledge
            </Link>
            <div className="w-px h-5 bg-slate-700" />
            <span className="text-slate-400 text-sm hidden sm:block font-serif">
              {user?.username}
            </span>
            <button
              onClick={logout}
              className="btn-ghost py-1.5 px-2.5 text-xs"
              title="Sair"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </nav>

      {/* Page content */}
      <main className="max-w-6xl mx-auto px-4 py-8">
        {title && (
          <h1 className="text-3xl font-serif text-amber-400 text-shadow-amber mb-6">
            {title}
          </h1>
        )}
        {children}
      </main>
    </div>
  )
}
