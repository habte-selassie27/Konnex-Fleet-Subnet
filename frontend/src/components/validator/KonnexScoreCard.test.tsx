import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { KonnexScoreCard } from './KonnexScoreCard'
import type { KonnexScore } from '../../types'

const score: KonnexScore = {
  safety_gate: 1,
  safety_violations: 0,
  task_match: 1,
  efficiency: 0.8,
  evidence_quality: 1,
  final: 0.94,
  weights: { task_match: 0.5, efficiency: 0.3, evidence_quality: 0.2 },
}

describe('KonnexScoreCard', () => {
  it('shows the gated score, components, and weights', () => {
    render(<KonnexScoreCard konnex={score} />)

    expect(screen.getByText('94.0%')).toBeInTheDocument()
    expect(screen.getByText('Safe')).toBeInTheDocument()
    expect(screen.getByText('80.0%')).toBeInTheDocument()
    expect(screen.getByText('open (0 violations)')).toBeInTheDocument()
    expect(screen.getByText('w=50%')).toBeInTheDocument()
    expect(screen.getByLabelText('Konnex work score')).toBeInTheDocument()
  })

  it('marks a safety-gated evaluation and zeroes the score', () => {
    render(
      <KonnexScoreCard
        konnex={{ ...score, safety_gate: 0, safety_violations: 2, final: 0 }}
      />,
    )

    expect(screen.getByText('Gated')).toBeInTheDocument()
    expect(screen.getByText('0.0%')).toBeInTheDocument()
    expect(screen.getByText('2 violations — score 0')).toBeInTheDocument()
  })

  it('handles a missing score without inventing one', () => {
    render(<KonnexScoreCard konnex={null} />)
    expect(screen.getByText('No Konnex score recorded for this evaluation.')).toBeInTheDocument()
  })
})
