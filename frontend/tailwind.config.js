/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // On-light text tokens (keep names so existing classes still work)
        ink: '#0f172a',
        muted: '#64748b',
        // App surfaces (clean white theme)
        base: '#f8fafc',
        surface: '#ffffff',
        raised: '#ffffff',
        line: '#e2e8f0',
        lineSoft: '#f1f5f9',
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
        glow: '0 0 0 1px rgba(20,113,232,0.10), 0 8px 40px -12px rgba(43,143,255,0.30)',
        card: '0 1px 2px rgba(15,23,42,0.05), 0 10px 30px -12px rgba(15,23,42,0.12)',
      },
      borderRadius: {
        xl2: '1.25rem',
      },
      backgroundImage: {
        'brand-gradient': 'linear-gradient(135deg, #1471e8 0%, #2b8fff 45%, #54b1ff 100%)',
        'login-glow':
          'radial-gradient(900px 460px at 15% -10%, rgba(43,143,255,0.12), transparent 60%), radial-gradient(700px 380px at 90% 110%, rgba(84,177,255,0.10), transparent 60%)',
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