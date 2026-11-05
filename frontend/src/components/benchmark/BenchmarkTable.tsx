// BenchmarkTable — policy comparison (AGENTS.md §1.2 benchmark/).
// There is no benchmark API yet, so this renders an honest empty state
// ("No data yet") — it never fabricates comparison numbers (Law 1).
import { BarChart3 } from 'lucide-react'

const COLUMNS = ['Policy', 'Score', 'Success', 'Collisions', 'Status'] as const

export function BenchmarkTable() {
  return (
    <section aria-label="Benchmark results" className="rounded-xl border border-slate-700/60 bg-slate-900 p-4">
      <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-slate-400">
        <BarChart3 className="h-3.5 w-3.5" aria-hidden="true" />
        Benchmarks
      </h2>

      <table className="mt-3 w-full text-left text-xs">
        <thead>
          <tr className="border-b border-slate-700/60 text-slate-500">
            {COLUMNS.map((column) => (
              <th key={column} scope="col" className="pb-2 pr-2 font-medium">
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          <tr>
            <td colSpan={COLUMNS.length} className="py-6 text-center text-slate-500">
              No benchmark data yet — run <code className="font-mono text-slate-400">make benchmark</code> to populate.
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  )
}
