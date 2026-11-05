import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../../services/api', () => ({
  api: {
    getRewardSplit: vi.fn(),
  },
}))

import { api } from '../../services/api'
import { RewardSplitTable } from './RewardSplitTable'
import type { RewardSplit } from '../../types'

const split: RewardSplit = {
  top_share: 0.75,
  note: 'Projected shares of a unit reward pool.',
  entries: [
    {
      policy_id: 'nearest',
      evaluation_id: 'eval-1',
      score: 0.94,
      competitive_share: 0.61,
      winner_takes_most_share: 0.75,
      is_top: true,
    },
    {
      policy_id: 'hungarian',
      evaluation_id: 'eval-2',
      score: 0.6,
      competitive_share: 0.39,
      winner_takes_most_share: 0.25,
      is_top: false,
    },
  ],
}

describe('RewardSplitTable', () => {
  it('renders each policy share and highlights the current policy', async () => {
    vi.mocked(api.getRewardSplit).mockResolvedValue(split)
    render(<RewardSplitTable policyId="hungarian" />)

    const table = await screen.findByRole('table')
    expect(within(table).getByText('nearest')).toBeInTheDocument()
    expect(within(table).getByText('top')).toBeInTheDocument()
    expect(within(table).getByText('current')).toBeInTheDocument()
    expect(within(table).getByText('61.0%')).toBeInTheDocument()
    expect(within(table).getByText('75.0%')).toBeInTheDocument()
    expect(screen.getByText('Projected shares of a unit reward pool.')).toBeInTheDocument()
  })

  it('shows an empty state when no policy has been scored', async () => {
    vi.mocked(api.getRewardSplit).mockResolvedValue({ ...split, entries: [] })
    render(<RewardSplitTable policyId="nearest" />)
    expect(await screen.findByText('No scored evaluations yet.')).toBeInTheDocument()
  })

  it('shows the API error instead of a fabricated split', async () => {
    vi.mocked(api.getRewardSplit).mockRejectedValue(new Error('API 500: boom'))
    render(<RewardSplitTable policyId="nearest" />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Reward split unavailable')
  })
})
