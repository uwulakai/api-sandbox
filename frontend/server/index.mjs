import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { handleRoutes } from './routes.mjs';

const port = Number(process.env.PORT || 8080);
const dist = new URL('../dist/', import.meta.url);
const types = { js: 'text/javascript', css: 'text/css' };
const policy = "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'";

createServer(async (req, res) => {
  try {
    if (handleRoutes(req, res)) return;
    if (req.method !== 'GET' && req.method !== 'HEAD') {
      res.writeHead(405, { Allow: 'GET, HEAD' }).end();
      return;
    }

    const path = new URL(req.url, 'http://localhost').pathname;
    const asset = /^\/assets\/([\w-]+)\.(js|css)$/.exec(path);
    if (path !== '/' && !asset) {
      res.writeHead(404).end('Not found');
      return;
    }
    const data = await readFile(new URL(asset ? path.slice(1) : 'index.html', dist));
    res.writeHead(200, {
      'Content-Type': `${asset ? types[asset[2]] : 'text/html'}; charset=utf-8`,
      'Cache-Control': asset ? 'public, max-age=31536000, immutable' : 'no-cache',
      'Content-Security-Policy': policy,
      'X-Content-Type-Options': 'nosniff',
    });
    res.end(req.method === 'HEAD' ? undefined : data);
  } catch (error) {
    res.writeHead(error.code === 'ENOENT' ? 404 : 500).end();
  }
}).listen(port, process.env.HOST || '127.0.0.1', () => console.log(`Frontend listening on port ${port}`));
