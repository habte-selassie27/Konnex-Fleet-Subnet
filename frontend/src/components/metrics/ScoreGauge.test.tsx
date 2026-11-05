import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ScoreGauge } from './ScoreGauge'

describe('ScoreGauge', () => {
  it('shows "No data yet" when no score exists (never zeros)', () => {
    render(<ScoreGauge score={null} />)
    expect(screen.getByText('No data yet')).toBeInTheDocument()
    expect(screen.getByLabelText('PoPW score: no data yet')).toBeInTheDocument()
  })

  it('renders the score value when provided', () => {
    render(<ScoreGauge score={94.2} />)
    expect(screen.getByText('94.2')).toBeInTheDocument()
    expect(screen.getByLabelText('PoPW score 94.2 out of 100')).toBeInTheDocument()
  })
})
