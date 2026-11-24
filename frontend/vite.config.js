import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
   base: '/cleanspot/',
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
      '/municipal': 'http://localhost:8000',
      '/uploads': 'http://localhost:8000'
    }
  },
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'CleanSpot',
        short_name: 'CleanSpot',
        description: 'Report illegal garbage dumping in one tap',
        start_url: '/cleanspot/',
        scope: '/cleanspot/',
        display: 'standalone',
        background_color: '#ffffff',
        theme_color: '#1f7a1f',
        icons: [
          { src: '/cleanspot/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/cleanspot/icons/icon-512.png', sizes: '512x512', type: 'image/png' }
        ]
      }
    })
  ]
})