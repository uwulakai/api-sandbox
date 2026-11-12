import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';

const template = new URL('../../backend/app/notifications/templates/verify_email.html', import.meta.url);
const port = Number(process.env.EMAIL_PREVIEW_PORT || 8894);

createServer(async (req, res) => {
  if (req.method !== 'GET' || req.url !== '/') {
    res.writeHead(404).end();
    return;
  }
  try {
    const html = (await readFile(template, 'utf8'))
      .replaceAll('${verification_url}', `http://localhost:8893/#verify-email=${'p'.repeat(43)}`)
      .replaceAll('${ttl_minutes}', '30');
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' });
    res.end(html);
  } catch {
    res.writeHead(500).end('Email preview unavailable');
  }
}).listen(port, '127.0.0.1', () => console.log(`Email preview: http://localhost:${port}`));
