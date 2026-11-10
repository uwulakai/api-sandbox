import { useState } from 'react';
import type { FormEvent } from 'react';
import { errorMessage, methods } from './api';
import type { Method, Mock, ProbeResult, Request } from './api';
import { ErrorNotice } from './ui';

export type ProbeTarget = { method: Method; path: string };

function formatBody(body: string) {
  if (!body) return 'Тело ответа пустое';
  try { return JSON.stringify(JSON.parse(body), null, 2); }
  catch { return body; }
}

export function Probe({ mock, target, call }: { mock: Mock; target: ProbeTarget; call: Request }) {
  const [method, setMethod] = useState(target.method);
  const [path, setPath] = useState(target.path);
  const [result, setResult] = useState<ProbeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const canSendBody = method !== 'GET' && method !== 'HEAD';

  async function send(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    setBusy(true);
    setResult(null);
    setError('');
    try {
      const json = String(fields.get('body') ?? '').trim();
      const data = await call<ProbeResult>('/probe', {
        method: 'POST',
        body: { id: mock.id, method, path: path.trim(), ...(json && { body: JSON.parse(json) }) },
      });
      setResult(data);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return <section className="panel probe-panel">
    <div className="panel-heading">
      <div><h2>Проверка запроса</h2><p>Запрос пройдет через внутренний mock gateway.</p></div>
    </div>
    <form onSubmit={send}>
      <div className="request-row">
        <label>Метод<select value={method} onChange={event => setMethod(event.target.value as Method)} disabled={busy}>
          {methods.map(item => <option key={item}>{item}</option>)}
        </select></label>
        <label>Путь и параметры<input value={path} onChange={event => setPath(event.target.value)} required
          className="mono" maxLength={4096} placeholder="/users?limit=10" disabled={busy} /></label>
        <button className="primary" disabled={busy}>{busy ? 'Ждем ответ…' : 'Отправить'}</button>
      </div>
      {canSendBody && <label>Тело запроса (JSON, необязательно)
        <textarea name="body" className="mono" rows={3} placeholder="{}" disabled={busy} />
      </label>}
    </form>
    <ErrorNotice message={error} />
    <div className="probe-output" aria-live="polite">
      {result ? <>
        <div className="result-meta">
          <span className={`result-status ${result.status >= 400 ? 'result-error' : ''}`}>HTTP {result.status}</span>
          <span>{result.elapsedMs} мс</span>
        </div>
        <pre aria-label="Тело ответа">{formatBody(result.body)}</pre>
        <details><summary>Заголовки ответа</summary>
          <pre>{Object.entries(result.headers).map(([name, value]) => `${name}: ${value}`).join('\n')}</pre>
        </details>
      </> : <p className="muted">{busy ? 'Запрос отправлен.' : 'Здесь появится ответ мока.'}</p>}
    </div>
  </section>;
}
