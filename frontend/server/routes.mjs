import { request as requestHttp } from 'node:http';
import { request as requestHttps } from 'node:https';
import { pipeline } from 'node:stream/promises';

const api = process.env.API_UPSTREAM || 'http://localhost:8890';
const gateway = process.env.MOCK_GATEWAY_UPSTREAM || 'http://localhost:8892';
const methods = new Set(['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']);
const maxBytes = 1024 * 1024;

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

async function readBody(stream, limitMessage, status) {
  const chunks = [];
  let size = 0;
  if (!stream) return Buffer.alloc(0);
  for await (const chunk of stream) {
    size += chunk.length;
    if (size > maxBytes) throw new HttpError(status, limitMessage);
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}

function json(res, status, data) {
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
  });
  res.end(JSON.stringify(data));
}

function upstream(url, options, timeout = 15_000) {
  return fetch(url, {
    ...options,
    redirect: 'manual',
    signal: AbortSignal.timeout(timeout),
  });
}

async function proxyApi(req, res, path) {
  const target = new URL(path, api);
  const request = target.protocol === 'https:' ? requestHttps : requestHttp;
  const response = await new Promise((resolve, reject) => {
    const headers = { Accept: 'application/json' };
    for (const name of ['authorization', 'content-type', 'content-length']) {
      if (req.headers[name] !== undefined) headers[name] = req.headers[name];
    }
    const outgoing = request(target, { method: req.method, headers, timeout: 15_000 }, resolve);
    outgoing.on('error', reject);
    outgoing.on('timeout', () => outgoing.destroy(new HttpError(504, 'API не ответил вовремя.')));
    res.once('close', () => outgoing.destroy());
    req.pipe(outgoing);
  });
  res.writeHead(response.statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    ...(response.headers['x-request-id'] && { 'X-Request-ID': response.headers['x-request-id'] }),
  });
  await pipeline(response, res);
}

async function probe(req, res) {
  if (req.method !== 'POST') throw new HttpError(405, 'Используйте POST.');
  if (!req.headers.authorization) throw new HttpError(401, 'Войдите в аккаунт.');
  if (req.headers['content-type']?.split(';')[0] !== 'application/json') {
    throw new HttpError(415, 'Ожидается JSON.');
  }
  const raw = await readBody(req.iterator({ destroyOnReturn: false }), 'Запрос превышает 1 МБ.', 413);
  let payload;
  try {
    payload = JSON.parse(raw.toString());
  } catch {
    throw new HttpError(400, 'Некорректный JSON.');
  }
  const { id, method, path, body } = payload ?? {};
  if (typeof id !== 'string' || !/^[\da-f]{8}-(?:[\da-f]{4}-){3}[\da-f]{12}$/i.test(id)
      || !methods.has(method) || typeof path !== 'string' || !path.startsWith('/')
      || path.length > 4096 || /[#\\\r\n]/.test(path)) {
    throw new HttpError(400, 'Укажите корректный метод и путь, начинающийся с /.');
  }
  const target = new URL(`/${id}${path}`, gateway);
  if (!target.pathname.startsWith(`/${id}/`)) throw new HttpError(400, 'Путь выходит за пределы мока.');

  const owned = await upstream(new URL(`/api/v1/mocks/${id}`, api), {
    headers: { Authorization: req.headers.authorization },
  });
  await owned.body?.cancel();
  if (owned.status === 401) throw new HttpError(401, 'Сессия истекла. Войдите снова.');
  if (owned.status === 404) throw new HttpError(404, 'Мок не найден.');
  if (!owned.ok) throw new HttpError(502, 'API не смог проверить доступ к моку.');

  const started = performance.now();
  const sendBody = body !== undefined && !['GET', 'HEAD'].includes(method);
  const response = await upstream(target, {
    method,
    ...(sendBody && { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }),
  }, 70_000);
  const content = await readBody(response.body, 'Ответ мока превышает 1 МБ.', 502);
  // Mock headers are data in the result. They never control the browser response.
  json(res, 200, {
    status: response.status,
    elapsedMs: Math.round(performance.now() - started),
    headers: Object.fromEntries(response.headers),
    body: content.toString(),
  });
}

export function handleRoutes(req, res) {
  const url = new URL(req.url, 'http://localhost');
  if (url.pathname !== '/probe' && !url.pathname.startsWith('/api/v1/')) return false;

  const operation = url.pathname === '/probe'
    ? probe(req, res)
    : proxyApi(req, res, url.pathname + url.search);

  operation.catch(error => {
    if (res.destroyed) return;
    if (res.headersSent) {
      res.destroy();
      return;
    }
    if (error instanceof HttpError) {
      json(res, error.status, { detail: error.message });
    } else if (error.name === 'TimeoutError') {
      json(res, 504, { detail: 'Сервис не ответил вовремя.' });
    } else {
      json(res, 502, { detail: 'Сервис временно недоступен.' });
    }
  });
  return true;
}
