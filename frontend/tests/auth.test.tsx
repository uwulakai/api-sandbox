import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { App } from '../src/App';
import { consumeVerificationLink } from '../src/registration';

const reply = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });

function api(handler: (path: string, body: Record<string, string>) => Response) {
  const fetcher = vi.fn(async (path: string, options?: RequestInit) => {
    if (path === '/api/v1/auth/me') return reply({ id: 1, email: 'user@example.com' });
    if (path === '/api/v1/mocks') return reply([]);
    return handler(path, JSON.parse(String(options?.body ?? '{}')));
  });
  vi.stubGlobal('fetch', fetcher);
  return fetcher;
}

async function openRegistration() {
  const user = userEvent.setup();
  render(<App />);
  await user.click(screen.getByRole('button', { name: 'Создать аккаунт' }));
  await user.type(screen.getByLabelText('Электронная почта'), 'user@example.com');
  return user;
}

function openVerification(token = 'email-token') {
  window.history.replaceState(null, '', `/#verify-email=${token}`);
  return render(<App initialVerification={consumeVerificationLink()} />);
}

async function fillPassword(user: ReturnType<typeof userEvent.setup>, password = 'password123', confirmation = password) {
  await user.type(screen.getByLabelText('Новый пароль'), password);
  await user.type(screen.getByLabelText('Повторите пароль'), confirmation);
  await user.click(screen.getByRole('button', { name: 'Завершить регистрацию' }));
}

describe('registration screens', () => {
  it('sends only email, displays pending state and lets the user change address', async () => {
    const fetcher = api(() => reply({ status: 'verification_required', resend_after_seconds: 23 }, 202));
    const user = await openRegistration();
    expect(screen.queryByLabelText('Пароль')).toBeNull();
    await user.click(screen.getByRole('button', { name: 'Получить ссылку' }));
    expect(await screen.findByRole('heading', { name: 'Проверьте почту' })).toBeTruthy();
    expect(screen.getByText('user@example.com')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Отправить повторно через 23 с' })).toHaveProperty('disabled', true);
    expect(JSON.parse(fetcher.mock.calls[0][1]!.body as string)).toEqual({ email: 'user@example.com' });
    expect(sessionStorage.length).toBe(0);
    await user.click(screen.getByRole('button', { name: 'Изменить адрес' }));
    expect(screen.getByLabelText('Электронная почта')).toHaveProperty('value', 'user@example.com');
  });

  it('counts down from the response and restarts the timer after a successful resend', async () => {
    vi.useFakeTimers();
    const fetcher = api(() => reply({ status: 'verification_required', resend_after_seconds: 3 }, 202));
    render(<App />);
    fireEvent.click(screen.getByRole('button', { name: 'Создать аккаунт' }));
    fireEvent.change(screen.getByLabelText('Электронная почта'), { target: { value: 'user@example.com' } });
    await act(async () => { fireEvent.submit(screen.getByRole('button', { name: 'Получить ссылку' }).closest('form')!); });
    expect(screen.getByRole('button', { name: 'Отправить повторно через 3 с' })).toHaveProperty('disabled', true);
    await act(async () => { vi.advanceTimersByTime(3000); });
    expect(screen.getByRole('button', { name: 'Отправить повторно' })).toHaveProperty('disabled', false);
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: 'Отправить повторно' })); });
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(screen.getByRole('button', { name: 'Отправить повторно через 3 с' })).toHaveProperty('disabled', true);
  });

  it('uses retry_after_seconds on 429', async () => {
    api(() => reply({ detail: { code: 'EMAIL_VERIFICATION_COOLDOWN', retry_after_seconds: 19 } }, 429));
    const user = await openRegistration();
    await user.click(screen.getByRole('button', { name: 'Получить ссылку' }));
    expect(await screen.findByRole('button', { name: 'Отправить повторно через 19 с' })).toHaveProperty('disabled', true);
  });

  it('offers login for an existing email', async () => {
    api(() => reply({ detail: 'EMAIL_ALREADY_REGISTERED' }, 409));
    const user = await openRegistration();
    await user.click(screen.getByRole('button', { name: 'Получить ссылку' }));
    await user.click(await screen.findByRole('button', { name: 'Войти в аккаунт' }));
    expect(screen.getByRole('heading', { name: 'Вход в аккаунт' })).toBeTruthy();
    expect(screen.getByLabelText('Пароль')).toBeTruthy();
  });

  it('allows retry immediately after mail delivery failure', async () => {
    api(() => reply({ detail: 'EMAIL_DELIVERY_UNAVAILABLE' }, 503));
    const user = await openRegistration();
    await user.click(screen.getByRole('button', { name: 'Получить ссылку' }));
    expect(await screen.findByRole('alert')).toHaveProperty('textContent', 'Письмо сейчас не удалось отправить. Попробуйте еще раз.');
    expect(screen.getByRole('button', { name: 'Получить ссылку' })).toHaveProperty('disabled', false);
  });

  it('highlights the email field on 422', async () => {
    api(() => reply({ detail: [{ loc: ['body', 'email'], msg: 'invalid email', type: 'value_error' }] }, 422));
    const user = await openRegistration();
    await user.click(screen.getByRole('button', { name: 'Получить ссылку' }));
    await waitFor(() => expect(screen.getByLabelText('Электронная почта').getAttribute('aria-invalid')).toBe('true'));
  });
});

describe('password selection', () => {
  it('never confirms by opening a link; confirms on submit and opens the workspace', async () => {
    const fetcher = api(() => reply({ token: 'session-token' }));
    openVerification();
    expect(window.location.hash).toBe('');
    expect(fetcher).not.toHaveBeenCalled();
    expect(sessionStorage.length).toBe(0);
    const user = userEvent.setup();
    await fillPassword(user);
    expect(await screen.findByRole('heading', { name: 'Создайте первый мок' })).toBeTruthy();
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/auth/verify-email');
    expect(JSON.parse(fetcher.mock.calls[0][1]!.body as string)).toEqual({ token: 'email-token', password: 'password123' });
    expect(sessionStorage.getItem('api-sandbox.session')).toBe('session-token');
    expect(JSON.stringify(sessionStorage)).not.toContain('password123');
    expect(JSON.stringify(sessionStorage)).not.toContain('email-token');
    expect(localStorage.length).toBe(0);
    expect(JSON.stringify(window.history.state)).not.toContain('email-token');
  });

  it('blocks mismatched passwords and UTF-8 byte overflow without an API request', async () => {
    const fetcher = api(() => reply({ token: 'session-token' }));
    openVerification();
    const user = userEvent.setup();
    await fillPassword(user, 'я'.repeat(37), 'different');
    expect(screen.getByText('Пароли не совпадают.')).toBeTruthy();
    expect(screen.getByText(/Пароль превышает 72 байта/)).toBeTruthy();
    expect(fetcher).not.toHaveBeenCalled();
  });

  it.each([
    [400, { detail: 'EMAIL_VERIFICATION_INVALID' }],
    [422, { detail: [{ loc: ['body', 'token'], msg: 'invalid', type: 'string_too_short' }] }],
  ])('offers a new email and login for invalid links (%s)', async (status, body) => {
    api(() => reply(body, status as number));
    openVerification();
    await fillPassword(userEvent.setup());
    expect(await screen.findByRole('button', { name: 'Запросить новое письмо' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Уже есть аккаунт? Войти' })).toBeTruthy();
    expect(screen.queryByLabelText('Новый пароль')).toBeNull();
  });

  it('recovers after reload without storing the email token', () => {
    const view = openVerification();
    view.unmount();
    render(<App initialVerification={consumeVerificationLink()} />);
    expect(screen.getByRole('heading', { name: 'Откройте ссылку из письма' })).toBeTruthy();
    expect(screen.queryByLabelText('Новый пароль')).toBeNull();
  });

  it('highlights a password validation error from the backend', async () => {
    api(() => reply({ detail: [{ loc: ['body', 'password'], msg: 'invalid', type: 'value_error' }] }, 422));
    openVerification();
    await fillPassword(userEvent.setup());
    await waitFor(() => expect(screen.getByLabelText('Новый пароль').getAttribute('aria-invalid')).toBe('true'));
  });

  it('keeps the existing email/password login contract', async () => {
    const fetcher = api(() => reply({ token: 'old-user-session' }));
    const user = userEvent.setup();
    render(<App />);
    await user.type(screen.getByLabelText('Электронная почта'), 'user@example.com');
    await user.type(screen.getByLabelText('Пароль'), 'existing-password');
    await user.click(screen.getByRole('button', { name: 'Войти' }));
    expect(await screen.findByRole('heading', { name: 'Создайте первый мок' })).toBeTruthy();
    expect(fetcher.mock.calls[0][0]).toBe('/api/v1/auth/login');
    expect(JSON.parse(fetcher.mock.calls[0][1]!.body as string)).toEqual({ email: 'user@example.com', password: 'existing-password' });
  });
});
