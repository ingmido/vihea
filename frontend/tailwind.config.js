export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    extend: {
      colors: {
        royal: { DEFAULT: '#003366', 700: '#1e3a8a', 50: '#eff4fb' },
        gold: { DEFAULT: '#d97706', 400: '#f59e0b' },
        slate: { bg: '#f8fafc' }
      },
      fontFamily: {
        khmer: ['"Kantumruy Pro"', 'sans-serif'],
        moul: ['Moul', 'serif']
      }
    }
  }
}
