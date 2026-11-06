import { Dices, Loader2, Play } from 'lucide-react'
import { useMemo, useState } from 'react'

import { api } from '../../services/api'
import { calculatePopw } from '../../data/popw'
import { simMissionFromSnapshot } from '../../data/simMission'
import {
  SIM_POLICIES,
  SIM_POLICY_ALGORITHMS,
  useSimulationProvider,
  useSimulationSnapshot,
  type SimPolicy,
} from '../../simulation/useSimulation'

/** Real, reproducible warehouse_v1 scenarios: 5 carts per mission, one crate
 * count per scenario from 5 up to 40. Run mission stages that many crates on
 * the warehouse floor and runs the visible mission in the viewport — the five
 * carts drive to the crates, lift them and stack them in the storage bin. */
const ROBOT_COUNT = 5
const CRATE_COUNTS = Array.from({ length: 36 }, (_, index) => index + 5)
const DEFAULT_CRATE_COUNT = 20

/** Shared control styling — a full 36px hit target so the menus are easy to hit. */
const CONTROL_CLASS =
  'h-9 w-full cursor-pointer rounded-md border border-line-strong bg-surface px-2.5 text-xs text-fg transition-colors hover:border-sky-500/60 focus-visible:border-sky-500 disabled:cursor-not-allowed disabled:opacity-60'

function randomSeed(): number {
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    const buf = new Uint32Array(1)
    crypto.getRandomValues(buf)
    return buf[0]
  }
  return Math.floor(Math.random() * 2_147_483_647)
}

export function PolicyRunner() {
  const [taskCount, setTaskCount] = useState<number>(DEFAULT_CRATE_COUNT)
  const [seed, setSeed] = useState<string>(() => String(randomSeed()))
  const [started, setStarted] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [missionId, setMissionId] = useState<string | null>(null)

  const runState = useSimulationProvider((s) => s.runState)
  const start = useSimulationProvider((s) => s.start)
  const policy = useSimulationProvider((s) => s.policy)
  const setPolicy = useSimulationProvider((s) => s.setPolicy)
  const { snapshot } = useSimulationSnapshot()

  const running = runState === 'running'

  // One source of truth: the local sim snapshot. The Mission panel and this
  // panel both read from it, so they always agree. The backend stores exactly
  // what the sim produced — no second, divergent simulation.
  const mission = useMemo(() => {
    if (!started || snapshot === null) return null
    const view = simMissionFromSnapshot(snapshot, runState)
    const popw =
      view.elapsed_seconds > 0
        ? (view.popw_score ??
          calculatePopw({
            tasks_completed: view.completed_tasks,
            tasks_total: view.total_tasks,
            elapsed_s: view.elapsed_seconds,
            time_limit_s: view.time_limit_s,
            collision_count: view.collision_count,
            energy_consumed: view.energy_consumed,
            energy_budget: view.energy_budget,
            failure_count: view.failure_count,
          })?.final ??
          null)
        : null
    return { view, popw }
  }, [started, snapshot, runState])

  const handleRun = async () => {
    const resolvedSeed = Number.parseInt(seed.trim(), 10)
    if (!Number.isFinite(resolvedSeed)) {
      setError('Enter a valid integer seed')
      return
    }
    setError(null)
    setStarted(true)
    setMissionId(null)

    // Run the sim locally — this is THE mission. Everything else reads from it.
    start({ itemCount: taskCount, seed: resolvedSeed, policy })

    // Poll until the sim finishes by reading fresh state from the store
    for (let i = 0; i < 240; i++) {
      await new Promise((r) => setTimeout(r, 500))
      if (useSimulationProvider.getState().runState === 'finished') break
    }

    if (useSimulationProvider.getState().runState !== 'finished') {
      setError('Simulation did not finish in time')
      setStarted(false)
      return
    }

    const engine = useSimulationProvider.getState().engine
    if (!engine) {
      setError('No simulation engine available')
      setStarted(false)
      return
    }

    const currentSnapshot = engine.snapshot()
    if (!currentSnapshot) {
      setError('No simulation snapshot available')
      setStarted(false)
      return
    }


    try {
      const created = await api.createMission({
        robot_count: ROBOT_COUNT,
        task_count: taskCount,
        seed: Number(seed),
        policy,
        time_limit_s: 600,
      })
      setMissionId(created.id)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Mission creation failed')
    }
  }

  return (
    <section aria-label="Run mission" className="rounded-xl border border-line/60 bg-panel p-4 transition-colors duration-200">
      <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
        <Play className="h-3.5 w-3.5" aria-hidden="true" />
        Run Mission
      </h2>

      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <div className="flex flex-col gap-1">
          <label
            htmlFor="policy-runner-policy"
            className="text-[10px] font-medium text-subtle uppercase tracking-wide"
          >
            Policy
          </label>
          <select
            id="policy-runner-policy"
            value={policy}
            onChange={(e) => setPolicy(e.target.value as SimPolicy)}
            className={CONTROL_CLASS}
            disabled={running}
            aria-label="Allocation policy"
          >
            {SIM_POLICIES.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
          <p className="mt-0.5 text-[10px] text-subtle">{SIM_POLICY_ALGORITHMS[policy]}</p>
        </div>

        <div className="flex flex-col gap-1">
          <label
            htmlFor="policy-runner-scenario"
            className="text-[10px] font-medium text-subtle uppercase tracking-wide"
          >
            Scenario
          </label>
          <select
            id="policy-runner-scenario"
            value={taskCount}
            onChange={(e) => setTaskCount(Number.parseInt(e.target.value, 10))}
            className={CONTROL_CLASS}
            disabled={running}
            aria-label="Scenario — crates to pick up"
          >
            {CRATE_COUNTS.map((crates) => (
              <option key={crates} value={crates}>
                Warehouse V1 · {ROBOT_COUNT} robots · {crates} crates
              </option>
            ))}
          </select>
          <p className="mt-0.5 text-[10px] text-subtle">
            {ROBOT_COUNT} robots pick up {taskCount} crates.
          </p>
        </div>

        <div className="flex flex-col gap-1">
          <label
            htmlFor="policy-runner-seed"
            className="text-[10px] font-medium text-subtle uppercase tracking-wide"
          >
            Seed
          </label>
          <div className="flex items-center gap-1.5">
            <input
              id="policy-runner-seed"
              type="number"
              value={seed}
              onChange={(e) => setSeed(e.target.value)}
              className="min-w-0 flex-1 rounded-md border border-line-strong bg-surface px-2.5 py-2 text-xs text-fg transition-colors hover:border-sky-500/60 focus-visible:border-sky-500"
              disabled={running}
              aria-label="Mission seed"
              placeholder="Any integer seed"
              step="1"
            />
            <button
              type="button"
              onClick={() => setSeed(String(randomSeed()))}
              disabled={running}
              className="shrink-0 rounded-md border border-line/60 bg-surface p-1.5 text-muted hover:text-fg disabled:opacity-50"
              aria-label="Generate random seed"
              title="Generate random seed"
            >
              <Dices className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </div>
          <p className="text-[10px] text-subtle">Arbitrary/dynamic — same seed = reproducible run.</p>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-[10px] font-medium text-subtle uppercase tracking-wide">Run</label>
          <button
            type="button"
            onClick={handleRun}
            disabled={running}
            className="flex items-center gap-1.5 rounded-md bg-sky-500 px-2.5 py-1.5 text-xs font-medium text-white disabled:opacity-50"
          >
            {running ? (
              <>
                <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />
                Running…
              </>
            ) : (
              <>
                <Play className="h-3 w-3" aria-hidden="true" />
                {runState === 'finished' ? 'Run again' : 'Run mission'}
              </>
            )}
          </button>
          <p className="mt-0.5 text-[10px] text-subtle">
            Runs on the warehouse floor — carts pick the crates and stack them in the storage bin.
          </p>
        </div>
      </div>

      {error && (
        <p className="mt-2 text-[10px] text-red-500" role="alert">
          {error}
        </p>
      )}

      {mission && mission.view && (
        <div className="mt-3 rounded-md border border-line/60 bg-surface p-3">
          <div className="flex items-center justify-between gap-2 mb-1">
            <span className="text-[10px] font-medium text-subtle">Mission</span>
            <span className="font-mono text-xs text-fg">
              {missionId ?? mission.view.mission_id}
            </span>
          </div>
          <table className="w-full text-xs">
            <tbody>
              <tr className="border-b border-line/40 last:border-b-0">
                <td className="py-1 pr-2 text-subtle">Policy</td>
                <td className="py-1 pr-2 font-mono text-fg">{mission.view.policy}</td>
              </tr>
              <tr className="border-b border-line/40 last:border-b-0">
                <td className="py-1 pr-2 text-subtle">Status</td>
                <td className="py-1 pr-2 font-mono text-fg capitalize">{mission.view.status}</td>
              </tr>
              <tr className="border-b border-line/40 last:border-b-0">
                <td className="py-1 pr-2 text-subtle">Crates stacked</td>
                <td className="py-1 pr-2 font-mono text-fg">
                  {mission.view.completed_tasks}/{mission.view.total_tasks}
                </td>
              </tr>
              <tr className="border-b border-line/40 last:border-b-0">
                <td className="py-1 pr-2 text-subtle">Collisions</td>
                <td className="py-1 pr-2 font-mono text-fg">{mission.view.collision_count}</td>
              </tr>
              <tr className="border-b border-line/40 last:border-b-0">
                <td className="py-1 pr-2 text-subtle">Elapsed</td>
                <td className="py-1 pr-2 font-mono text-fg">{mission.view.elapsed_seconds.toFixed(1)} s</td>
              </tr>
              <tr className="last:border-b-0">
                <td className="py-1 pr-2 text-subtle">PoPW Score</td>
                <td className="py-1 pr-2 font-mono text-fg font-bold">
                  {mission.popw === null ? '—' : mission.popw.toFixed(1)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
