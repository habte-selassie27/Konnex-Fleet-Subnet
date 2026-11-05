# frontend/

Operational dashboard + grant demo (Phase 9).

**Stack (AGENTS.md §1.1):** React 18 (hooks only) · TypeScript 5 strict (zero `any`) · Vite 5 · Tailwind 3 · Three.js + React Three Fiber · Recharts · Zustand + TanStack Query · native WebSocket hook · Lucide icons · Vitest + Testing Library · ESLint + Prettier.

| Path | Contents (planned) |
|---|---|
| `src/components/FleetMap.tsx` | Live robot position visualization (3D warehouse map) |
| `src/components/MissionStatus.tsx` | Active mission overview |
| `src/components/MetricsPanel.tsx` | PoPW score, task progress, collisions, energy |
| `src/components/PolicySelector.tsx` | Switch between competing policies |
| `src/components/ValidatorLog.tsx` | Evaluation / validator status |
| `src/services/api.ts` | Typed API client — all fetch calls here (never in components) |
| `src/types/index.ts` | Shared TS types |

**Rules (AGENTS.md §1.6):** never render mock data; show `SIMULATOR OFFLINE — no live data` when Gazebo is down; all async states handled; error boundaries around every panel; a11y (aria-labels, color never the only indicator).

**Status: STUB — placeholder app only, pending Phase 9.**
