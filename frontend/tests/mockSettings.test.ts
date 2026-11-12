import { describe, expect, it } from 'vitest';
import { defaultHeaderErrors, mockDefaultsFromForm } from '../src/mockSettings';

describe('default response headers', () => {
  it('accepts HTTP tokens, Latin-1 and internal tabs', () => {
    expect(defaultHeaderErrors([{ name: 'X-Example', value: 'café\tvalue' }])).toEqual([{}]);
  });

  it.each(['Content-Length', 'Content-Encoding', 'Transfer-Encoding', 'Connection', 'Keep-Alive',
    'Proxy-Authenticate', 'Proxy-Authorization', 'Proxy-Connection', 'TE', 'Trailer', 'Upgrade'])('rejects %s ignoring case', name => {
    expect(defaultHeaderErrors([{ name: name.toUpperCase(), value: 'value' }])[0].name).toContain('служебный');
  });

  it.each(['with space', 'Сервер', '', 'X\nHeader'])('rejects an invalid name %j', name => {
    expect(defaultHeaderErrors([{ name, value: '' }])[0].name).toBeTruthy();
  });

  it.each([' value', 'value\t', 'line\r\nbreak', 'кириллица', 'x\x00y', 'x\x7fy', '🙂'])('rejects an invalid value %j', value => {
    expect(defaultHeaderErrors([{ name: 'X-Test', value }])[0].value).toBeTruthy();
  });

  it('rejects both exact and case-insensitive duplicates before object serialization', () => {
    expect(defaultHeaderErrors([{ name: 'X-Source', value: 'a' }, { name: 'x-source', value: 'b' }])
      .every(error => !!error.name)).toBe(true);
    const form = new FormData();
    form.append('default_header_name', 'X-Source');
    form.append('default_header_value', 'a');
    form.append('default_header_name', 'X-Source');
    form.append('default_header_value', 'b');
    expect(() => mockDefaultsFromForm(form)).toThrow('уже используется');
  });

  it('sends explicit empty defaults for clearing saved settings', () => {
    const form = new FormData();
    form.set('default_delay_ms', '0');
    expect(mockDefaultsFromForm(form)).toEqual({ default_delay_ms: 0, default_response_headers: {} });
  });

  it.each(['-1', '60001', '1.5', 'NaN'])('rejects delay %s', delay => {
    const form = new FormData();
    form.set('default_delay_ms', delay);
    expect(() => mockDefaultsFromForm(form)).toThrow('задержка');
  });
});
