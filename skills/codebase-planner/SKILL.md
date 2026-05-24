---
name: codebase-planner
description: |
  Decide how much planning a code change needs, then produce the right
  weight of plan — from a 3-bullet sketch for a small function to a
  fully decomposed interface-skeleton architecture with human gate.
  First-class decision is **planning scale** (micro / local / feature /
  system); lane drives whether a worktree is created, whether skeletons
  are emitted, and what downstream marker (if any) the implementer skill
  honors. Language-agnostic. Manual invocation only —
  `/codebase-planner`.
disable-model-invocation: true
---

# Codebase Planner

## Overview

Plan a code change at the **lightest sufficient weight** for the task.
The skill classifies the request into one of four scale lanes before
any mutation, then runs only the phases that lane needs.

| Scale lane | Worktree | Artifacts | Skeletons emitted | Downstream marker |
|---|---|---|---|---|
| **micro** | no | none | no | `(plan-micro, human-confirmed)` — chat only |
| **local** | no | none | no | `(plan-local, human-confirmed)` — chat only |
| **feature** | yes | `plan.md` + `plan.mmd` | optional (only on real cross-boundary contract) | `(plan-feature, human-confirmed)` |
| **system** | yes | `architecture.html` + `architecture.mmd` | yes (full interface skeletons + 9-field docstrings) | `(interfaces only, human-confirmed)` |

The system lane preserves the **full pre-rename `codebase-architect`
workflow verbatim** — worktree, Phase 5 interface skeletons, Phase 7
HTML rubric, merge marker. The other three lanes are progressively
lighter. See [triage-and-readiness.md](references/triage-and-readiness.md)
for the scoring tuple and [implementer-contract.md](references/implementer-contract.md)
for the downstream gate.

`disable-model-invocation: true` — the skill spans read-only (micro,
local) and side-effect (feature, system) lanes; uniform manual
invocation prevents mode confusion. Never auto-trigger.

**Thought publishing** — each meaningful checkpoint writes to canvas-terminal's
collab-memory for peer agents (silent no-op when no session resolves; spec, table, heredoc form: [thought-publishing.md](references/thought-publishing.md)).

## Workflow Decision Tree

```
Phase L:   Dialog language (preamble) — see references/language-selection.md
Phase 0:   Detect repo state ──┬─ on-dev-with-scaffold ─────┐
                               ├─ on-dev-no-scaffold ───────┤── feature/system: warn + ask; micro/local: proceed
                               ├─ on-default-needs-dev ─────┤── feature/system only: create-dev dialog
                               ├─ inside-planner-worktree ──┤── resume from .planner-state.json
                               ├─ inside-legacy-architect-worktree ── refuse, ask user to finish/discard legacy run
                               ├─ inside-other-worktree ────┤── refuse, run from MAIN_CHECKOUT
                               └─ unrelated ─────────────────── refuse, surface reason
Phase 0.5: Triage + readiness ─┬─ discovery (read CLAUDE.md, named files, callers, git log)
                               ├─ score tuple (scope, risk, ambiguity)
                               └─ pick lane: micro | local | feature | system
                                  │
                                  └─→ per-lane phases below; full rubric in references/triage-and-readiness.md
```

State variables captured during Phase 0/0.5 and threaded through later phases:

- `MAIN_CHECKOUT` — absolute path to the parent main worktree
- `BASE_BRANCH` — branch the planner worktree branches from (default `dev`); only used by feature+system lanes
- `PLANNER_ID` — stable run handle; computed at Phase 0.5 for ALL lanes (drives collab-memory checkpoints; reused as worktree/branch suffix in feature+system Phase 4)
- `LANGUAGE_STACK` — detected from build files; drives Phase 5/6 commands (feature+system only)
- `LANGUAGE` — dialog language (`Korean` default | `English`); captured at Phase L (preamble) per [references/language-selection.md](references/language-selection.md); persisted at Phase 4 for feature+system, memory-only for micro+local
- `SCALE` — `micro` | `local` | `feature` | `system` — chosen in Phase 0.5

---

## Phase L — Dialog language (preamble, runs before Phase 0)

Detect `LANGUAGE` from invocation utterance (Korean default, English fallback), echo + confirm. Persist at Phase 4 (feature+system); memory-only otherwise. Spec — including resume + mid-flow switches: [references/language-selection.md](references/language-selection.md).

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
| `on-dev-with-scaffold` | on `dev`, project-scaffolder marker commit present | proceed to Phase 0.5 |
| `on-dev-no-scaffold` | on `dev` but no `chore(scaffold): initialize` commit in history | for feature/system lanes: warn + ask. For micro/local: proceed (scaffold not needed). Lane is decided at Phase 0.5 — defer this branch until then |
| `on-default-needs-dev` | on `main`/`master`, but `dev` does not exist locally | for feature/system lanes: run the "create dev from `<default_branch>`?" dialog from [git-worktree-flow.md](references/git-worktree-flow.md). For micro/local: skip — no worktree will be created |
| `on-nonbase-main-checkout` | in main checkout, on a non-`dev` non-default branch (e.g. a feature branch) | for micro/local lanes: **proceed** — they're read-only and don't need a worktree. For feature/system: refuse and ask user to switch to `dev` (or run with explicit `BASE_BRANCH` override via the dialog) |
| `inside-planner-worktree` | cwd is inside an `*/.worktrees/planner-*` worktree (root or subdirectory) | resume from `.planner-state.json` if present, else refuse |
| `inside-legacy-architect-worktree` | cwd is inside an `*/.worktrees/architect-*` worktree from the pre-rename `codebase-architect` skill | refuse with clear message: "legacy architect-run detected. Finish it via the old skill if still installed, or `git worktree remove <path>` to discard. No auto-migration." |
| `inside-other-worktree` | inside a non-planner linked worktree | refuse, instruct user to run from `MAIN_CHECKOUT` |
| `unrelated` | not in a git repo, detached HEAD, repo with no commits, or some other branch | refuse, surface the `reason` field from the JSON to the user |

Capture from JSON: `MAIN_CHECKOUT`, `default_branch`. Set `BASE_BRANCH`
to `dev` by default for feature/system lanes (configurable via dialog
if the user objects); micro/local lanes don't use `BASE_BRANCH`.

Detect language stack (feature/system lanes only — defer if the Phase 0.5
classifier picks micro/local):

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

**Gate**: capture `MAIN_CHECKOUT` + `default_branch` before Phase 0.5.
`BASE_BRANCH` + `LANGUAGE_STACK` are decided lazily once Phase 0.5
picks a lane (only feature/system need them).

---

## Phase 0.5 — Triage & readiness

See [triage-and-readiness.md](references/triage-and-readiness.md) for
full rubric, discovery rule, and worked examples.

1. **Discovery first** (no user questions yet): read CLAUDE.md /
   AGENTS.md / README.md, every file the user named, grep call sites +
   tests, `git log -n 20 --oneline -- <path>`. Surface what you found.
2. **Score** `(scope, risk, ambiguity)` each 0–3, with reasoning shown.
3. **Resolve lane**: `final_scale = max(scope, risk)` →
   `micro` (0) / `local` (1) / `feature` (2) / `system` (3).
4. **Block if `ambiguity >= 2` AND `final_scale <= 1`**: one
   consolidated question round; re-score with answers. No silent
   upgrades.
5. Print classification, prompt `confirm scale` / suggest different
   lane (upgrade free; downgrade needs `confirm downgrade`) / `revise`.
6. Compute `PLANNER_ID="$(date +%s | tail -c 6)-$$-${RANDOM}"`; publish each
   checkpoint via `${CLAUDE_SKILL_DIR}/scripts/publish_thought.sh` (**heredoc body** per [thought-publishing.md](references/thought-publishing.md)).

Persist `SCALE` and the three scores to `.planner-state.json`
(feature/system only — micro/local create no state file).

**After Phase 0.5:**
- micro / local → "Lightweight lanes" below
- feature → Phase 1 (decomposition + `plan.md` / `plan.mmd`; see
  [self-verification.md](references/self-verification.md))
- system → Phase 1 (full pipeline below, Phases 1–8 unchanged)

---

## Lightweight lanes (micro & local)

Read-only. No worktree, no commits, no skeleton, no state file. Chat is
the entire artifact. The 9-field docstring schema does NOT apply.

1. **Verbal-only ingestion** — chat request is the plan; don't ask for
   files/URLs (see [plan-ingestion.md](references/plan-ingestion.md)).
2. **3–7 bullet plan reflection** — touched files, logical steps,
   validation/test plan, risks. No Mermaid DAG.
3. **Prompt** `confirm plan` / `revise` / `escalate`. On each prompt publish
   `light/plan` via `publish_thought.sh "${PLANNER_ID}" light plan` (**heredoc
   body required** per [thought-publishing.md](references/thought-publishing.md) — a bare call writes an empty body).
4. **Hand-off marker on confirm** — one chat line:
   `scale: <micro|local>   marker: (plan-<lane>, human-confirmed)`.
   Downstream implementer reads this from chat per
   [implementer-contract.md](references/implementer-contract.md).
   Also publish `8/outcome` (body = the marker line; heredoc per thought-publishing.md).

Concurrency: stateless on disk; the implementer pairs planner-output
and confirm token by chat-adjacency, so two parallel micro/local runs
in one conversation should be paired carefully (see implementer-contract.md).

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

0. **Locally** ignore `.worktrees/` in the main checkout (rationale + path-format fallback: [git-worktree-flow.md](references/git-worktree-flow.md)):
   ```bash
   COMMON_DIR="$(git -C "${MAIN_CHECKOUT}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || git -C "${MAIN_CHECKOUT}" rev-parse --git-common-dir)"
   case "${COMMON_DIR}" in /*) ;; *) COMMON_DIR="${MAIN_CHECKOUT}/${COMMON_DIR}" ;; esac
   grep -qxF '.worktrees/' "${COMMON_DIR}/info/exclude" || echo '.worktrees/' >> "${COMMON_DIR}/info/exclude"
   ```
1. **Reuse `PLANNER_ID`** from Phase 0.5 (stable across the entire run):
   ```bash
   # Sanitize PROJECT_SLUG defensively: lowercase → strip non-[a-z0-9-] →
   # strip leading dash (else `git worktree add -b "-foo"` is misread as
   # a flag) → collapse consecutive dashes → cap at 40 chars.
   raw_slug="<short-project-slug>"   # captured from user
   PROJECT_SLUG="$(printf '%s' "${raw_slug}" | tr 'A-Z' 'a-z' | tr -cd 'a-z0-9-' | sed -e 's/^-*//' -e 's/-\{2,\}/-/g' -e 's/-*$//' | cut -c1-40)"
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

## Phase 5 — Interface skeleton generation (system + feature-with-contract)

For each interface from Phase 3, generate a language-appropriate
abstraction (interface / Protocol / trait / etc.) per
[language-skeletons.md](references/language-skeletons.md).

**Feature-lane branch**: if `SCALE == feature`, Phase 5 fires only when
Phase 3 detected a real cross-boundary contract AND the user explicitly
typed `emit skeletons`. Otherwise skip Phase 5 entirely and proceed to
Phase 7 with plan-only artifacts. See
[feature-lane.md](references/feature-lane.md) for the full conditional.

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

**Python placeholder + monorepo paths**: see
[language-skeletons.md](references/language-skeletons.md); never `mypy --strict .` the worktree root.
**Feature lane with skeletons skipped**: no compile target — validation moves into Phase 7 as a header + Mermaid smoke check
([feature-lane.md](references/feature-lane.md)).

If validation fails: stop, report failure, **never auto-prune the
worktree**. Update `.planner-state.json` `phase_completed: validated`
on success.

---

## Phase 7 — Self-verification artifacts

Outputs per [self-verification.md](references/self-verification.md)
(system defaults; feature deltas in
[feature-lane.md](references/feature-lane.md)): rubric (4-point × 6
criteria — drop "Docstring quality"+"Interface cohesion" for feature
without skeletons), checklist, visual artifacts. The Mermaid renderer
escapes interface names against `click ... href` injection.

```bash
case "${SCALE}" in
  system)  ARTIFACTS="architecture.mmd architecture.html"; MARKER="(interfaces only, human-confirmed)"
           python3 "${CLAUDE_SKILL_DIR}/scripts/render_mermaid_dag.py" .planner-state.json > architecture.mmd
           python3 "${CLAUDE_SKILL_DIR}/scripts/render_html_report.py" .planner-state.json > architecture.html ;;
  feature) ARTIFACTS="plan.mmd plan.md";                   MARKER="(plan-feature, human-confirmed)"
           python3 "${CLAUDE_SKILL_DIR}/scripts/render_mermaid_dag.py" .planner-state.json > plan.mmd ;;
esac
```

**Agent step (feature only, not shell)**: compose `plan.md` per
feature-lane.md and run smoke-check (headers + Mermaid parse) before:

```bash
git add ${ARTIFACTS}
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
3. Paths to the artifacts emitted in Phase 7 (`${ARTIFACTS}` — `architecture.mmd`+`.html` for system, `plan.mmd`+`plan.md` for feature)
4. The exact prompt:

```
Type `confirm plan` to mark this planner output human-confirmed
(unlocks the implementation gate), or `revise` to iterate.
```

- `confirm plan` →
  - Update `.planner-state.json` **locally** (file is gitignored —
    used for resume tracking only): set
    `phase_completed: human_confirmed`, record reviewer + ISO-8601
    timestamp.
  - The canonical confirmation record on the planner branch is the
    Phase 7 commit of `${ARTIFACTS}` (already in place) plus the Phase 8
    merge commit message `feat(planner): merge ... ${MARKER}` that
    follows next. There is intentionally NO separate
    `.planner-state.json` commit — the file is gitignored on the
    worktree's `.gitignore`, so `git add` of it is a silent no-op and
    `git commit` would fail with "nothing to commit". Downstream
    automation looks at the tracked artifacts and the merge commit
    instead (see "Implementation gate" below).
  - Then prompt:
    ```
    Type `confirm merge` to merge planner/<slug>-<id> into <BASE_BRANCH>,
    or `keep` to leave the worktree intact for further iteration.
    ```
  - On `confirm merge` (uses the `${MARKER}` set in Phase 7):
    ```bash
    git -C "${MAIN_CHECKOUT}" checkout "${BASE_BRANCH}"
    git -C "${MAIN_CHECKOUT}" merge --no-ff "planner/${PROJECT_SLUG}-${PLANNER_ID}" \
      -m "feat(planner): merge ${PROJECT_SLUG} ${MARKER}"
    ```
    For system this expands to `... merge <slug> (interfaces only,
    human-confirmed)`; for feature, `... merge <slug> (plan-feature,
    human-confirmed)`. The explicit `-m` is mandatory — without it git
    drops into `$EDITOR` and hangs in non-interactive use. **Do not**
    `git push` — that is the user's call.
- `revise` → leave worktree intact, return to relevant phase.
- Anything else → re-ask.

After a successful merge, ask: "Remove the worktree at `.worktrees/...`?"
On yes: `git -C "${MAIN_CHECKOUT}" worktree remove <path>` (no `--force`).
On no: leave it.

After any prompt resolves (outer `confirm plan`/`revise`, inner `confirm merge`/`keep`;
"Anything else → re-ask" is NOT a resolution), publish `8/outcome` via `publish_thought.sh "${PLANNER_ID}" 8 outcome` (heredoc per [thought-publishing.md](references/thought-publishing.md)).

---

## Implementation gate (downstream contract)

Skills, subagents, and Claude sessions that intend to write
**implementation** code based on a planner run MUST honor the
**scale-tagged marker family** documented in
[implementer-contract.md](references/implementer-contract.md). Summary:

| Scale | Marker | Where to find it | Files to check |
|---|---|---|---|
| micro | `(plan-micro, human-confirmed)` | chat history | — |
| local | `(plan-local, human-confirmed)` | chat history | — |
| feature | `(plan-feature, human-confirmed)` | `git log` merge commit | `plan.md` + `plan.mmd` |
| system | `(interfaces only, human-confirmed)` | `git log` merge commit | `architecture.html` + `architecture.mmd` |

The system marker is preserved verbatim from the pre-rename
`codebase-architect` skill; downstream automation that already greps
for it continues to work. Lower scales are additive.

**Honest limitations**: the gate is a documented social contract, not
cryptographic. A determined user can fake marker files / commit
messages; the goal is catching accidental misuse and making deliberate
bypass visible in git history. Stronger enforcement (signed commits,
git notes, external attestation) is out of scope — layer on top, do
not replace.

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
- Generating method bodies — defer to the implementer skill (gated by
  the tracked artifacts + merge marker per "Implementation gate" above,
  NOT by `.planner-state.json` which is gitignored local working state)
- Hardcoded language/framework versions in any generated file
- Treating user silence as confirmation at any gate
- Creating `README.md`, `INSTALLATION_GUIDE.md`, etc. inside this skill folder
- Writing fewer than the 9 docstring fields on any generated method
  (feature+system lanes only — micro/local emit no methods)

---

## Resumability

If re-invoked from inside an existing planner worktree
(`inside-planner-worktree`), read `.planner-state.json` and resume
from the next phase after `phase_completed`. See
[state-and-resume.md](references/state-and-resume.md) for the full
mapping.

If `inside-planner-worktree` but no state file → refuse and ask the
user to either delete the worktree or supply a state file.
