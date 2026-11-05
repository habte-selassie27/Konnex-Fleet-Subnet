// App — dashboard layout (AGENTS.md §1.3: 3-column grid sidebar|map|metrics).
// Bootstraps the WebSocket; every major panel is wrapped in an ErrorBoundary
// so one crash never takes down the dashboard (AGENTS.md §1.6).
import { useFleetSocket } from './hooks/useFleetSocket'
import { BenchmarkTable } from './components/benchmark/BenchmarkTable'
import { Header } from './components/layout/Header'
import { Sidebar } from './components/layout/Sidebar'
import { WarehouseMap } from './components/fleet/WarehouseMap'
import { MissionPanel } from './components/mission/MissionPanel'
import { MetricsDashboard } from './components/metrics/MetricsDashboard'
import { EvaluationCard } from './components/validator/EvaluationCard'
import { ErrorBoundary } from './components/shared/ErrorBoundary'
import { PaymentPanel } from './components/payments/PaymentPanel'

export function App() {
  useFleetSocket()

  return (
    <div className="flex h-screen flex-col bg-slate-950 text-slate-100">
      <Header />
      <div className="flex min-h-0 flex-1">
        <ErrorBoundary label="Fleet sidebar">
          <Sidebar />
        </ErrorBoundary>

        <main className="flex min-w-0 flex-1 flex-col gap-4 p-4" aria-label="Dashboard">
          <ErrorBoundary label="Warehouse map">
            <div className="min-h-[36rem] flex-[2]">
              <WarehouseMap />
            </div>
          </ErrorBoundary>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <ErrorBoundary label="Mission panel">
              <MissionPanel />
            </ErrorBoundary>
            <ErrorBoundary label="Evaluation panel">
              <EvaluationCard />
            </ErrorBoundary>
          </div>

          <ErrorBoundary label="Benchmark panel">
            <BenchmarkTable />
          </ErrorBoundary>

          <ErrorBoundary label="Agent payments panel">
            <PaymentPanel />
          </ErrorBoundary>
        </main>

        <ErrorBoundary label="Metrics panel">
          <div className="w-80 shrink-0 overflow-y-auto border-l border-slate-800 bg-slate-950 p-4">
            <MetricsDashboard />
          </div>
        </ErrorBoundary>
      </div>
    </div>
  )
}
