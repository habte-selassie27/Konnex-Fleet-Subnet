// AgentDecisionList — every persisted decision the agent made (paid or
// no-action), newest first, with the provider comparison behind each choice.
import { BrainCircuit } from 'lucide-react'
import type { AgentDecision } from '../../types'
import { AgentDecisionCard } from './AgentDecisionCard'

interface AgentDecisionListProps {
  decisions: AgentDecision[]
  isMock: boolean
}

export function AgentDecisionList({ decisions, isMock }: AgentDecisionListProps) {
  return (
    <section aria-label="Agent decisions">
      <h3 className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-subtle">
        <BrainCircuit className="h-3.5 w-3.5" aria-hidden="true" />
        Agent Decisions
      </h3>
      {decisions.length === 0 ? (
        <div className="rounded-xl border border-line/60 bg-panel p-4 text-center text-xs text-subtle">
          No agent decisions yet — the agent records one whenever live fleet telemetry reports a
          low battery or a failed robot. You can also run the demo to see it evaluate providers.
        </div>
      ) : (
        <div className="space-y-3">
          {decisions.map((decision) => (
            <AgentDecisionCard
              key={decision.id || `${decision.vehicle_id}-${decision.service}-${decision.timestamp}`}
              decision={decision}
              isMock={isMock}
            />
          ))}
        </div>
      )}
    </section>
  )
}
