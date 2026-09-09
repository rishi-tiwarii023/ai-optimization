# Health API

Implement a FastAPI service with a single health check.

## Endpoint

`GET /health`

## Response

- Status code: `200`
- Body: `{"status":"ok"}`

## Constraints

- Keep the ASGI application importable as `app.main:app`.
- Do not rename the `app` package in the starter repository.
