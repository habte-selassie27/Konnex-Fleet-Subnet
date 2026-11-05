// Header test — the provenance badge must say it describes the mission, so it
// cannot be read as the fleet's source while the scene shows SIM carts.
import { cleanup, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { Header } from './Header'

afterEach(cleanup)

describe('Header provenance badge', () => {
  it('labels the source as mission-scoped', () => {
    render(<Header />)

    const group = screen.getByRole('group', { name: 'Mission data source' })
    expect(within(group).getByText('Mission')).toBeInTheDocument()
    expect(within(group).getByText('RECORDED')).toBeInTheDocument()
  })
})
