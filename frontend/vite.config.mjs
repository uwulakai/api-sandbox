import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { handleRoutes } from './server/routes.mjs';

export default defineConfig({
  plugins: [
    react(),
    {
      name: 'api-sandbox-routes',
      configureServer(server) {
        server.middlewares.use((req, res, next) => {
          if (!handleRoutes(req, res)) next();
        });
      },
    },
  ],
});
