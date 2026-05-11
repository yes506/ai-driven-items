# Tier-2 Stack Fallback

When the user wants a stack outside the tier-1 list (Next.js, Spring Boot,
FastAPI, Go, Node/Express), do **not** improvise from training memory — the
risk of generating outdated or incorrect scaffolding is too high. Instead,
hand the steering wheel back to the user.

## When this applies

Any stack not listed in the tier-1 table of [stack-selection.md](stack-selection.md).
Examples: Rust+Axum, Kotlin+Ktor, Elixir+Phoenix, Django, Rails, NestJS,
SvelteKit, Solid, Remix, Hono, AdonisJS.

## Dialog

```
The stack you described (<user's stack>) is outside our tier-1 list, so I'd
like to confirm a few details before scaffolding to make sure I match your
team's conventions.

1) Canonical project layout — is there a starter command (e.g. `cargo new`,
   `mix phx.new`, `rails new`) you want me to use? If yes, paste the exact
   command. If no, describe the directory layout you expect.

2) Package/build tool — which one (and any required version)?

3) Lint + format — which tools? (e.g. `clippy + rustfmt`, `credo + mix format`)

4) Test framework + ONE smoke test command (so I can verify the baseline boots).

5) Container baseline — which base image family?

6) Anything stack-specific I should NOT generate? (e.g. for Django, you may
   want to skip default `admin/` wiring.)
```

## After the user answers

1. Echo the answers back as a fenced block (the source of truth).
2. Ask for `confirm` before creating the worktree (Phase 4).
3. Generate only the *Allowed* column of [scaffold-contract.md](scaffold-contract.md),
   using the user's answers as the layout authority.
4. Fall back to the standard validation flow in Phase 6 — use the user-provided
   smoke-test command.

## What this flow never does

- Pretend expertise the agent does not have.
- Generate stack-specific files based on training data alone.
- Skip the user-confirmation gate just because tier-2 is "less standard".
