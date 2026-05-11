# Stack Selection — Recommendation Pattern

Goal: present 2–4 viable stacks for the user's intent, each with one explicit
trade-off, and let the user pick (or override with their own).

## Tier-1 stacks (well-supported)

| Slug | Language | Best for |
|---|---|---|
| `nextjs-app-router` | TypeScript | web apps, dashboards, SSR/RSC, marketing sites |
| `spring-boot` | Java/Kotlin | enterprise APIs, JVM shops, complex domain models |
| `fastapi` | Python | data/ML APIs, fast prototyping, Python-native teams |
| `go-stdlib` or `go-gin` | Go | high-throughput services, single-binary deployment |
| `node-express` | TypeScript | small-to-medium APIs, Node-only shops, BFF layers |

For each tier-1 stack, see the matching `references/stack-<slug>.md` for the
canonical scaffold layout.

## Tier-2 stacks

Anything outside the tier-1 list (Rust+Axum, Kotlin+Ktor, Elixir+Phoenix,
Django, Rails, NestJS, SvelteKit, etc.) → follow [tier2-fallback.md](tier2-fallback.md).

## Recommendation rules

1. Map the user's intent to a *category* (web, API, CLI, mobile, library, data).
2. Pick **2–4** stacks from the matching tier-1 entries that fit the intent.
   - If the user already declared a language preference, narrow accordingly.
   - If only one tier-1 stack fits cleanly, still offer one tier-2 alternative
     so the user has a real choice.
3. For each option, present:
   - **Language + framework**
   - **Build tool / package manager**
   - **Test framework**
   - **Lint/format**
   - **Container baseline** (Dockerfile pattern, base image family)
   - **One trade-off sentence** (what you lose by picking this)
4. End with: *"Pick one of the above (e.g. `1`), or describe your own stack."*

## Version handling

Never bake versions into recommendations. Phrasing template:

> Next.js (current stable from `https://nextjs.org/`), pinned at scaffold
> time via `npx create-next-app@latest`.

If a runtime lookup is impossible, emit a TODO in the scaffolded file pointing
to the canonical source.

## Anti-patterns

- Hidden default ("just use Next.js" without offering alternatives).
- Recommending a stack outside tier-1 without first checking that tier-2 fallback
  applies.
- Hard-coded major-version numbers ("Spring Boot 3.2") anywhere.
