import { useId, useState } from 'react';
import { defaultHeaderErrors } from './mockSettings';
import type { HeaderRow } from './mockSettings';

export function DefaultHeadersEditor({ initialHeaders = {} }: { initialHeaders?: Record<string, string> }) {
  const id = useId();
  const [rows, setRows] = useState<(HeaderRow & { id: string })[]>(() =>
    Object.entries(initialHeaders).map(([name, value], index) => ({ id: `${index}`, name, value })));
  const errors = defaultHeaderErrors(rows);

  function update(rowId: string, field: 'name' | 'value', value: string) {
    setRows(previous => previous.map(row => row.id === rowId ? { ...row, [field]: value } : row));
  }

  return <section className="headers-editor" aria-labelledby={`${id}-title`}>
    <div className="panel-heading">
      <h3 id={`${id}-title`}>Заголовки по умолчанию</h3>
      <button type="button" onClick={() => setRows(previous => [...previous, { id: crypto.randomUUID(), name: '', value: '' }])}>＋ Заголовок</button>
    </div>
    <p className="auth-hint" id={`${id}-hint`}>Применяются ко всем известным маршрутам. Заголовок эндпоинта с тем же именем заменит общий, независимо от регистра.</p>
    {rows.length ? <div className="headers-table-wrap"><table className="headers-table">
      <thead><tr><th scope="col">Имя</th><th scope="col">Значение</th><th scope="col"><span className="sr-only">Действия</span></th></tr></thead>
      <tbody>{rows.map((row, index) => <tr key={row.id}>
        <td><input name="default_header_name" value={row.name} required aria-label={`Имя заголовка ${index + 1}`}
          className="mono" placeholder="X-Environment" aria-invalid={!!errors[index].name}
          aria-describedby={errors[index].name ? `${id}-${row.id}-name-error` : `${id}-hint`}
          ref={input => { input?.setCustomValidity(errors[index].name ?? ''); }}
          onChange={event => update(row.id, 'name', event.target.value)} />
          {errors[index].name && <small className="field-error" id={`${id}-${row.id}-name-error`}>{errors[index].name}</small>}
        </td>
        <td><input name="default_header_value" value={row.value} aria-label={`Значение заголовка ${index + 1}`}
          placeholder="sandbox" aria-invalid={!!errors[index].value}
          aria-describedby={errors[index].value ? `${id}-${row.id}-value-error` : `${id}-hint`}
          ref={input => { input?.setCustomValidity(errors[index].value ?? ''); }}
          onChange={event => update(row.id, 'value', event.target.value)} />
          {errors[index].value && <small className="field-error" id={`${id}-${row.id}-value-error`}>{errors[index].value}</small>}
        </td>
        <td><button type="button" className="danger" aria-label={`Удалить заголовок ${index + 1}`}
          onClick={() => setRows(previous => previous.filter(item => item.id !== row.id))}>×</button></td>
      </tr>)}</tbody>
    </table></div> : <p className="headers-empty muted">Общие заголовки не заданы.</p>}
  </section>;
}
