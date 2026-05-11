# Stack: FastAPI (Python, uv or poetry)

## Initialization

Use `uv` (preferred — fast, current) or `poetry`:

```bash
# uv
uv init <project-name> --package
cd <project-name>
uv add fastapi uvicorn[standard] pydantic-settings
uv add --dev pytest ruff httpx
```

Layout (uv-init produces `src/<pkg>/`):

```
<project-name>/
├── pyproject.toml
├── src/<pkg>/
│   ├── __init__.py
│   ├── main.py            # FastAPI app + /health route
│   ├── config.py          # pydantic-settings BaseSettings
│   ├── logging.py         # structlog or stdlib JSON
│   └── errors.py          # base exception + handler
├── tests/
│   └── test_health.py     # one smoke test
├── .env.example
├── .python-version
├── Dockerfile
└── .dockerignore
```

## Allowed scaffold contents

- `main.py`: FastAPI app, mount `/health` GET → `{"status":"ok"}`, register exception handler
- `config.py`: `BaseSettings` with placeholder fields, validates env load
- `logging.py`: structured logger setup
- `errors.py`: `class AppError(Exception)` + handler
- `tests/test_health.py`: `client.get("/health").status_code == 200`
- `Dockerfile`: multi-stage with `uv` or `pip` install
- `.github/workflows/ci.yml`: `ruff check . && pytest -q` (opt-in)

## Denied

- Any `routers/<domain>.py` with business endpoints
- SQLAlchemy `DeclarativeBase` subclasses (defer ORM modeling)
- Auth dependency wiring (`Depends(get_current_user)` with real impl)
- Alembic migrations with real schema (init the tool, leave migrations empty)

## Smoke test

```bash
ruff check . && pytest -q
```

## Versions

Use `uv add fastapi` (no version pin). Let `uv` resolve current stable.
Reference: <https://fastapi.tiangolo.com/>.
