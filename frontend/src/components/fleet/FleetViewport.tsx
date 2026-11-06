// FleetViewport — dashboard viewport that switches renderers keyed by the
// provider mode: the local simulation engine ('sim') or the WebSocket-driven
// live renderer ('live').
//
// Both modes share one 3-column layout (fleet rail | scene | metrics rail):
//  • the fleet rail is built by useFleetRail — from the engine snapshot in SIM
//    mode, from live/captured telemetry otherwise — so the cards always match
//    the scene in the middle;
//  • the metrics rail is MetricsDashboard (useMissionView), which follows the
//    same run: SIM carts → SIM numbers, live mission → live numbers.
//
// The SIM badge stays honest: it labels the client-side engine, never a fake
// LIVE feed (AGENTS.md §1.6 / §0.3).
import { Circle, CirclePause, CheckCircle, RefreshCw, Square } from 'lucide-react'

import { useSimulationProvider, type SimRunState } from '../../simulation/useSimulation'
import { WarehouseMap } from './LiveViewRender'
import { RunSetupForm } from '../simulation/RunSetupForm'
import { SceneCanvas } from '../simulation/SceneCanvas'
import { TelemetryOverlay } from '../simulation/TelemetryOverlay'
import { Sidebar } from '../layout/Sidebar'
import { MetricsDashboard } from '../metrics/MetricsDashboard'

export function FleetViewport() {
  const mode = useSimulationProvider((s) => s.mode)
  const initialized = useSimulationProvider((s) => s.initialized)
  const runState = useSimulationProvider((s) => s.runState)
  const reset = useSimulationProvider((s) => s.reset)
  const start = useSimulationProvider((s) => s.start)
  const pause = useSimulationProvider((s) => s.pause)
  const resume = useSimulationProvider((s) => s.resume)
  const stop = useSimulationProvider((s) => s.stop)
  const isRunning = useSimulationProvider((s) => s.runState === 'running')
  const isPaused = useSimulationProvider((s) => s.runState === 'paused')

  return (
    <div className="flex h-full min-h-[36rem] flex-col lg:flex-row">
      {/* Left rail: fleet summary + per-cart cards (SIM carts in SIM mode) */}
      <Sidebar />

      {/* Center: the scene — SIM engine canvas or the live warehouse map */}
      <main className="relative flex min-h-0 min-w-0 flex-1 flex-col" aria-label="Warehouse scene">
        {mode === 'sim' ? (
          <>
            <div className="relative min-h-[24rem] flex-1">
              <SceneCanvas />
              <TelemetryOverlay />
              <SimOverlays runState={runState} initialized={initialized} />
            </div>

            {/* Playback controls — honest per-state labels, single source of
                truth is the provider run state (AGENTS.md §1.6 / §0.3). */}
            <div className="flex items-center gap-2 border-t border-line bg-surface px-4 py-2 transition-colors duration-200">
              {runState === 'running' ? (
                <ControlButton onClick={pause} icon={CirclePause} label="Pause">
                  Pause
                </ControlButton>
              ) : runState === 'paused' ? (
                <ControlButton onClick={resume} icon={CirclePause} label="Resume">
                  Resume
                </ControlButton>
              ) : (
                <ControlButton onClick={() => start()} icon={Circle} primary label={runState === 'finished' ? 'Run again' : 'Start'}>
                  {runState === 'finished' ? 'Run again' : 'Start'}
                </ControlButton>
              )}
              <ControlButton onClick={stop} icon={Square} label="Stop" disabled={!isRunning && !isPaused && runState !== 'finished'}>
                Stop
              </ControlButton>
              <ControlButton onClick={reset} icon={RefreshCw} label="Reset" disabled={runState === 'running'}>
                Reset
              </ControlButton>
            </div>
          </>
        ) : (
          <div className="min-h-[36rem] flex-1">
            <WarehouseMap />
          </div>
        )}
      </main>

      {/* Right rail: metrics rail — the exact same run as the scene */}
      <aside
        className="scrollbar-thin w-full shrink-0 overflow-y-auto border-t border-line bg-surface p-4 transition-colors duration-200 lg:w-80 lg:border-t-0 lg:border-l"
        aria-label="Metrics rail"
      >
        <MetricsDashboard />
      </aside>
    </div>
  )
}

function SimOverlays({ runState, initialized }: { runState: SimRunState; initialized: boolean }) {
  if (!initialized) {
    // SceneCanvas renders the "Initializing simulation" placeholder itself —
    // don't duplicate it here (FleetViewport.test asserts a single instance).
    return null
  }

  // Honest SIM badge — only the running dot pulses; paused/finished/ready show
  // a static marker so the viewport never implies activity that isn't happening.
  const finished = runState === 'finished'

  return (
    <>
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
            Mission complete — press Reset to replay
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
    <span className={`inline-flex items-center gap-1.5 rounded-full bg-panel/80 px-3 py-1 text-xs font-medium ring-1 ring-line backdrop-blur ${meta.className}`}>
      {dot}
      SIM · {meta.label}
    </span>
  )
}

function ControlButton({
  onClick,
  icon: Icon,
  label,
  primary = false,
  disabled = false,
  children,
}: {
  onClick: () => void
  icon: typeof Circle
  label: string
  primary?: boolean
  disabled?: boolean
  children: string
}) {
  const buttonClass = primary
    ? 'bg-sky-500 text-white hover:bg-sky-400'
    : 'border border-line-strong bg-elevated text-fg hover:bg-surface-strong'

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={label}
      title={label}
      className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11px] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500 ${buttonClass}`}
    >
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />
      {children}
    </button>
  )
}
