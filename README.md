# API Sandbox

Платформа для конструирования и запуска API-заглушек.

## Архитектура MVP

- `backend/api` — публичный control-plane API.
- `frontend` — интерфейс React и TypeScript для настройки и проверки моков.
- `backend/runtime_worker` — синхронизация состояния Mock-серверов с Docker.
- `mock_runtime` — фиксированный runtime-образ одной API-заглушки.
- `mock_gateway` — внутренний HTTP gateway для маршрутизации запросов к Mock-контейнерам по Docker DNS.
- `autotests` — Jenkins и встроенный pytest-набор для проверки уже запущенного API.
- PostgreSQL — пользователи, сессии, Mock-серверы и endpoints.

Пользователь управляет только декларативным контрактом API. Docker image, command, network, volumes и лимиты ресурсов задаются платформой.

## Локальный запуск

1. Скопировать `.env.example` в `.env` и при необходимости изменить настройки.
2. Собрать и запустить приложение:

```powershell
docker compose up --build -d
```

3. Открыть `http://localhost:8893`. Порт на компьютере можно поменять через `FRONTEND_HTTP_PORT`.

Compose создаёт bridge-сеть `<имя проекта>_mocks_network`. В ней работают `mock_gateway`, `runtime_worker` и динамически создаваемые Mock-контейнеры. Ручное создание сети при запуске не требуется.

Dokploy подключает сервисы с доменами к сети Traefik. В режиме Isolated Deployments это отдельная сеть проекта.

Для `api`, `mock_gateway`, `frontend` и `autotests` явно задан label `traefik.docker.network`. Переменная `TRAEFIK_DOCKER_NETWORK` должна содержать точное имя общей сети этих сервисов и Traefik: `dokploy-network` при стандартном размещении либо имя сети проекта при Isolated Deployments. Например, для текущего изолированного стенда в Environment Dokploy:

```dotenv
TRAEFIK_DOCKER_NETWORK=apisandbox-monolite-uw4fku
```

После изменения нужен redeploy Compose. В Preview Compose должны сохраниться этот label и подключение к указанной сети. Если Traefik настроен на отсутствующую у сервиса сеть, он выбирает другую доступную сеть; при нескольких сетях очередное Docker-событие может изменить выбранный IP и привести к gateway timeout.

Traefik/Dokploy завершает TLS и направляет запросы к сервисам Compose. Mock-контейнеры не содержат Traefik labels и не предоставляют gateway доступ к Docker socket.

`runtime_worker` владеет lifecycle Mock-контейнеров. При запуске Compose он сначала удаляет старые managed-контейнеры и поднимает Mock-серверы с `desired_status=running`. При штатной остановке Compose worker обрабатывает `SIGTERM`, удаляет managed-контейнеры, а следующий запуск Compose восстанавливает активные Mock-серверы. Рестарт только `api` Mock-контейнеры не затрагивает.

## Фронтенд

В интерфейсе можно зарегистрироваться, создать и запустить мок, настроить эндпоинт и отправить пробный запрос. Публичный URL из карточки пригодится для проверки из curl или Postman. Вкладка «Проверка» отправляет запрос через внутренний `mock_gateway` и показывает HTTP-код, время, заголовки и тело ответа.

Для публикации через Dokploy добавьте домен для сервиса `frontend` с контейнерным портом `8080`, включите HTTPS и разверните Compose. Фронтенд обращается к `api` и `mock_gateway` по именам сервисов. Отдельные публичные адреса API и настройки CORS для интерфейса не требуются.

Для разработки с обновлением страницы при изменениях запустите Compose, затем из каталога `frontend` (Node.js 24+):

```powershell
npm ci
npm run dev
```

Vite выводит адрес приложения и передаёт запросы API и пробные запросы контейнеру `frontend` через `127.0.0.1:8893`. Если локальный порт изменён в Compose, задайте то же значение `FRONTEND_HTTP_PORT` в окружении перед запуском Vite. Команда `npm run build` проверяет типы и собирает production-версию.

## Доступ через HTTPS в Dokploy

Назначьте домены в Dokploy, включив HTTPS и Let's Encrypt. В настройках домена укажите порт внутри контейнера.

| Домен | Сервис | Порт контейнера |
| --- | --- | --- |
| `api.apisandbox.mnrg.tech` | `api` | `8000` |
| `mockserver.apisandbox.mnrg.tech` | `mock_gateway` | `8080` |
| `tests.apisandbox.mnrg.tech` | `autotests` | `8080` |
| Домен фронтенда | `frontend` | `8080` |

Перед redeploy проверьте адреса в Environment Dokploy.

```dotenv
API_BASE_URL=https://api.apisandbox.mnrg.tech
MOCK_PUBLIC_BASE_URL=https://mockserver.apisandbox.mnrg.tech
```

`MOCK_PUBLIC_BASE_URL` — внешний адрес gateway, который API возвращает в `public_url`
каждого мока. Dokploy не синхронизирует эту переменную при изменении домена.
Сохранённое в Environment значение имеет приоритет над значением по умолчанию
в Compose; после смены адреса нужно обновить Environment и выполнить redeploy.
При локальном запуске значение `http://mock_gateway:8080` доступно внутри сети Compose.
Для проверки локального мока из браузера используйте вкладку «Проверка».
Полный E2E-набор проверяет совпадение `X-Request-ID` в ответах gateway, поэтому
`404` от постороннего маршрута больше не считается подтверждением удаления runtime.

## API

- Swagger: `/docs`
- Health: `/health`
- Auth: `/api/v1/auth`
- Mock servers: `/api/v1/mocks`
- Mock endpoints: `/api/v1/mocks/{mock_id}/endpoints`

Внешний URL Mock имеет вид:

```text
https://mockserver.apisandbox.mnrg.tech/{mock_id}/{path}
```

## Автотесты запущенного приложения

- [HTTP E2E: запуск, покрытие и отчёты](e2e/README.md).
- [Jenkins: общий Compose для Dokploy, UI и расписание](automation/README.md).
- [Результаты первого live-прогона](e2e/RESULTS-2026-09-27.md).
- [Диагностика публичного gateway и серверный E2E-прогон 2026-11-04](e2e/RESULTS-2026-11-04.md).

## Status

Сейчас реализуется первый вертикальный срез backend’а. Расширенный backlog возможностей Mockoon находится в [TODO.md](./TODO.md).
