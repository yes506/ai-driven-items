---
name: codebase-implementer
description: |
  Implement the code bodies that a prior `codebase-planner` run gated as
  human-confirmed. Reads the scale-tagged planner handoff (micro / local
  / feature / system), creates its own git worktree, generates
  implementation bodies autonomously across all phases (no per-step
  confirmation), runs the project's compile+test command with bounded
  auto-fix, emits a self-verification report, and merges to the base
  branch only after the user types `confirm merge`. Language-agnostic.
  Body-generation only — does NOT re-architect, refactor, or
  re-classify scale. Manual invocation only — `/codebase-implementer`.
disable-model-invocation: true
---

# Codebase Implementer

## Overview

Execute the plan that `codebase-planner` produced. The implementer is
the **downstream half** of the planner→implementer chain: it consumes
the planner's scale-tagged, human-confirmed handoff and turns it into
working code.

| Scale lane | Upstream marker | Worktree | Artifacts produced | Downstream marker |
|---|---|---|---|---|
| **micro** | `(plan-micro, human-confirmed)` (chat) | yes | impl + `report.<impl-id>.md` | `(impl-micro, human-confirmed)` |
| **local** | `(plan-local, human-confirmed)` (chat) | yes | impl + `report.<impl-id>.md` | `(impl-local, human-confirmed)` |
| **feature** | `(plan-feature, human-confirmed)` (commit) | yes | impl + `report.<impl-id>.md` | `(impl-feature, human-confirmed)` |
| **system** | `(interfaces only, human-confirmed)` (commit; preserved verbatim from pre-rename `codebase-architect` for backward compat) | yes | impl + `report.<impl-id>.md` | `(impl-system, human-confirmed)` |

The implementer accepts both the new `(plan-<scale>, human-confirmed)`
family AND the `(interfaces only, human-confirmed)` marker (preserved
verbatim for backward compat; treated as `scale=system`). See
[references/marker-detection.md](references/marker-detection.md) for
the full gate-check rubric.

**Autonomy boundary**: the implementer runs Phases 0-5 without
per-step user prompts. The ONLY pauses are (a) genuine blockers per
[references/implementation-loop.md](references/implementation-loop.md),
and (b) the final `confirm merge` gate at Phase 6.

**Scope discipline**: body-generation only. NO re-architecting, NO
refactoring committed interfaces, NO scale re-classification, NO
"polish" of code the loop didn't write. See
[references/forbidden-actions.md](references/forbidden-actions.md).

`disable-model-invocation: true` because the skill has heavy side
effects (writes code, runs git, creates worktrees, merges branches).
Never auto-trigger.

## Workflow Decision Tree

```
Phase L:  Dialog language (preamble) — see references/language-selection.md
Phase 0:  Repo state + marker verification ──┬─ on-base-with-marker ───────── proceed (Phase 1)
                                             ├─ on-base-no-marker ─────────── refuse unless micro/local chat-gate passes
                                             ├─ on-default-needs-dev ──────── refuse — re-run planner
                                             ├─ on-nonbase-main-checkout ──── refuse unless micro/local chat-gate
                                             ├─ inside-implementer-worktree ─ resume from .implementer-state.json
                                             ├─ inside-planner-worktree ───── refuse — finish planner run first
                                             ├─ inside-legacy-architect-wt ── refuse — finish/discard legacy run
                                             ├─ inside-other-worktree ─────── refuse
                                             └─ unrelated ──────────────────── refuse
Phase 1:  Work-queue extraction (per scale, read-only)
Phase 2:  Worktree creation (FIRST mutation)
Phase 3:  Autonomous implementation loop (no per-step prompts)
Phase 4:  Validate + bounded auto-fix
Phase 5:  Self-verification artifact + commit
Phase 6:  Human gate + merge (ONLY user prompt: `confirm merge`)
```

State variables captured during Phases L–2 and threaded through later phases:

- `LANGUAGE` — dialog language (`Korean` default | `English`); captured at Phase L (preamble) per [references/language-selection.md](references/language-selection.md); held in memory through Phases 0–1, persisted at Phase 2
- `MAIN_CHECKOUT` — absolute path to the parent main worktree
- `BASE_BRANCH` — branch the implementer worktree branches from (default `dev`)
- `IMPLEMENTER_ID` — short suffix used in both worktree path and branch name
- `PROJECT_SLUG` — inherited from the planner merge subject when possible
- `SCALE` — `micro` | `local` | `feature` | `system` — derived from the marker
- `LANGUAGE_STACK` — detected at Phase 1 from root build files (planner's `.planner-state.json` is gitignored, so not portable across runs); persisted at Phase 2 once the worktree exists
- `VALIDATION_COMMAND` — full compile+test command (broader than the planner's compile-only); resolved at Phase 1 from the detected stack; persisted at Phase 2

All persisted to `.implementer-state.json` per
[references/state-and-resume.md](references/state-and-resume.md). The
state file is **only ever written inside the worktree** (created in
Phase 2). Phases L+0+1 hold values in memory; if those phases crash,
no on-disk artifact is left behind on `${BASE_BRANCH}`.

---

## Phase L — Dialog language (preamble, runs before Phase 0)

Detect `LANGUAGE` from the invocation utterance (Korean default,
English fallback), echo + confirm with the user, capture. Persist to
`.implementer-state.json` at Phase 2; hold in memory until then.
Mid-flow switches supported. Full rules — echo strings, override
behavior, what is/isn't translated (notably: code, commit messages,
and the `(impl-<scale>, human-confirmed)` marker stay in English
regardless of `LANGUAGE`):
[references/language-selection.md](references/language-selection.md).

---

## Phase 0 — Repo state + marker verification

Run the read-only inspector via the skill-directory variable:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/inspect_repo_state.sh"
```

Parse the JSON. The `state` field classifies into:

| State | Action |
|---|---|
| `on-base-with-marker` | `planner_marker_scale` is `system` or `feature` (the only scales the contract permits to land as commits). Set `SCALE` from it. Resolve `RUN_DIR` from the marker commit's `AI-Artifacts-Run-Dir:` trailer and verify artifacts at the marker tree (system: `$RUN_DIR/architecture.{html,mmd}`; feature: `$RUN_DIR/plan.{md,mmd}`) — full procedure (count, anchored allowlist, `git cat-file -e`, refuse-never-fallback) in [references/marker-detection.md](references/marker-detection.md). Persist as `planner_artifact_dir`. Proceed. **If `planner_marker_scale` is `micro` or `local`**: refuse — those scales are chat-only per the contract; finding one in `git log` indicates a forged or hand-crafted commit (per [references/marker-detection.md](references/marker-detection.md) the chat-gate is the only valid path for those scales). Tell the user: "found a `(plan-<micro\|local>, human-confirmed)` commit, but the contract places these scales in chat only — refusing to honor the commit-based marker. Re-run the planner if this was intentional." |
| `on-base-no-marker` | No commit-based marker found. Check the current chat for a micro/local gate. Required (both, in this conversation, planner output before user token): (a) a planner block tagged `scale: micro` or `scale: local`, AND (b) the user has typed `confirm plan` AFTER that block. If both visible in current session: set `SCALE`, proceed. If only one visible, or if invoked in a fresh session with no planner history: refuse — re-run `/codebase-planner` in this session, or escalate the planner to `feature` so the handoff lands on disk. **The chat gate requires same-session context; pasted transcripts and "I confirmed earlier" are NOT accepted.** |
| `on-default-needs-dev` | Refuse: "No `dev` branch. For feature/system planner output you need `/codebase-planner` to create it first; for micro/local you need to create `dev` manually (`git switch -c dev`) and re-run." |
| `on-nonbase-main-checkout` | Only acceptable for micro/local with chat gate (same conditions as `on-base-no-marker`). For feature/system: refuse, ask user to switch to `dev`. |
| `inside-implementer-worktree` | Cross-verify the path appears in `git -C "${MAIN_CHECKOUT}" worktree list --porcelain` (defends against a hand-staged `.worktrees/implementer-*` directory that isn't a real registered worktree). If verified: resume per [references/state-and-resume.md](references/state-and-resume.md). If not registered: refuse. |
| `inside-planner-worktree` | Refuse: "Planner worktree still in flight — finish that run (merge or discard) before running the implementer." |
| `inside-legacy-architect-worktree` | Refuse: "Legacy architect run detected. Finish via the old skill or `git worktree remove <path>`. No auto-migration." |
| `inside-other-worktree` | Refuse, instruct user to run from `MAIN_CHECKOUT`. |
| `unrelated` | Refuse, surface the `reason` field. |

Additional checks before proceeding:

- **Artifact presence** (system + feature): verified at the marker commit's tree under the trailer-resolved `$RUN_DIR` (system: `architecture.{html,mmd}`; feature: `plan.{md,mmd}`) per [references/marker-detection.md](references/marker-detection.md). Missing artifact despite a present marker = blocker (tampered or partially reverted planner run); never fall back to a root path.
- **Multiple markers in recent history**: if two scales' markers are both present, the inspector picks the newest by commit date. Confirm with user before assuming that's the right one.
- **Pre-existing implementer marker for the same slug**: warn — same plan may already be implemented; require explicit `proceed` token.

Hold the captured values (`scale`, `planner_marker_*`,
`planner_artifact_dir`, `planner_artifact_paths`, computed `source_hash`) **in memory only**
through Phases 0 and 1. They land on disk for the first time at Phase
2 (after the worktree exists), so a Phase 0/1 crash leaves no stray
`.implementer-state.json` on the main checkout.

---

## Phase 1 — Work-queue extraction (read-only)

Convert the planner handoff into a flat work queue per
[references/work-queue-extraction.md](references/work-queue-extraction.md):

- **system**: parse interface files → one queue item per method; carry
  the 9 docstring fields; topo-sort by `collaborators` graph
  (leaf-first).
- **feature**: parse `$RUN_DIR/plan.md` numbered steps → one item per
  step; use `$RUN_DIR/plan.mmd` for ordering if present.
- **micro / local**: parse the chat bullets → one item per bullet,
  source order preserved.

Each item is recorded (held in memory until Phase 2; see
[references/state-and-resume.md](references/state-and-resume.md))
with `status: pending` and a `spec_payload` holding the raw planner
content. Empty queue = refusal.

The detected language stack drives the `VALIDATION_COMMAND` capture.
Detect by checking root-level build files: `pom.xml` /
`build.gradle*` → Java, `pyproject.toml` / `setup.py` → Python,
`tsconfig.json` → TypeScript (or JavaScript with a TS migration
note), `go.mod` → Go, `Cargo.toml` → Rust. If a monorepo with
multiple build files, ask the user once which stack to operate on;
refuse to operate on multiple stacks in a single run. If `unknown`,
ask the user once. Pick the matching `VALIDATION_COMMAND` per
[references/validation-and-autofix.md](references/validation-and-autofix.md)
("Validation command — provenance").

Both `work_queue` and the captured `language_stack` /
`validation_command` are still in memory at end of Phase 1. They are
written to `.implementer-state.json` for the first time at Phase 2.

---

## Phase 2 — Worktree creation (first mutation)

Order matters — execute only after Phases 0+1 succeeded. See
[references/git-worktree-flow.md](references/git-worktree-flow.md) for
the full command sequence; summary:

```bash
# Step 0 — local exclude. CRITICAL: --git-common-dir returns a RELATIVE path on
# older git; use --path-format=absolute (git ≥ 2.31) with fallback, otherwise
# the exclude lands at "<cwd>/.git/info/exclude" not MAIN_CHECKOUT's.
COMMON_DIR="$(git -C "${MAIN_CHECKOUT}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || git -C "${MAIN_CHECKOUT}" rev-parse --git-common-dir)"
case "${COMMON_DIR}" in /*) ;; *) COMMON_DIR="${MAIN_CHECKOUT}/${COMMON_DIR}" ;; esac
grep -qxF '.worktrees/' "${COMMON_DIR}/info/exclude" || echo '.worktrees/' >> "${COMMON_DIR}/info/exclude"

# Step 1 — compute IMPLEMENTER_ID once; interpolate consistently.
# `tail -c 6` returns at most 6 bytes (including newline); command substitution
# strips the trailing newline, so the captured value is 5 ASCII digits — safe
# to embed in branch/path names.
IMPLEMENTER_ID="$(date +%s | tail -c 6)-$$-${RANDOM}"
raw_slug="<from-planner-commit-subject-or-user>"
# Sanitization order: lowercase → strip non-[a-z0-9-] → strip leading dash
# (a leading dash would be misread by `git worktree add -b "-foo"` as a flag) →
# collapse consecutive dashes → cap at 40 chars to keep path lengths sane.
PROJECT_SLUG="$(printf '%s' "${raw_slug}" \
  | tr 'A-Z' 'a-z' \
  | tr -cd 'a-z0-9-' \
  | sed -e 's/^-*//' -e 's/-\{2,\}/-/g' -e 's/-*$//' \
  | cut -c1-40)"
[ -z "${PROJECT_SLUG}" ] && { echo "empty slug after sanitization — ask user for an ASCII slug"; exit 1; }

git -C "${MAIN_CHECKOUT}" worktree add \
  ".worktrees/implementer-${PROJECT_SLUG}-${IMPLEMENTER_ID}" \
  -b "implementer/${PROJECT_SLUG}-${IMPLEMENTER_ID}" "${BASE_BRANCH}"

# Step 2 — cd into the worktree for all subsequent file ops
cd "${MAIN_CHECKOUT}/.worktrees/implementer-${PROJECT_SLUG}-${IMPLEMENTER_ID}"

# Step 3 — committed gitignore so .worktrees/ + .implementer-state.json stay hidden
for entry in '.worktrees/' '.implementer-state.json'; do
  grep -qxF "${entry}" .gitignore 2>/dev/null \
    || echo "${entry}" >> .gitignore
done
```

Then:

- Record baseline validation exit: run `${VALIDATION_COMMAND}` on the
  fresh worktree HEAD (which is `${BASE_BRANCH}` content). Save
  `baseline_validation_exit` (0 = clean; non-zero = pre-existing
  failures the implementer is NOT responsible for fixing).
- If baseline is non-zero, surface to user once: "Baseline validation
  is failing. The implementer will not treat fixing those as in-scope;
  blocker semantics still apply for any new regressions. Continue?" —
  require `proceed` token. Default refusal.
- Estimate validation duration; if >10min, drop `max_autofix_attempts`
  to 1 (per [references/validation-and-autofix.md](references/validation-and-autofix.md)).

Edge cases (path collision, dirty `BASE_BRANCH`, nested invocation,
untracked files on resume, merge conflicts at Phase 6) are documented
in [references/git-worktree-flow.md](references/git-worktree-flow.md).
Always stop and ask — never auto-resolve.

Persist: `project_slug`, `main_checkout`, `base_branch`,
`implementer_id`, `language_stack`, `validation_command`,
`baseline_validation_exit`, `max_autofix_attempts`,
`phase_completed: worktree_created`.

---

## Phase 3 — Autonomous implementation loop

Iterate `work_queue` in order. For each item:

1. Mark `status: in_progress`, write `started_at`.
2. Load context: target file, neighbors, collaborators.
3. Generate the body / change per the item's spec (rules in
   [references/implementation-loop.md](references/implementation-loop.md)).
4. Apply via `Edit` / `Write` (never shell `sed`).
5. Mark `status: completed`, write `files_touched` + `completed_at`.
6. Print one progress line: `implemented item <i>/<N>: <item_id>`.

**No per-step user prompts.** The autonomy budget is the queue itself.

**Blocker triggers** (the only allowed pause): missing collaborator,
impossible postcondition, failure-mode contradicts language idiom,
plan refers to nonexistent file, validation auto-fix exhausted,
source-hash mismatch on resume, scope-expansion required, conflicting
concurrent edits. Full enumeration in
[references/implementation-loop.md](references/implementation-loop.md).
On blocker: stop, mark `status: blocked` with `blocker_reason`, set
`phase_completed: impl_in_progress` (so resume picks up at the next
pending item after the user resolves the blocker), print the
diagnostic format, exit cleanly.

Commit cadence — commit after every Nth completed item (default N=5)
OR at end-of-queue, whichever comes first. Stage **only** the
`files_touched` paths from the just-completed items (not `git add
-A`), and run a secrets sniff against the staged diff before
committing. Use a bash array (NOT a space-joined string — paths with
spaces would word-split):

```bash
# Build FILES_TOUCHED_THIS_BATCH as a bash array from
# work_queue[*].files_touched of items completed in this batch:
#   FILES_TOUCHED_THIS_BATCH=(); FILES_TOUCHED_THIS_BATCH+=("$path") ...
git add -- "${FILES_TOUCHED_THIS_BATCH[@]}"

# Secrets sniff — fail closed. Covers both quoted ("apikey = '...'") and
# unquoted .env-style (APIKEY=...) forms; fixed-prefix tokens (AKIA, ghp_,
# sk_live_, xox-, AIza); PEM/PGP private keys; JWTs; OAuth client_secret;
# Slack webhooks; DSN URLs. False-positive rate ~10% on auth code;
# false-negative bounded — layer trufflehog / detect-secrets / gitleaks
# on top (forbidden-actions.md calls this a floor, not a ceiling).
SECRETS_PATTERN='(api[_-]?keys?[[:space:]]*[=:][[:space:]]*['"'"'"][A-Za-z0-9._/+-]{16,}|api[_-]?keys?[[:space:]]*=[[:space:]]*[A-Za-z0-9/_+-]{20,}|secret[_-]?(key|token)[[:space:]]*[=:][[:space:]]*['"'"'"][A-Za-z0-9._/+-]{16,}|secret[_-]?(key|token)[[:space:]]*=[[:space:]]*[A-Za-z0-9/_+-]{20,}|password[[:space:]]*[=:][[:space:]]*['"'"'"][^'"'"'"[:space:]]{6,}|password[[:space:]]*=[[:space:]]*[A-Za-z0-9/_+-]{8,}|client_secret[[:space:]]*[=:][[:space:]]*['"'"'"]?[A-Za-z0-9._/+-]{16,}|bearer[[:space:]]+[A-Za-z0-9._-]{20,}|aws_(access_key_id|secret_access_key|session_token)|AKIA[A-Z0-9]{16}|ghp_[A-Za-z0-9]{36}|sk_(live|test)_[A-Za-z0-9]{16,}|xox[abprs]-[A-Za-z0-9-]+|hooks\.slack\.com/services/[A-Z0-9]{8,}/[A-Z0-9]{8,}/[A-Za-z0-9]{20,}|-----BEGIN[[:space:]]+(RSA[[:space:]]+|EC[[:space:]]+|OPENSSH[[:space:]]+|PGP[[:space:]]+)?PRIVATE[[:space:]]+KEY|"private_key"[[:space:]]*:[[:space:]]*"-----BEGIN|AIza[0-9A-Za-z_-]{35}|eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}|(postgres|mysql|mongodb(\+srv)?|redis)://[^:/@[:space:]]+:[^@[:space:]]+@)'

if git diff --cached -U0 | grep -E -i "${SECRETS_PATTERN}" >/dev/null; then
  echo "BLOCKER: candidate secret in staged diff — refusing to commit. Inspect manually."
  git diff --cached -U0 | grep -E -i -n "${SECRETS_PATTERN}" | head -10
  exit 1
fi

git commit -m "feat(implementer): items <range> for ${PROJECT_SLUG}"
```

This keeps the implementer branch reviewable as a sequence of small
commits, and prevents `.env` / scratch files / leaked credentials from
sliding in via `git add -A`.

Persist after every sub-step. `phase_completed: impl_done` when queue
is empty (no pending items); `phase_completed: impl_in_progress` if
the loop exited due to a blocker mid-queue.

---

## Phase 4 — Validate + bounded auto-fix

Run `${VALIDATION_COMMAND}`. On non-zero exit, enter the auto-fix
loop bounded by `max_autofix_attempts` (default 3).

```
attempt = 1
while attempt <= max_autofix_attempts:
  1. Capture stderr+stdout (cap at 200 tail lines)
  2. Diagnose: which queue items' files are implicated?
  3. Generate fix(es), constrained to those files
  4. Apply, commit:
     git commit -m "fix(implementer): autofix attempt ${attempt}"
  5. Re-run validation; exit 0 → done
  attempt += 1
```

Auto-fix scope discipline mirrors the main loop (same prohibitions on
re-architecting, signature changes, test-relaxing). See
[references/validation-and-autofix.md](references/validation-and-autofix.md).

If budget exhausted: emit the blocker format (last command, exit code,
implicated items, attempted fixes, suggested next steps), exit
cleanly. **Do NOT merge. Do NOT clean up the worktree.**

Persist per attempt: append to `validation_runs[]`. On success:
`phase_completed: validated`.

---

## Phase 5 — Self-verification artifact + commit

Emit the report at `${REPORT_PATH}` (`mkdir -p` its dir first; path
resolution per lane in [references/state-and-resume.md](references/state-and-resume.md), "Report path"). Required sections:

```markdown
# Implementation report — ${PROJECT_SLUG}

## Source
- Planner marker: <scale> from commit <sha-short> (or "chat" for micro/local)
- Planner artifacts: <list>
- Source hash: <sha256-short>

## Work queue summary
- Total items: <N>
- Completed: <M>
- Blocked: <K> (with reasons)

## Files changed
<bullet list of relative paths with line-count deltas>

## Validation
- Baseline exit (BASE_BRANCH HEAD): <code>
- Final validation command: <cmd>
- Final exit: <code>
- Auto-fix attempts used: <i>/<max>
- Tail of last run (20 lines): <fenced block>

## Per-item outcomes
<table: item_id | status | files_touched | notes>

## Scope-discipline self-check
- [ ] No new interfaces / files outside hints
- [ ] No renames of committed public names
- [ ] No signature changes on planner-committed methods
- [ ] No edits to validation_command configuration
- [ ] No edits to files outside the work queue's hint set
```

Commit:

```bash
git add -- "${REPORT_PATH}"
git commit -m "docs(implementer): self-verification report"
```

Persist: `phase_completed: report_emitted`.

---

## Phase 6 — Human gate + merge

The agent's cwd may be inside the worktree. Use `git -C
"${MAIN_CHECKOUT}"` so subsequent commands are cwd-independent.

Print:

1. The Phase 5 report (or the path to it)
2. The final validation outcome (exit 0 expected)
3. The exact prompt:

```
Type `confirm merge` to merge implementer/<slug>-<id> into <BASE_BRANCH>
with marker (impl-<scale>, human-confirmed),
or `keep` to leave the worktree intact for further iteration,
or `revise` to address something before merging.
```

Behavior per response:

- `confirm merge` →
  Before checkout, refuse if `MAIN_CHECKOUT`'s current branch has any
  uncommitted changes (a long-running implementer run can be overtaken
  by the user editing `MAIN_CHECKOUT` in another shell — `git checkout
  "${BASE_BRANCH}"` would either fail mid-way on conflicting files, or
  silently carry the unrelated dirty edits onto `${BASE_BRANCH}` if
  they don't conflict, then pull them into the merge change-set):

  ```bash
  if [ -n "$(git -C "${MAIN_CHECKOUT}" status --porcelain)" ]; then
    echo "BLOCKER: ${MAIN_CHECKOUT} has uncommitted changes on its current branch — refusing to merge. Commit/stash/discard first."
    git -C "${MAIN_CHECKOUT}" status --porcelain
    exit 1
  fi
  git -C "${MAIN_CHECKOUT}" checkout "${BASE_BRANCH}"
  git -C "${MAIN_CHECKOUT}" merge --no-ff "implementer/${PROJECT_SLUG}-${IMPLEMENTER_ID}" \
    -m "feat(implementer): merge ${PROJECT_SLUG} (impl-${SCALE}, human-confirmed)"
  ```
  The explicit `-m` is mandatory. Do NOT `git push`.

  After successful merge, ask: "Remove the worktree at
  `.worktrees/implementer-${PROJECT_SLUG}-${IMPLEMENTER_ID}`?" On yes:
  `git -C "${MAIN_CHECKOUT}" worktree remove <path>` (no `--force`).
  On no: leave it.

- `revise` → leave worktree intact, ask the user **which** phase to
  re-enter (Phase 3 to re-implement specific items, Phase 4 to re-run
  validation, Phase 5 to regenerate the report). Do not guess.
- `keep` → leave worktree intact, no merge, exit cleanly.
- Anything else → re-ask. Silence is not yes.

Persist: `phase_completed: human_confirmed`.

---

## Upstream gate (planner contract)

Skills, subagents, and Claude sessions that intend to RUN this skill
MUST have a `codebase-planner` handoff with the scale-tagged marker
documented in
[references/marker-detection.md](references/marker-detection.md). The
implementer refuses without it.

Reciprocally, downstream tooling (CI, review skills) can grep
`git log` for `(impl-<scale>, human-confirmed)` to detect implementer
landings — that's the contract this skill offers to consumers further
down the chain.

---

## Forbidden actions

Full enumeration in
[references/forbidden-actions.md](references/forbidden-actions.md).
The load-bearing rules — refuse even if user asks mid-flow:

- `git push`, `git push --force`, `git reset --hard`, `git clean -f`,
  `git worktree remove --force`
- `git merge` without `--no-ff` for the implementer branch
- `git merge` or `git commit` without `-m`
- `--no-verify` on commits; `git commit --amend` after a commit lands
- Adding new interfaces / files outside `files_hinted`; renaming
  committed public names; changing planner-committed signatures
- Re-classifying scale mid-run; "polishing" code the loop didn't write
- Editing `validation_command` configuration to skip failing tests
- Treating user silence as confirmation at any gate
- Generating bodies without a planner marker (or chat-gate for
  micro/local)
- Auto-running the planner to manufacture a missing marker
- Hardcoded language/framework versions in any generated file

---

## Resumability

If re-invoked from inside an existing implementer worktree
(`inside-implementer-worktree`), read `.implementer-state.json` and
resume from the next phase after `phase_completed`. See
[references/state-and-resume.md](references/state-and-resume.md) for
the full resume map.

If `inside-implementer-worktree` but no state file → refuse and ask
the user to either remove the worktree (`git worktree remove`, NOT
`--force`) or supply a state file.

If `source_hash` no longer matches the planner artifacts (planner was
re-run since extraction): blocker — surface the diff, ask user
whether to re-extract (discards in-progress impl) or abort.
