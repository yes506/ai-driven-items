# Stack: Next.js (App Router, TypeScript)

## Initialization

Use the official starter to pin to current stable:

```bash
npx create-next-app@latest <project-name> \
  --typescript --eslint --app --src-dir --tailwind --import-alias "@/*"
```

Do not hand-roll — `create-next-app` produces an up-to-date layout that the
scaffolder must not reinvent.

## Allowed scaffold additions on top of the starter

Per [scaffold-contract.md](scaffold-contract.md):

- `src/lib/logger.ts` — structured logger primitive (pino or console wrapper)
- `src/lib/config.ts` — typed env reader (zod-validated)
- `src/lib/errors.ts` — base error class hierarchy
- `src/app/health/route.ts` — `/health` GET endpoint returning `{status:"ok"}`
- `.env.example` — placeholder env keys, no real values
- `.github/workflows/ci.yml` — lint + test + build (only if user opts in)
- `Dockerfile` (multi-stage: deps → build → runner) and `.dockerignore`

## Denied

- Any `app/<domain>/page.tsx` — domain pages are out of scope
- Auth provider wiring (NextAuth route handlers, Clerk components, etc.)
- Database client wiring (Prisma schemas, Drizzle tables, etc.)
- shadcn/ui or other component-library installs (defer to a follow-up task)

## Smoke test

```bash
npm run lint && npm run build
```

If the user wants a unit-test runner, add Vitest:

```bash
npm install -D vitest @vitest/ui jsdom @testing-library/react
```

…and emit one trivial `src/lib/__tests__/config.test.ts` that asserts the
config reader throws on missing required vars.

## Versions

Pin via `create-next-app@latest` and use `node:lts-alpine` in any Dockerfile
(not a pinned major like `node:20-alpine` — `lts` tracks current Node LTS).
Do not write a Next.js major version into any scaffolded file.
Reference: <https://nextjs.org/docs>.
