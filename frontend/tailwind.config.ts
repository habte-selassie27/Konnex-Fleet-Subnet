import type { Config } from 'tailwindcss'

// Tailwind config (AGENTS.md §1.3). Design tokens (colors, typography scale).
//
// The palette lives in CSS variables (src/index.css: `:root` light values +
// `.dark` overrides). Every color is declared with Tailwind's `/ <alpha-value>`
// form so utilities like `bg-panel/85`, `border-line/60` and `text-subtle/70`
// resolve per-element alpha instead of baking it into the variable.
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        surface: 'rgb(var(--surface) / <alpha-value>)',
        'surface-strong': 'rgb(var(--elevated) / <alpha-value>)',
        panel: 'rgb(var(--panel) / <alpha-value>)',
        elevated: 'rgb(var(--elevated) / <alpha-value>)',
        line: 'rgb(var(--line) / <alpha-value>)',
        'line-strong': 'rgb(var(--line-strong) / <alpha-value>)',
        fg: 'rgb(var(--fg) / <alpha-value>)',
        muted: 'rgb(var(--muted) / <alpha-value>)',
        subtle: 'rgb(var(--subtle) / <alpha-value>)',
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
    },
  },
  plugins: [],
} satisfies Config
