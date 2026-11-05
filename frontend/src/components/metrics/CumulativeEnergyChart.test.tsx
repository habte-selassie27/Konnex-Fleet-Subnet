import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { CumulativeEnergyChart } from './CumulativeEnergyChart'

describe('CumulativeEnergyChart', () => {
  it('labels the single captured energy point', () => {
    render(<CumulativeEnergyChart total={211.8} elapsed_s={600} time_limit_s={600} />)

    expect(screen.getByRole('img')).toHaveAccessibleName(
      'Cumulative energy 211.8 units at 600 seconds',
    )
    expect(
      screen.getByText('Final total only — the capture has no per-step energy series.'),
    ).toBeInTheDocument()
  })

  it('shows a no-data state instead of inventing a series', () => {
    render(<CumulativeEnergyChart total={0} elapsed_s={600} time_limit_s={600} />)
    expect(screen.getByText('No energy data')).toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })
})
