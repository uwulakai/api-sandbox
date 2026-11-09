import { useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { errorMessage } from './api';
import type { RuntimeStatus } from './api';

const statusLabels: Record<RuntimeStatus, string> = {
  running: 'Работает',
  stopped: 'Остановлен',
  pending: 'В очереди',
  starting: 'Запускается',
  stopping: 'Останавливается',
  error: 'Ошибка',
};

export function Status({ status }: { status: RuntimeStatus }) {
  return <span className={`status status-${status}`}><span aria-hidden="true" />{statusLabels[status]}</span>;
}

export function Brand() {
  return (
    <div className="brand">
      <span className="brand-icon" aria-hidden="true">{'{ }'}</span>
      <span>API Sandbox<small>Конструктор API-заглушек</small></span>
    </div>
  );
}

export function ErrorNotice({ message }: { message: string }) {
  return message ? <p className="error" role="alert">{message}</p> : null;
}

export function Editor({ title, onClose, onSave, children, submitLabel = 'Сохранить', destructive = false }: {
  title: string;
  onClose: () => void;
  onSave: (fields: FormData) => Promise<void>;
  children: ReactNode;
  submitLabel?: string;
  destructive?: boolean;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    dialog.current?.showModal();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fields = new FormData(event.currentTarget);
    setBusy(true);
    setError('');
    try {
      await onSave(fields);
      onClose();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return <dialog ref={dialog} aria-labelledby="editor-title" onCancel={event => {
    event.preventDefault();
    if (!busy) onClose();
  }}>
    <form onSubmit={submit}>
      <h2 id="editor-title">{title}</h2>
      <ErrorNotice message={error} />
      <fieldset disabled={busy}>{children}</fieldset>
      <div className="dialog-actions">
        <button type="button" disabled={busy} onClick={onClose}>Отмена</button>
        <button className={destructive ? 'danger' : 'primary'} disabled={busy}>{busy ? 'Подождите…' : submitLabel}</button>
      </div>
    </form>
  </dialog>;
}
