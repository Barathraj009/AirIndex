/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // On-dark text tokens (keep names so existing classes still work)
        ink: '#e2e8f0',
        muted: '#94a3b8',
        // App surfaces
        base: '#0b1220',
        surface: '#0f172a',
        raised: '#131c2e',
        line: '#1e293b',
        lineSoft: '#182233',
        // Brand (aviation sky)
        brand: {
          50: '#eef7ff',
          100: '#d9ecff',
          200: '#b9dfff',
          300: '#8accff',
          400: '#54b1ff',
          500: '#2b8fff',
          600: '#1471e8',
          700: '#115bc0',
          800: '#144b99',
          900: '#15407a',
          950: '#112852',
        },
      },
      fontFamily: {
        sans: [
          'Inter',
          '-apple-system',
          'BlinkMacSystemFont',
          'Segoe UI',
          'Roboto',
          'Helvetica',
          'Arial',
          'sans-serif',
        ],
      },
      boxShadow: {
        glow: '0 0 0 1px rgba(84,177,255,0.15), 0 8px 40px -12px rgba(43,143,255,0.35)',
        card: '0 1px 0 0 rgba(255,255,255,0.03) inset, 0 10px 30px -12px rgba(0,0,0,0.6)',
      },
      borderRadius: {
        xl2: '1.25rem',
      },
      backgroundImage: {
        'brand-gradient': 'linear-gradient(135deg, #1471e8 0%, #2b8fff 45%, #54b1ff 100%)',
        'login-glow':
          'radial-gradient(1000px 500px at 15% -10%, rgba(43,143,255,0.22), transparent 60%), radial-gradient(800px 400px at 90% 110%, rgba(84,177,255,0.12), transparent 60%)',
      },
      keyframes: {
        'fade-in-up': {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.45' },
        },
      },
      animation: {
        'fade-in-up': 'fade-in-up 0.4s ease-out both',
        'pulse-soft': 'pulse-soft 1.8s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}