import { describe, expect, it, vi } from 'vitest';
import { ApiError, request } from '../src/api';
import { authFieldErrors, clearVerificationMarker, consumeVerificationLink, validateNewPassword } from '../src/registration';

describe('verification link privacy and recovery', () => {
  it('consumes the fragment without storing the token and recovers after reload', () => {
    window.history.replaceState({ existing: 'state' }, '', '/?from=mail#verify-email=secret-email-token');
    expect(consumeVerificationLink()).toEqual({ token: 'secret-email-token', interrupted: false });
    expect(window.location.hash).toBe('');
    expect(window.location.search).toBe('?from=mail');
    expect(window.history.state.existing).toBe('state');
    expect(JSON.stringify(window.history.state)).not.toContain('secret-email-token');
    expect(sessionStorage.length).toBe(0);
    expect(localStorage.length).toBe(0);
    expect(consumeVerificationLink()).toEqual({ token: null, interrupted: true });
    clearVerificationMarker();
    expect(consumeVerificationLink()).toBeNull();
  });

  it('handles an empty link as recovery, not confirmation', () => {
    window.history.replaceState(null, '', '/#verify-email=');
    expect(consumeVerificationLink()).toEqual({ token: null, interrupted: true });
    expect(window.location.hash).toBe('');
  });
});

describe('password rules', () => {
  it('enforces characters, UTF-8 bytes and confirmation separately', () => {
    expect(validateNewPassword('a'.repeat(72), 'a'.repeat(72))).toEqual({});
    expect(validateNewPassword('я'.repeat(36), 'я'.repeat(36))).toEqual({});
    expect(validateNewPassword('я'.repeat(37), 'я'.repeat(37)).password).toContain('байта');
    expect(validateNewPassword('🙂'.repeat(19), '🙂'.repeat(19)).password).toContain('байта');
    expect(validateNewPassword('short', 'short').password).toContain('символов');
    expect(validateNewPassword('a'.repeat(73), 'a'.repeat(73)).password).toContain('символов');
    expect(validateNewPassword('password123', 'different').confirmation).toContain('не совпадают');
  });
});

describe('structured API errors', () => {
  it('preserves cooldown data instead of converting it to an HTTP-only message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({
      detail: { code: 'EMAIL_VERIFICATION_COOLDOWN', retry_after_seconds: 17 },
    }), { status: 429 })));
    const error = await request('/api/v1/auth/register', { method: 'POST', body: { email: 'a@example.com' } }).catch(e => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.code).toBe('EMAIL_VERIFICATION_COOLDOWN');
    expect(error.retryAfterSeconds).toBe(17);
  });

  it('maps 422 errors to their fields and recognizes token errors', () => {
    const error = new ApiError(422, 'validation', [
      { loc: ['body', 'email'], msg: 'invalid', type: 'value_error' },
      { loc: ['body', 'token'], msg: 'too short', type: 'string_too_short' },
    ]);
    expect(authFieldErrors(error)).toEqual({
      email: 'Введите корректный адрес электронной почты.', token: 'Ссылка недействительна. Запросите новое письмо.',
    });
  });
});
