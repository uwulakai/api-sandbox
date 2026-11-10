import { useEffect, useState } from 'react';
import { ApiError, errorMessage, mockPath, mocksPath } from './api';
import type { Mock, Request, User } from './api';
import { Brand, Editor, ErrorNotice, Status } from './ui';
import { MockDetail } from './MockDetail';

export function Workspace({ user, call, onLogout }: { user: User; call: Request; onLogout: () => Promise<void> }) {
  const [mocks, setMocks] = useState<Mock[] | null>(null);
  const [selectedId, setSelectedId] = useState('');
  const [editing, setEditing] = useState<Mock | 'new' | null>(null);
  const [deleting, setDeleting] = useState<Mock | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState('');
  const [actionError, setActionError] = useState('');
  const [busy, setBusy] = useState(false);
  const selected = mocks?.find(mock => mock.id === selectedId) ?? mocks?.[0];
  const reload = () => setRefresh(value => value + 1);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function load() {
      try {
        const data = await call<Mock[]>(mocksPath, { signal: controller.signal });
        if (!controller.signal.aborted) {
          setMocks(data);
          setError('');
        }
      } catch (error) {
        if (!controller.signal.aborted) setError(errorMessage(error));
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(load, 4000);
      }
    }
    void load();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [call, refresh]);

  async function saveMock(fields: FormData) {
    const name = String(fields.get('name')).trim();
    if (!name) throw new ApiError(400, 'Введите название мока.');
    const description = String(fields.get('description')).trim() || null;
    const creating = editing === 'new';
    const existing = editing && editing !== 'new' ? editing : null;
    const saved = await call<Mock>(existing ? mockPath(existing.id) : mocksPath, {
      method: creating ? 'POST' : 'PATCH',
      body: { name, description, ...(creating && { desired_status: fields.get('start') ? 'running' : 'stopped' }) },
    });
    setMocks(previous => creating
      ? [saved, ...(previous ?? [])]
      : previous?.map(mock => mock.id === saved.id ? saved : mock) ?? [saved]);
    setSelectedId(saved.id);
    reload();
  }

  async function doAction(action: () => Promise<void>) {
    setBusy(true);
    setActionError('');
    try { await action(); }
    catch (error) { setActionError(errorMessage(error)); }
    finally { setBusy(false); }
  }

  function changeRuntime(mock: Mock, command: 'start' | 'stop' | 'restart') {
    return doAction(async () => {
      const updated = await call<Mock>(`${mockPath(mock.id)}/${command}`, { method: 'POST' });
      setMocks(previous => previous?.map(item => item.id === mock.id ? updated : item) ?? [updated]);
      reload();
    });
  }

  async function deleteMock(mock: Mock) {
    await call<void>(mockPath(mock.id), { method: 'DELETE' });
    setMocks(previous => previous?.filter(item => item.id !== mock.id) ?? []);
    reload();
  }

  const edited = editing && editing !== 'new' ? editing : null;
  return <div className="workspace">
    <aside className="sidebar">
      <Brand />
      <div className="sidebar-profile"><span className="avatar">{user.email.slice(0, 1).toUpperCase()}</span><div><strong>Мое пространство</strong><small>{user.email}</small></div></div>
      <div className="sidebar-heading">
        <h2>Мои моки <span>{mocks?.length ?? '—'}</span></h2>
        <button aria-label="Обновить список" title="Обновить список" onClick={reload}>↻</button>
      </div>
      <button className="primary create-mock" onClick={() => setEditing('new')}>＋ Новый мок</button>
      <nav aria-label="Мои моки" className="mock-list">
        {mocks?.map(mock => <button className="mock-item" key={mock.id}
          aria-current={selected?.id === mock.id ? 'true' : undefined}
          onClick={() => { setSelectedId(mock.id); setActionError(''); }}>
          <strong>{mock.name}</strong><Status status={mock.runtime_status} />
        </button>)}
      </nav>
      <footer className="sidebar-footer">
        <span title={user.email}>{user.email}</span>
        <button disabled={busy} onClick={() => void doAction(onLogout)}>Выйти</button>
      </footer>
    </aside>
    <main className="workspace-main">
      <div className="workspace-topbar"><span className="topbar-title">Рабочая область</span><span className="connection"><i /> Система онлайн</span></div>
      <ErrorNotice message={error || actionError} />
      {selected ? <MockDetail key={selected.id} mock={selected} call={call} busy={busy}
        onEdit={() => setEditing(selected)} onDelete={() => setDeleting(selected)}
        onRuntime={command => void changeRuntime(selected, command)} onEndpointsChanged={reload} />
        : mocks ? <section className="empty-state">
          <span className="empty-icon" aria-hidden="true">{'{ }'}</span>
          <h1>Создайте первый мок</h1>
          <p>Добавьте эндпоинт, задайте JSON-ответ и отправьте пробный запрос.</p>
          <button className="primary" onClick={() => setEditing('new')}>Новый мок</button>
        </section> : <p role="status" className="muted">Загружаем моки…</p>}
    </main>
    {editing && <Editor title={edited ? 'Настройки мока' : 'Новый мок'} onClose={() => setEditing(null)} onSave={saveMock}>
      <label>Название<input name="name" required maxLength={120} defaultValue={edited?.name} placeholder="Например, Users API"
        onFocus={event => {
          const input = event.currentTarget;
          input.setSelectionRange(input.value.length, input.value.length);
        }} /></label>
      <label>Описание<textarea name="description" rows={3} maxLength={500} defaultValue={edited?.description ?? ''} /></label>
      {!edited && <label className="check"><input name="start" type="checkbox" defaultChecked /> Запустить после создания</label>}
    </Editor>}
    {deleting && <Editor title="Удалить мок?" submitLabel="Удалить" destructive
      onClose={() => setDeleting(null)} onSave={() => deleteMock(deleting)}>
      <p>Мок «{deleting.name}» и его эндпоинты будут удалены.</p>
    </Editor>}
  </div>;
}
