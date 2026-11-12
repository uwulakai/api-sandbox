import { ApiError } from './api';

export interface HeaderRow { name: string; value: string }
export interface HeaderErrors { name?: string; value?: string }

const httpName = /^[!#$%&'*+.^_`|~0-9A-Za-z-]+$/;
const forbiddenHeaders = new Set([
  'content-length', 'content-encoding', 'transfer-encoding', 'connection', 'keep-alive',
  'proxy-authenticate', 'proxy-authorization', 'proxy-connection', 'te', 'trailer', 'upgrade',
]);

export function defaultHeaderErrors(rows: HeaderRow[]): HeaderErrors[] {
  const counts = new Map<string, number>();
  for (const row of rows) {
    const key = row.name.toLowerCase();
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  return rows.map(({ name, value }) => {
    const errors: HeaderErrors = {};
    if (!httpName.test(name)) errors.name = 'Используйте HTTP-имя: латиница, цифры и допустимые знаки, без пробелов.';
    else if (forbiddenHeaders.has(name.toLowerCase())) errors.name = 'Этот служебный заголовок нельзя задать в общих настройках.';
    else if ((counts.get(name.toLowerCase()) ?? 0) > 1) errors.name = 'Имя уже используется. Регистр букв не учитывается.';
    if (value !== value.replace(/^[ \t]+|[ \t]+$/g, '')) errors.value = 'Уберите пробелы и табуляцию по краям значения.';
    else if ([...value].some(char => {
      const code = char.codePointAt(0)!;
      return code > 255 || (code < 32 && char !== '\t') || code === 127;
    })) errors.value = 'Используйте Latin-1 без переносов строк и управляющих символов. Табуляция допустима внутри строки.';
    return errors;
  });
}

export function mockDefaultsFromForm(form: FormData) {
  const names = form.getAll('default_header_name').map(String);
  const values = form.getAll('default_header_value').map(String);
  const rows = names.map((name, index) => ({ name, value: values[index] ?? '' }));
  const errors = defaultHeaderErrors(rows);
  const invalid = errors.findIndex(error => error.name || error.value);
  if (invalid !== -1) throw new ApiError(400, `Заголовок ${invalid + 1}: ${errors[invalid].name || errors[invalid].value}`);
  const delay = Number(form.get('default_delay_ms'));
  if (!Number.isInteger(delay) || delay < 0 || delay > 60_000) {
    throw new ApiError(400, 'Общая задержка должна быть целым числом от 0 до 60 000 мс.');
  }
  return { default_response_headers: Object.fromEntries(rows.map(row => [row.name, row.value])), default_delay_ms: delay };
}
