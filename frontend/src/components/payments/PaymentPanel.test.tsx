import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

// Mock the API client so the panel renders from fixtures without a backend.
vi.mock('../../services/api', () => ({
  api: {
    getPaymentWallet: vi.fn(),
    getPaymentTransactions: vi.fn(),
    getPaymentSummary: vi.fn(),
    paymentDemo: vi.fn(),
  },
}))

import { api } from '../../services/api'
import { PaymentPanel } from './PaymentPanel'
import type {
  PaymentDemoResult,
  PaymentSummary,
  PaymentTransaction,
  PaymentWallet,
} from '../../types'

const wallet: PaymentWallet = {
  wallet_id: 'fleet-agent-wallet-001',
  currency: 'USDC',
  balance_usdc: 825,
  daily_budget_usdc: 500,
  spent_today_usdc: 175,
  remaining_today_usdc: 325,
  max_tx_usdc: 250,
  is_mock: true,
  network: 'arc-mock',
}

const summary: PaymentSummary = {
  wallet,
  autonomous_payments: 3,
  usdc_settled: 175,
  arc_transactions: 3,
  receipts: 3,
  rejected_intents: 0,
}

const transaction: PaymentTransaction = {
  id: 'tx-1',
  intent_id: 'intent-1',
  fleet_id: 'FLEET-017',
  vehicle_id: 'TRUCK-42',
  provider_id: 'prov_charge_a',
  provider_name: 'VoltCharge',
  provider_address: '0x3f398ba703c2c69cd0817e28682e5e7468ffc6c2',
  service: 'charging',
  amount_usdc: 18,
  currency: 'USDC',
  status: 'settled',
  settlement_status: 'settled',
  tx_hash: '0xMOCK7c30f8f1e27b0983366c2516317c2e947e7c4eb5bb6c38e38237328f',
  receipt_id: 'rcpt_tx-1',
  reason: 'charging required (battery 18%)',
  decision_rationale: 'Battery 18% (urgency 2.0).',
  explorer_url: 'https://mock-explorer.arc.local/tx/0xMOCK7c30f8',
  is_mock: true,
  created_at: 1_700_000_000,
  executed_at: 1_700_000_000,
  settled_at: 1_700_000_000,
}

const demoResult: PaymentDemoResult = {
  decisions: [
    {
      fleet_id: 'FLEET-017',
      vehicle_id: 'TRUCK-42',
      service: 'charging',
      amount_usdc: 18,
      rationale: 'Battery 18% (urgency 2.0). Selected VoltCharge.',
      no_action: false,
      selected_provider_id: 'prov_charge_a',
      quotes: [
        {
          provider_id: 'prov_charge_a',
          name: 'VoltCharge',
          service: 'charging',
          price_usdc: 18,
          distance_km: 3,
          rating: 4.8,
          address: '0x3f398ba703c2c69cd0817e28682e5e7468ffc6c2',
          score: 20.04,
          selected: true,
        },
      ],
    },
  ],
  transactions: [transaction],
  summary,
}

const mockedApi = api as unknown as {
  getPaymentWallet: ReturnType<typeof vi.fn>
  getPaymentTransactions: ReturnType<typeof vi.fn>
  getPaymentSummary: ReturnType<typeof vi.fn>
  paymentDemo: ReturnType<typeof vi.fn>
}

describe('PaymentPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedApi.getPaymentWallet.mockResolvedValue(wallet)
    mockedApi.getPaymentTransactions.mockResolvedValue([transaction])
    mockedApi.getPaymentSummary.mockResolvedValue(summary)
  })

  it('loads and shows the agent wallet with a MOCK badge', async () => {
    render(<PaymentPanel />)
    expect(await screen.findByText('Agent Wallet')).toBeInTheDocument()
    expect(screen.getByText('825.00')).toBeInTheDocument()
    expect(screen.getAllByText('MOCK / DEMO').length).toBeGreaterThan(0)
    expect(screen.getByText('175.00')).toBeInTheDocument() // USDC settled total
  })

  it('renders payment history with the mock tx hash', async () => {
    render(<PaymentPanel />)
    expect(await screen.findByText('Payment History')).toBeInTheDocument()
    expect(screen.getByText('TRUCK-42')).toBeInTheDocument()
    expect(screen.getByText('VoltCharge')).toBeInTheDocument()
    expect(screen.getByText('Mock')).toBeInTheDocument()
  })

  it('runs the demo scenario on button click and shows the agent decision', async () => {
    mockedApi.paymentDemo.mockResolvedValue(demoResult)
    render(<PaymentPanel />)
    const button = await screen.findByRole('button', { name: /run end-to-end demo/i })
    button.click()
    expect(await screen.findByText(/Battery 18%/)).toBeInTheDocument()
    expect((await screen.findAllByText('VoltCharge')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('MOCK / DEMO').length).toBeGreaterThan(0)
  })
})
