// uiStore — theme state for the dashboard.
//
// AGENTS.md §1.6 rule 4 forbids localStorage/sessionStorage in components, so
// the preference lives in Zustand for the session. Applying the theme is a
// single class toggle on <html> (see App.tsx); index.css owns both palettes and
// the WebGL scene reads the same value through scenePalette.ts.
import { create } from 'zustand'

export type Theme = 'dark' | 'light'

interface UiState {
  theme: Theme
  toggleTheme: () => void
  setTheme: (theme: Theme) => void
}

export const useUiStore = create<UiState>((set) => ({
  // The product is a dark-mode-first operations console (AGENTS.md §1.3).
  theme: 'dark',
  toggleTheme: () => set((s) => ({ theme: s.theme === 'dark' ? 'light' : 'dark' })),
  setTheme: (theme) => set({ theme }),
}))
