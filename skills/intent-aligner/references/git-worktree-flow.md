# Git worktree flow for intent-aligner

Mirrors `codebase-planner` and `codebase-implementer` exactly to keep
mental overhead low for maintainers familiar with those skills.

## Worktree path + branch name

```
.worktrees/intent-<project-slug>-<id>/   ← physical path
intent/<project-slug>-<id>                 ← branch name
```

`<id>` is `date +%s | tail -c 6`-`$$`-`${RANDOM}` — short epoch suffix +
shell PID + RANDOM. The PID distinguishes host-shell runs; `$RANDOM`
covers PID-namespaced containers where `$$` is always `1`.

`<project-slug>` is a short ASCII identifier captured from the user at
Phase 3 (e.g., `slow-builds`, `payments-dashboard`). Phase 4 sanitizes
it defensively (see the shell snippet in SKILL.md Phase 4) — a slug
like `../etc` is collapsed to `etc` so it cannot escape `.worktrees/`.

## Base branch resolution

Default `BASE_BRANCH=dev`. If `dev` doesn't exist:

| State | Action |
|---|---|
| `main`/`master` exists, `dev` doesn't | inspector emits `state: on-default-needs-dev`; SKILL.md Phase 0 runs the dialog "Create dev from `<default_branch>`? Or pick a different base?" |
| Neither exists | inspector emits `state: unrelated`; refuse — repo isn't shaped for this skill |

Whatever branch results becomes `BASE_BRANCH` and is persisted in
`.intent-state.json` for Phase 4 worktree creation and Phase 6 merge.

## `on-default-needs-dev` dialog

```
`dev` branch not found. Options:
  1) Create dev from <default_branch> (recommended)
  2) Use a different base branch (specify name, must already exist)
  3) Abort — let me set up dev myself first
Type 1, 2 <branch-name>, or abort.
```

If option 1: `git -C "${MAIN_CHECKOUT}" branch dev "${DEFAULT_BRANCH}"`
then re-run the inspector to confirm `on-dev`.

## Edge cases (always stop and ask, never auto-resolve)

### Path collision

`.worktrees/intent-<slug>-<id>` already exists. Likely a partial prior
run. Surface what's there and ask: "Resume that one (read its
`.intent-state.json`), or pick a different slug?"

### Dirty BASE_BRANCH

`git -C "${MAIN_CHECKOUT}" status --porcelain` is non-empty on
`${BASE_BRANCH}`. Refuse to create the worktree until the user
commits/stashes/discards. Show the dirty paths so the user can decide.

### Nested invocation

The user re-runs `/intent-aligner` while already inside an intent
worktree. Phase 0 detects this as `inside-intent-worktree`. If
`.intent-state.json` is present → resume per
[state-and-resume.md](state-and-resume.md). Otherwise refuse and ask
the user to either remove the worktree or supply a state file.

### Untracked files in worktree on resume

Resume mode finds untracked files inside the worktree that aren't in
the state file. Refuse, list the unexpected files, and ask the user to
either delete them or commit them as a separate concern before
proceeding.

### Merge conflicts at Phase 6

Intent branch can't fast-forward or 3-way merge cleanly into
`${BASE_BRANCH}`. Refuse to merge. Surface the conflicts. Ask the user
to either: (a) update the intent branch with `git pull --rebase` from
a fresh checkout of `${BASE_BRANCH}` and re-run Phase 6, or (b) abort
the merge and decide manually. Do NOT use `--strategy=ours` or any
conflict-skipping flag.

### Default branch is `master`, not `main`

The inspector returns `default_branch=master`. Honor it for any
base-branch fallback dialog. The intent worktree itself still branches
from `dev` when present.

### Sibling intent run for the same slug

User has an in-flight intent worktree at
`.worktrees/intent-<slug>-<id-A>/` and tries to start a new run with
the same slug. The new `<id-B>` differs so the path doesn't collide,
but two intent runs for the same project at once is usually a mistake.
Surface the existing path and ask explicitly: "There's already an
in-flight intent run for `<slug>` at `<path>`. Resume that one, or
start fresh under a different slug?"

## Worktree creation command sequence

The exact sequence (executed only after Phase 3 `confirm intent`):

```bash
# Step 0 — local exclude so .worktrees/ doesn't dirty status. Resolve
# common-dir via git so the exclude lands on the real .git even if
# MAIN_CHECKOUT is itself a linked worktree. CRITICAL: --git-common-dir
# returns a RELATIVE path on older git; use --path-format=absolute (git >=
# 2.31) with fallback.
COMMON_DIR="$(git -C "${MAIN_CHECKOUT}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null \
              || git -C "${MAIN_CHECKOUT}" rev-parse --git-common-dir)"
case "${COMMON_DIR}" in /*) ;; *) COMMON_DIR="${MAIN_CHECKOUT}/${COMMON_DIR}" ;; esac
grep -qxF '.worktrees/' "${COMMON_DIR}/info/exclude" \
  || echo '.worktrees/' >> "${COMMON_DIR}/info/exclude"

# Step 1 — reuse INTENT_ID from Phase 1 (stable across the entire run).
# Sanitize PROJECT_SLUG defensively: lowercase -> strip non-[a-z0-9-] ->
# strip leading dash (else `git worktree add -b "-foo"` is misread as a
# flag) -> collapse consecutive dashes -> cap at 40 chars.
raw_slug="<captured-from-user-at-Phase-3>"
PROJECT_SLUG="$(printf '%s' "${raw_slug}" \
  | tr 'A-Z' 'a-z' \
  | tr -cd 'a-z0-9-' \
  | sed -e 's/^-*//' -e 's/-\{2,\}/-/g' -e 's/-*$//' \
  | cut -c1-40)"
[ -z "${PROJECT_SLUG}" ] && { echo "empty slug after sanitization — ask user for an ASCII slug"; exit 1; }

git -C "${MAIN_CHECKOUT}" worktree add \
  ".worktrees/intent-${PROJECT_SLUG}-${INTENT_ID}" \
  -b "intent/${PROJECT_SLUG}-${INTENT_ID}" "${BASE_BRANCH}"

# Step 2 — cd into the worktree for all subsequent file ops
cd "${MAIN_CHECKOUT}/.worktrees/intent-${PROJECT_SLUG}-${INTENT_ID}"

# Step 3 — committed gitignore so .worktrees/ + .intent-state.json
# stay hidden after the merge to ${BASE_BRANCH}
for entry in '.worktrees/' '.intent-state.json'; do
  grep -qxF "${entry}" .gitignore 2>/dev/null \
    || echo "${entry}" >> .gitignore
done
```

## Forbidden git operations

Inherits the global rules from CLAUDE.md:

- No `git push`, `git push --force`
- No `git reset --hard`, `git clean -f`, `git worktree remove --force`
- No `git merge` without `--no-ff` for the intent branch
- No `git merge` or `git commit` without `-m` (would hang on `$EDITOR`)
- No `--no-verify` on commits
- No `git commit --amend` once a commit lands on the intent branch —
  create a new commit instead, even if the previous was trivially
  wrong. Amend rewrites history that `--no-ff` was meant to preserve.
