// BenchmarkTable — policy comparison (AGENTS.md §1.2 benchmark/).
//
// Data comes exclusively from the backend's measured rows (GET
// /experiments/benchmarks — produced by `make benchmark`). The table never
// fabricates numbers: unmeasured rows show em dashes plus their skip reason,
// and API failures surface as an alert instead of fake rows (AGENTS.md Law 1).
import { BarChart3 } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../../services/api'
import type { BenchmarkResult } from '../../types'
import { LoadingSpinner } from '../shared/LoadingSpinner'

type LoadState =
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'empty' }
  | { kind: 'data'; rows: BenchmarkResult[] }

function scoreCell(mean: number | null, std: number | null): string {
  if (mean === null) return '—'
  // The ± spread is part of the record even when it is 0.0 (% ± 0.0 %) —
  // hiding it would overstate certainty beyond what was measured.
  return std === null
    ? mean.toFixed(1)
    : `${mean.toFixed(1)} ± ${std.toFixed(1)}`
}

function successCell(mean: number | null, std: number | null): string {
  if (mean === null) return '—'
  const base = `${(mean * 100).toFixed(1)}%`
  return std === null
    ? base
    : `${base} ± ${(std * 100).toFixed(1)}%`
}

function collisionsCell(mean: number | null, std: number | null): string {
  if (mean === null) return '—'
  return std === null
    ? mean.toFixed(1)
    : `${mean.toFixed(1)} ± ${std.toFixed(1)}`
}

/** Meta line under the policy name, segments dropped when absent. */
function metaLine(row: BenchmarkResult): string {
  const segments: string[] = [row.experiment_id]
  if (row.harness) segments.push(row.harness)
  if (row.robot_count) segments.push(`${row.robot_count} robots`)
  if (row.n_runs) segments.push(`${row.n_runs} runs`)
  return segments.join(' · ')
}

const MEASURED = /COMPLETE|UNSTABLE/

export function BenchmarkTable() {
  const [state, setState] = useState<LoadState>({ kind: 'loading' })

  useEffect(() => {
    let cancelled = false
    api
      .listBenchmarks()
      .then((rows) => {
        if (cancelled) return
        setState(rows.length > 0 ? { kind: 'data', rows } : { kind: 'empty' })
      })
      .catch((error: unknown) => {
        if (cancelled) return
        setState({
          kind: 'error',
          message: error instanceof Error ? error.message : 'Request failed',
        })
      })
    return () => {
      cancelled = true
    }
  }, [])

  const COLUMNS = ['Policy', 'Score', 'Success', 'Collisions', 'Status'] as const

  return (
    <section aria-label="Benchmark results" className="rounded-xl border border-line/60 bg-panel p-4 transition-colors duration-200">
      <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
        <BarChart3 className="h-3.5 w-3.5" aria-hidden="true" />
        Benchmarks
      </h2>

      {state.kind === 'loading' && (
        <LoadingSpinner label="Loading benchmark results…" />
      )}

      {state.kind === 'error' && (
        <p className="mt-3 text-xs text-red-500" role="alert">
          Benchmark results unavailable: {state.message}
        </p>
      )}

      {state.kind === 'empty' && (
        <p className="mt-3 text-xs text-subtle">
          No benchmark data yet — run{' '}
          <code className="font-mono text-muted">make benchmark</code> to produce results.
        </p>
      )}

      {state.kind === 'data' && (
        <>
          <table className="mt-3 w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line text-subtle">
                {COLUMNS.map((column) => (
                  <th key={column} scope="col" className="pb-2 pr-2 font-medium">
                    {column}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {state.rows.map((row) => (
                <tr key={`${row.policy}-${row.source}`} className="border-b border-line/40 last:border-b-0">
                  <td className="py-2 pr-2">
                    <span className="font-mono text-fg">{row.policy}</span>
                    <span className="mt-0.5 block text-[10px] text-subtle">{metaLine(row)}</span>
                  </td>
                  <td className="py-2 pr-2 font-mono text-fg">
                    {scoreCell(row.mean_popw_score, row.std_popw_score)}
                  </td>
                  <td className="py-2 pr-2 font-mono text-fg">
                    {successCell(row.mean_success_rate, row.std_success_rate)}
                  </td>
                  <td className="py-2 pr-2 font-mono text-fg">
                    {collisionsCell(row.mean_collision_count, row.std_collision_count)}
                  </td>
                  <td className="py-2 pr-2">
                    <span className="inline-flex items-center gap-1 text-muted">
                      {row.status}
                    </span>
                    {row.skip_reason && (
                      <span className="mt-0.5 block text-[10px] text-subtle">{row.skip_reason}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {state.rows.some((row) => MEASURED.test(row.status)) && (
            <p className="mt-2 text-[10px] uppercase tracking-wide text-subtle">
              {state.rows.length} measured
            </p>
          )}
        </>
      )}
    </section>
  )
}
