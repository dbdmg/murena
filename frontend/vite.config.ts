import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const frontendDir = fileURLToPath(new URL('.', import.meta.url));
  const scenariosDir = resolve(frontendDir, process.env.DEMO_SCENARIOS_DIR || env.DEMO_SCENARIOS_DIR || '../backend/experiments/data/scenarios_v3');
  const benchmarkDir = resolve(frontendDir, process.env.VITE_BENCHMARK_RESULTS_DIR || env.VITE_BENCHMARK_RESULTS_DIR || '../backend/experiments/results/all_scenarios_codex');
  const backendPort = process.env.VITE_BACKEND_PORT || process.env.PORT || env.VITE_BACKEND_PORT || env.PORT || '8000';
  
  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@demo-scenarios': resolve(scenariosDir, 'scenario_triplets.json'),
        '@benchmark-manifest': resolve(benchmarkDir, 'manifest.json'),
        '@benchmark-runs': resolve(benchmarkDir, 'runs.jsonl'),
      },
    },
    server: {
      proxy: mode === 'demo' || env.VITE_DEMO_MODE === 'true' ? undefined : {
        '/api': {
          target: `http://localhost:${backendPort}`,
          changeOrigin: true,
          ws: true,
        },
      },
    },
    build: {
      // Split heavy vendors into cacheable chunks: faster first paint and
      // no giant single bundle re-downloaded on every deploy.
      rollupOptions: {
        output: {
          manualChunks: {
            'vendor-react': ['react', 'react-dom', 'react-router-dom'],
            'vendor-map': ['leaflet', 'react-leaflet', 'supercluster', 'use-supercluster'],
            'vendor-charts': ['recharts'],
            'vendor-motion': ['framer-motion'],
          },
        },
      },
      chunkSizeWarningLimit: 900,
    },
  };
})
