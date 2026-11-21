import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({
  plugins: [vue()],
  server: { allowedHosts: true, proxy: { '/api': { target: 'http://127.0.0.1:5000', xfwd: true } } }
})
