/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy:  { 900: '#0b1e3d', 800: '#112849', 700: '#1a3f6f', 600: '#1e5096' },
        teal:  { 400: '#2dd4bf', 500: '#14b8a6', 600: '#0d9488' },
        amber: { 400: '#fbbf24', 500: '#f59e0b' },
        danger:{ 500: '#ef4444', 600: '#dc2626' },
      },
      fontFamily: {
        sans: ['"DM Sans"', 'ui-sans-serif', 'system-ui'],
        mono: ['"JetBrains Mono"', 'ui-monospace'],
      },
      animation: {
        'fade-in':   'fadeIn 0.4s ease both',
        'slide-up':  'slideUp 0.35s ease both',
        'pulse-dot': 'pulseDot 1.4s ease-in-out infinite',
      },
      keyframes: {
        fadeIn:   { from: { opacity: 0 }, to: { opacity: 1 } },
        slideUp:  { from: { opacity: 0, transform: 'translateY(12px)' }, to: { opacity: 1, transform: 'translateY(0)' } },
        pulseDot: { '0%,100%': { opacity: 1 }, '50%': { opacity: 0.3 } },
      },
    },
  },
  plugins: [],
}
