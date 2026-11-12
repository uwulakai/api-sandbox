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
  default_response_headers: Record<string, string>;
  default_delay_ms: number;
  public_url: string;
  desired_status: DesiredStatus;
  runtime_status: RuntimeStatus;
  config_version: number;
  last_error: string | null;
}

export interface EndpointFields {
  name: string | null;
  description: string | null;
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

export interface ValidationIssue {
  loc: (string | number)[];
  msg: string;
  type: string;
}

export class ApiError extends Error {
  constructor(public status: number, message: string, public detail?: unknown, public retryAfterSeconds?: number) {
    super(message);
  }

  get code(): string | undefined {
    if (typeof this.detail === 'string') return this.detail;
    if (this.detail && typeof this.detail === 'object' && 'code' in this.detail
        && typeof this.detail.code === 'string') return this.detail.code;
    return undefined;
  }

  get issues(): ValidationIssue[] {
    if (!Array.isArray(this.detail)) return [];
    return this.detail.filter((issue): issue is ValidationIssue =>
      issue && Array.isArray(issue.loc) && typeof issue.msg === 'string' && typeof issue.type === 'string');
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
    const retry = detail?.retry_after_seconds ?? response.headers.get('Retry-After');
    const retrySeconds = retry == null ? undefined : Number(retry);
    throw new ApiError(response.status, message, detail,
      retrySeconds !== undefined && Number.isFinite(retrySeconds) && retrySeconds >= 0 ? retrySeconds : undefined);
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
