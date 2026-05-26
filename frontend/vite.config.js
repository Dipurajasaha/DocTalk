import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // reduce wait and handle backend-down errors gracefully to avoid noisy ECONNREFUSED logs
        timeout: 2000,
        proxyTimeout: 2000,
        onError(err, req, res) {
          try {
            if (!res.headersSent) {
              res.writeHead ? res.writeHead(502, { 'Content-Type': 'application/json' }) : null;
              res.end(JSON.stringify({ error: 'backend_unavailable' }));
            }
          } catch (e) {}
        },
      },
      '/static': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        timeout: 2000,
        proxyTimeout: 2000,
        onError(err, req, res) {
          try {
            if (!res.headersSent) {
              res.writeHead ? res.writeHead(502, { 'Content-Type': 'application/json' }) : null;
              res.end(JSON.stringify({ error: 'backend_unavailable' }));
            }
          } catch (e) {}
        },
      },
      '/me': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        timeout: 2000,
        proxyTimeout: 2000,
        onError(err, req, res) {
          try {
            if (!res.headersSent) {
              res.writeHead ? res.writeHead(502, { 'Content-Type': 'application/json' }) : null;
              res.end(JSON.stringify({ error: 'backend_unavailable' }));
            }
          } catch (e) {}
        },
      },
    },
  },
});