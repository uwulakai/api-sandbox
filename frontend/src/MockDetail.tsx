import { useEffect, useRef, useState } from 'react';
import { ApiError, endpointsPath, errorMessage, methods } from './api';
import type { Endpoint, EndpointFields, Method, Mock, Request } from './api';
import { Editor, ErrorNotice, Status } from './ui';
import { Probe } from './Probe';
import type { ProbeTarget } from './Probe';

function endpointFields(form: FormData): EndpointFields {
  const response_headers: unknown = JSON.parse(String(form.get('response_headers')));
  if (!response_headers || typeof response_headers !== 'object' || Array.isArray(response_headers)
      || Object.values(response_headers).some(value => typeof value !== 'string')) {
    throw new ApiError(400, 'Заголовки должны быть JSON-объектом со строковыми значениями.');
  }
  const path = String(form.get('path')).trim();
  if (!path) throw new ApiError(400, 'Укажите путь эндпоинта.');
  return {
    method: String(form.get('method')) as Method,
    path,
    status_code: Number(form.get('status_code')),
    delay_ms: Number(form.get('delay_ms')),
    enabled: form.has('enabled'),
    response_headers: response_headers as Record<string, string>,
    response_body: JSON.parse(String(form.get('response_body'))),
  };
}

export function MockDetail({ mock, call, busy, onEdit, onDelete, onRuntime, onEndpointsChanged }: {
  mock: Mock;
  call: Request;
  busy: boolean;
  onEdit: () => void;
  onDelete: () => void;
  onRuntime: (command: 'start' | 'stop' | 'restart') => void;
  onEndpointsChanged: () => void;
}) {
  const [endpoints, setEndpoints] = useState<Endpoint[] | null>(null);
  const [editing, setEditing] = useState<Endpoint | 'new' | null>(null);
  const [target, setTarget] = useState<ProbeTarget | null>(null);
  const [error, setError] = useState('');
  const [refresh, setRefresh] = useState(0);
  const [deleting, setDeleting] = useState<Endpoint | null>(null);
  const [copyNote, setCopyNote] = useState('');
  const urlInput = useRef<HTMLInputElement>(null);
  const path = endpointsPath(mock.id);
  const edited = editing && editing !== 'new' ? editing : null;

  useEffect(() => {
    const controller = new AbortController();
    call<Endpoint[]>(path, { signal: controller.signal })
      .then(data => {
        if (!controller.signal.aborted) {
          setEndpoints(data);
          setError('');
        }
      })
      .catch(error => { if (!controller.signal.aborted) setError(errorMessage(error)); });
    return () => controller.abort();
  }, [call, path, refresh]);

  async function saveEndpoint(fields: FormData) {
    const saved = await call<Endpoint>(edited ? `${path}/${edited.id}` : path, {
      method: edited ? 'PATCH' : 'POST',
      body: endpointFields(fields),
    });
    setEndpoints(previous => edited
      ? previous?.map(item => item.id === saved.id ? saved : item) ?? [saved]
      : [...(previous ?? []), saved]);
    onEndpointsChanged();
  }

  async function deleteEndpoint(endpoint: Endpoint) {
    await call<void>(`${path}/${endpoint.id}`, { method: 'DELETE' });
    setEndpoints(previous => previous?.filter(item => item.id !== endpoint.id) ?? []);
    onEndpointsChanged();
  }

  async function copyUrl() {
    try {
      await navigator.clipboard.writeText(mock.public_url);
      setCopyNote('Скопировано');
    } catch {
      urlInput.current?.focus();
      urlInput.current?.select();
      setCopyNote('URL выделен');
    }
  }

  const transitional = ['pending', 'starting', 'stopping'].includes(mock.runtime_status);
  return <>
    <header className="mock-heading">
      <div>
        <p className="eyebrow">Мои моки / Обзор</p>
        <h1>{mock.name}</h1>
        {mock.description && <p className="mock-description">{mock.description}</p>}
      </div>
      <div className="actions">
        <button disabled={busy} onClick={onEdit}>Настройки</button>
        <button className="danger" disabled={busy} onClick={onDelete}>Удалить мок</button>
      </div>
    </header>
    <section className="panel runtime-panel" aria-label="Состояние мока">
      <div className="runtime-row">
        <div className="runtime-state">
          <Status status={mock.runtime_status} />
          <span className="muted">Конфигурация v{mock.config_version}</span>
        </div>
        <div className="actions">
          <button disabled={busy || transitional} onClick={() => onRuntime(mock.desired_status === 'running' ? 'stop' : 'start')}>
            {mock.desired_status === 'running' ? 'Остановить' : 'Запустить'}
          </button>
          {mock.desired_status === 'running' && <button disabled={busy || transitional} onClick={() => onRuntime('restart')}>Перезапустить</button>}
        </div>
      </div>
      <ErrorNotice message={mock.last_error ?? ''} />
      <div className="url-field">
        <label htmlFor="mock-url">Публичный URL</label>
        <div className="url-row">
          <input id="mock-url" ref={urlInput} value={mock.public_url} readOnly className="mono" />
          <button type="button" onClick={() => void copyUrl()}>Копировать</button>
        </div>
      </div>
      <span className="copy-note" role="status">{copyNote}</span>
    </section>
    <nav className="section-switch" aria-label="Разделы мока">
      <button aria-pressed={!target} onClick={() => setTarget(null)}>Эндпоинты <span>{endpoints?.length ?? '—'}</span></button>
      <button aria-pressed={!!target} onClick={() => setTarget(previous => previous ?? { method: 'GET', path: '/' })}>Проверка</button>
    </nav>
    {target ? <Probe key={`${target.method} ${target.path}`} mock={mock} target={target} call={call} /> :
      <section className="panel endpoints-panel">
        <div className="panel-heading">
          <div><h2>Эндпоинты</h2><p>Задайте метод, путь и ответ для каждого маршрута.</p></div>
          <button className="primary" disabled={endpoints === null} onClick={() => setEditing('new')}>＋ Эндпоинт</button>
        </div>
        <ErrorNotice message={error} />
        {error && <button onClick={() => setRefresh(value => value + 1)}>Обновить эндпоинты</button>}
        {endpoints?.length ? <div className="endpoint-list">
          {endpoints.map(endpoint => <article key={endpoint.id} className="endpoint-row">
            <div className="endpoint-route">
              <span className={`method method-${endpoint.method.toLowerCase()}`}>{endpoint.method}</span>
              <code>{endpoint.path}</code>
            </div>
            <div className="endpoint-meta">
              <span>HTTP {endpoint.status_code}</span>
              {endpoint.delay_ms > 0 && <span>{endpoint.delay_ms} мс</span>}
              {!endpoint.enabled && <span>Выключен</span>}
            </div>
            <div className="actions endpoint-actions">
              <button onClick={() => setTarget({ method: endpoint.method, path: endpoint.path })}>Проверить</button>
              <button onClick={() => setEditing(endpoint)}>Изменить</button>
              <button className="danger" onClick={() => setDeleting(endpoint)}>Удалить</button>
            </div>
          </article>)}
        </div> : <p className="endpoint-empty muted">{endpoints ? 'У этого мока пока нет эндпоинтов.' : 'Загружаем эндпоинты…'}</p>}
      </section>}
    {editing && <Editor title={edited ? 'Изменить эндпоинт' : 'Новый эндпоинт'}
      onClose={() => setEditing(null)} onSave={saveEndpoint}>
      <div className="fields-row">
        <label>Метод<select name="method" defaultValue={edited?.method ?? 'GET'}>
          {methods.map(method => <option key={method}>{method}</option>)}
        </select></label>
        <label>Путь<input name="path" className="mono" defaultValue={edited?.path} placeholder="/users" required maxLength={2048} /></label>
      </div>
      <div className="fields-row equal">
        <label>Код ответа<input name="status_code" type="number" min={100} max={599} defaultValue={edited?.status_code ?? 200} required /></label>
        <label>Задержка (мс)<input name="delay_ms" type="number" min={0} max={60000} defaultValue={edited?.delay_ms ?? 0} required /></label>
      </div>
      <label>Тело ответа (JSON)<textarea name="response_body" className="mono" rows={5}
        defaultValue={edited ? JSON.stringify(edited.response_body, null, 2) : '{\n  "ok": true\n}'} required /></label>
      <label>Заголовки ответа (JSON)<textarea name="response_headers" className="mono" rows={3}
        defaultValue={JSON.stringify(edited?.response_headers ?? {}, null, 2)} required /></label>
      <label className="check"><input name="enabled" type="checkbox" defaultChecked={edited?.enabled ?? true} /> Эндпоинт включен</label>
    </Editor>}
    {deleting && <Editor title="Удалить эндпоинт?" submitLabel="Удалить" destructive
      onClose={() => setDeleting(null)} onSave={() => deleteEndpoint(deleting)}>
      <p>Маршрут <code>{deleting.method} {deleting.path}</code> будет удален.</p>
    </Editor>}
  </>;
}
