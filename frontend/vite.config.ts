import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,         // Equivale a --host, risolve il problema di Edge/IPv6
    port: 5173,         // Forza la porta 5173
    strictPort: true,   // Se la 5173 è occupata, dà errore invece di cambiare porta
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000', // Usa l'IP per andare sul sicuro col backend
        changeOrigin: true,
      },
    },
  },
})