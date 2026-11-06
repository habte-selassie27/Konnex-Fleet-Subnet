// App — dashboard layout (AGENTS.md §1.3: fleet rail | scene | metrics rail).
//
// The viewport is the single dashboard: FleetViewport holds the fleet rail, the
// scene (SIM engine or live map) and the metrics rail in lockstep via
// useFleetRail / useMissionView. Below it live the mission overview, the
// validator evaluation card and the benchmark / payment panels.
//
// Bootstraps the WebSocket; every major panel is wrapped in an ErrorBoundary
// so one crash never takes down the dashboard (AGENTS.md §1.6). The theme (a
// single `.dark` class on <html>) is applied here from the uiStore so the CSS
// token palettes and the WebGL scene palette stay in sync.
import { useEffect } from 'react'

import { useFleetSocket } from './hooks/useFleetSocket'
import { BenchmarkTable } from './components/benchmark/BenchmarkTable'
import { Header } from './components/layout/Header'
import { FleetViewport } from './components/fleet/FleetViewport'
import { MissionPanel } from './components/mission/MissionPanel'
import { EvaluationCard } from './components/validator/EvaluationCard'
import { ValidatorPanel } from './components/validator/ValidatorPanel'
import { ErrorBoundary } from './components/shared/ErrorBoundary'
import { PaymentPanel } from './components/payments/PaymentPanel'
import { useUiStore } from './store/uiStore'

export function App() {
  useFleetSocket()
  const theme = useUiStore((s) => s.theme)

  // Theme is a single class on <html>: index.css carries both palettes and
  // scenePalette.ts reads the same flag for the WebGL scene.
  useEffect(() => {
    const root = document.documentElement
    root.classList.toggle('dark', theme === 'dark')
  }, [theme])

  return (
    <div className="flex h-screen flex-col bg-surface text-fg transition-colors duration-200">
      <Header />

      <div className="min-h-0 flex-1 p-3">
        <ErrorBoundary label="Fleet viewport">
          <div className="h-full overflow-hidden rounded-xl border border-line/60 bg-panel">
            <FleetViewport />
          </div>
        </ErrorBoundary>
      </div>

      <div className="grid grid-cols-1 gap-3 px-3 pb-3 lg:grid-cols-3">
        <ErrorBoundary label="Mission panel">
          <MissionPanel />
        </ErrorBoundary>
        <ErrorBoundary label="Evaluation card">
          <EvaluationCard />
        </ErrorBoundary>
        <ErrorBoundary label="Validator panel">
          <ValidatorPanel />
        </ErrorBoundary>
      </div>

      <ErrorBoundary label="Benchmark table">
        <div className="px-3 pb-3">
          <BenchmarkTable />
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
