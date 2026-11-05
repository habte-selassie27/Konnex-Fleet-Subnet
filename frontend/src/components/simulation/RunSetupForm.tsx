// RunSetupForm — operator control for the SIM floor: how many crates drop at
// once (5..40, or a random roll) before the carts start.
//
// Applying restages the floor and starts a new run, so the count on the form is
// always the number of crates actually staged — never a label over an unchanged
// scene (AGENTS.md Law 1). The note under the controls states the two things the
// engine really does per run: drop every crate at t = 0 and place the carts on
// fresh random cells.
import { useEffect, useState } from 'react'
import { ChevronDown, ChevronUp, Dices, Play } from 'lucide-react'

import { MAX_ITEMS, MIN_ITEMS, randomItemCount } from '../../simulation/engine'
import { useSimulationProvider } from '../../simulation/useSimulation'

export function RunSetupForm() {
  const itemCount = useSimulationProvider((s) => s.itemCount)
  const seed = useSimulationProvider((s) => s.seed)
  const start = useSimulationProvider((s) => s.start)

  const [draft, setDraft] = useState(itemCount)
  const [open, setOpen] = useState(true)

  // Follow the applied count when a run is staged from elsewhere (Reset, or a
  // Start that rolled a new seed) so the form never shows a stale number.
  useEffect(() => {
    setDraft(itemCount)
  }, [itemCount])

  const rollRandom = () => setDraft(randomItemCount())

  return (
    <div className="w-64 rounded-xl border border-line bg-panel/85 p-3 shadow-xl backdrop-blur transition-colors duration-200">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls="run-setup-body"
        className="flex w-full items-center justify-between gap-2 text-left focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500"
      >
        <span className="text-[10px] font-semibold uppercase tracking-widest text-subtle">
          Run setup
        </span>
        {open ? (
          <ChevronUp className="h-3.5 w-3.5 text-subtle" aria-hidden="true" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-subtle" aria-hidden="true" />
        )}
      </button>

      {open ? (
        <div id="run-setup-body">
          <div className="mt-2 flex items-baseline justify-between">
            <label htmlFor="crate-count" className="text-[11px] text-muted">
              Crates dropped
            </label>
            <output htmlFor="crate-count" className="font-mono text-sm font-semibold text-fg">
              {draft}
            </output>
          </div>

          <input
            id="crate-count"
            type="range"
            min={MIN_ITEMS}
            max={MAX_ITEMS}
            step={1}
            value={draft}
            onChange={(e) => setDraft(Number(e.target.value))}
            aria-label={`Crates dropped on the floor, ${MIN_ITEMS} to ${MAX_ITEMS}`}
            className="mt-1.5 w-full accent-sky-500"
          />
          <div className="flex justify-between font-mono text-[9px] text-subtle">
            <span>{MIN_ITEMS}</span>
            <span>{MAX_ITEMS}</span>
          </div>

          <div className="mt-2 flex items-center gap-1.5">
            <button
              type="button"
              onClick={rollRandom}
              title={`Roll a random count between ${MIN_ITEMS} and ${MAX_ITEMS}`}
              aria-label={`Roll a random crate count between ${MIN_ITEMS} and ${MAX_ITEMS}`}
              className="inline-flex items-center gap-1 rounded-md border border-line-strong bg-elevated px-2 py-1 text-[11px] font-medium text-fg transition-colors hover:bg-surface-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-sky-500"
            >
              <Dices className="h-3 w-3" aria-hidden="true" />
              Random
            </button>

            <button
              type="button"
              onClick={() => start({ itemCount: draft })}
              title="Stage this many crates on the floor and start a new run"
              className="inline-flex flex-1 items-center justify-center gap-1 rounded-md bg-sky-500 px-2 py-1 text-[11px] font-semibold text-white transition-colors hover:bg-sky-400 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500"
            >
              <Play className="h-3 w-3" aria-hidden="true" />
              Apply &amp; start
            </button>
          </div>

          <p className="mt-2 text-[10px] leading-snug text-subtle">
            Apply stages a new run: {draft} crates drop on the floor at once, before any
            cart moves, and the 5 carts start from fresh random cells. Every run rolls a
            new seed, so the layout is never the same twice.
          </p>
          <p className="mt-1 font-mono text-[10px] text-subtle">
            staged: {itemCount} crates · seed {seed}
          </p>
        </div>
      ) : null}
    </div>
  )
}
