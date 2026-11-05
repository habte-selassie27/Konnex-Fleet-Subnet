// RunSetupForm test — the form must start a run with exactly the crate count it
// shows, and the random roll must stay inside the engine's supported 5..40 drop.
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { MAX_ITEMS, MIN_ITEMS } from '../../simulation/engine'
import { useSimulationProvider } from '../../simulation/useSimulation'
import { RunSetupForm } from './RunSetupForm'

let realStart: (opts?: { itemCount?: number }) => void

beforeEach(() => {
  realStart = useSimulationProvider.getState().start
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  // The provider is a module-level store — put the real action back so a mocked
  // start never leaks into the next test.
  useSimulationProvider.setState({ start: realStart })
})

function slider(): HTMLInputElement {
  return screen.getByRole('slider', {
    name: new RegExp(`crates dropped on the floor, ${MIN_ITEMS} to ${MAX_ITEMS}`, 'i'),
  }) as HTMLInputElement
}

describe('RunSetupForm', () => {
  it('shows the staged crate count and the supported range', () => {
    useSimulationProvider.setState({ itemCount: 24, seed: 991 })
    render(<RunSetupForm />)

    expect(screen.getByText('24')).toBeInTheDocument()
    expect(slider().value).toBe('24')
    expect(slider().min).toBe(String(MIN_ITEMS))
    expect(slider().max).toBe(String(MAX_ITEMS))
    expect(screen.getByText(/24 crates · seed 991/)).toBeInTheDocument()
  })

  it('starts a new run with the count chosen on the slider', () => {
    const start = vi.fn()
    useSimulationProvider.setState({ itemCount: 36, start })
    render(<RunSetupForm />)

    fireEvent.change(slider(), { target: { value: '14' } })
    fireEvent.click(screen.getByRole('button', { name: /apply & start/i }))

    expect(start).toHaveBeenCalledTimes(1)
    expect(start).toHaveBeenCalledWith({ itemCount: 14 })
  })

  it('rolls a random crate count inside 5..40', () => {
    useSimulationProvider.setState({ itemCount: 36, start: vi.fn() })
    render(<RunSetupForm />)

    const random = vi.spyOn(Math, 'random')
    random.mockReturnValue(0) // lowest roll
    fireEvent.click(screen.getByRole('button', { name: /roll a random crate count/i }))
    expect(slider().value).toBe(String(MIN_ITEMS))

    random.mockReturnValue(0.999999) // highest roll
    fireEvent.click(screen.getByRole('button', { name: /roll a random crate count/i }))
    expect(slider().value).toBe(String(MAX_ITEMS))
  })
})
