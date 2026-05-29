# DOCTYPE: api-spec

API endpoint reference documentation. Stub primitive: **per-endpoint**.
`OUTPUT_STACK = text`.

## When to pick this DOCTYPE

- The intent is to document or specify HTTP/gRPC/GraphQL endpoints.
- The audience is integration partners, internal client teams, or
  external API consumers.
- The eventual deliverable is markdown, OpenAPI YAML, or a similar
  text-stack format.

## Stub primitive: per-endpoint

One stub = one endpoint. An endpoint is a path + method pair
(`GET /users/{id}`, `POST /orders`, `gRPC OrderService.Create`).

If the api-spec covers multiple sibling endpoints with shared schemas
(e.g. `/users/{id}` GET / PUT / DELETE), each method gets its own
stub. The shared schema is captured once as a separate root stub
(e.g. `schema-user`) and referenced via `dependencies:`.

## Field interpretations

| Field | api-spec interpretation |
|---|---|
| `id` | kebab-case: `<method-or-verb>-<resource>` (e.g. `get-user`, `post-order`, `delete-user-session`) |
| `purpose` | What client problem this endpoint solves. Not the implementation — the client-facing role |
| `audience` | `[external partners]` / `[internal client teams]` / `[both]` typically |
| `key claims` | The endpoint's contract: input shape, output shape, error codes, idempotency, rate limits, auth requirements |
| `evidence sources` | OpenAPI spec file path, controller source path, existing client SDK, integration tests |
| `dependencies` | Other endpoints called as part of a typical flow (e.g. `post-order` depends on `post-cart`), or shared-schema stubs |
| `acceptance criteria` | Concrete checks: example request/response, error matrix, auth example, pagination/cursor semantics if applicable |
| `length budget` | Endpoint complexity tag — `simple-CRUD`, `auth-flow`, `paginated-list-with-filters`, `streaming`, `idempotent-with-retries`. Optionally `<request-bytes>req / <response-bytes>resp` for size hints |
| `open questions` | Versioning strategy, deprecation timeline, auth scope inheritance, rate-limit policy if not yet decided |

## Phase 2 (outline) shape

Group endpoints by resource, then by typical client flow:

```
1. Authentication
   1.1 post-login
   1.2 post-refresh
   1.3 post-logout
2. Users
   2.1 schema-user (shared)
   2.2 get-user
   2.3 patch-user
3. Orders
   3.1 post-order
   3.2 get-order
   3.3 list-orders
```

## Validation hints (Phase 6)

`validate_doc_structure.py` and `validate_internal_refs.py` are
DOCTYPE-agnostic — same rules apply. But for api-spec specifically,
the Phase 7 rubric's "Cross-stub references" criterion should also
implicitly check that shared-schema stubs are referenced by every
endpoint that uses them (orphan shared-schemas are a smell).

## Implementer handoff notes

`document-implementer` for api-spec generates either:
- Markdown reference (one heading per endpoint, with the OpenAPI-style
  contract laid out in tables).
- OpenAPI YAML / JSON if the user specified that format at Phase 0.5.

`[[stub-id]]` transformation: markdown anchor `#<stub-id>`, or
OpenAPI `$ref` form when generating openapi.yaml.

## Honest limitations

- v1 stub primitive is one-endpoint-one-stub. A "versioned endpoint"
  (e.g. `/v1/users/{id}` AND `/v2/users/{id}`) is two stubs in v1 —
  there's no first-class "endpoint version" field. If many endpoints
  share versioning concerns, capture that in document-level
  `Constraints` at Phase 1.
- Schema-evolution stubs (deprecated fields, sunset timelines) are
  ordinary stubs; the implementer is expected to surface them
  consistently across the doc.
