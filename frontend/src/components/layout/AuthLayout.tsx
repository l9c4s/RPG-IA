import React, { type ReactNode } from 'react'
import { Sword } from 'lucide-react'

interface AuthLayoutProps {
  children:   ReactNode
  subtitle?:  string
  icon?:      ReactNode
}

export function AuthLayout({
  children,
  subtitle = 'Enter the realm of legends',
  icon,
}: AuthLayoutProps): React.ReactElement {
  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background decorative elements */}
      <div className="absolute inset-0 bg-dungeon-texture opacity-30 pointer-events-none" />
      <div className="absolute top-0 left-0 w-96 h-96 bg-amber-900/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 right-0 w-96 h-96 bg-red-900/10 rounded-full blur-3xl pointer-events-none" />

      <div className="relative w-full max-w-md">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <div className="w-16 h-16 bg-amber-600/20 rounded-full flex items-center justify-center border-2 border-amber-600/40 shadow-amber">
              {icon ?? <Sword className="w-8 h-8 text-amber-500" />}
            </div>
          </div>
          <h1 className="text-3xl font-serif text-amber-400 tracking-wider text-shadow-amber">
            RPG·IA
          </h1>
          <p className="text-slate-400 mt-1 text-sm italic font-serif">
            {subtitle}
          </p>
        </div>

        {/* Card */}
        {children}

        {/* Footer */}
        <p className="text-center text-slate-600 text-xs mt-6 font-serif italic">
          Powered by Artificial Dungeon Master Intelligence
        </p>
      </div>
    </div>
  )
}
