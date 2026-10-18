# API Sandbox

Платформа для конструирования и запуска API-заглушек.

## Архитектура MVP

- `backend/api` — публичный control-plane API.
- `backend/runtime_worker` — синхронизация состояния Mock-серверов с Docker.
- `mock_runtime` — фиксированный runtime-образ одной API-заглушки.
- `mock_gateway` — внутренний HTTP gateway для маршрутизации запросов к Mock-контейнерам по Docker DNS.
- `autotests` — Jenkins и встроенный pytest-набор для проверки уже запущенного API.
- PostgreSQL — пользователи, сессии, Mock-серверы и endpoints.

Пользователь управляет только декларативным контрактом API. Docker image, command, network, volumes и лимиты ресурсов задаются платформой.

## Локальный запуск

1. Скопировать `.env.example` в `.env` и при необходимости изменить настройки.
2. Создать сети для локального запуска:

```powershell
docker network create api-sandbox-mocks
docker network create api-sandbox-public
```

3. Собрать фиксированный runtime-образ:

```powershell
docker compose build mock_runtime_image
```

4. Запустить control plane:

```powershell
docker compose up --build -d postgres api runtime_worker mock_gateway autotests
```

В Dokploy сеть `api-sandbox-mocks` должна существовать заранее: это external-сеть для динамических Mock-контейнеров. Dokploy подключает сервисы с доменами к сети внешнего Traefik; в режиме Isolated Deployments это отдельная сеть проекта. Домен `mock-server.api-sandbox.merlant.xyz` направляется на `mock_gateway:8080`.

Для `api`, `mock_gateway` и `autotests` явно задан label `traefik.docker.network`. Переменная `TRAEFIK_DOCKER_NETWORK` должна содержать точное имя общей сети этих сервисов и Traefik: `dokploy-network` при стандартном размещении либо имя сети проекта при Isolated Deployments. Например, для текущего изолированного стенда в Environment Dokploy:

```dotenv
TRAEFIK_DOCKER_NETWORK=apisandbox-monolite-uw4fku
```

После изменения нужен redeploy Compose. В Preview Compose должны сохраниться этот label и подключение к указанной сети. Если Traefik настроен на отсутствующую у сервиса сеть, он выбирает другую доступную сеть; при нескольких сетях очередное Docker-событие может изменить выбранный IP и привести к gateway timeout. Сеть `api-sandbox-mocks` выбирать для внешнего Traefik не нужно.

Внешний Traefik/Dokploy используется только для TLS и передачи запроса в `mock_gateway`. Mock-контейнеры не содержат Traefik labels и не предоставляют gateway доступ к Docker socket.

`runtime_worker` владеет lifecycle Mock-контейнеров. При запуске Compose он сначала удаляет старые managed-контейнеры и поднимает Mock-серверы с `desired_status=running`. При штатной остановке Compose worker обрабатывает `SIGTERM`, удаляет managed-контейнеры, а следующий запуск Compose восстанавливает активные Mock-серверы. Рестарт только `api` Mock-контейнеры не затрагивает.

## API

- Swagger: `/docs`
- Health: `/health`
- Auth: `/api/v1/auth`
- Mock servers: `/api/v1/mocks`
- Mock endpoints: `/api/v1/mocks/{mock_id}/endpoints`

Внешний URL Mock имеет вид:

```text
https://mock-server.api-sandbox.merlant.xyz/{mock_id}/{path}
```

## Автотесты запущенного приложения

- [HTTP E2E: запуск, покрытие и отчёты](e2e/README.md).
- [Jenkins: общий Compose для Dokploy, UI и расписание](automation/README.md).
- [Результаты первого live-прогона](e2e/RESULTS-2026-09-27.md).

## Status

Сейчас реализуется первый вертикальный срез backend’а. Расширенный backlog возможностей Mockoon находится в [TODO.md](./TODO.md).
