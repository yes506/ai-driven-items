---
name: project-scaffolder
description: |
  Bootstrap a new project's *common, non-domain* baseline (directory layout,
  build/lint/format/test config, logging, config loading, error scaffolding,
  health endpoint, CI stub) when the user starts a new codebase or adds a new
  sub-project. Recommends 2-4 tech-stack options with trade-offs and waits for
  the user to select one (or specify their own intent) before generating files.
  Runs all scaffolding inside a dedicated git worktree branched from `dev` and
  asks for explicit user confirmation before merging back. Language-agnostic —
  tier-1 stacks: Next.js, Spring Boot, FastAPI, Go (Gin or stdlib), Node/Express;
  tier-2 stacks fall back to a "describe-your-stack" dialog. Triggers on phrases
  like "start a new project", "scaffold a backend", "bootstrap a Next.js app",
  "set up project skeleton", "프로젝트 스캐폴딩".
disable-model-invocation: true
---

# Project Scaffolder

## Overview

Walk the user from *intent → tech-stack selection → scaffolded baseline* without
ever generating domain logic. All file mutations happen inside a dedicated git
worktree branched from `dev`, and the worktree only merges back after explicit
user confirmation.

`disable-model-invocation: true` means this skill only fires on explicit
`/project-scaffolder` invocation — never auto-trigger it.

## Workflow Decision Tree

```
Phase 0: Detect repo state ──┬─ greenfield ──┐
                             ├─ existing+dev ┤
                             ├─ existing-dev ┤── dialog
                             └─ in-worktree ─── refuse, exit
                                                │
Phase 1: Capture intent (no mutations) ─────────┤
Phase 2: Recommend 2-4 stacks (no mutations) ───┤
Phase 3: User confirms stack ───── silence = stop, not yes
Phase 4: Create worktree from dev (first mutation)
Phase 5: Scaffold per scaffold-contract.md
Phase 6: Validate (stack-appropriate command) + write state file
Phase 7: Show summary, await `confirm merge` (anything else = abort)
         on confirm: git merge --no-ff into dev, leave worktree intact
```

Each phase below states **inputs**, **what the agent does**, and **gates**.

---

## Phase 0 — Repo state detection

**Inputs**: current working directory.

Run the read-only inspector and parse the JSON it prints:

```bash
bash scripts/inspect_repo_state.sh
```

Classify into exactly one of:

| State | Meaning | Action |
|---|---|---|
| `greenfield` | no `.git`, or `.git` with zero commits | offer to `git init` + initial commit + create `dev` from `main` (after asking) |
| `existing-with-dev` | repo has commits, `dev` exists locally or on origin | proceed to Phase 1 |
| `existing-without-dev` | repo has commits but no `dev` | dialog: create `dev` from `main`? target a different branch? abort? |
| `inside-worktree` | invoked from inside a `.worktrees/...` path | refuse, instruct user to run from main checkout |

**Gate**: do not advance if state is `inside-worktree` or if user has not chosen
a fallback in `existing-without-dev`.

See [git-worktree-flow.md](references/git-worktree-flow.md) for branch-fallback
dialog wording and edge-case handling.

---

## Phase 1 — Intent capture (no mutations)

Ask the user (in batches, not all at once):

- **Project type**: web app, API service, mobile, CLI, library, data pipeline, other?
- **Deployment target**: cloud (which?), on-prem, container, serverless?
- **Constraints**: corporate proxy, language preference, team familiarity, scale?
- **High-level needs**: persistence, auth, external integrations?

Do not generate stacks yet. Reflect captured intent back as a short bullet list
and confirm before Phase 2.

---

## Phase 2 — Stack recommendation (no mutations)

Read [stack-selection.md](references/stack-selection.md) for the recommendation
pattern.

Present **2–4 options**, each stating: language, primary framework, build tool,
test framework, lint/format, container baseline, and one explicit trade-off
sentence. Do not pick a default behind the user's back.

For tier-1 stacks (Next.js, Spring Boot, FastAPI, Go, Node/Express), source
specifics from the matching `references/stack-*.md`. For anything else, follow
[tier2-fallback.md](references/tier2-fallback.md) — ask the user to describe
the stack rather than improvising.

**Versions**: never hardcode "Next.js 14" or "Spring Boot 3.2". When a
version-sensitive choice matters, look up the current stable version from
official docs at scaffold time, or emit a TODO with the canonical lookup URL.

---

## Phase 3 — Stack confirmation gate

Reflect the chosen stack back as a single fenced block (the source of truth).

Wait for `confirm`, `yes`, or `proceed`. **Silence is not confirmation.**
Anything ambiguous → re-ask.

---

## Phase 4 — Worktree creation (first mutation)

Order matters — only after Phase 3 confirmation:

1. Pick a slug from the chosen stack (e.g. `nextjs-app-router`).
2. Create the worktree:
   ```bash
   git worktree add ".worktrees/scaffold-<stack-slug>-$(date +%s | tail -c 6)" \
     -b "scaffold/<stack-slug>-<short-id>" dev
   ```
3. `cd` into the new worktree for all subsequent file operations.

Worktree path encodes the stack so `git worktree list` / `git branch` is
self-describing.

Edge cases (path collision, dirty `dev`, missing `dev` locally but on origin,
nested invocation, untracked files on re-run, merge conflicts at the gate) are
documented in [git-worktree-flow.md](references/git-worktree-flow.md). Stop and
ask the user — never auto-resolve.

---

## Phase 5 — Scaffold (file mutations)

Generate **only** items in the *Allowed* column of
[scaffold-contract.md](references/scaffold-contract.md). Treat *Gray-area*
items as "ask the user". Refuse *Denied* items even if asked — defer them to a
follow-up task outside this skill.

Use the matching `references/stack-*.md` for the canonical layout of the
selected stack:

- [stack-nextjs.md](references/stack-nextjs.md)
- [stack-spring-boot.md](references/stack-spring-boot.md)
- [stack-fastapi.md](references/stack-fastapi.md)
- [stack-go.md](references/stack-go.md)
- [stack-node-express.md](references/stack-node-express.md)

After file generation, write a resumable state file at the worktree root:

```json
// .scaffold-state.json
{
  "stack": { "language": "...", "framework": "...", "version_lookup": "..." },
  "phase_completed": "scaffolded",
  "decisions": { "linter": "...", "test_runner": "...", "ci": "..." },
  "scaffolded_at": "2026-05-11T11:00:00+09:00"
}
```

Initial commit on the scaffold branch:

```
chore(scaffold): initialize <stack> baseline (no domain logic)
```

---

## Phase 6 — Validate

Run the stack-appropriate validation command (lint + test stub):

| Stack | Command |
|---|---|
| Next.js / Node-Express | `npm run lint && npm test -- --run` |
| Spring Boot | `./gradlew check` |
| FastAPI | `ruff check . && pytest -q` |
| Go | `go vet ./... && go test ./...` |

If validation fails: stop, report failure, **never auto-prune the worktree**.
Update `.scaffold-state.json` `phase_completed` to `validated` on success.

---

## Phase 7 — Merge gate

Print:

1. `git diff --stat dev..HEAD` (what changed).
2. The decisions block from `.scaffold-state.json`.
3. The exact prompt:

```
Type `confirm merge` to merge scaffold/<slug> into dev,
or `abort` to leave the worktree intact for further iteration.
```

- `confirm merge` → from main checkout: `git merge --no-ff scaffold/<slug>`
  into `dev`. **Do not** `git push` — that is the user's call.
- Anything else → leave worktree intact, exit.

After a successful merge, ask: "Remove the worktree at `.worktrees/...`?"
On yes: `git worktree remove <path>` (no `--force`). On no: leave it.

---

## Forbidden actions

The skill must refuse to execute any of these even if the user requests them
mid-flow (politely surface the forbidden item and ask for confirmation to
deviate, but default to refusal):

- `git push`, `git push --force`
- `git merge` without the `--no-ff` flag for the scaffold branch
- `git reset --hard`, `git clean -f`, `git worktree remove --force`
- `--no-verify` on commits (pre-commit hooks must run)
- Generating domain entities, business routes, or product-named screens
- Hardcoded framework versions in any scaffolded file
- Treating user silence as confirmation at any gate
- Creating `README.md`, `INSTALLATION_GUIDE.md`, or similar docs *inside this
  skill folder* (a top-level project README in the *scaffolded project* is
  fine and expected)

---

## Resumability

If the user re-invokes the skill from inside an existing scaffold worktree,
read `.scaffold-state.json` and resume from the next phase after
`phase_completed`. Do not restart the wizard.
