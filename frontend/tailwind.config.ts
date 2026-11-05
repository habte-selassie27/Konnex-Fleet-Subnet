import type { Config } from 'tailwindcss'

// Tailwind config (AGENTS.md §1.3). Design tokens (colors, typography scale)
// are added in Phase 9 per AGENTS.md §1.3.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config
