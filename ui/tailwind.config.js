/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: '#1C1917', soft: '#57534E', mute: '#8B857D' },
        paper: '#FAFAF8',
        line: { DEFAULT: '#E7E4DF', strong: '#D3CEC6' },
        crimson: { DEFAULT: '#BE1E2D', deep: '#8F1421', tint: '#FBEDEE' },
        gold: { DEFAULT: '#C8960C', deep: '#8A6508', tint: '#FBF3DC' },
        ok: { DEFAULT: '#1E7B3C', tint: '#E8F3EC' },
        lvl: { 1: '#E6D8A8', 2: '#E3A83A', 3: '#D26B3A', 4: '#BE1E2D' },
      },
      fontFamily: {
        display: ['"Archivo Variable"', 'system-ui', 'sans-serif'],
        sans: ['"Source Sans 3 Variable"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono Variable"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        sheet: '0 1px 0 rgba(28,25,23,.04), 0 16px 36px -16px rgba(28,25,23,.22)',
        soft: '0 1px 2px rgba(28,25,23,.05)',
      },
    },
  },
  plugins: [],
}
