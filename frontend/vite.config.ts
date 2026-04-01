import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { Agent } from 'http'

// Inside Docker the service names are used; outside Docker falls back to localhost
const apiHost = process.env.VITE_API_HOST ?? 'localhost'
const wsHost  = process.env.VITE_WS_HOST  ?? 'localhost'
const httpAgent = new Agent({ keepAlive: false })

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      // Campaign-specific character list
      '^/api/campaigns/[^/]+/characters(/.*)?$': {
        target:  `http://${process.env.VITE_CHARACTER_HOST ?? apiHost}:8003`,
        rewrite: (path) => path.replace(/^\/api/, ''),
        agent: httpAgent,
      },
      // Campaign service — campanhas, sessões, GM actions
      '/api/campaigns': {
        target:  `http://${process.env.VITE_CAMPAIGN_HOST ?? apiHost}:8002`,
        rewrite: (path) => path.replace(/^\/api/, ''),
        agent: httpAgent,
      },
      '/api/sessions': {
        target:  `http://${process.env.VITE_CAMPAIGN_HOST ?? apiHost}:8002`,
        rewrite: (path) => path.replace(/^\/api/, ''),
        agent: httpAgent,
      },
      '/api/session': {
        target:  `http://${process.env.VITE_CAMPAIGN_HOST ?? apiHost}:8002`,
        rewrite: (path) => path.replace(/^\/api/, ''),
        agent: httpAgent,
      },
      // Characters service
      '/api/characters': {
        target:  `http://${process.env.VITE_CHARACTER_HOST ?? apiHost}:8003`,
        rewrite: (path) => path.replace(/^\/api\/characters/, '/characters'),
        agent: httpAgent,
      },
      // PDF / knowledge service
      '/api/books': {
        target:  `http://${process.env.VITE_PDF_HOST ?? apiHost}:8001`,
        rewrite: (path) => path.replace(/^\/api\/books/, ''),
        agent: httpAgent,
      },
      // Gateway — auth e rotas gerais (fallback)
      '/api': {
        target:  `http://${apiHost}:8000`,
        rewrite: (path) => path.replace(/^\/api/, ''),
        agent: httpAgent,
      },
      // WebSocket multiplayer
      '/ws': {
        target: `ws://${wsHost}:8002`,
        ws:     true,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/__tests__/setup.ts'],
    css: false,
  },
})
