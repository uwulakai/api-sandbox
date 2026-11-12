import { useEffect, useRef, useState } from 'react';
import type { FormEvent } from 'react';
import { ApiError, authPath, errorMessage, request } from './api';
import { authFieldErrors, validateNewPassword } from './registration';
import type { VerificationLink } from './registration';
import { Brand, ErrorNotice } from './ui';

type Mode = 'login' | 'register' | 'pending' | 'verify' | 'recovery';
interface PendingResponse { status: 'verification_required'; resend_after_seconds: number }

export function AuthPage({ onLogin, notice, verification, onDiscardVerification }: {
  onLogin: (token: string) => void;
  notice: string;
  verification: VerificationLink | null;
  onDiscardVerification: () => void;
}) {
  const [mode, setMode] = useState<Mode>(verification ? verification.token ? 'verify' : 'recovery' : 'login');
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [fields, setFields] = useState<Record<string, string>>({});
  const [canLogin, setCanLogin] = useState(false);
  const [sent, setSent] = useState(false);
  const [deadline, setDeadline] = useState(0);
  const [remaining, setRemaining] = useState(0);
  const [cooldownEmail, setCooldownEmail] = useState('');
  const locked = useRef(false);

  useEffect(() => {
    if (!verification) return;
    setMode(verification.token ? 'verify' : 'recovery');
    setError('');
    setFields({});
  }, [verification]);

  useEffect(() => {
    const tick = () => setRemaining(Math.max(0, Math.ceil((deadline - Date.now()) / 1000)));
    tick();
    if (!deadline) return;
    const timer = window.setInterval(tick, 250);
    return () => window.clearInterval(timer);
  }, [deadline]);

  function startCooldown(seconds: number) {
    const duration = Number.isFinite(seconds) ? Math.max(0, seconds) : 0;
    setDeadline(Date.now() + duration * 1000);
    setRemaining(Math.ceil(duration));
    setCooldownEmail(email.trim().toLowerCase());
  }

  function navigate(next: Mode) {
    onDiscardVerification();
    setMode(next);
    setError('');
    setFields({});
    setCanLogin(false);
  }

  function showError(caught: unknown, operation: 'register' | 'verify' | 'login') {
    if (!(caught instanceof ApiError)) { setError(errorMessage(caught)); return; }
    if (caught.code === 'EMAIL_ALREADY_REGISTERED') {
      setError('Этот адрес уже зарегистрирован. Войдите в аккаунт.');
      setCanLogin(true);
    } else if (caught.status === 429 && operation === 'register') {
      startCooldown(caught.retryAfterSeconds ?? 60);
      setMode('pending');
      setError('Письмо уже запрошено. Повторная отправка будет доступна после таймера.');
    } else if (caught.code === 'EMAIL_DELIVERY_UNAVAILABLE') {
      setError('Письмо сейчас не удалось отправить. Попробуйте еще раз.');
    } else if (caught.code === 'EMAIL_VERIFICATION_INVALID') {
      onDiscardVerification();
      setMode('recovery');
      setError('Ссылка недействительна, истекла или уже использована. Запросите новое письмо или войдите.');
    } else if (caught.status === 422) {
      const validation = authFieldErrors(caught);
      setFields(validation);
      if (validation.email && operation === 'register') setMode('register');
      if (validation.token) {
        onDiscardVerification();
        setMode('recovery');
        setError(validation.token);
      } else if (!Object.keys(validation).length) setError('Проверьте введенные данные и повторите запрос.');
    } else if (operation === 'login' && caught.status === 401) {
      setError('Неверная почта или пароль. Если вы только регистрируетесь, сначала откройте письмо и задайте пароль.');
    } else setError(errorMessage(caught));
  }

  const coolingDown = remaining > 0 && email.trim().toLowerCase() === cooldownEmail;

  async function sendEmail() {
    if (locked.current || coolingDown) return;
    locked.current = true;
    setBusy(true);
    setError('');
    setFields({});
    setCanLogin(false);
    try {
      const data = await request<PendingResponse>(`${authPath}/register`, {
        method: 'POST', body: { email: email.trim() },
      });
      setEmail(email.trim());
      startCooldown(data.resend_after_seconds);
      setSent(true);
      setMode('pending');
    } catch (caught) { showError(caught, 'register'); }
    finally { locked.current = false; setBusy(false); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (mode === 'register') { await sendEmail(); return; }
    if (locked.current) return;
    const form = new FormData(event.currentTarget);
    const password = String(form.get('password') ?? '');
    setError('');
    setFields({});
    if (mode === 'verify') {
      const validation = validateNewPassword(password, String(form.get('confirmation') ?? ''));
      if (Object.keys(validation).length) { setFields(validation); return; }
      if (!verification?.token) { setMode('recovery'); return; }
    }
    locked.current = true;
    setBusy(true);
    try {
      const data = await request<{ token: string }>(`${authPath}/${mode === 'verify' ? 'verify-email' : 'login'}`, {
        method: 'POST',
        body: mode === 'verify' ? { token: verification?.token, password } : { email: email.trim(), password },
      });
      onLogin(data.token);
    } catch (caught) { showError(caught, mode === 'verify' ? 'verify' : 'login'); }
    finally { locked.current = false; setBusy(false); }
  }

  const titles: Record<Mode, string> = {
    login: 'Вход в аккаунт', register: 'Создать аккаунт', pending: 'Проверьте почту',
    verify: 'Придумайте пароль', recovery: 'Откройте ссылку из письма',
  };

  return <main className="auth-shell">
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
    <section className="auth-form" aria-label={titles[mode]}>
      <div className="auth-content">
        <p className="eyebrow">API Sandbox</p>
        {(mode === 'pending' || mode === 'recovery') && <span className="auth-step-icon" aria-hidden="true">↗</span>}
        <h2>{titles[mode]}</h2>
        <ErrorNotice message={error || notice} />
        {mode === 'pending' ? <>
          <p className="muted">{sent ? 'Отправили ссылку на' : 'Ссылка для регистрации запрошена для'} <strong className="auth-email">{email}</strong></p>
          <p className="muted">Откройте письмо и задайте пароль. Если письма нет во входящих, проверьте папку «Спам».</p>
          <p className="auth-hint">После повторной отправки используйте ссылку из последнего письма.</p>
          <button className="primary" disabled={busy || coolingDown} onClick={() => void sendEmail()}>
            {busy ? 'Отправляем…' : coolingDown ? `Отправить повторно через ${remaining} с` : 'Отправить повторно'}
          </button>
          <span className="sr-only" role="status">{coolingDown ? 'Повторная отправка пока недоступна.' : 'Можно отправить письмо повторно.'}</span>
          <button className="link-button" disabled={busy} onClick={() => navigate('register')}>Изменить адрес</button>
        </> : mode === 'recovery' ? <>
          <p className="muted">Чтобы выбрать пароль, снова откройте ссылку из письма. После обновления страницы нужно перейти по ней еще раз.</p>
          <button className="primary" onClick={() => navigate('register')}>Запросить новое письмо</button>
        </> : <form key={mode} onSubmit={submit}>
          <p className="muted">{mode === 'register' ? 'Отправим ссылку на почту. Пароль вы зададите на следующем шаге.'
            : mode === 'verify' ? 'Регистрация завершится только после сохранения пароля.' : 'Войдите, чтобы открыть свои моки.'}</p>
          {mode !== 'verify' && <label><span id="email-label">Электронная почта</span>
            <input name="email" type="email" autoComplete="email" required placeholder="name@example.com" value={email}
              aria-labelledby="email-label"
              disabled={busy} aria-invalid={!!fields.email} aria-describedby={fields.email ? 'email-error' : undefined}
              onChange={event => { setEmail(event.target.value); setFields({}); setCanLogin(false); }} />
            {fields.email && <small id="email-error" className="field-error">{fields.email}</small>}
          </label>}
          {mode !== 'register' && <label><span id="password-label">{mode === 'verify' ? 'Новый пароль' : 'Пароль'}</span>
            <input name="password" type="password" required autoComplete={mode === 'verify' ? 'new-password' : 'current-password'}
              aria-labelledby="password-label"
              disabled={busy} aria-invalid={!!fields.password} aria-describedby={fields.password ? 'password-error' : mode === 'verify' ? 'password-hint' : undefined}
              onChange={() => setFields(previous => ({ ...previous, password: '' }))} />
            {fields.password && <small id="password-error" className="field-error">{fields.password}</small>}
          </label>}
          {mode === 'verify' && <>
            <p id="password-hint" className="auth-hint">От 8 до 72 символов, не более 72 байт UTF-8.</p>
            <label><span id="confirmation-label">Повторите пароль</span>
              <input name="confirmation" type="password" required autoComplete="new-password" disabled={busy}
                aria-labelledby="confirmation-label"
                aria-invalid={!!fields.confirmation} aria-describedby={fields.confirmation ? 'confirmation-error' : undefined}
                onChange={() => setFields(previous => ({ ...previous, confirmation: '' }))} />
              {fields.confirmation && <small id="confirmation-error" className="field-error">{fields.confirmation}</small>}
            </label>
          </>}
          <button className="primary" disabled={busy || (mode === 'register' && coolingDown)}>
            {busy ? 'Подождите…' : mode === 'verify' ? 'Завершить регистрацию'
              : mode === 'register' ? coolingDown ? `Отправить через ${remaining} с` : 'Получить ссылку' : 'Войти'}
          </button>
        </form>}
        {canLogin && mode !== 'login' && <button className="primary" disabled={busy} onClick={() => navigate('login')}>Войти в аккаунт</button>}
        {mode === 'verify' && <button className="link-button" disabled={busy} onClick={() => navigate('register')}>Запросить новое письмо</button>}
        <button className="link-button" disabled={busy} onClick={() => navigate(mode === 'login' ? 'register' : 'login')}>
          {mode === 'login' ? 'Создать аккаунт' : 'Уже есть аккаунт? Войти'}
        </button>
      </div>
    </section>
  </main>;
}
