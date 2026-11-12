import { useCallback, useEffect, useState } from 'react';
import { ApiError, authPath, errorMessage, request } from './api';
import type { Request, User } from './api';
import { Workspace } from './Workspace';
import { Brand, ErrorNotice } from './ui';
import { AuthPage } from './AuthPage';
import { clearVerificationMarker, consumeVerificationLink } from './registration';
import type { VerificationLink } from './registration';

const sessionKey = 'api-sandbox.session';

export function App({ initialVerification = null }: { initialVerification?: VerificationLink | null }) {
  const [verification, setVerification] = useState(initialVerification);
  const [token, setToken] = useState(() => sessionStorage.getItem(sessionKey) || '');
  const [user, setUser] = useState<User | null>(null);
  const [notice, setNotice] = useState('');
  const [verificationError, setVerificationError] = useState('');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const receiveLink = () => {
      if (new URLSearchParams(window.location.hash.slice(1)).has('verify-email')) {
        setVerification(consumeVerificationLink());
      }
    };
    window.addEventListener('hashchange', receiveLink);
    return () => window.removeEventListener('hashchange', receiveLink);
  }, []);

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
    if (!token || verification) return;
    const controller = new AbortController();
    call<User>(`${authPath}/me`, { signal: controller.signal })
      .then(data => { if (!controller.signal.aborted) setUser(data); })
      .catch(error => { if (!controller.signal.aborted) setVerificationError(errorMessage(error)); });
    return () => controller.abort();
  }, [token, call, attempt, verification]);

  if (!token || verification) {
    return <AuthPage notice={notice} verification={verification} onDiscardVerification={() => {
      clearVerificationMarker();
      setVerification(null);
      endSession();
    }} onLogin={value => {
      clearVerificationMarker();
      setVerification(null);
      sessionStorage.setItem(sessionKey, value);
      setUser(null);
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
