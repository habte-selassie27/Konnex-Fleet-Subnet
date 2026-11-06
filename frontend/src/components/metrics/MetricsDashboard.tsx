// MetricsDashboard — right-hand metrics rail (AGENTS.md §1.2 metrics/).
//
// Reads the same mission the viewport is showing (useMissionView): when the
// scene is the SIM engine, every number is computed from the live engine
// snapshot; when it is Live/recorded, the numbers come from the WebSocket
// mission or the captured run. Rail and scene can never disagree (AGENTS.md
// Law 1 / §0.3).
//
// PoPW score: the recorded run carries a backend-evaluated score; live and sim
// missions do not, so the prototype formula (data/popw.ts — the same weights as
// validator/scoring/engine.py) is recomputed live and labelled PROVISIONAL.
// A staged-but-not-started SIM run shows "No data yet" — scoring a mission
// before it does any work would be fabricated (§1.6 rule 3).
import { useMemo } from 'react'
import { AlertTriangle, Bot, Clock, PackageCheck, Users } from 'lucide-react'

import { calculatePopw } from '../../data/popw'
import type { MissionView } from '../../data/missionView'
import { useMissionView } from '../../hooks/useMissionView'
import { useSimulationProvider } from '../../simulation/useSimulation'
import { CumulativeEnergyChart } from './CumulativeEnergyChart'
import { EnergyChart } from './EnergyChart'
import { ScoreGauge } from './ScoreGauge'
import { SourcePill } from '../shared/SourcePill'

function formatElapsed(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

export function MetricsDashboard() {
  const { mission, source, energyHistory } = useMissionView()
  // Playback state of the sim run — a staged-but-not-started run must not
  // display a "score" for a mission that has not executed any work yet.
  const runState = useSimulationProvider((s) => s.runState)

  const mission_staged_not_started =
    source === 'simulation' && runState === 'idle' && mission?.elapsed_seconds === 0

  // Score precedence: backend-evaluated score when the source carries one,
  // otherwise the prototype formula recomputed from these same numbers.
  const score = useMemo(() => {
    if (!mission || mission_staged_not_started) return null
    if (mission.popw_score !== null) return mission.popw_score
    return (
      calculatePopw({
        tasks_completed: mission.completed_tasks,
        tasks_total: mission.total_tasks,
        elapsed_s: mission.elapsed_seconds,
        time_limit_s: mission.time_limit_s,
        collision_count: mission.collision_count,
        energy_consumed: mission.energy_consumed,
        energy_budget: mission.energy_budget,
        failure_count: mission.failure_count,
      })?.final ?? null
    )
  }, [mission, mission_staged_not_started])

  // A score computed in the browser (not delivered by the backend evaluation)
  // is always labelled PROVISIONAL — it is the prototype formula, not the
  // validator's verdict.
  const provisional = mission !== null && mission.popw_score === null && score !== null

  if (!mission) {
    return (
      <section aria-label="Mission metrics" className="space-y-4">
        <div className="rounded-xl border border-line bg-panel p-4 transition-colors duration-200">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
            PoPW Score
          </h2>
          <div className="mt-3">
            <ScoreGauge score={null} />
          </div>
          <p className="mt-4 text-center text-xs text-subtle">No data yet</p>
        </div>
      </section>
    )
  }

  const progress =
    mission.total_tasks > 0 ? Math.round((mission.completed_tasks / mission.total_tasks) * 100) : 0
  const timeBudgetPct =
    mission.time_limit_s && mission.time_limit_s > 0
      ? Math.max(0, Math.min(100, (mission.elapsed_seconds / mission.time_limit_s) * 100))
      : null

  return (
    <section aria-label="Mission metrics" className="space-y-4">
      <div className="rounded-xl border border-line bg-panel p-4 transition-colors duration-200">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">
          PoPW Score
        </h2>
        <div className="mt-3">
          <ScoreGauge score={score} />
        </div>
        <p
          className="mt-3 text-center text-[10px] font-medium uppercase tracking-widest text-subtle"
          title={
            provisional
              ? 'Recomputed in the browser with the prototype Konnex PoPW weights (not a backend evaluation).'
              : 'Score delivered by the backend evaluation for this mission.'
          }
        >
          {score === null
            ? mission_staged_not_started
              ? 'No data yet — run the mission'
              : 'No score available'
            : provisional
              ? 'Provisional · live prototype score'
              : 'Backend evaluated'}
        </p>
      </div>

      <div className="rounded-xl border border-line bg-panel p-4 transition-colors duration-200">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">Mission</h2>
        <dl className="mt-3 space-y-3">
          <MetricRow icon={PackageCheck} label="Tasks" value={`${mission.completed_tasks} / ${mission.total_tasks}`} />
          <MetricRow icon={Clock} label="Elapsed" value={formatElapsed(mission.elapsed_seconds)} />
          <MetricRow icon={AlertTriangle} label="Collisions" value={String(mission.collision_count)} />
          <MetricRow icon={Bot} label="Failures" value={String(mission.failure_count)} />
        </dl>

        <div className="mt-4">
          <div className="mb-1 flex justify-between text-xs">
            <span className="text-subtle">Completion</span>
            <span className="font-mono text-fg">{progress}%</span>
          </div>
          <div
            className="h-2 overflow-hidden rounded-full bg-elevated"
            role="img"
            aria-label={`Task completion ${progress}%`}
          >
            <div className="h-full rounded-full bg-sky-500 transition-all duration-500" style={{ width: `${progress}%` }} />
          </div>
        </div>

        {timeBudgetPct !== null && (
          <div className="mt-3">
            <div className="mb-1 flex justify-between text-xs">
              <span className="text-subtle">Time budget</span>
              <span className="font-mono text-fg">{Math.round(timeBudgetPct)}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-elevated" role="img" aria-label={`Time budget ${Math.round(timeBudgetPct)}% used`}>
              <div
                className={`h-full rounded-full transition-all duration-500 ${
                  timeBudgetPct >= 90 ? 'bg-red-500' : timeBudgetPct >= 75 ? 'bg-amber-500' : 'bg-sky-500'
                }`}
                style={{ width: `${timeBudgetPct}%` }}
              />
            </div>
          </div>
        )}
      </div>

      <div className="rounded-xl border border-line bg-panel p-4 transition-colors duration-200">
        <div className="flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-muted">Energy</h2>
          <span className="font-mono text-xs font-medium text-fg">
            {mission.energy_consumed.toFixed(1)} u
            {mission.energy_budget !== null && ` / ${mission.energy_budget} u`}
          </span>
        </div>
        <div className="mt-3">
          <EnergyChartish mission={mission} source={source} energyHistory={energyHistory} />
        </div>
      </div>

      <div className="rounded-xl border border-line bg-panel p-4 transition-colors duration-200">
        <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted">
          <Users className="h-3.5 w-3.5" aria-hidden="true" />
          Status
        </h2>
        <p className="mt-2 text-sm capitalize text-fg">{mission.status}</p>
        <p className="mt-1 font-mono text-[10px] text-subtle">
          {mission.mission_id.slice(0, 8)}
        </p>
        <div className="mt-3 border-t border-line pt-3">
          <SourcePill source={source} capturedAt={mission.captured_at} />
        </div>
      </div>
    </section>
  )
}

/**
 * Pick the honest energy visualisation per source:
 *  • simulation — the 1 Hz series sampled from the live engine run;
 *  • live       — the store's MISSION_UPDATE samples (streamed while online);
 *  • recorded   — a capture holds only the final total, plot exactly that;
 *  • none       — "No data yet".
 */
function EnergyChartish({
  mission,
  source,
  energyHistory,
}: {
  mission: MissionView
  source: ReturnType<typeof useMissionView>['source']
  energyHistory: ReturnType<typeof useMissionView>['energyHistory']
}) {
  if (source === 'simulation') {
    return <EnergyChart history={energyHistory ?? undefined} />
  }
  if (source === 'live') {
    return <EnergyChart />
  }
  if (source === 'recorded') {
    return (
      <CumulativeEnergyChart
        total={mission.energy_consumed}
        elapsed_s={mission.elapsed_seconds}
        time_limit_s={mission.time_limit_s ?? 0}
      />
    )
  }
  return (
    <div className="flex h-40 items-center justify-center rounded-lg border border-dashed border-line text-xs text-subtle">
      No data yet
    </div>
  )
}

interface MetricRowProps {
  icon: typeof Clock
  label: string
  value: string
}

function MetricRow({ icon: Icon, label, value }: MetricRowProps) {
  return (
    <div className="flex items-center justify-between">
      <dt className="flex items-center gap-2 text-xs text-subtle">
        <Icon className="h-3.5 w-3.5" aria-hidden="true" />
        {label}
      </dt>
      <dd className="font-mono text-sm font-medium text-fg">{value}</dd>
    </div>
  )
}
