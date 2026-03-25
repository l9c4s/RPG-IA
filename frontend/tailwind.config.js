/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Dark fantasy backgrounds
        parchment: {
          50:  '#fdf8ee',
          100: '#f9edcc',
          200: '#f0d68a',
        },
        blood: {
          500: '#8b1a1a',
          600: '#6b1212',
          700: '#4a0d0d',
        },
        arcane: {
          400: '#a78bfa',
          500: '#7c3aed',
          600: '#5b21b6',
        },
      },
      fontFamily: {
        serif:  ['"Palatino Linotype"', 'Palatino', 'Georgia', 'serif'],
        sans:   ['Inter', 'system-ui', 'sans-serif'],
        rune:   ['"MedievalSharp"', 'Georgia', 'serif'],
      },
      backgroundImage: {
        'dungeon-texture': "url(\"data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23334155' fill-opacity='0.15'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E\")",
      },
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'flicker': 'flicker 2s linear infinite',
        'fade-in': 'fadeIn 0.3s ease-in-out',
      },
      keyframes: {
        flicker: {
          '0%, 19.999%, 22%, 62.999%, 64%, 64.999%, 70%, 100%': { opacity: '1' },
          '20%, 21.999%, 63%, 63.999%, 65%, 69.999%':            { opacity: '0.4' },
        },
        fadeIn: {
          '0%':   { opacity: '0', transform: 'translateY(4px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      boxShadow: {
        'arcane':  '0 0 15px rgba(124, 58, 237, 0.4)',
        'amber':   '0 0 15px rgba(245, 158, 11, 0.4)',
        'blood':   '0 0 15px rgba(139, 26, 26, 0.5)',
        'inner-dark': 'inset 0 2px 8px rgba(0,0,0,0.6)',
      },
      borderColor: {
        'rune': '#d97706',
      },
    },
  },
  plugins: [],
}
