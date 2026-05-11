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
  tier-2 stacks fall back to a "describe-your-stack" dialog. User-facing
  dialog renders in Korean by default, or English when the invocation
  utterance is predominantly English (other languages fall back to English).
  Triggers on phrases like "start a new project", "scaffold a backend",
  "bootstrap a Next.js app", "set up project skeleton", "프로젝트 스캐폴딩".
disable-model-invocation: true
---

# Project Scaffolder

## Overview

Walk the user from *intent → tech-stack selection → scaffolded baseline* without
ever generating domain logic. All file mutations happen inside a dedicated git
worktree branched from `dev` (or a user-chosen base), and the worktree only
merges back after explicit user confirmation.

`disable-model-invocation: true` means this skill only fires on explicit
`/project-scaffolder` invocation — never auto-trigger it.

## Workflow Decision Tree

```
Phase L: Language selection (detect from invocation utterance, default Korean)
Phase 0: Detect repo state ──┬─ greenfield ─────────┐
                             ├─ existing-with-dev ──┤
                             ├─ existing-without-dev ┤── dialog → BASE_BRANCH
                             ├─ not-a-repo ─────────┤── dialog → init or relocate
                             ├─ inside-scaffold-wt ─┤── resume from .scaffold-state.json
                             └─ inside-other-wt ────── refuse, exit
                                                    │
Phase 1: Capture intent (no mutations) ─────────────┤
Phase 2: Recommend 2-4 stacks (no mutations) ───────┤
Phase 3: User confirms stack ─── silence = stop, not yes
Phase 4: Create worktree from BASE_BRANCH (first mutation, SCAFFOLD_ID computed once)
Phase 5: Scaffold per scaffold-contract.md + write .scaffold-state.json (incrementally)
Phase 6: Validate (stack-appropriate command)
Phase 7: Show summary, await `confirm merge` (anything else = abort)
         on confirm: git -C MAIN_CHECKOUT merge --no-ff -m "..." into BASE_BRANCH
```

State variables captured during Phase L / Phase 0 and threaded through later phases:

- `LANGUAGE` — `Korean` (default) or `English`; renders all user-facing dialog in this language
- `MAIN_CHECKOUT` — absolute path to the parent main worktree
- `BASE_BRANCH` — branch the scaffold branches from (default `dev`)
- `SCAFFOLD_ID` — short suffix used in both worktree path and branch name
- `SCAFFOLD_STATE` — `.scaffold-state.json` contents on resume

---

## Phase L — Language selection (preamble)

Determine the language for **all subsequent user-facing dialog** in this skill —
intent-capture questions, stack-recommendation presentations, confirmation
prompts, status updates, error messages. The choice persists in
`.scaffold-state.json` for resumability.

**This applies to dialog only.** Scaffolded code, configuration files,
`.env.example`, the generated project's `README.md`, and code comments stay in
their natural form (typically English) regardless of `LANGUAGE`. This skill's
own `SKILL.md`, `references/*.md`, and `scripts/` are agent-facing and never
translated.

### Detection rule

1. **Inspect the invocation utterance** (the user's `/project-scaffolder ...`
   message plus any follow-up text in the same turn).
2. Classify:

   | Signal | `LANGUAGE` |
   |---|---|
   | Predominantly Hangul characters in the utterance | `Korean` |
   | Predominantly English text in the utterance | `English` |
   | Empty, ambiguous, or non-text invocation | `Korean` (default) |

3. **Echo the choice and wait for confirmation** in the chosen language:
   - Korean: `진행 언어를 한국어로 설정했습니다. 다른 언어를 원하시면 알려주세요 (지원: 한국어, 영어). 그대로 진행하려면 "확인"이라고 답해 주세요.`
   - English: `Communication language set to English. Reply with another language name to switch (supported: Korean, English). Type "confirm" to proceed.`

4. **On user override**:
   - If the user picks Korean → `LANGUAGE=Korean`.
   - If the user picks English → `LANGUAGE=English`.
   - If the user picks any other language → fall back to English with a polite
     note: *"Other languages aren't first-class supported yet — I'll continue
     in English. You can use Korean or English freely at any point."*

5. **Mid-flow switches**: if the user explicitly asks to change language at
   any later phase (e.g. "switch to English" / "영어로 바꿔줘"), update
   `LANGUAGE` in `.scaffold-state.json` and continue in the new language.
   Do not reset other phase progress.

### Gate

Do not advance to Phase 0 until `LANGUAGE` is set (either auto-detected and
confirmed, or explicitly chosen).

---

## Phase 0 — Repo state detection

**Inputs**: current working directory.

Run the read-only inspector via the skill-directory variable (the bundled
script is **not** at the user's project root):

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/inspect_repo_state.sh"
```

Parse the JSON. The `state` field classifies into exactly one of:

| State | Meaning | Action |
|---|---|---|
| `greenfield` | no `.git` with commits, or repo with zero commits | offer `git init -b main` (if needed), initial empty commit, then `git branch dev` (after asking) |
| `existing-with-dev` | `dev` exists locally or on origin | set `BASE_BRANCH=dev`, proceed to Phase 1 |
| `existing-without-dev` | repo has commits but no `dev` | dialog (below) → `BASE_BRANCH` is set from user's pick |
| `not-a-repo` | cwd is not inside any git repo | dialog: offer `git init` here, OR ask the user to `cd` to the target repo and re-invoke. **If `git init` is chosen**: run **only** `git init -b "${default_branch:-main}"` first, then **re-run `inspect_repo_state.sh`** to refresh `MAIN_CHECKOUT` and `default_branch` (they were `null` while `not-a-repo`). The refreshed state will be `greenfield` — follow that row's action (initial empty commit, then `git branch dev`, asking the user before each command). |
| `inside-scaffold-worktree` | cwd matches `*/.worktrees/scaffold-*` AND is a linked worktree | if `.scaffold-state.json` present → resume from `phase_completed`; else refuse |
| `inside-other-worktree` | inside a linked worktree NOT matching scaffold pattern | refuse, instruct user to run from `MAIN_CHECKOUT` |

Also capture from the JSON:

- `MAIN_CHECKOUT = json.main_checkout` (absolute path)
- `default_branch` (used for greenfield-bootstrap and main/master detection)

### `existing-without-dev` dialog

```
`dev` branch not found. Options:
  1) Create dev from <default_branch> (recommended)
  2) Use a different base branch (specify name, must already exist)
  3) Abort — let me set up dev myself first
Type 1, 2 <branch-name>, or abort.
```

Whatever branch results becomes `BASE_BRANCH`. Persist it for Phase 4 and Phase 7.

**Gate**: do not advance unless `BASE_BRANCH` is decided.

See [git-worktree-flow.md](references/git-worktree-flow.md) for fallback dialog
wording, greenfield bootstrap commands, and edge-case handling.

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

**Versions**: never hardcode specific major versions. When a version-sensitive
choice matters, look up the current stable version from official docs at
scaffold time, or emit a TODO with the canonical lookup URL. The references
follow this rule too — if any reference shows a pinned version, treat the pin
as a placeholder and re-resolve.

---

## Phase 3 — Stack confirmation gate

Reflect the chosen stack back as a single fenced block (the source of truth).

Wait for `confirm`, `yes`, or `proceed`. **Silence is not confirmation.**
Anything ambiguous → re-ask.

---

## Phase 4 — Worktree creation (first mutation)

Order matters — only after Phase 3 confirmation:

0. **Locally** ignore `.worktrees/` in the main checkout so the in-flight
   scaffold doesn't dirty `git status` on `${BASE_BRANCH}` (this file is
   never committed, so it covers the pre-merge interval that step 3 below
   does not):
   ```bash
   grep -qxF '.worktrees/' "${MAIN_CHECKOUT}/.git/info/exclude" \
     || echo '.worktrees/' >> "${MAIN_CHECKOUT}/.git/info/exclude"
   ```
1. Compute `SCAFFOLD_ID` **once**, then interpolate consistently into both
   the path and the branch name:
   ```bash
   SCAFFOLD_ID="$(date +%s | tail -c 6)"
   STACK_SLUG="<chosen-slug>"   # e.g. nextjs-app-router, spring-boot, fastapi
   git -C "${MAIN_CHECKOUT}" worktree add \
     ".worktrees/scaffold-${STACK_SLUG}-${SCAFFOLD_ID}" \
     -b "scaffold/${STACK_SLUG}-${SCAFFOLD_ID}" "${BASE_BRANCH}"
   ```
2. `cd` into the new worktree for all subsequent file operations.
3. Append `.worktrees/` and `.scaffold-state.json` to the **worktree's**
   `.gitignore` if either is missing. This file is committed on the scaffold
   branch and lands on `${BASE_BRANCH}` via Phase 7's merge, so future
   contributors never see those paths as untracked. (The local exclude in
   step 0 covers the pre-merge interval; this committed entry covers
   post-merge forever.)

Worktree path encodes the stack so `git worktree list` / `git branch` are
self-describing.

Edge cases (path collision, dirty `BASE_BRANCH`, missing `dev` locally but on
origin, nested invocation, untracked files on re-run, merge conflicts at the
gate, default-branch is `master` not `main`) are documented in
[git-worktree-flow.md](references/git-worktree-flow.md). Stop and ask the
user — never auto-resolve.

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

Write `.scaffold-state.json` **incrementally** at the worktree root after each
sub-step, so a mid-scaffold failure stays resumable:

```json
{
  "language": "Korean | English",
  "stack": { "language": "...", "framework": "...", "version_lookup": "..." },
  "base_branch": "<BASE_BRANCH>",
  "main_checkout": "<MAIN_CHECKOUT>",
  "scaffold_id": "<SCAFFOLD_ID>",
  "phase_completed": "worktree_created | initialized | scaffold_files_written | validated",
  "decisions": { "linter": "...", "test_runner": "...", "ci": "..." },
  "scaffolded_at": "<ISO-8601>"
}
```

Note: the top-level `language` field is the dialog `LANGUAGE` from Phase L
(distinct from `stack.language`, which is the chosen programming language).

Initial commit on the scaffold branch (use the explicit `-m` form — a bare
`git commit` would drop into `$EDITOR` and hang in non-interactive runs):

```bash
git add -A
git commit -m "chore(scaffold): initialize ${STACK_SLUG} baseline (no domain logic)"
```

The state file is gitignored (Phase 4 step 3) so it does not appear in the
commit.

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

The agent's cwd may be inside the worktree. Use `git -C "${MAIN_CHECKOUT}"`
so the merge command is cwd-independent.

Print:

1. `git -C "${MAIN_CHECKOUT}" diff --stat ${BASE_BRANCH}..scaffold/${STACK_SLUG}-${SCAFFOLD_ID}` (what changed).
2. The decisions block from `.scaffold-state.json`.
3. The exact prompt:

```
Type `confirm merge` to merge scaffold/<slug>-<id> into <BASE_BRANCH>,
or `abort` to leave the worktree intact for further iteration.
```

- `confirm merge` → run from anywhere:
  ```bash
  git -C "${MAIN_CHECKOUT}" checkout "${BASE_BRANCH}"
  git -C "${MAIN_CHECKOUT}" merge --no-ff "scaffold/${STACK_SLUG}-${SCAFFOLD_ID}" \
    -m "feat(scaffold): merge ${STACK_SLUG} baseline"
  ```
  The explicit `-m` is mandatory — without it git drops into `$EDITOR` and
  hangs in non-interactive use. **Do not** `git push` — that is the user's call.
- Anything else → leave worktree intact, exit.

After a successful merge, ask: "Remove the worktree at `.worktrees/...`?"
On yes: `git -C "${MAIN_CHECKOUT}" worktree remove <path>` (no `--force`).
On no: leave it.

---

## Forbidden actions

The skill must refuse to execute any of these even if the user requests them
mid-flow (politely surface the forbidden item and ask for confirmation to
deviate, but default to refusal):

- `git push`, `git push --force`
- `git merge` without the `--no-ff` flag for the scaffold branch
- `git merge` or `git commit` without the `-m` flag (would hang on `$EDITOR`)
- `git reset --hard`, `git clean -f`, `git worktree remove --force`
- `--no-verify` on commits (pre-commit hooks must run)
- Generating domain entities, business routes, or product-named screens
- Hardcoded framework versions in any scaffolded file (re-resolve at scaffold
  time even if the references show pinned versions)
- Treating user silence as confirmation at any gate
- Creating `README.md`, `INSTALLATION_GUIDE.md`, or similar docs *inside this
  skill folder* (a top-level project README in the *scaffolded project* is
  fine and expected)

---

## Resumability

If the user re-invokes the skill from inside an existing scaffold worktree
(state `inside-scaffold-worktree`), read `.scaffold-state.json` and resume
from the next phase after `phase_completed`. Do not restart the wizard.

On resume, **also restore `LANGUAGE`** from the state file's top-level
`language` field — skip Phase L entirely. If the user wants to switch
language mid-resume, follow Phase L's "Mid-flow switches" rule.

Resume mapping:

| `phase_completed` value | Resume at |
|---|---|
| `worktree_created` | Phase 5 (scaffold files) |
| `initialized` | Phase 5 (scaffold files), after the `initialized` sub-step |
| `scaffold_files_written` | Phase 6 (validate) |
| `validated` | Phase 7 (merge gate) |

If `inside-scaffold-worktree` but no state file → refuse and ask the user to
either delete the worktree or supply a state file.
