// ErrorBoundary — one crashing panel must never take down the dashboard
// (AGENTS.md §1.6). Wraps every major panel.
import { Component, type ErrorInfo, type ReactNode } from 'react'

interface ErrorBoundaryProps {
  children: ReactNode
  label?: string
}

interface ErrorBoundaryState {
  hasError: boolean
  message: string
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, message: '' }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, message: error.message }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Structured logging hook — replace with your logger when available.
    console.error('[ErrorBoundary]', error, info.componentStack)
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          aria-label={`${this.props.label ?? 'Panel'} failed to load`}
          className="flex h-full min-h-24 w-full flex-col items-center justify-center gap-2 rounded-xl border border-red-900/60 bg-red-950/20 p-4 text-center"
        >
          <p className="text-sm font-semibold text-red-400">
            {this.props.label ?? 'Panel'} unavailable
          </p>
          <p className="max-w-sm text-xs text-slate-400">{this.state.message}</p>
        </div>
      )
    }
    return this.props.children
  }
}
