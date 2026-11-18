import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const frontendDir = fileURLToPath(new URL('.', import.meta.url));
  const benchmarkDir = resolve(frontendDir, process.env.VITE_BENCHMARK_RESULTS_DIR || env.VITE_BENCHMARK_RESULTS_DIR || '../backend/experiments/results/imperfect_user_v4_multiseed_seed13');
  const manifestPath = resolve(benchmarkDir, 'manifest.json');
  const runsPath = resolve(benchmarkDir, 'runs.jsonl');
  // Benchmark artifacts are optional for the normal frontend; the benchmark page
  // can render its empty state when no results directory has been configured.
  const benchmarkManifest = existsSync(manifestPath) ? readFileSync(manifestPath, 'utf8') : '{}';
  const benchmarkRuns = existsSync(runsPath) ? readFileSync(runsPath, 'utf8') : '';
  const backendPort = process.env.VITE_BACKEND_PORT || process.env.PORT || env.VITE_BACKEND_PORT || env.PORT || '8000';
  
  return {
    plugins: [react()],
    define: {
      __BENCHMARK_MANIFEST__: JSON.stringify(benchmarkManifest),
      __BENCHMARK_RUNS__: JSON.stringify(benchmarkRuns),
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
