import { Play, StopCircle } from 'lucide-react'
import { useEffect, useState } from 'react'

import { api } from '../../services/api'

type Policy = { id: string; name: string; algorithm: string; available: boolean }

/** Real, reproducible scenario definitions from experiments/configs (warehouse_v1). */
const SCENARIOS = [
  { id: 'warehouse_v1', name: 'Warehouse V1', robot_count: 5, task_count: 20 },
] as const

/** Valid, reproducible seeds from the experiment configs (exp_001..exp_003). */
const SEEDS = [1000, 1010, 1020, 1029] as const

type MissionResult = {
  id: string
  scenario_id: string
  status: string
  policy: string
  robot_count: number
  task_count: number
  completed_tasks: number
  collision_count: number
  elapsed_seconds: number
  popw_score: number | null
} | null

export function PolicyRunner() {
  const [policies, setPolicies] = useState<Policy[]>([])
  const [policy, setPolicy] = useState<string>('nearest')
  const [scenario, setScenario] = useState<string>('warehouse_v1')
  const [seed, setSeed] = useState<number>(1000)
  const [customSeed, setCustomSeed] = useState<string>('')
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [mission, setMission] = useState<MissionResult>(null)

  // Load genuinely registered policies from the backend.
  useEffect(() => {
    let cancelled = false
    api
      .getPolicies()
      .then((data) => {
        if (cancelled) return
        const valid = data.filter((p) => p.available)
        setPolicies(valid)
        if (valid.length > 0 && !valid.some((p) => p.id === policy)) {
          setPolicy(valid[0].id)
        }
      })
      .catch(() => {
        // Fall back to the policies the backend allocator actually supports.
        setPolicies([
          { id: 'nearest', name: 'nearest', algorithm: 'NearestTaskAllocator', available: true },
          { id: 'hungarian', name: 'hungarian', algorithm: 'HungarianAllocator', available: true },
          { id: 'cost_optimizer', name: 'cost_optimizer', algorithm: 'CostOptimizerAllocator', available: true },
        ])
      })
    return () => {
      cancelled = true
    }
  }, [])

  const isCustomSeed = seed.toString() === 'custom'

  const handleRun = async () => {
    setRunning(true)
    setError(null)
    setMission(null)
    try {
      const resolvedSeed = isCustomSeed ? Number(customSeed) : seed
      if (Number.isNaN(resolvedSeed)) {
        throw new Error('Invalid seed')
      }
      const created = await api.createMission({
        robot_count: 5,
        task_count: 20,
        seed: resolvedSeed,
        policy,
        time_limit_s: 600,
      })
      setMission({
        id: created.id,
        scenario_id: '',
        status: 'running',
        policy,
        robot_count: 5,
        task_count: 20,
        completed_tasks: 0,
        collision_count: 0,
        elapsed_seconds: 0,
        popw_score: null,
      })
      await pollMission(created.id)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Mission creation failed')
    } finally {
      setRunning(false)
    }
  }

  const pollMission = async (missionId: string) => {
    for (let i = 0; i < 120; i++) {
      if (running === false) return
      try {
        const m = await fetch(`/api/v1/missions/${missionId}`, {
          headers: { 'X-Fleet-API-Key': 'dev-only-key' },
        })
        if (!m.ok) throw new Error(`mission fetch failed: ${m.status}`)
        const data = (await m.json()) as MissionResult
        if (!data) throw new Error('Empty mission response')
        setMission(data)
        if (data.status === 'complete' || data.status === 'failed' || data.status === 'timed_out') {
          return
        }
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to poll mission')
        return
      }
      await new Promise((r) => setTimeout(r, 1000))
    }
    setError('Mission timed out while polling')
  }

  return (
    <section aria-label="Run mission" className="rounded-xl border border-line/60 bg-panel p-4 transition-colors duration-200">
      <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
        <Play className="h-3.5 w-3.5" aria-hidden="true" />
        Policy Runner
      </h2>

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-medium text-subtle uppercase tracking-wide">Policy</label>
          <select
            value={policy}
            onChange={(e) => setPolicy(e.target.value)}
            className="rounded-md border border-line/60 bg-surface px-2 py-1.5 text-xs text-fg"
            aria-label="Allocation policy"
            disabled={running}
          >
            {policies.map((p) => (
              <option key={p.id} value={p.id} disabled={!p.available}>
                {p.name} {p.available ? '' : ' (unavailable)'}
              </option>
            ))}
          </select>
          <p className="mt-0.5 text-[10px] text-subtle">
            {policies.find((p) => p.id === policy)?.algorithm ?? ''}
          </p>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-medium text-subtle uppercase tracking-wide">Scenario</label>
          <select
            value={scenario}
            onChange={(e) => setScenario(e.target.value)}
            className="rounded-md border border-line/60 bg-surface px-2 py-1.5 text-xs text-fg"
            disabled
            aria-label="Scenario"
          >
            {SCENARIOS.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.robot_count} robots · {s.task_count} tasks)
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-medium text-subtle uppercase tracking-wide">Seed</label>
          <select
            value={seed}
            onChange={(e) => {
              setSeed(Number(e.target.value))
              setCustomSeed('')
            }}
            className="rounded-md border border-line/60 bg-surface px-2 py-1.5 text-xs text-fg"
            disabled={running}
          >
            {SEEDS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
            <option value="custom">Custom…</option>
          </select>
          {isCustomSeed && (
            <input
              type="number"
              value={customSeed}
              onChange={(e) => setCustomSeed(e.target.value)}
              className="mt-1 rounded-md border border-line/60 bg-surface px-2 py-1 text-xs text-fg w-full"
              placeholder="e.g. 1015"
            />
          )}
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-medium text-subtle uppercase tracking-wide">Run</label>
          <button
            type="button"
            onClick={handleRun}
            disabled={running || policies.find((p) => p.id === policy)?.available === false}
            className="flex items-center gap-1.5 rounded-md bg-sky-500 px-2.5 py-1.5 text-xs font-medium text-white disabled:opacity-50"
          >
            {running ? (
              <>
                <StopCircle className="h-3 w-3" aria-hidden="true" />
                Stopping…
              </>
            ) : (
              <>
                <Play className="h-3 w-3" aria-hidden="true" />
                Run mission
              </>
            )}
          </button>
        </div>
      </div>

      {error && (
        <p className="mt-2 text-[10px] text-red-500" role="alert">
          {error}
        </p>
      )}

      {mission && (
        <div className="mt-3 rounded-md border border-line/60 bg-surface p-3">
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className="text-[10px] font-medium text-subtle">Mission</span>
            <span className="font-mono text-xs text-fg">
              {mission.id.slice(0, 8)}
            </span>
          </div>
          <table className="w-full text-xs">
            <tbody>
              <tr className="border-b border-line/40 last:border-b-0">
                <td className="py-1 pr-2 text-subtle">Policy</td>
                <td className="py-1 pr-2 font-mono text-fg">{mission.policy}</td>
              </tr>
              <tr className="border-b border-line/40 last:border-b-0">
                <td className="py-1 pr-2 text-subtle">Status</td>
                <td className="py-1 pr-2 font-mono text-fg capitalize">{mission.status}</td>
              </tr>
              <tr className="border-b border-line/40 last:border-b-0">
                <td className="py-1 pr-2 text-subtle">Tasks</td>
                <td className="py-1 pr-2 font-mono text-fg">
                  {mission.completed_tasks}/{mission.task_count}
                </td>
              </tr>
              <tr className="border-b border-line/40 last:border-b-0">
                <td className="py-1 pr-2 text-subtle">Collisions</td>
                <td className="py-1 pr-2 font-mono text-fg">{mission.collision_count}</td>
              </tr>
              <tr className="border-b border-line/40 last:border-b-0">
                <td className="py-1 pr-2 text-subtle">Elapsed</td>
                <td className="py-1 pr-2 font-mono text-fg">{mission.elapsed_seconds.toFixed(1)} s</td>
              </tr>
              <tr className="last:border-b-0">
                <td className="py-1 pr-2 text-subtle">PoPW Score</td>
                <td className="py-1 pr-2 font-mono text-fg font-bold">
                  {mission.popw_score === null ? '—' : mission.popw_score.toFixed(1)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
