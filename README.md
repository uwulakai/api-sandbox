# API Sandbox

Платформа для конструирования и запуска API-заглушек.

## Архитектура MVP

- `backend/api` — публичный control-plane API.
- `backend/runtime_worker` — синхронизация состояния Mock-серверов с Docker.
- `mock_runtime` — фиксированный runtime-образ одной API-заглушки.
- `mock_gateway` — внутренний Traefik gateway для маршрутизации запросов к Mock-контейнерам.
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
docker compose --profile build build mock_runtime_image
```

4. Запустить control plane:

```powershell
docker compose up --build -d postgres api runtime_worker mock_gateway
```

В Dokploy `public_network` должна быть подключена к сети, в которой работает внешний Traefik. Домен `mock-server.api-sandbox.merlant.xyz` направляется на `mock_gateway:8080`.

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

## Status

Сейчас реализуется первый вертикальный срез backend’а. Расширенный backlog возможностей Mockoon находится в [TODO.md](./TODO.md).
