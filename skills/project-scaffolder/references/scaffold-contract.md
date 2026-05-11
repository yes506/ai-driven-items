# Scaffold Contract — Allowed / Denied / Gray-area

The scaffolder generates *common, non-domain* baseline only. This table is the
objective stopping rule.

| Category | Allowed | Denied (refuse) | Gray-area (ask user) |
|---|---|---|---|
| **Project structure** | Standard layout for chosen stack (`src/`, `tests/`, `cmd/`, `app/`, etc.) | Domain-named modules (`users/`, `orders/`, `payments/`) | Monorepo vs single-package |
| **Build / package** | `package.json`, `build.gradle.kts`, `pyproject.toml`, `go.mod`, `Cargo.toml` | Domain-specific scripts | Optional dev-deps beyond the baseline |
| **Lint / format** | ESLint+Prettier, ktlint+spotless, ruff+black, golangci-lint | Custom domain-specific rules | Style preset choice (Airbnb / Standard / etc.) |
| **Testing** | Test runner setup + ONE smoke test that asserts the baseline boots | Domain-specific test fixtures | E2E framework (Playwright / Cypress / etc.) |
| **Logging** | Logger primitive + structured-logging baseline | Pre-built audit/business log emitters | Log-shipping target (CloudWatch / Datadog / etc.) |
| **Config** | Typed settings loader + `.env.example` with placeholders | Real secrets, real env values | Config library choice (pydantic-settings / convict / etc.) |
| **Errors** | Base error / exception hierarchy stub | Domain-specific error subclasses | — |
| **HTTP** | `/health` endpoint stub | Business endpoints (`/users`, `/orders`) | OpenAPI auto-generation |
| **DB** | DB connection + migration tool init (no migrations) | Schemas, entities, seed data | ORM vs query-builder choice |
| **Auth** | Empty auth-middleware skeleton | Real auth flow, real provider config | Auth library choice (NextAuth / Spring Security / etc.) |
| **CI** | Lint + test workflow stub | Deployment pipelines, release automation | Provider (GH Actions / GitLab / CircleCI) |
| **Docs** | Top-level project `README.md` (minimal, ≤30 lines) | Architecture docs, ADRs with content, API docs | Empty `docs/adr/` directory |
| **Container** | Multi-stage Dockerfile baseline + `.dockerignore` | `docker-compose` with real services wired up | Compose for local-dev only |

## How to use this table

1. For each file the agent considers writing, find the matching row.
2. If the file falls in *Allowed*, write it.
3. If it falls in *Denied*, refuse — defer to a follow-up task outside this skill.
4. If *Gray-area*, ask the user once. Cache the answer in `.scaffold-state.json`
   under `decisions`.

## Domain-leak tells

The agent must self-check before writing any file that includes:

- Real entity names from the user's intent ("User", "Order", "Patient")
- Real business verbs ("checkout", "subscribe", "onboard")
- Real route paths beyond `/health`
- Real env values (not placeholders)

If any is present, stop and re-scope to the *Allowed* column.
