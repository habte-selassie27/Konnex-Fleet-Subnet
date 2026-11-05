// OfflineIndicator — "Simulator offline" state (AGENTS.md §1.6: never render
// fake robots when there is no live data).
import { WifiOff } from 'lucide-react'

interface OfflineIndicatorProps {
  message?: string
}

export function OfflineIndicator({ message = 'Simulator offline — no live data' }: OfflineIndicatorProps) {
  return (
    <div
      role="status"
      aria-label="Simulator offline"
      className="flex h-full w-full flex-col items-center justify-center gap-3 rounded-xl border border-slate-700 bg-slate-900/80 p-6 text-center"
    >
      <WifiOff className="h-10 w-10 text-slate-500" aria-hidden="true" />
      <p className="text-sm font-medium text-slate-300">{message}</p>
      <p className="text-xs text-slate-500">Start the backend, then refresh to see live fleet data.</p>
    </div>
  )
}
