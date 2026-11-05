// Vitest setup — Testing Library jest-dom matchers (AGENTS.md §1.1).
import '@testing-library/jest-dom/vitest'

// Recharts' ResponsiveContainer observes its parent with ResizeObserver,
// which jsdom does not implement — provide a minimal no-op mock.
class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

globalThis.ResizeObserver = globalThis.ResizeObserver ?? ResizeObserverMock
