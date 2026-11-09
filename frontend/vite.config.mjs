import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const target = `http://127.0.0.1:${process.env.FRONTEND_HTTP_PORT || '8893'}`;

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/v1/': target,
      '^/probe($|[?])': target,
    },
  },
});
