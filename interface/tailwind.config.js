export default {
  content: ['./src/**/*.{js,jsx,ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"DM Sans"', 'system-ui', 'sans-serif'],
        mono: ['"DM Mono"', 'monospace'],
      },
      colors: {
        surface: {
          primary: '#ffffff',
          secondary: '#f5f4f2',
          tertiary: '#edece9',
        },
        ink: {
          primary: '#0a0a0a',
          secondary: '#6b6b6b',
          tertiary: '#b0b0b0',
        },
        accent: {
          DEFAULT: '#2d7a5f',
          bg: '#eef6f2',
        },
      },
      borderColor: {
        DEFAULT: 'rgba(0,0,0,0.08)',
        strong: 'rgba(0,0,0,0.14)',
      },
      borderRadius: {
        sm: '8px',
        md: '14px',
        lg: '20px',
        pill: '100px',
      },
      fontSize: {
        '10': ['10px', { lineHeight: '1.4' }],
        '10.5': ['10.5px', { lineHeight: '1.4' }],
        '13': ['13px', { lineHeight: '1.65' }],
      },
    },
  },
  plugins: [],
}
