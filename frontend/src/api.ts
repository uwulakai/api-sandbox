export const methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'] as const;
export type Method = typeof methods[number];
export type DesiredStatus = 'running' | 'stopped';
export type RuntimeStatus = DesiredStatus | 'pending' | 'starting' | 'stopping' | 'error';

export interface User {
  id: number;
  email: string;
}

export interface Mock {
  id: string;
  name: string;
  description: string | null;
  public_url: string;
  desired_status: DesiredStatus;
  runtime_status: RuntimeStatus;
  config_version: number;
  last_error: string | null;
}

export interface EndpointFields {
  method: Method;
  path: string;
  status_code: number;
  delay_ms: number;
  enabled: boolean;
  response_headers: Record<string, string>;
  response_body: unknown;
}

export interface Endpoint extends EndpointFields {
  id: string;
}

export interface ProbeResult {
  status: number;
  elapsedMs: number;
  headers: Record<string, string>;
  body: string;
}

interface Options {
  method?: string;
  body?: unknown;
  signal?: AbortSignal;
}

export type Request = <T>(path: string, options?: Options) => Promise<T>;

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof SyntaxError) return 'Проверьте синтаксис JSON.';
  return 'Не удалось выполнить запрос. Проверьте подключение и повторите.';
}

export async function request<T>(path: string, { method = 'GET', body, signal }: Options = {}, token?: string): Promise<T> {
  const response = await fetch(path, {
    method,
    signal,
    headers: {
      ...(token && { Authorization: `Bearer ${token}` }),
      ...(body !== undefined && { 'Content-Type': 'application/json' }),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
    cache: 'no-store',
  });
  const data = response.status === 204 ? undefined : await response.json().catch(() => undefined);
  if (!response.ok) {
    const detail = data?.detail;
    const message = Array.isArray(detail)
      ? detail.map(item => `${item.loc?.slice(1).join('.') || 'Запрос'}: ${item.msg}`).join('\n')
      : typeof detail === 'string' ? detail : `Ошибка HTTP ${response.status}.`;
    throw new ApiError(response.status, message);
  }
  if (response.status !== 204 && data === undefined) {
    throw new ApiError(502, 'Сервис вернул ответ в неожиданном формате.');
  }
  return data as T;
}

export const mocksPath = '/api/v1/mocks';
export const mockPath = (id: string) => `${mocksPath}/${encodeURIComponent(id)}`;
export const endpointsPath = (id: string) => `${mockPath(id)}/endpoints`;
export const authPath = '/api/v1/auth';
