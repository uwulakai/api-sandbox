import { useCallback, useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError, authPath, errorMessage, request } from './api';
import type { Request, User } from './api';
import { Workspace } from './Workspace';
import { Brand, ErrorNotice } from './ui';

const sessionKey = 'api-sandbox.session';

function AuthPage({ onLogin, notice }: { onLogin: (token: string) => void; notice: string }) {
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError('');
    try {
      const data = await request<{ token: string }>(`${authPath}/${register ? 'register' : 'login'}`, {
        method: 'POST',
        body: { email: String(form.get('email')).trim(), password: form.get('password') },
      });
      onLogin(data.token);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-shell">
      <section className="auth-intro">
        <Brand />
        <div>
          <p className="eyebrow">Рабочая область</p>
          <h1>Настройте ответ.<br />Проверьте запрос.</h1>
          <p>Создавайте моки, задавайте маршруты и проверяйте ответы прямо в браузере.</p>
        </div>
        <div className="auth-example" aria-hidden="true">
          <div><b className="method">GET</b> <code>/users</code> <span>200 OK</span></div>
          <pre>{'{\n  "users": []\n}'}</pre>
        </div>
      </section>
      <section className="auth-form">
        <form onSubmit={submit}>
          <p className="eyebrow">API Sandbox</p>
          <h2>{register ? 'Создать аккаунт' : 'Вход в аккаунт'}</h2>
          <p className="muted">{register ? 'После регистрации откроется список моков.' : 'Войдите, чтобы открыть свои моки.'}</p>
          <ErrorNotice message={error || notice} />
          <label>Электронная почта<input name="email" type="email" autoComplete="email" required placeholder="name@example.com" /></label>
          <label>Пароль
            <input name="password" type="password" required minLength={register ? 8 : undefined}
              maxLength={register ? 128 : undefined} autoComplete={register ? 'new-password' : 'current-password'} />
          </label>
          {register && <small className="muted">Не менее 8 символов</small>}
          <button className="primary" disabled={busy}>{busy ? 'Подождите…' : register ? 'Зарегистрироваться' : 'Войти'}</button>
          <button type="button" className="link-button" disabled={busy} onClick={() => {
            setRegister(!register);
            setError('');
          }}>{register ? 'Уже есть аккаунт? Войти' : 'Создать аккаунт'}</button>
        </form>
      </section>
    </main>
  );
}

export function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem(sessionKey) || '');
  const [user, setUser] = useState<User | null>(null);
  const [notice, setNotice] = useState('');
  const [verificationError, setVerificationError] = useState('');
  const [attempt, setAttempt] = useState(0);

  const endSession = useCallback((message = '') => {
    sessionStorage.removeItem(sessionKey);
    setToken('');
    setUser(null);
    setNotice(message);
  }, []);

  const call: Request = useCallback(async <T,>(path: string, options?: Parameters<Request>[1]) => {
    try {
      return await request<T>(path, options, token);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401 && sessionStorage.getItem(sessionKey) === token) {
        endSession('Сессия истекла. Войдите снова.');
      }
      throw error;
    }
  }, [token, endSession]);

  useEffect(() => {
    if (!token) return;
    const controller = new AbortController();
    call<User>(`${authPath}/me`, { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setUser(data); })
      .catch(error => { if (!controller.signal.aborted) setVerificationError(errorMessage(error)); });
    return () => controller.abort();
  }, [token, call, attempt]);

  if (!token) {
    return <AuthPage notice={notice} onLogin={value => {
      sessionStorage.setItem(sessionKey, value);
      setVerificationError('');
      setNotice('');
      setToken(value);
    }} />;
  }
  if (!user) {
    return <main className="session-loading">
      <Brand />
      {verificationError ? <>
        <ErrorNotice message={verificationError} />
        <div className="actions">
          <button onClick={() => { setVerificationError(''); setAttempt(n => n + 1); }}>Повторить</button>
          <button onClick={() => endSession()}>К форме входа</button>
        </div>
      </> : <p role="status">Проверяем сессию…</p>}
    </main>;
  }
  return <Workspace key={token} user={user} call={call} onLogout={async () => {
    await call(`${authPath}/logout`, { method: 'POST' });
    endSession();
  }} />;
}
