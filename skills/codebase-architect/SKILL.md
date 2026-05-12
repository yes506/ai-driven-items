---
name: codebase-architect
description: |
  Plan a project's package/directory layout and generate one
  language-appropriate abstract component (Java interface / Python
  Protocol / TypeScript interface / Go interface / Rust trait) per
  cohesive responsibility — with a structured 9-field docstring on every
  method — BEFORE any implementation begins. Sequences after
  `project-scaffolder`. Runs entirely inside an isolated git worktree and
  emits a human-confirmation gate (rubric self-review + checklist + Mermaid
  DAG + self-contained HTML report) that downstream skills/agents must
  observe before generating implementation code. Language-agnostic.
  Triggers on phrases like "design the architecture", "plan the codebase",
  "create interfaces for", "design interfaces", "plan packages",
  "코드베이스 설계".
disable-model-invocation: true
---

# Codebase Architect

## Overview

Plan packages and emit interface-only skeletons for a project that has
already been baseline-scaffolded (typically by `project-scaffolder`).
Every method on every emitted interface represents one node in the
end-to-end pipeline; interfaces aggregate cohesive methods that share a
responsibility/lifecycle. No implementation may begin until this skill
emits `phase_completed: human_confirmed` in `.architect-state.json` after
the user types `confirm architecture`.

`disable-model-invocation: true` means this skill only fires on explicit
`/codebase-architect` invocation — never auto-trigger it.

## Workflow Decision Tree

```
Phase 0: Detect repo state ──┬─ on dev (post-scaffold) ────┐
                             ├─ inside-architect-worktree ─┤── resume from .architect-state.json
                             ├─ on dev (no scaffold marker) ┤── warn + ask to proceed
                             └─ unrelated state ──────────── refuse, exit
                                                            │
Phase 1: Plan ingestion (no mutations) — multi-method input ─┤
Phase 2: Package/directory plan (no mutations) ──────────────┤
Phase 3: Pipeline-node decomposition (no mutations) ─────────┤
         user confirms Phases 1-3 individually — silence = stop, not yes
Phase 4: Worktree creation (first mutation; ARCHITECT_ID computed once)
Phase 5: Interface skeleton generation + .architect-state.json (incremental)
Phase 6: Validate — language-appropriate compile/type-check on the skeleton
Phase 7: Self-verification artifacts — rubric + checklist + Mermaid DAG + HTML report
Phase 8: Human gate — `confirm architecture` → mark human_confirmed
         then offer `confirm merge` → merge worktree to BASE_BRANCH
```

State variables captured during Phase 0 and threaded through later phases:

- `MAIN_CHECKOUT` — absolute path to the parent main worktree
- `BASE_BRANCH` — branch the architect worktree branches from (default `dev`)
- `ARCHITECT_ID` — short suffix used in both worktree path and branch name
- `ARCHITECT_STATE` — `.architect-state.json` contents on resume
- `LANGUAGE_STACK` — detected from build files; drives Phase 5/6 commands

---

## Phase 0 — Repo state detection

Run the read-only inspector via the skill-directory variable (the bundled
script is **not** at the user's project root):

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/inspect_repo_state.sh"
```

Parse the JSON. The `state` field classifies into:

| State | Meaning | Action |
|---|---|---|
| `on-dev-with-scaffold` | on `dev`, project-scaffolder marker commit present | proceed to Phase 1 |
| `on-dev-no-scaffold` | on `dev` but no `chore(scaffold): initialize` commit in history | warn user, ask explicit confirmation to proceed without a scaffold baseline |
| `inside-architect-worktree` | cwd matches `*/.worktrees/architect-*` | resume from `.architect-state.json` if present, else refuse |
| `inside-other-worktree` | inside a non-architect linked worktree | refuse, instruct user to run from `MAIN_CHECKOUT` |
| `unrelated` | not in a git repo / not on a sensible base | refuse, surface what's off |

Capture from JSON: `MAIN_CHECKOUT`, `default_branch`. Set `BASE_BRANCH`
to `dev` by default (configurable via dialog if the user objects).

Detect language stack:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/detect_language_stack.sh"
```

Output gives `language` (`java | python | typescript | javascript | go |
rust | unknown`) and the corresponding `validation_command` for Phase 6.
If `unknown`, follow the dialog in
[language-skeletons.md](references/language-skeletons.md) to capture from
the user. If `javascript` and no `tsconfig.json`, ask whether to treat as
TypeScript (recommended) or refuse (no first-class skeleton language for
plain JS).

See [git-worktree-flow.md](references/git-worktree-flow.md) for edge cases.

**Gate**: do not advance unless `BASE_BRANCH` and `LANGUAGE_STACK` are decided.

---

## Phase 1 — Plan ingestion (no mutations)

Accept the project plan via multiple input methods, **presented separately**
so each can be normalized in isolation before synthesis:

- **File paths** — markdown / text / PDF specs the user has on disk
- **URLs** — Notion / wiki / GitHub issue / spec page
- **Inline pasted text** — user pastes plan content directly in chat

Read [plan-ingestion.md](references/plan-ingestion.md) for the
normalization rubric (extract goal, in-scope features, out-of-scope,
constraints, success criteria, open questions).

Reflect the normalized synthesis back to the user as a single fenced
block. Wait for `confirm plan` before Phase 2. Silence is not yes.

---

## Phase 2 — Package/directory plan (no mutations)

Propose a package layout consistent with the language stack and the
scaffolded baseline. Show as a directory tree plus a one-line dependency
direction summary (which packages depend on which). Justify each top-level
package by linking back to a goal/feature from Phase 1.

Wait for `confirm packages` before Phase 3.

---

## Phase 3 — Pipeline-node decomposition (no mutations)

Read [decomposition.md](references/decomposition.md) for the rule:
**one method = one pipeline stage = one node**; interfaces aggregate
cohesive methods that share a responsibility/lifecycle.

Enumerate every E2E pipeline stage from Phase 1's flow as a table:

| Node # | Stage | Interface | Method | Belongs to package |
|---|---|---|---|---|

Then render the same data as a Mermaid DAG so dependencies are visible.
Wait for `confirm decomposition` before Phase 4.

---

## Phase 4 — Worktree creation (first mutation)

Order matters — only after Phase 3 confirmation:

0. **Locally** ignore `.worktrees/` in the main checkout so the in-flight
   architect work doesn't dirty `git status` on `${BASE_BRANCH}`:
   ```bash
   grep -qxF '.worktrees/' "${MAIN_CHECKOUT}/.git/info/exclude" \
     || echo '.worktrees/' >> "${MAIN_CHECKOUT}/.git/info/exclude"
   ```
1. Compute `ARCHITECT_ID` **once**, then interpolate consistently into
   both the path and the branch name:
   ```bash
   ARCHITECT_ID="$(date +%s | tail -c 6)"
   PROJECT_SLUG="<short-project-slug>"
   git -C "${MAIN_CHECKOUT}" worktree add \
     ".worktrees/architect-${PROJECT_SLUG}-${ARCHITECT_ID}" \
     -b "architect/${PROJECT_SLUG}-${ARCHITECT_ID}" "${BASE_BRANCH}"
   ```
2. `cd` into the new worktree for all subsequent file operations.
3. Append `.worktrees/` and `.architect-state.json` to the **worktree's**
   `.gitignore` if either is missing. Lands on `${BASE_BRANCH}` via
   Phase 8's merge so future contributors never see those paths as
   untracked.

Edge cases (path collision, dirty `BASE_BRANCH`, nested invocation,
untracked files on resume, merge conflicts at the gate) are documented
in [git-worktree-flow.md](references/git-worktree-flow.md). Stop and ask
the user — never auto-resolve.

---

## Phase 5 — Interface skeleton generation

For each interface from Phase 3, generate a language-appropriate
abstraction (interface / Protocol / trait / etc.) per
[language-skeletons.md](references/language-skeletons.md).

**Every method MUST carry the 9-field docstring** per
[docstring-schema.md](references/docstring-schema.md). No exceptions.
A method without the docstring fails Phase 7 self-verification rubric
explicitly.

Write `.architect-state.json` **incrementally** at the worktree root
after each sub-step per
[state-and-resume.md](references/state-and-resume.md), so a mid-run
failure stays resumable.

Initial commit on the architect branch (use the explicit `-m` form — a
bare `git commit` would drop into `$EDITOR` and hang in non-interactive
runs):

```bash
git add -A
git commit -m "chore(architect): initialize ${PROJECT_SLUG} interface skeleton (no implementation)"
```

The state file is gitignored (Phase 4 step 3) so it does not appear in
the commit.

---

## Phase 6 — Validate

Run the language-appropriate compile/type-check on the empty skeleton
(commands defined in
[language-skeletons.md](references/language-skeletons.md)):

| Stack | Command |
|---|---|
| Java (Gradle) | `./gradlew compileJava` |
| Java (Maven) | `mvn compile` |
| Python | `mypy --strict <package>` (or `pyright`) |
| TypeScript | `tsc --noEmit` |
| Go | `go build ./...` |
| Rust | `cargo check` |

If validation fails: stop, report failure, **never auto-prune the
worktree**. Update `.architect-state.json` `phase_completed: validated`
on success.

---

## Phase 7 — Self-verification artifacts

Produce all three handoff outputs per
[self-verification.md](references/self-verification.md):

1. **Rubric-scored self-review** — analytic 4-point rubric across 6
   criteria (decomposition completeness, docstring quality, interface
   cohesion, dependency direction, validation status, plan coverage).
2. **Human-confirmation checklist** — single-point rubric (proficiency
   threshold + space for above/below comments).
3. **Visual outputs:**
   - Mermaid dependency DAG:
     ```bash
     python3 "${CLAUDE_SKILL_DIR}/scripts/render_mermaid_dag.py" \
       .architect-state.json > architecture.mmd
     ```
   - Self-contained HTML report:
     ```bash
     python3 "${CLAUDE_SKILL_DIR}/scripts/render_html_report.py" \
       .architect-state.json > architecture.html
     ```

Both visual artifacts go in the worktree root and are committed via:

```bash
git add architecture.mmd architecture.html
git commit -m "docs(architect): self-verification artifacts"
```

Update state: `phase_completed: artifacts_emitted`.

---

## Phase 8 — Human gate + merge

The agent's cwd may be inside the worktree. Use `git -C "${MAIN_CHECKOUT}"`
so subsequent commands are cwd-independent.

Print:

1. The rubric scores (Phase 7.1)
2. The human-confirmation checklist (Phase 7.2)
3. Paths to `architecture.mmd` and `architecture.html`
4. The exact prompt:

```
Type `confirm architecture` to mark this architecture human-confirmed
(unlocks the implementation gate), or `revise` to iterate.
```

- `confirm architecture` →
  - Update `.architect-state.json`: set `phase_completed: human_confirmed`,
    record reviewer + ISO-8601 timestamp.
  - Commit:
    ```bash
    git add .architect-state.json
    git commit -m "chore(architect): human-confirmed architecture (unlocks implementation)"
    ```
  - Then prompt:
    ```
    Type `confirm merge` to merge architect/<slug>-<id> into <BASE_BRANCH>,
    or `keep` to leave the worktree intact for further iteration.
    ```
  - On `confirm merge`:
    ```bash
    git -C "${MAIN_CHECKOUT}" checkout "${BASE_BRANCH}"
    git -C "${MAIN_CHECKOUT}" merge --no-ff "architect/${PROJECT_SLUG}-${ARCHITECT_ID}" \
      -m "feat(architect): merge ${PROJECT_SLUG} architecture (interfaces only, human-confirmed)"
    ```
    The explicit `-m` is mandatory — without it git drops into `$EDITOR`
    and hangs in non-interactive use. **Do not** `git push` — that is the
    user's call.
- `revise` → leave worktree intact, return to relevant phase.
- Anything else → re-ask.

After a successful merge, ask: "Remove the worktree at `.worktrees/...`?"
On yes: `git -C "${MAIN_CHECKOUT}" worktree remove <path>` (no `--force`).
On no: leave it.

---

## Implementation gate (downstream contract)

Skills, subagents, and Claude sessions that intend to write
**implementation** code (method bodies for the interfaces this skill
emitted) MUST first read `.architect-state.json` from the project root.
If `phase_completed` is not exactly `human_confirmed`, REFUSE to write
implementation and ask the user to complete `/codebase-architect` first.

This is the single source of truth for the gate. The skill itself
enforces it via documented refusal in this section; downstream
automation honors it by checking the file.

---

## Forbidden actions

The skill must refuse to execute any of these even if the user requests
them mid-flow (politely surface the forbidden item and ask for
confirmation to deviate, but default to refusal):

- `git push`, `git push --force`
- `git merge` without the `--no-ff` flag for the architect branch
- `git merge` or `git commit` without the `-m` flag (would hang on `$EDITOR`)
- `git reset --hard`, `git clean -f`, `git worktree remove --force`
- `--no-verify` on commits (pre-commit hooks must run)
- Generating method bodies (implementation) — defer to a separate task
  outside this skill, gated by `.architect-state.json: human_confirmed`
- Hardcoded language/framework versions in any generated file
- Treating user silence as confirmation at any gate
- Creating `README.md`, `INSTALLATION_GUIDE.md`, etc. inside this skill folder
- Writing fewer than the 9 docstring fields on any generated method

---

## Resumability

If re-invoked from inside an existing architect worktree
(`inside-architect-worktree`), read `.architect-state.json` and resume
from the next phase after `phase_completed`. See
[state-and-resume.md](references/state-and-resume.md) for the full
mapping.

If `inside-architect-worktree` but no state file → refuse and ask the
user to either delete the worktree or supply a state file.
