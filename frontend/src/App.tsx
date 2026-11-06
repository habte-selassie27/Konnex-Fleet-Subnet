// App — dashboard layout (AGENTS.md §1.3: fleet rail | scene | metrics rail).
//
// The viewport is the single dashboard: FleetViewport holds the fleet rail, the
// scene (SIM engine or live map) and the metrics rail in lockstep via
// useFleetRail / useMissionView. Below it live the mission overview, the
// validator network and the benchmark / payment panels.
//
// Bootstraps the WebSocket; every major panel is wrapped in an ErrorBoundary
// so one crash never takes down the dashboard (AGENTS.md §1.6). The theme (a
// single `.dark` class on <html>) is applied here from the uiStore so the CSS
// token palettes and the WebGL scene palette stay in sync.
import { useEffect } from 'react'

import { useFleetSocket } from './hooks/useFleetSocket'
import { useAutoCaptureSim } from './hooks/useAutoCaptureSim'
import { BenchmarkTable } from './components/benchmark/BenchmarkTable'
import { PerRobotLeaderboard } from './components/benchmark/PerRobotLeaderboard'
import { Header } from './components/layout/Header'
import { FleetViewport } from './components/fleet/FleetViewport'
import { MissionPanel } from './components/mission/MissionPanel'
import { ValidatorNetworkPanel } from './components/validator/ValidatorNetworkPanel'
import { ErrorBoundary } from './components/shared/ErrorBoundary'
import { PaymentPanel } from './components/payments/PaymentPanel'
import { useUiStore } from './store/uiStore'

export function App() {
  useFleetSocket()
  useAutoCaptureSim()
  const theme = useUiStore((s) => s.theme)

  // Theme is a single class on <html>: index.css carries both palettes and
  // scenePalette.ts reads the same flag for the WebGL scene.
  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('dark', theme === 'dark')
  }, [theme])

  return (
    <div className="flex min-h-screen flex-col bg-surface text-fg transition-colors duration-200">
      <Header />

      {/* The scene gets a definite height, never a shrinkable flex-basis: as a
          `flex-1 min-h-0` row it collapsed to ~60px whenever the panels below
          were tall, and `overflow-hidden` then clipped the 576px map to a
          blank strip. On desktop it fills the first screen; the panels below
          scroll with the page (AGENTS.md §1.7). */}
      <div className="p-3 lg:h-[calc(100vh-3.5rem)] lg:min-h-[37.5rem] lg:shrink-0">
        <ErrorBoundary label="Fleet viewport">
          <div className="overflow-hidden rounded-xl border border-line/60 bg-panel lg:h-full">
            <FleetViewport />
          </div>
        </ErrorBoundary>
      </div>

      <div className="grid grid-cols-1 gap-3 px-3 pb-3 lg:grid-cols-3">
        <ErrorBoundary label="Mission panel">
          <MissionPanel />
        </ErrorBoundary>
        <ErrorBoundary label="Validator network">
          <ValidatorNetworkPanel />
        </ErrorBoundary>
      </div>

      <ErrorBoundary label="Benchmark table">
        <div className="px-3 pb-3">
          <BenchmarkTable />
          <div className="mt-3">
            <PerRobotLeaderboard />
          </div>
        </div>
      </ErrorBoundary>

      <ErrorBoundary label="Payment panel">
        <div className="grow overflow-y-auto px-3 pb-4">
          <PaymentPanel />
        </div>
      </ErrorBoundary>
    </div>
  )
}
