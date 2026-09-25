# API Sandbox — TODO

## Product boundary

- [x] Treat `Mock` as an isolated API server owned by one user.
- [x] Store multiple independent endpoints inside a `Mock`.
- [x] Keep the Docker implementation fully platform-owned: fixed image, command, framework, network, volumes and resource limits.
- [x] Expose only declarative API configuration to users.
- [x] Restart or recreate a Mock container after its configuration changes.

## MVP backend

### Authentication and authorization

- [x] User registration with email and password.
- [x] Login and logout.
- [x] Current-user endpoint.
- [x] Server-side bearer sessions with hashed tokens.
- [x] Owner-only access to Mock servers and their endpoints.
- [ ] Tests for IDOR/ownership boundaries.

### Mock servers

- [x] Create, list, get, update and delete Mock servers.
- [x] Generate a stable public identifier/slug for every Mock.
- [x] Store desired and actual runtime status.
- [x] Return the public URL in the Mock response.
- [x] Support explicit start, stop and restart operations.
- [x] Add a healthcheck for every runtime container.
- [x] Persist the last runtime error and basic container metadata.

### HTTP endpoints

- [x] Create, list, get, update and delete endpoints belonging to a Mock.
- [x] Support the HTTP method and exact path matching.
- [x] Support one JSON response per endpoint initially.
- [x] Support response status code.
- [x] Support response headers, including `Content-Type`.
- [x] Validate that endpoints inside one Mock do not conflict.
- [x] Return a deterministic 404 response for an unknown route.
- [ ] Add tests for method/path uniqueness and route isolation between Mocks.

### Runtime and deployment

- [x] Build a fixed `mock-runtime` image from this repository.
- [x] Run one independent runtime container per Mock.
- [x] Run a separate runtime worker responsible for Docker lifecycle operations.
- [x] Keep the Docker socket unavailable to the public API container.
- [x] Reconcile desired Mock state with the actual Docker state.
- [x] Make container creation, restart and deletion idempotent.
- [ ] Clean up orphaned containers created by the platform.
- [ ] Add resource limits and a fixed security profile for runtime containers.

### Public gateway

- [x] Add one public `mock-gateway` container to Docker Compose.
- [x] Connect the gateway to the Dokploy network and the private Mock network.
- [x] Keep runtime Mock containers on the private Mock network only.
- [x] Route requests using:
      `https://mock-server.api-sandbox.merlant.xyz/{mock-server-id}/{path}`
- [x] Resolve the first path segment to a Mock container.
- [x] Strip the Mock identifier before forwarding the request.
- [x] Preserve method, query string, request body and relevant headers.
- [x] Return a clear response when the Mock is stopped, unavailable or unknown.
- [ ] Add gateway integration tests.

## Mockoon-inspired feature backlog

The list below is a product backlog, not an instruction to implement everything in the MVP. The first implementation should cover only the MVP section above.

### Mock/environment settings

- [ ] Mock name and description.
- [ ] API prefix/base path.
- [ ] Public base URL.
- [ ] Environment-level response headers.
- [ ] Environment-level latency.
- [ ] Random latency between zero and a configured maximum.
- [ ] Automatic CORS preflight handling.
- [ ] Configurable CORS headers.
- [ ] Enable/disable a Mock without deleting its configuration.
- [ ] Mock folders/groups and ordering.
- [ ] Mock tags and search.
- [ ] Runtime state reset.
- [ ] Runtime port/hostname as internal platform settings only, never user-controlled Docker settings.

### HTTP route configuration

- [ ] Exact method and path routes.
- [ ] All-method routes.
- [ ] Route path parameters, for example `/users/:id`.
- [ ] Optional path parameters.
- [ ] Wildcard routes.
- [ ] Regular-expression routes.
- [ ] Route ordering and precedence.
- [ ] Enabled/disabled routes.
- [ ] Route name and description.
- [ ] Query parameters excluded from the route declaration but available for rules and templates.
- [ ] Route documentation metadata.

### Responses

- [ ] Multiple responses per route.
- [ ] Default response.
- [ ] Response ordering.
- [ ] Response status code.
- [ ] JSON response body.
- [ ] Custom response headers.
- [ ] Response latency.
- [ ] Random response latency.
- [ ] Random response selection.
- [ ] Sequential response selection.
- [ ] Fallback to another route or proxy when no response rule matches.
- [ ] Response callbacks/webhooks.
- [ ] Callback delay and retry policy.
- [ ] Response metadata headers.

### Request-based rules

- [ ] Match by request header.
- [ ] Match by query parameter.
- [ ] Match by cookie.
- [ ] Match by path parameter.
- [ ] Match by request path.
- [ ] Match by HTTP method.
- [ ] Match by request body.
- [ ] Match by request number.
- [ ] Match by JSON path/object path.
- [ ] Equality, inequality, regex and array operators.
- [ ] JSON Schema validation rules.
- [ ] AND/OR rule groups.
- [ ] Rule negation.
- [ ] Rule ordering and rule enable/disable.

### Templates and generated data

- [ ] Handlebars-style response templates.
- [ ] Request helpers: body, query, headers, cookies, path parameters, method and URL.
- [ ] Faker-generated values.
- [ ] Global variables.
- [ ] Environment variables with a safe allowlist.
- [ ] JSON/string conversion helpers.
- [ ] Date, random, encoding and UUID helpers.
- [ ] Data buckets as reusable JSON data.
- [ ] Data bucket references inside response bodies and headers.
- [ ] Data bucket state reset.
- [ ] JSON Schema data buckets.

### Stateful and CRUD behavior

- [ ] CRUD route type.
- [ ] In-memory JSON data buckets.
- [ ] GET collection and item routes.
- [ ] POST create operation.
- [ ] PUT replace operation.
- [ ] PATCH partial update operation.
- [ ] DELETE operation.
- [ ] Automatic resource identifiers.
- [ ] Filtering, sorting and pagination.
- [ ] Configurable CRUD resource key.
- [ ] State reset after Mock restart.
- [ ] Explicit state purge endpoint for tests.

### Proxy and callbacks

- [ ] Partial proxy mode for unmatched routes.
- [ ] Proxy target URL.
- [ ] Remove or preserve API prefix when proxying.
- [ ] Additional request headers for proxy calls.
- [ ] Additional response headers for proxy calls.
- [ ] Configurable proxy timeout.
- [ ] Callback HTTP method, URL, body and headers.
- [ ] Callback templating.
- [ ] Callback loop protection.

### Observability and administration

- [ ] Request/response transaction logs.
- [ ] Log route, status, latency and container identifier.
- [ ] Redact authorization, cookies, API keys and other sensitive headers.
- [ ] Per-Mock log retention limit.
- [ ] API endpoint for reading Mock logs.
- [ ] API endpoint for clearing logs.
- [ ] Runtime events via Server-Sent Events.
- [ ] Prometheus metrics for gateway and runtime worker.
- [ ] Container stdout/stderr retrieval with pagination or tail support.

### Protocols and integrations

- [ ] Native WebSocket routes.
- [ ] WebSocket conversational mode.
- [ ] WebSocket streaming modes.
- [ ] OpenAPI v2 import.
- [ ] OpenAPI v3 import.
- [ ] OpenAPI v3 export.
- [ ] Import preview and conflict resolution.
- [ ] Export/import of the complete native Mock configuration.
- [ ] CLI/headless runtime compatibility.
- [ ] Configuration versioning and rollback.

## Architectural follow-ups

- [ ] Add Alembic migrations and remove startup `SQLModel.metadata.create_all` from production flow.
- [ ] Decide whether configuration updates recreate the container or use an internal runtime admin API.
- [ ] Define a versioned native Mock configuration schema.
- [ ] Define the exact route conflict algorithm and precedence rules.
- [ ] Define wildcard DNS and Dokploy network configuration.
- [ ] Define limits for users, Mocks, endpoints, body size, request size and runtime resources.
- [ ] Define public Mock access policy: anonymous, token-protected or user-authenticated.
- [ ] Define cleanup policy for deleted users, stopped Mocks and orphaned containers.
- [ ] Add API contract documentation and OpenAPI contract tests.

## Sources

- [Mockoon features](https://mockoon.com/features/)
- [HTTP routes](https://mockoon.com/docs/latest/api-endpoints/http-routes/)
- [Routing](https://mockoon.com/docs/latest/api-endpoints/routing/)
- [Multiple responses](https://mockoon.com/docs/latest/route-responses/multiple-responses/)
- [Dynamic rules](https://mockoon.com/docs/latest/route-responses/dynamic-rules/)
- [Response headers](https://mockoon.com/docs/latest/response-configuration/response-headers/)
- [Response body](https://mockoon.com/docs/latest/response-configuration/response-body/)
- [Templating](https://mockoon.com/docs/latest/templating/overview/)
- [Data buckets](https://mockoon.com/docs/latest/data-buckets/overview/)
- [CRUD routes](https://mockoon.com/docs/latest/api-endpoints/crud-routes/)
- [Proxy mode](https://mockoon.com/docs/latest/server-configuration/proxy-mode/)
- [Callbacks](https://mockoon.com/docs/latest/callbacks/overview/)
- [Request logging](https://mockoon.com/docs/latest/logging-and-recording/requests-logging/)
- [OpenAPI import/export](https://mockoon.com/docs/latest/openapi/import-export-openapi-format/)
- [WebSockets](https://mockoon.com/docs/latest/api-endpoints/websockets/)
