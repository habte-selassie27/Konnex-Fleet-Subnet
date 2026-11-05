import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { PolicyRegistry } from './PolicyRegistry'
import { api } from '../../services/api'
import type { PolicyRecord } from '../../types'

vi.mock('../../services/api', () => ({
  api: { listPolicies: vi.fn(), submitPolicy: vi.fn() },
}))

const listPolicies = vi.mocked(api.listPolicies)

afterEach(cleanup)
beforeEach(() => {
  listPolicies.mockReset()
})

function policy(overrides: Partial<PolicyRecord> = {}): PolicyRecord {
  return {
    id: 'policy-1',
    name: 'my-hungarian-v2',
    version: '0.1.0',
    author: 'miner-1',
    algorithm: 'hungarian',
    policy_hash: '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
    status: 'VERIFIED',
    size_bytes: 2048,
    duplicate: false,
    artifact_url: '/api/v1/policies/policy-1/artifact',
    created_at: '2026-11-04T12:00:00Z',
    ...overrides,
  }
}

describe('PolicyRegistry', () => {
  it('renders verified submissions with a shortened hash', async () => {
    listPolicies.mockResolvedValue([policy()])
    render(<PolicyRegistry />)

    expect(await screen.findByText('my-hungarian-v2')).toBeInTheDocument()
    expect(screen.getByText('hungarian')).toBeInTheDocument()
    expect(screen.getByText('VERIFIED')).toBeInTheDocument()
    expect(screen.getByText('9f86d081884c7d65…')).toBeInTheDocument()
    expect(screen.getByText('1 verified')).toBeInTheDocument()
    expect(screen.getByText(/v0.1.0 · miner-1 · 2048 B/)).toBeInTheDocument()
  })

  it('shows an empty state before any policy is submitted', async () => {
    listPolicies.mockResolvedValue([])
    render(<PolicyRegistry />)

    expect(
      await screen.findByText(/No policies submitted yet/),
    ).toBeInTheDocument()
  })

  it('reports a failed policy fetch instead of pretending there are none', async () => {
    listPolicies.mockRejectedValue(new Error('API 503: Service Unavailable'))
    render(<PolicyRegistry />)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Policies unavailable: API 503: Service Unavailable',
    )
  })
})
