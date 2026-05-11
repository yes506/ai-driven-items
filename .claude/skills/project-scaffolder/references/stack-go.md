# Stack: Go (stdlib `net/http` or Gin)

## Initialization

```bash
mkdir <project-name> && cd <project-name>
go mod init <module-path>
```

If the user picked `go-gin`:
```bash
go get github.com/gin-gonic/gin
```

Otherwise default to stdlib `net/http`.

Layout:

```
<project-name>/
├── go.mod
├── cmd/server/main.go      # entrypoint, mounts /health
├── internal/
│   ├── config/config.go    # env reader (envconfig or stdlib)
│   ├── logging/logger.go   # slog wrapper
│   └── errors/errors.go    # error sentinels + helpers
├── internal/health/handler.go
├── internal/health/handler_test.go
├── .env.example
├── Dockerfile              # multi-stage scratch/distroless
└── .dockerignore
```

## Allowed scaffold contents

- `cmd/server/main.go`: server bootstrap, `/health` route, graceful shutdown
- `internal/config/config.go`: typed config struct populated from env
- `internal/logging/logger.go`: thin wrapper around `log/slog`
- `internal/errors/errors.go`: `var ErrNotFound = errors.New(...)` exemplars
- `internal/health/handler.go` + test: GET → 200 `{"status":"ok"}`
- `Dockerfile`: multi-stage `golang:1.x-alpine` → `gcr.io/distroless/static`
- `.github/workflows/ci.yml`: `go vet ./... && go test ./...` (opt-in)

## Denied

- Any `internal/<domain>/` package with real business logic
- DB driver wiring (sqlx, gorm) beyond `import _ "github.com/lib/pq"` placeholder
- Auth middleware with real provider
- Migration files with real schema

## Smoke test

```bash
go vet ./... && go test ./...
```

## Versions

Use the latest stable Go toolchain per `go.mod` `go 1.x`. Never write a
specific Gin version — `go get github.com/gin-gonic/gin` resolves current.
Reference: <https://go.dev/doc/>.
