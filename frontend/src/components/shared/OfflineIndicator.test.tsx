import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { OfflineIndicator } from './OfflineIndicator'

describe('OfflineIndicator', () => {
  it('renders the default offline message with role=status', () => {
    render(<OfflineIndicator />)
    expect(screen.getByRole('status')).toHaveTextContent('Simulator offline — no live data')
  })

  it('renders a custom message', () => {
    render(<OfflineIndicator message="Backend unreachable" />)
    expect(screen.getByText('Backend unreachable')).toBeInTheDocument()
  })
})
