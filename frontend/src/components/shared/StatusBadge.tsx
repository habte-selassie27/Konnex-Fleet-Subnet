// StatusBadge — renders a status as color + icon + text (accessibility rule:
// color is never the sole indicator of state, AGENTS.md §1.6).
import type { LucideIcon } from 'lucide-react'

interface StatusBadgeProps {
  label: string
  icon: LucideIcon
  className: string
}

export function StatusBadge({ label, icon: Icon, className }: StatusBadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${className}`}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {label}
    </span>
  )
}
