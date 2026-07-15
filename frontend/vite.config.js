import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const PROXY_TIMEOUT_MS = 60000;

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        timeout: PROXY_TIMEOUT_MS,
        proxyTimeout: PROXY_TIMEOUT_MS,
      },
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        ws: true,
        timeout: PROXY_TIMEOUT_MS,
        proxyTimeout: PROXY_TIMEOUT_MS,
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
        timeout: PROXY_TIMEOUT_MS,
        proxyTimeout: PROXY_TIMEOUT_MS,
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
        timeout: PROXY_TIMEOUT_MS,
        proxyTimeout: PROXY_TIMEOUT_MS,
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