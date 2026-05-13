---
name: codebase-planner
description: |
  Plan a project's package/directory layout and emit interface-only
  language-appropriate skeletons (Java interface / Python Protocol /
  TypeScript interface / Go interface / Rust trait) with a structured
  9-field docstring on every method, BEFORE any implementation begins.
  Sequences after `project-scaffolder`. Runs entirely inside an isolated
  git worktree and emits a human-confirmation gate (rubric self-review +
  checklist + Mermaid DAG + HTML report) that downstream skills/agents
  must observe before generating implementation code. Language-agnostic.
  Manual invocation only — `/codebase-planner`.
disable-model-invocation: true
---

# Codebase Planner

## Overview

Plan packages and emit interface-only skeletons for a project that has
already been baseline-scaffolded (typically by `project-scaffolder`).
Every method on every emitted interface represents one node in the
end-to-end pipeline; interfaces aggregate cohesive methods that share a
responsibility/lifecycle. No implementation may begin until this skill
commits the Phase 7 architecture artifacts (`architecture.html` +
`architecture.mmd`) and lands the planner-merge commit on
`${BASE_BRANCH}` carrying the `(interfaces only, human-confirmed)`
marker — see "Implementation gate (downstream contract)" below for the
canonical check. (`.planner-state.json` is gitignored local-only
working state for resume tracking, not a downstream gate signal.)

`disable-model-invocation: true` means this skill only fires on explicit
`/codebase-planner` invocation — never auto-trigger it.

## Workflow Decision Tree

```
Phase 0: Detect repo state ──┬─ on-dev-with-scaffold ──────┐
                             ├─ on-dev-no-scaffold ────────┤── warn + ask to proceed
                             ├─ on-default-needs-dev ──────┤── run "create dev?" dialog
                             ├─ inside-planner-worktree ─┤── resume from .planner-state.json
                             ├─ inside-other-worktree ─────┤── refuse, run from MAIN_CHECKOUT
                             └─ unrelated ──────────────── refuse, surface reason
                                                          │
Phase 1: Plan ingestion (no mutations) — multi-method input ─┤
Phase 2: Package/directory plan (no mutations) ──────────────┤
Phase 3: Pipeline-node decomposition (no mutations) ─────────┤
         user confirms Phases 1-3 individually — silence = stop, not yes
Phase 4: Worktree creation (first mutation; PLANNER_ID computed once;
         initial .planner-state.json written with phase_completed=worktree_created)
Phase 5: Interface skeleton generation + .planner-state.json (incremental)
Phase 6: Validate — language-appropriate compile/type-check on the skeleton
Phase 7: Self-verification artifacts — rubric + checklist + Mermaid DAG + HTML report
Phase 8: Human gate — `confirm plan` → mark human_confirmed locally
         then offer `confirm merge` → merge worktree to BASE_BRANCH
```

State variables captured during Phase 0 and threaded through later phases:

- `MAIN_CHECKOUT` — absolute path to the parent main worktree
- `BASE_BRANCH` — branch the planner worktree branches from (default `dev`)
- `PLANNER_ID` — short suffix used in both worktree path and branch name
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
| `on-default-needs-dev` | on `main`/`master`, but `dev` does not exist locally | run the "create dev from `<default_branch>`?" dialog from [git-worktree-flow.md](references/git-worktree-flow.md) |
| `inside-planner-worktree` | cwd is inside an `*/.worktrees/planner-*` worktree (root or subdirectory) | resume from `.planner-state.json` if present, else refuse |
| `inside-other-worktree` | inside a non-planner linked worktree | refuse, instruct user to run from `MAIN_CHECKOUT` |
| `unrelated` | not in a git repo, detached HEAD, repo with no commits, or some other branch | refuse, surface the `reason` field from the JSON to the user |

Capture from JSON: `MAIN_CHECKOUT`, `default_branch`. Set `BASE_BRANCH`
to `dev` by default (configurable via dialog if the user objects).

Detect language stack:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/detect_language_stack.sh"
```

Output gives `language` (primary recommendation: `java | python |
typescript | javascript | go | rust | unknown`), `validation_command`
for Phase 6, AND `detected_build_files` — a normalized list of stack
markers found at the project root. (Normalization: when both
`tsconfig.json` and `package.json` are present at the root, only
`tsconfig.json` is listed since the `package.json` is part of the
canonical TypeScript pairing, not a separate stack signal. Any other
combination of build files is reported verbatim.)

**Handle multi-build-file projects (monorepos)**: when
`detected_build_files` lists more than one entry (e.g. `pom.xml` AND
`package.json`), the primary recommendation alone will silently hide
the secondary stack. Ask the user explicitly which stack codebase-planner
should design for; if the user wants to cover both, surface that this
skill is single-stack per invocation and recommend running it twice in
separate worktrees, **with distinct project slugs per stack** (e.g.
`myproj-backend` for the Java side, `myproj-frontend` for the TS side)
— same slug across runs would collide on the worktree path.

If `language` is `unknown`, follow the dialog in
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
   planner work doesn't dirty `git status` on `${BASE_BRANCH}`:
   ```bash
   grep -qxF '.worktrees/' "${MAIN_CHECKOUT}/.git/info/exclude" \
     || echo '.worktrees/' >> "${MAIN_CHECKOUT}/.git/info/exclude"
   ```
1. Compute `PLANNER_ID` **once**, then interpolate consistently into
   both the path and the branch name. The `$$-$RANDOM` suffix gives
   true uniqueness — `$$` distinguishes within a host shell, `$RANDOM`
   covers PID-namespaced containers where `$$` is always `1`:
   ```bash
   PLANNER_ID="$(date +%s | tail -c 6)-$$-${RANDOM}"

   # Sanitize PROJECT_SLUG defensively before interpolation — even if
   # the user typed a clean value, this prevents path-traversal /
   # nested-ref bugs from a slug like '../../etc' or 'my/slug'.
   raw_slug="<short-project-slug>"   # captured from user
   PROJECT_SLUG="$(printf '%s' "${raw_slug}" | tr 'A-Z' 'a-z' | tr -cd 'a-z0-9-')"
   [ -z "${PROJECT_SLUG}" ] && { echo "Empty slug after sanitization — ask user for an ASCII slug"; exit 1; }

   git -C "${MAIN_CHECKOUT}" worktree add \
     ".worktrees/planner-${PROJECT_SLUG}-${PLANNER_ID}" \
     -b "planner/${PROJECT_SLUG}-${PLANNER_ID}" "${BASE_BRANCH}"
   ```
2. `cd` into the new worktree for all subsequent file operations.
3. Append `.worktrees/` and `.planner-state.json` to the **worktree's**
   `.gitignore` if either is missing. Lands on `${BASE_BRANCH}` via
   Phase 8's merge so future contributors never see those paths as
   untracked.
4. **Write the initial `.planner-state.json`** with
   `phase_completed: worktree_created`, plus `project_slug`,
   `main_checkout`, `base_branch`, `planner_id`, `language_stack`,
   `validation_command` from Phase 0. This is what makes resume work
   if the skill crashes between Phase 4 and Phase 5's first sub-step
   (without this initial write, Phase 0 on resume sees no state file
   and refuses).

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

Write `.planner-state.json` **incrementally** at the worktree root
after each sub-step per
[state-and-resume.md](references/state-and-resume.md), so a mid-run
failure stays resumable.

Initial commit on the planner branch (use the explicit `-m` form — a
bare `git commit` would drop into `$EDITOR` and hang in non-interactive
runs):

```bash
git add -A
git commit -m "chore(planner): initialize ${PROJECT_SLUG} interface skeleton (no implementation)"
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

**Python substitution**: `detect_language_stack.sh` emits
`mypy --strict <package>` as a template (with the `<package>`
placeholder). Before running, substitute `<package>` with the actual
package directory from Phase 2 (e.g. `mypy --strict src/myproj`).
**Never run `mypy --strict .` over the worktree root** — it picks up
generated artifacts, virtualenvs, and other noise that inflate false
failures.

If validation fails: stop, report failure, **never auto-prune the
worktree**. Update `.planner-state.json` `phase_completed: validated`
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
   - Mermaid dependency DAG (interface names are HTML-entity-escaped at
     emit time so malicious names in the state file cannot inject
     `click ... href` directives if the file is later rendered):
     ```bash
     python3 "${CLAUDE_SKILL_DIR}/scripts/render_mermaid_dag.py" \
       .planner-state.json > architecture.mmd
     ```
   - HTML report (fully self-contained — no CDN, no external scripts;
     the Mermaid block is inlined as plain text for the reviewer to
     paste into a renderer of their choice):
     ```bash
     python3 "${CLAUDE_SKILL_DIR}/scripts/render_html_report.py" \
       .planner-state.json > architecture.html
     ```

Both visual artifacts go in the worktree root and are committed via:

```bash
git add architecture.mmd architecture.html
git commit -m "docs(planner): self-verification artifacts"
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
Type `confirm plan` to mark this architecture human-confirmed
(unlocks the implementation gate), or `revise` to iterate.
```

- `confirm plan` →
  - Update `.planner-state.json` **locally** (file is gitignored —
    used for resume tracking only): set
    `phase_completed: human_confirmed`, record reviewer + ISO-8601
    timestamp.
  - The canonical confirmation record on the planner branch is the
    Phase 7 commit of `architecture.mmd` + `architecture.html` (already
    in place) plus the Phase 8 merge commit message
    `feat(planner): merge ... (interfaces only, human-confirmed)` that
    follows next. There is intentionally NO separate
    `.planner-state.json` commit — the file is gitignored on the
    worktree's `.gitignore`, so `git add` of it is a silent no-op and
    `git commit` would fail with "nothing to commit". Downstream
    automation looks at the architecture artifacts and the merge commit
    instead (see "Implementation gate" below).
  - Then prompt:
    ```
    Type `confirm merge` to merge planner/<slug>-<id> into <BASE_BRANCH>,
    or `keep` to leave the worktree intact for further iteration.
    ```
  - On `confirm merge`:
    ```bash
    git -C "${MAIN_CHECKOUT}" checkout "${BASE_BRANCH}"
    git -C "${MAIN_CHECKOUT}" merge --no-ff "planner/${PROJECT_SLUG}-${PLANNER_ID}" \
      -m "feat(planner): merge ${PROJECT_SLUG} architecture (interfaces only, human-confirmed)"
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
emitted) MUST first verify the planner phase has been merged. The
canonical check on the current branch:

```bash
test -f architecture.html && test -f architecture.mmd \
  && git log --grep='(interfaces only, human-confirmed)' --format=%H | grep -q .
```

If any part fails, REFUSE to write implementation and ask the user to
complete `/codebase-planner` first. The check is two-pronged:

- `architecture.html` + `architecture.mmd` exist on the current branch
  (they were committed at Phase 7 of a completed planner run)
- The planner-merge marker `(interfaces only, human-confirmed)`
  appears anywhere in `git log` history on the current branch — using
  `--grep` (not `git log -1`) so the gate continues to pass after
  unrelated commits land on top of the merge

**Honest limitations**: this gate is a documented social contract, not
a cryptographic one. A determined user can hand-craft the marker files
and a fake merge commit message to bypass the check; the goal is to
catch accidental misuse and make any deliberate bypass visible in git
history. Stronger physical enforcement (signed commits / git notes
verified against a maintainer key / external service) is out of scope
for this skill. If your downstream automation needs that, layer it on
top of this contract — do not replace it.

---

## Forbidden actions

The skill must refuse to execute any of these even if the user requests
them mid-flow (politely surface the forbidden item and ask for
confirmation to deviate, but default to refusal):

- `git push`, `git push --force`
- `git merge` without the `--no-ff` flag for the planner branch
- `git merge` or `git commit` without the `-m` flag (would hang on `$EDITOR`)
- `git commit --amend` once a commit has landed on the planner branch
  (create a new commit instead — amend rewrites history that the merge
  commit's `--no-ff` was meant to preserve)
- `git reset --hard`, `git clean -f`, `git worktree remove --force`
- `--no-verify` on commits (pre-commit hooks must run)
- Generating method bodies (implementation) — defer to a separate task
  outside this skill, gated by the tracked-artifacts + merge-marker
  check documented in "Implementation gate (downstream contract)" above
  (NOT by `.planner-state.json`, which is gitignored local working state)
- Hardcoded language/framework versions in any generated file
- Treating user silence as confirmation at any gate
- Creating `README.md`, `INSTALLATION_GUIDE.md`, etc. inside this skill folder
- Writing fewer than the 9 docstring fields on any generated method

---

## Resumability

If re-invoked from inside an existing planner worktree
(`inside-planner-worktree`), read `.planner-state.json` and resume
from the next phase after `phase_completed`. See
[state-and-resume.md](references/state-and-resume.md) for the full
mapping.

If `inside-planner-worktree` but no state file → refuse and ask the
user to either delete the worktree or supply a state file.
