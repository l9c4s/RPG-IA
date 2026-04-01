import React, { type ReactNode } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

interface ErrorBoundaryProps {
  children:  ReactNode
  fallback?: ReactNode
}

interface ErrorBoundaryState {
  hasError:     boolean
  errorMessage: string
}

export class ErrorBoundary extends React.Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, errorMessage: '' }
  }

  static getDerivedStateFromError(error: unknown): ErrorBoundaryState {
    const message =
      error instanceof Error ? error.message : 'Erro desconhecido'
    return { hasError: true, errorMessage: message }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error('[ErrorBoundary] Caught error:', error, info)
  }

  handleReset = (): void => {
    this.setState({ hasError: false, errorMessage: '' })
  }

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <div className="min-h-screen bg-slate-900 flex items-center justify-center p-8">
          <div className="card-rune max-w-md w-full p-8 text-center space-y-5">
            <div className="flex justify-center">
              <div className="w-16 h-16 bg-red-900/30 rounded-full flex items-center justify-center border border-red-700/50">
                <AlertTriangle className="w-8 h-8 text-red-400" />
              </div>
            </div>

            <div className="space-y-2">
              <h1 className="text-2xl font-serif text-amber-400">
                Algo deu errado
              </h1>
              <p className="text-slate-400 text-sm font-serif italic">
                Um erro inesperado ocorreu no reino.
              </p>
            </div>

            {this.state.errorMessage && (
              <div className="bg-red-900/30 border border-red-700/40 rounded-md px-4 py-3 text-left">
                <p className="text-red-300 text-xs font-mono break-all">
                  {this.state.errorMessage}
                </p>
              </div>
            )}

            <button
              onClick={this.handleReset}
              className="btn-primary w-full justify-center"
            >
              <RefreshCw className="w-4 h-4" />
              Tentar novamente
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}
