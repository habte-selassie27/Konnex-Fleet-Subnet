// FleetViewport — top-level viewport that switches between the live renderer
// (live-robot rail driven by the WebSocket fleet state) and the local
// simulation renderer (SceneCanvas + telemetry), keyed by SIM_MODE.
//
// When the user picks "Live" in the Header, SIM_MODE=live → the live rail
// shows real robot telemetry from the WebSocket. When the user picks "Sim",
// SIM_MODE=sim → the dark cyberpunk simulation canvas with an honest SIM badge
// (never a fake LIVE badge — AGENTS.md §1.6 / §0.3).
//
// Live view: 3-column dashboard layout (sidebar rail | map | metrics) for the
// WebSocket-driven renderer, same as the original dashboard intent. The map is
// the WarehouseMap component (honest LIVE badge, no fabricated robots).

import { CirclePause, CheckCircle, Circle } from 'lucide-react'

import { useSimulationProvider, type SimRunState } from '../../simulation/useSimulation'
import { WarehouseMap } from './LiveViewRender'
import { RunSetupForm } from '../simulation/RunSetupForm'
import { SceneCanvas } from '../simulation/SceneCanvas'
import { TelemetryOverlay } from '../simulation/TelemetryOverlay'
import { FleetSummary } from './FleetSummary'
import { RobotCard } from './RobotCard'
import { useFleetRail } from '../../hooks/useFleetRail'
import { MetricsDashboard } from '../metrics/MetricsDashboard'

export function FleetViewport() {
  const mode = useSimulationProvider((s) => s.mode)
  const initialized = useSimulationProvider((s) => s.initialized)

  return (
    <div className="relative min-h-[36rem] flex-[2]">
      {mode === 'live' ? (
        <LiveView />
      ) : (
        <SimView initialized={initialized} />
      )}
    </div>
  )
}

function LiveView() {
  const { cards, counts, avgBattery, source, capturedAt } = useFleetRail()

  // Live 3-column layout: sidebar rail | warehouse map | metrics panel.
  // Cards come from the resolved fleet view (WebSocket telemetry, then the
  // captured run) — never fabricated data.
  return (
    <div className="flex h-full min-h-[36rem] flex-col lg:flex-row">
      {/* Left rail: fleet summary + per-robot cards */}
      <aside className="w-full shrink-0 border-b border-line lg:w-72 lg:border-b-0 lg:border-r border-line bg-surface p-4 flex flex-col gap-4 overflow-y-auto" aria-label="Fleet sidebar">
        <FleetSummary
          counts={counts}
          avgBattery={avgBattery}
          source={source}
          capturedAt={capturedAt}
        />
        {cards.length === 0 ? (
          <p className="text-center text-xs text-subtle">Waiting for robot telemetry…</p>
        ) : (
          <ul className="space-y-2">
            {cards.map((card) => (
              <RobotCard key={card.id} robot={card} />
            ))}
          </ul>
        )}
      </aside>

      {/* Center: 3D warehouse map with real live robot positions */}
      <main className="flex min-h-0 flex-1 flex-col gap-4 p-4" aria-label="Live warehouse map">
        <WarehouseMap />
      </main>

      {/* Right rail: live metrics */}
      <aside className="w-full shrink-0 border-t border-line lg:w-80 lg:border-t-0 lg:border-l border-line bg-surface p-4 overflow-y-auto" aria-label="Live metrics">
        <MetricsDashboard />
      </aside>
    </div>
  )
}

function SimView({ initialized }: { initialized: boolean }) {
  const runState = useSimulationProvider((s) => s.runState)

  if (!initialized) {
    return (
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="rounded-full bg-panel px-3 py-1 text-xs font-medium text-muted ring-1 ring-line">
          Initializing simulation
        </span>
      </div>
    )
  }

  const finished = runState === 'finished'

  return (
    <>
      <SceneCanvas />
      <TelemetryOverlay />
      {/* Honest SIM badge — only the running dot pulses, and only while the engine
          is actually advancing. Paused/finished/ready show a static marker so the
          viewport never implies activity that isn't happening (AGENTS.md §1.6/§0.3). */}
      <div className="pointer-events-none absolute left-3 top-3 flex gap-2">
        <SimRunBadge runState={runState} />
      </div>
      {/* Drop-count setup — restages the floor with the chosen number of crates. */}
      <div className="absolute left-3 top-12">
        <RunSetupForm />
      </div>
      {runState === 'idle' ? (
        <div className="pointer-events-none absolute bottom-16 left-1/2 -translate-x-1/2">
          <span className="rounded-full bg-sky-500/15 px-3 py-1 text-xs font-medium text-sky-400 ring-1 ring-line backdrop-blur">
            Press Start to run the fleet
          </span>
        </div>
      ) : null}
      {finished ? (
        <div className="pointer-events-none absolute bottom-16 left-1/2 -translate-x-1/2">
          <span className="rounded-full bg-sky-500/15 px-3 py-1 text-xs font-medium text-sky-400 ring-1 ring-line backdrop-blur">
            Mission complete — press Start to run again, or Reset to stage a fresh run
          </span>
        </div>
      ) : null}
      {runState === 'paused' ? (
        <div className="pointer-events-none absolute bottom-16 left-1/2 -translate-x-1/2">
          <span className="rounded-full bg-amber-500/15 px-3 py-1 text-xs font-medium text-amber-400 ring-1 ring-line backdrop-blur">
            Paused — press Resume to continue
          </span>
        </div>
      ) : null}
    </>
  )
}

const SIM_BADGE_LABELS: Record<SimRunState, { label: string; className: string }> = {
  idle:    { label: 'READY',  className: 'text-subtle' },
  running: { label: 'RUNNING', className: 'text-cyan-400' },
  paused:  { label: 'PAUSED',  className: 'text-amber-400' },
  finished:{ label: 'DONE',    className: 'text-sky-400' },
}

function SimRunBadge({ runState }: { runState: SimRunState }) {
  const meta = SIM_BADGE_LABELS[runState]
  const running = runState === 'running'

  const dot =
    running ? (
      <span className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse" aria-hidden="true" />
    ) : runState === 'paused' ? (
      <CirclePause className="h-2 w-2 text-amber-400" aria-hidden="true" />
    ) : runState === 'finished' ? (
      <CheckCircle className="h-2 w-2 text-sky-400" aria-hidden="true" />
    ) : (
      <Circle className="h-2 w-2 text-subtle" aria-hidden="true" />
    )

  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full bg-panel/80 px-3 py-1 text-xs font-medium ring-1 ring-line ${meta.className}`}>
      {dot}
      SIM · {meta.label}
    </span>
  )
}
