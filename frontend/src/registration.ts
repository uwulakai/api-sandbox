import { ApiError } from './api';

export interface VerificationLink {
  token: string | null;
  interrupted: boolean;
}

const verificationMarker = 'apiSandboxVerification';

// The URL fragment is consumed before React renders. Only a non-secret recovery
// marker remains in history; neither the email token nor the password is stored.
export function consumeVerificationLink(): VerificationLink | null {
  const params = new URLSearchParams(window.location.hash.slice(1));
  if (params.has('verify-email')) {
    const token = params.get('verify-email') || null;
    window.history.replaceState({ ...window.history.state, [verificationMarker]: true }, '',
      window.location.pathname + window.location.search);
    return { token, interrupted: !token };
  }
  return window.history.state?.[verificationMarker] ? { token: null, interrupted: true } : null;
}

export function clearVerificationMarker() {
  const state = { ...window.history.state };
  delete state[verificationMarker];
  window.history.replaceState(state, '', window.location.pathname + window.location.search);
}

export function validateNewPassword(password: string, confirmation: string): Record<string, string> {
  const errors: Record<string, string> = {};
  const length = [...password].length;
  if (length < 8 || length > 72) errors.password = 'Пароль должен содержать от 8 до 72 символов.';
  else if (new TextEncoder().encode(password).length > 72) {
    errors.password = 'Пароль превышает 72 байта UTF-8. Сократите его, особенно если используете кириллицу или эмодзи.';
  }
  if (password !== confirmation) errors.confirmation = 'Пароли не совпадают.';
  return errors;
}

export function authFieldErrors(error: ApiError): Record<string, string> {
  const fields: Record<string, string> = {};
  for (const issue of error.issues) {
    const field = String(issue.loc[0] === 'body' ? issue.loc[1] : issue.loc[0]);
    if (field === 'email') fields.email = 'Введите корректный адрес электронной почты.';
    if (field === 'password') fields.password = 'Пароль должен содержать от 8 до 72 символов и не более 72 байт UTF-8.';
    if (field === 'token') fields.token = 'Ссылка недействительна. Запросите новое письмо.';
  }
  return fields;
}
