// ScoreGauge — PoPW score gauge. Per AGENTS.md §1.6: animates ONLY when the
// score changes; shows "No data yet" when no score exists (never zeros).
// Colors use the theme tokens so the gauge reads correctly in both modes.
import { useEffect, useState } from 'react'

interface ScoreGaugeProps {
  score: number | null
}

function polar(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}

function arcPath(cx: number, cy: number, r: number, startDeg: number, endDeg: number) {
  const start = polar(cx, cy, r, endDeg)
  const end = polar(cx, cy, r, startDeg)
  const largeArc = endDeg - startDeg <= 180 ? 0 : 1
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y}`
}

export function ScoreGauge({ score }: ScoreGaugeProps) {
  const [display, setDisplay] = useState<number | null>(score)

  // Animate only on actual change (prevents idle re-animation loops).
  useEffect(() => {
    if (score !== null && score !== display) {
      setDisplay(score)
    }
  }, [score, display])

  const value = display
  const pct = value === null ? 0 : Math.max(0, Math.min(100, value))
  const angle = (pct / 100) * 270 // 270° gauge from -225° to 45°

  return (
    <div
      className="relative mx-auto h-36 w-36"
      role="img"
      aria-label={value === null ? 'PoPW score: no data yet' : `PoPW score ${value.toFixed(1)} out of 100`}
    >
      <svg viewBox="0 0 120 120" className="h-full w-full">
        <path
          d={arcPath(60, 60, 50, -225, 45)}
          fill="none"
          stroke="rgb(var(--line-strong))"
          strokeWidth={9}
          strokeLinecap="round"
        />
        {value !== null && (
          <path
            d={arcPath(60, 60, 50, -225, -225 + angle)}
            fill="none"
            stroke={pct >= 70 ? '#10b981' : pct >= 40 ? '#f59e0b' : '#ef4444'}
            strokeWidth={9}
            strokeLinecap="round"
            className="transition-all duration-700 ease-out"
          />
        )}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        {value === null ? (
          <>
            <span className="text-sm font-semibold text-fg">—</span>
            <span className="text-[10px] uppercase tracking-wide text-subtle">No data yet</span>
          </>
        ) : (
          <>
            <span className="font-mono text-2xl font-bold text-fg">{value.toFixed(1)}</span>
            <span className="text-[10px] uppercase tracking-wide text-subtle">/ 100</span>
          </>
        )}
      </div>
    </div>
  )
}
