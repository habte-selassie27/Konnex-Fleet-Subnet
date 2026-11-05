import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'
import { useFleetStore } from '../../store/fleetStore'
import { EnergyChart } from './EnergyChart'

function setOnlineAndMission() {
  useFleetStore.setState({ isOnline: true })
}

describe('EnergyChart', () => {
  beforeEach(() => {
    useFleetStore.getState().reset()
  })

  it('shows "No data yet" when there are no samples', () => {
    setOnlineAndMission()
    render(<EnergyChart />)
    expect(screen.getByText('No data yet')).toBeInTheDocument()
  })

  it('shows "No data yet" when the simulator is offline', () => {
    useFleetStore.getState().recordEnergySample(0, 0)
    render(<EnergyChart />)
    expect(screen.getByText('No data yet')).toBeInTheDocument()
  })

  it('renders a labelled chart with the current energy value once data flows', () => {
    setOnlineAndMission()
    useFleetStore.getState().recordEnergySample(0, 0)
    useFleetStore.getState().recordEnergySample(1, 2.5)
    useFleetStore.getState().recordEnergySample(2, 5)

    render(<EnergyChart />)
    expect(screen.getByRole('img')).toHaveAccessibleName(
      'Energy consumption chart, current 5.0 units',
    )
    expect(screen.queryByText('No data yet')).not.toBeInTheDocument()
  })
})
