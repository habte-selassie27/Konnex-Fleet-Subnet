import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { BenchmarkTable } from './BenchmarkTable'
import { api } from '../../services/api'
import type { BenchmarkResult } from '../../types'

vi.mock('../../services/api', () => ({ api: { listBenchmarks: vi.fn() } }))

const listBenchmarks = vi.mocked(api.listBenchmarks)

afterEach(cleanup)
beforeEach(() => {
  listBenchmarks.mockReset()
})

function row(overrides: Partial<BenchmarkResult> = {}): BenchmarkResult {
  return {
    experiment_id: 'fleet_env_unified',
    policy: 'mappo',
    scenario_id: 'warehouse_v1_20tasks',
    harness: 'FleetEnv',
    robot_count: 5,
    n_runs: 30,
    seed_range: [1000, 1029],
    mean_popw_score: 92.928,
    std_popw_score: 2.14,
    mean_success_rate: 1.0,
    std_success_rate: 0.0,
    mean_collision_count: 1.1,
    std_collision_count: 0.88,
    mean_completion_time_s: 135.6,
    std_completion_time_s: 14.2,
    status: 'COMPLETE',
    skip_reason: '',
    ran_at: '2026-11-03T09:15:29Z',
    git_commit: 'e014648c',
    source: 'fleet_env_unified',
    ...overrides,
  }
}

describe('BenchmarkTable', () => {
  it('renders measured scores, success, and collisions', async () => {
    listBenchmarks.mockResolvedValue([row()])
    render(<BenchmarkTable />)

    expect(await screen.findByText('mappo')).toBeInTheDocument()
    expect(screen.getByText('92.9 ± 2.1')).toBeInTheDocument()
    expect(screen.getByText('100.0% ± 0.0%')).toBeInTheDocument()
    expect(screen.getByText('1.1 ± 0.9')).toBeInTheDocument()
    expect(screen.getByText('COMPLETE')).toBeInTheDocument()
    expect(screen.getByText('fleet_env_unified · FleetEnv · 5 robots · 30 runs')).toBeInTheDocument()
    expect(screen.getByText('1 measured')).toBeInTheDocument()
  })

  it('shows an em dash and the skip reason for an unmeasured row', async () => {
    listBenchmarks.mockResolvedValue([
      row({ policy: 'mappo', mean_popw_score: null, status: 'SKIPPED', skip_reason: 'no checkpoint' }),
    ])
    render(<BenchmarkTable />)

    expect(await screen.findByText('SKIPPED')).toBeInTheDocument()
    expect(screen.getByText('no checkpoint')).toBeInTheDocument()
  })

  it('keeps the honest empty state when no results exist', async () => {
    listBenchmarks.mockResolvedValue([])
    render(<BenchmarkTable />)

    expect(await screen.findByText(/No benchmark data yet/)).toBeInTheDocument()
  })

  it('reports an API failure instead of rendering numbers', async () => {
    listBenchmarks.mockRejectedValue(new Error('API 500: Internal Server Error'))
    render(<BenchmarkTable />)

    expect(await screen.findByRole('alert')).toHaveTextContent('Benchmark results unavailable')
  })
})
