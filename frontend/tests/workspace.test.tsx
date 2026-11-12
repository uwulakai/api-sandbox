import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { Endpoint, Mock, Request } from '../src/api';
import { Workspace } from '../src/Workspace';
import { MockDetail } from '../src/MockDetail';
import { Probe } from '../src/Probe';
import { DefaultHeadersEditor } from '../src/DefaultHeadersEditor';

const mock: Mock = {
  id: 'mock-id', name: 'Users API', description: null, default_response_headers: {}, default_delay_ms: 0,
  public_url: 'http://localhost/mock-id', runtime_status: 'running', desired_status: 'running',
  config_version: 1, last_error: null,
};
const endpoint: Endpoint = {
  id: 'endpoint-id', method: 'GET', path: '/users', status_code: 200, delay_ms: 10,
  enabled: true, name: 'Пользователи', description: 'Список пользователей', response_headers: {}, response_body: {},
};

describe('mock settings forms', () => {
  it('creates a mock with headers and shared delay', async () => {
    const call = vi.fn(async (path, options) => {
      if (options?.method === 'POST') return { ...mock, ...options.body };
      return path.endsWith('/endpoints') ? [] : [];
    });
    render(<Workspace user={{ id: 1, email: 'user@example.com' }} call={call as Request} onLogout={vi.fn()} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: '＋ Новый мок' }));
    const dialog = within(screen.getByRole('dialog'));
    await user.type(dialog.getByLabelText('Название'), 'Users API');
    await user.click(dialog.getByRole('button', { name: '＋ Заголовок' }));
    await user.type(dialog.getByLabelText('Имя заголовка 1'), 'X-Environment');
    await user.type(dialog.getByLabelText('Значение заголовка 1'), 'sandbox');
    await user.clear(dialog.getByLabelText('Общая задержка, мс'));
    await user.type(dialog.getByLabelText('Общая задержка, мс'), '250');
    await user.click(dialog.getByRole('button', { name: 'Сохранить' }));
    await waitFor(() => expect(call.mock.calls.find(([, options]) => options?.method === 'POST')?.[1].body).toEqual({
      name: 'Users API', description: null, default_response_headers: { 'X-Environment': 'sandbox' },
      default_delay_ms: 250, desired_status: 'running',
    }));
  });

  it('opens legacy mocks with empty defaults and positions the cursor at the end', async () => {
    const { default_delay_ms, default_response_headers, ...legacy } = mock;
    const call = vi.fn(async (path, options) => {
      if (options?.method === 'PATCH') return { ...mock, ...options.body };
      return path.endsWith('/endpoints') ? [] : [legacy];
    });
    render(<Workspace user={{ id: 1, email: 'user@example.com' }} call={call as Request} onLogout={vi.fn()} />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole('button', { name: 'Настройки' }));
    const dialog = within(screen.getByRole('dialog'));
    const name = dialog.getByLabelText('Название') as HTMLInputElement;
    expect(document.activeElement).toBe(name);
    expect(name.selectionStart).toBe(name.value.length);
    expect(dialog.getByLabelText('Общая задержка, мс')).toHaveProperty('value', '0');
    expect(dialog.getByText('Общие заголовки не заданы.')).toBeTruthy();
    await user.click(dialog.getByRole('button', { name: 'Сохранить' }));
    await waitFor(() => expect(call.mock.calls.find(([, options]) => options?.method === 'PATCH')?.[1].body).toEqual({
      name: 'Users API', description: null, default_response_headers: {}, default_delay_ms: 0,
    }));
  });

  it('clears saved headers by removing rows, with errors on case-insensitive duplicates', async () => {
    render(<form><DefaultHeadersEditor initialHeaders={{ 'X-Source': 'mock' }} /></form>);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: '＋ Заголовок' }));
    await user.type(screen.getByLabelText('Имя заголовка 2'), 'x-source');
    expect(screen.getByLabelText('Имя заголовка 1').getAttribute('aria-invalid')).toBe('true');
    expect((screen.getByLabelText('Имя заголовка 2') as HTMLInputElement).checkValidity()).toBe(false);
    await user.click(screen.getByRole('button', { name: 'Удалить заголовок 2' }));
    expect((screen.getByLabelText('Имя заголовка 1') as HTMLInputElement).checkValidity()).toBe(true);
    await user.click(screen.getByRole('button', { name: 'Удалить заголовок 1' }));
    expect(screen.queryByRole('table')).toBeNull();
    expect(screen.getByText('Общие заголовки не заданы.')).toBeTruthy();
  });
});

describe('endpoint metadata', () => {
  function detail(record: Partial<Endpoint>) {
    const call = vi.fn(async (_path, options) => options?.method === 'PATCH'
      ? { ...endpoint, ...options.body } : [record]);
    const changed = vi.fn();
    render(<MockDetail mock={mock} call={call as Request} busy={false} onEdit={vi.fn()} onDelete={vi.fn()}
      onRuntime={vi.fn()} onEndpointsChanged={changed} />);
    return { call, changed };
  }

  it('shows a route when old endpoint metadata is missing and opens empty fields', async () => {
    const { name, description, ...legacy } = endpoint;
    detail(legacy);
    expect(await screen.findByText('/users')).toBeTruthy();
    await userEvent.setup().click(screen.getByRole('button', { name: 'Изменить' }));
    const dialog = within(screen.getByRole('dialog'));
    expect(dialog.getByLabelText('Название')).toHaveProperty('value', '');
    expect(dialog.getByLabelText('Описание')).toHaveProperty('value', '');
  });

  it('shows metadata and sends explicit nulls when it is cleared', async () => {
    const { call, changed } = detail(endpoint);
    expect(await screen.findByText('Пользователи')).toBeTruthy();
    expect(screen.getByText('Список пользователей')).toBeTruthy();
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: 'Изменить' }));
    const dialog = within(screen.getByRole('dialog'));
    await user.clear(dialog.getByLabelText('Название'));
    await user.clear(dialog.getByLabelText('Описание'));
    await user.click(dialog.getByRole('button', { name: 'Сохранить' }));
    await waitFor(() => expect(changed).toHaveBeenCalledOnce());
    const body = call.mock.calls.find(([, options]) => options?.method === 'PATCH')?.[1].body;
    expect(body).toMatchObject({ name: null, description: null, method: 'GET', path: '/users' });
  });
});

describe('runtime synchronization', () => {
  it('blocks requests until the updated configuration is running', async () => {
    const call = vi.fn(async () => ({ status: 200, elapsedMs: 250, headers: { 'x-environment': 'sandbox' }, body: '{}' }));
    const view = render(<Probe mock={{ ...mock, runtime_status: 'pending' }} target={{ method: 'GET', path: '/users' }} call={call as Request} />);
    expect(screen.getByRole('button', { name: 'Отправить' })).toHaveProperty('disabled', true);
    fireEvent.submit(screen.getByRole('button', { name: 'Отправить' }).closest('form')!);
    expect(call).not.toHaveBeenCalled();
    view.rerender(<Probe mock={mock} target={{ method: 'GET', path: '/users' }} call={call as Request} />);
    await userEvent.setup().click(screen.getByRole('button', { name: 'Отправить' }));
    expect(await screen.findByText('HTTP 200')).toBeTruthy();
    expect(call).toHaveBeenCalledOnce();
  });
});
