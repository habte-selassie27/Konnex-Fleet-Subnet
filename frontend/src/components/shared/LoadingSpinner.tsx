// LoadingSpinner — async loading state (AGENTS.md §1.6: all async states
// handled: loading / error / empty / data).
export function LoadingSpinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" aria-label={label} className="flex items-center justify-center gap-2 p-6">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-600 border-t-sky-400" />
      <span className="text-xs text-slate-400">{label}</span>
    </div>
  )
}
