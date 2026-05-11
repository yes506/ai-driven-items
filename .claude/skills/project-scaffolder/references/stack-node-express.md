# Stack: Node + Express (TypeScript)

## Initialization

```bash
mkdir <project-name> && cd <project-name>
npm init -y
npm install express
npm install -D typescript @types/node @types/express tsx vitest \
  eslint @typescript-eslint/parser @typescript-eslint/eslint-plugin \
  prettier eslint-config-prettier
npx tsc --init
```

Layout:

```
<project-name>/
├── package.json
├── tsconfig.json
├── src/
│   ├── server.ts           # express app + /health
│   ├── config.ts           # zod-validated env reader
│   ├── logger.ts           # pino or console wrapper
│   ├── errors.ts           # base error class
│   └── __tests__/
│       └── health.test.ts  # one smoke test
├── .env.example
├── .eslintrc.cjs
├── .prettierrc
├── Dockerfile
└── .dockerignore
```

## Allowed scaffold contents

- `src/server.ts`: express app, mount `GET /health → 200 {status:"ok"}`,
  graceful shutdown handler
- `src/config.ts`: zod schema validating `process.env`, exported typed config
- `src/logger.ts`: pino instance or console wrapper
- `src/errors.ts`: `class AppError extends Error` + middleware error handler
- `src/__tests__/health.test.ts`: supertest hits `/health`, asserts 200
- `Dockerfile`: multi-stage `node:20-alpine` → `node:20-alpine` runtime
- `.github/workflows/ci.yml`: `npm run lint && npm test -- --run` (opt-in)

## Denied

- Any `src/routes/<domain>.ts` with business endpoints
- DB client (Prisma, TypeORM, Knex) beyond install
- Auth middleware with real provider (Passport strategies, etc.)
- Migrations with real schema

## Smoke test

```bash
npm run lint && npm test -- --run
```

## Versions

`npm install` resolves to current stable. Do not pin major versions in any
scaffolded `package.json` constraint beyond what npm writes.
Reference: <https://expressjs.com/>.
