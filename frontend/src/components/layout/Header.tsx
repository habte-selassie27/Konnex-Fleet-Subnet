// Header — top bar with the mission-scoped provenance badge, the policy/task
// context of the exact mission the panels below show, and the theme toggle.
//
// The badge is driven by useMissionView — the same hook that feeds
// MissionPanel and the metrics rail — so it can never describe a different
// run than the one on screen (AGENTS.md Law 1 / §0.3). In SIM mode the scene,
// the fleet rail and the header all describe the same engine run.
import { Moon, Sun } from 'lucide-react'

import { useMissionView } from '../../hooks/useMissionView'
import { useSimulationProvider } from '../../simulation/useSimulation'
import { useUiStore } from '../../store/uiStore'
import { SourcePill } from '../shared/SourcePill'

export function Header() {
  const { mission, source } = useMissionView()
  const theme = useUiStore((s) => s.theme)
  const toggleTheme = useUiStore((s) => s.toggleTheme)
  // Scene renderer mode: the SIM engine floor or the live WebSocket warehouse.
  // The viewport, the fleet rail and the metrics rail all follow this mode, so
  // the toggle is the one control that picks what the whole dashboard shows.
  const simMode = useSimulationProvider((s) => s.mode === 'sim')
  const setMode = useSimulationProvider((s) => s.setMode)

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-line bg-surface px-4 transition-colors duration-200">
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-semibold text-fg">Konnex Fleet Intelligence</h1>

        {/* Mission-scoped provenance: describes the mission panels below, while
            the viewport badge describes the scene renderer. */}
        <div role="group" aria-label="Mission data source" className="flex items-center gap-2">
          <span className="text-xs text-muted">Mission</span>
          <SourcePill source={source} capturedAt={mission?.captured_at ?? null} />
        </div>

        {/* Scene mode: what the center viewport + fleet rail render. */}
        <div
          role="group"
          aria-label="Scene mode"
          className="inline-flex items-center rounded-lg border border-line bg-elevated p-0.5 transition-colors duration-200"
        >
          <button
            type="button"
            onClick={() => setMode('sim')}
            aria-pressed={simMode}
            aria-label="Show SIM scene"
            title="SIM — client-side simulation engine"
            className={`rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500 ${
              simMode
                ? 'bg-sky-500 text-white'
                : 'text-muted hover:text-fg'
            }`}
          >
            Sim
          </button>
          <button
            type="button"
            onClick={() => setMode('live')}
            aria-pressed={!simMode}
            aria-label="Show LIVE scene"
            title="LIVE — WebSocket robot telemetry"
            className={`rounded-md px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500 ${
              !simMode
                ? 'bg-sky-500 text-white'
                : 'text-muted hover:text-fg'
            }`}
          >
            Live
          </button>
        </div>
      </div>

      <div className="flex items-center gap-4 text-xs text-muted">
        {mission && (
          <>
            <span>
              Policy{' '}
              <span className="font-mono text-fg">{mission.policy ?? '—'}</span>
            </span>
            <span className="font-mono">
              {mission.completed_tasks}/{mission.total_tasks} tasks
            </span>
          </>
        )}

        <button
          type="button"
          onClick={toggleTheme}
          aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-line bg-panel text-muted transition-colors hover:border-line-strong hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500"
        >
          {theme === 'dark' ? (
            <Sun className="h-4 w-4" aria-hidden="true" />
          ) : (
            <Moon className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
      </div>
    </header>
  )
}
