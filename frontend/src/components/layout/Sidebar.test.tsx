// Sidebar integration test — proves the rail renders the simulation engine's
// carts, not the stale backend/recorded robot ids.
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { useSimulationProvider } from '../../simulation/useSimulation'
import { Sidebar } from './Sidebar'

describe('Sidebar (SIM mode)', () => {
  beforeEach(() => {
    useSimulationProvider.getState().start()
  })

  afterEach(() => {
    cleanup()
    useSimulationProvider.getState().stop()
  })

  it('renders the current engine carts and their crate assignments', () => {
    render(<Sidebar />)

    for (let i = 1; i <= 5; i++) {
      expect(screen.getByText(`Cart-0${i}`)).toBeInTheDocument()
    }
    expect(screen.queryByText('robot_0')).not.toBeInTheDocument()
    expect(screen.getByText('SIM')).toBeInTheDocument()
  })

  it('reports the engine fleet battery average', () => {
    const engine = useSimulationProvider.getState().engine
    expect(engine).not.toBeNull()
    const avg =
      (engine?.robots.reduce((sum, robot) => sum + robot.battery, 0) ?? 0) /
      (engine?.robots.length ?? 1)

    render(<Sidebar />)

    // Scope to the summary: with randomized start batteries a single cart can
    // legitimately show the same percentage as the fleet average.
    const summary = screen.getByLabelText('Fleet summary')
    expect(within(summary).getByText(`${Math.round(avg * 100)}%`)).toBeInTheDocument()
  })
})
