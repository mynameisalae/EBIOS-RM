/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ground: '#F5F3EF',
        sheet: '#FFFFFF',
        ink: { DEFAULT: '#17140F', soft: '#4F4A43', mute: '#857F76' },
        line: { DEFAULT: '#E6E2DB', strong: '#CFC9BF' },
        crimson: { DEFAULT: '#BE1E2D', deep: '#8F1421', tint: '#FBEDEE' },
        gold: { DEFAULT: '#CC9900', deep: '#8A6508', tint: '#FBF3DC' },
        ok: { DEFAULT: '#1E7B3C', tint: '#E8F3EC' },
        lvl: { 1: '#E6D8A8', 2: '#E3A83A', 3: '#D26B3A', 4: '#BE1E2D' },
      },
      fontFamily: {
        display: ['"Archivo Variable"', 'system-ui', 'sans-serif'],
        sans: ['"Source Sans 3 Variable"', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono Variable"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        sheet: '0 1px 0 rgba(23,20,15,.04), 0 24px 48px -24px rgba(23,20,15,.25)',
        soft: '0 1px 2px rgba(23,20,15,.05)',
      },
    },
  },
  plugins: [],
}
