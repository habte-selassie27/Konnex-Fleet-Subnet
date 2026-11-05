// TelemetryOverlay — glass HUD for the Fleet Intelligence viewport.
//
// Displays only values the simulation engine actually produced (AGENTS.md
// Law 1): items collected, crates stacked in the bin, active carts, fleet
// throughput, a reward-policy preview line, and the live action feed. If the
// engine has not published yet it says "No data yet" rather than rendering
// zeros. The reward preview is explicitly informational — no real payment
// fires when a sim cart completes a task (see engine.ts and PaymentPanel).
import { useMemo, useState } from 'react'
import { Boxes, Layers, Package, Timer } from 'lucide-react'

import { useSimulationProvider, useSimulationSnapshot } from '../../simulation/useSimulation'
import { type TeamRewardEvent, setTeamRewardHandler } from '../../simulation/engine'
import type { SimEventKind } from '../../simulation/engine'

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

const EVENT_DOT: Record<SimEventKind, string> = {
  spawn: 'bg-subtle',
  assign: 'bg-sky-500',
  pickup: 'bg-amber-500',
  stack: 'bg-emerald-500',
  collision: 'bg-red-500',
  charge: 'bg-sky-500',
  full: 'bg-red-500',
}

export function TelemetryOverlay() {
  const { snapshot, engine } = useSimulationSnapshot()
  const runState = useSimulationProvider((s) => s.runState)
  const [lastReward, setLastReward] = useState<TeamRewardEvent | null>(null)

  useMemo(() => {
    if (!engine) return
    const handler = (event: TeamRewardEvent) => setLastReward(event)
    setTeamRewardHandler(engine, handler)
    return () => setTeamRewardHandler(engine, null)
  }, [engine])

  const data = useMemo(() => {
    if (!snapshot) return null

    const robots = snapshot.robots
    // Any cart that is visibly on the warehouse floor counts as active —
    // idle, staging, moving, picking, depositing or charging all read as a
    // real cart present in the scene.
    const activeCarts = robots.length

    const batteryAvg =
      robots.length > 0 ? robots.reduce((a, r) => a + r.battery, 0) / robots.length : 0

    return {
      simTime: snapshot.simTime,
      collected: snapshot.collected,
      stacked: snapshot.stacked,
      capacity: snapshot.binCapacity,
      throughput: snapshot.throughputPerMin,
      activeCarts,
      cartCount: robots.length,
      collisions: snapshot.collisions,
      batteryAvg,
      binFull: snapshot.binFull,
      events: [...snapshot.events].slice(-6).reverse(),
    }
  }, [snapshot])

  if (!data) {
    return (
      <div className="pointer-events-none absolute right-3 top-3 rounded-xl border border-line bg-panel/85 px-4 py-3 text-center backdrop-blur">
        <p className="text-xs text-subtle">No data yet</p>
      </div>
    )
  }

  const running = runState === 'running'
  const finished = runState === 'finished'

  return (
    <>
      {/* KPI panel */}
      <div className="pointer-events-none absolute right-3 top-3 w-64 rounded-xl border border-line bg-panel/85 p-3 shadow-xl backdrop-blur transition-colors duration-200">
        <div className="flex items-center justify-between">
          <p className="text-[10px] font-semibold uppercase tracking-widest text-subtle">
            Fleet Output
          </p>
          <span className="font-mono text-[10px] text-subtle">{formatTime(data.simTime)}</span>
        </div>

        {/* State line — keeps the HUD honest with the engine's real run state, not
            with a fake pulse that implies activity when the sim is paused. */}
        <div className="mt-2 flex items-center justify-between">
          <span className="text-[10px] font-medium uppercase tracking-wider">
            {finished ? 'Mission complete' : running ? 'In progress' : runState === 'paused' ? 'Paused' : 'Ready'}
          </span>
          <span className={`text-[10px] font-medium uppercase tracking-wider ${
            finished ? 'text-sky-400' : running ? 'text-emerald-400' : runState === 'paused' ? 'text-amber-400' : 'text-subtle'
          }`}>
            {finished ? 'DONE' : running ? 'RUNNING' : runState === 'paused' ? 'PAUSED' : 'READY'}
          </span>
        </div>

        <div className="mt-3 grid grid-cols-2 gap-2">
          <Kpi
            icon={<Package className="h-3.5 w-3.5" aria-hidden="true" />}
            label="Items Collected"
            value={String(data.collected)}
            tone="text-cyan-500"
            dimmed={!running && !finished}
          />
          <Kpi
            icon={<Layers className="h-3.5 w-3.5" aria-hidden="true" />}
            label="Stacked in Bin"
            value={`${data.stacked}/${data.capacity}`}
            tone="text-emerald-500"
            dimmed={!running && !finished}
          />
          <Kpi
            icon={<Boxes className="h-3.5 w-3.5" aria-hidden="true" />}
            label="Carts on Floor"
            value={`${data.activeCarts}/${data.cartCount}`}
            tone="text-sky-500"
            dimmed={!running && !finished}
          />
          <Kpi
            icon={<Timer className="h-3.5 w-3.5" aria-hidden="true" />}
            label="Throughput"
            value={`${data.throughput.toFixed(1)}/min`}
            tone="text-amber-500"
            dimmed={!running}
          />
        </div>

        <div className="mt-3 space-y-1.5 border-t border-line pt-2">
          <Bar label="Bin fill" value={data.capacity ? data.stacked / data.capacity : 0} tone="bg-emerald-500" />
          <Bar label="Fleet battery" value={data.batteryAvg} tone="bg-cyan-500" />
          <div className="flex justify-between text-[11px]">
            <span className="text-subtle">Collisions</span>
            <span className={`font-mono font-medium ${data.collisions > 0 ? 'text-red-500' : 'text-fg'}`}>
              {data.collisions}
            </span>
          </div>
        </div>

        {data.binFull ? (
          <p className="mt-2 rounded-md bg-red-500/15 px-2 py-1 text-center text-[10px] font-semibold uppercase tracking-wide text-red-500">
            Bin full
          </p>
        ) : null}

        {/* Reward-policy preview — informational only. */}
        {lastReward && (
          <div className="mt-2 rounded-md border border-sky-500/40 bg-sky-500/10 px-2 py-1.5">
            <div className="flex items-center justify-between text-[10px]">
              <span className="font-medium uppercase tracking-wider text-sky-400">
                Reward preview
              </span>
              <span className="font-mono font-semibold text-sky-300">
                ${lastReward.reward_usdc.toFixed(2)} USDC
                {' · '}
                {lastReward.reward_crates} crate
              </span>
            </div>
            <p className="mt-0.5 text-[10px] text-subtle">
              This is a preview only — no USDC moved, no Arc tx, no wallet spend.
              The sim is a fallback viewer; real payments are gated by the backend
              on operational failure, not task completion.
            </p>
          </div>
        )}
      </div>

      {/* Action feed */}
      <div
        className={
          'absolute bottom-3 left-3 w-80 rounded-xl border border-line bg-panel/85 p-3 shadow-xl backdrop-blur transition-colors duration-200 ' +
          (!running && runState !== 'finished' ? 'opacity-60' : '')
        }
      >
        <p className="text-[10px] font-semibold uppercase tracking-widest text-subtle">
          Action Feed
        </p>
        <ul className="mt-2 space-y-1" aria-live="polite">
          {data.events.length === 0 ? (
            <li className="text-[11px] text-subtle">Waiting for fleet activity…</li>
          ) : (
            data.events.map((event) => (
              <li key={event.id} className="flex items-start gap-2 text-[11px] leading-tight">
                <span
                  className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${EVENT_DOT[event.kind]}`}
                  aria-hidden="true"
                />
                <span className="w-9 shrink-0 font-mono text-[10px] text-subtle">
                  {formatTime(event.t)}
                </span>
                <span className="text-muted">{event.message}</span>
              </li>
            ))
          )}
        </ul>
      </div>
    </>
  )
}

function Kpi({
  icon,
  label,
  value,
  tone,
  dimmed = false,
}: {
  icon: React.ReactNode
  label: string
  value: string
  tone: string
  dimmed?: boolean
}) {
  return (
    <div className={`rounded-lg border border-line bg-elevated/60 p-2 transition-colors duration-200 ${
      dimmed ? 'opacity-45 grayscale' : ''
    }`}>
      <div className={`flex items-center gap-1 ${tone}`}>
        {icon}
        <span className="text-[9px] font-medium uppercase tracking-wide">{label}</span>
      </div>
      <p className="mt-1 font-mono text-lg font-semibold leading-none text-fg">{value}</p>
    </div>
  )
}

function Bar({ label, value, tone }: { label: string; value: number; tone: string }) {
  const pct = Math.max(0, Math.min(1, value)) * 100
  return (
    <div>
      <div className="flex justify-between text-[11px]">
        <span className="text-subtle">{label}</span>
        <span className="font-mono text-fg">{pct.toFixed(0)}%</span>
      </div>
      <div className="mt-0.5 h-1.5 overflow-hidden rounded-full bg-elevated">
        <div className={`h-full rounded-full ${tone} transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
