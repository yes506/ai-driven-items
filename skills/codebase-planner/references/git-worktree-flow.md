# Git worktree flow for codebase-planner

Mirrors `project-scaffolder`'s flow exactly to keep mental overhead low
for maintainers familiar with that skill.

## Worktree path + branch name

```
.worktrees/planner-<project-slug>-<id>/   ← physical path
planner/<project-slug>-<id>                 ← branch name
```

`<id>` is `date +%s | tail -c 6`-`$$`-`${RANDOM}` — short epoch
suffix + shell PID + RANDOM. The PID distinguishes host-shell runs;
`$RANDOM` covers PID-namespaced containers where `$$` is always `1`.
`<project-slug>` is a short ASCII identifier for the project being
architected (e.g., `order-service`, `analytics-pipeline`) — lowercase,
hyphens only, no spaces or path separators. Phase 4 sanitizes it
defensively (see the shell snippet there) — a slug like `../etc` is
collapsed to `etc` so it can't escape `.worktrees/`.

## Base branch resolution

Default `BASE_BRANCH=dev`. If `dev` doesn't exist:

| State | Action |
|---|---|
| `main`/`master` exists, `dev` doesn't | inspector emits `state: on-default-needs-dev`; SKILL.md Phase 0 runs the dialog "Create dev from `<default_branch>`? Or pick a different base?" |
| Neither exists | refuse — repo isn't shaped for this skill |

Whatever branch results becomes `BASE_BRANCH` and is persisted in
`.planner-state.json` for Phase 4 worktree creation and Phase 8 merge.

If `dev` exists only on `origin` (not local), the inspector currently
returns `unrelated, not_on_dev_in_main_checkout`; ask the user to
either `git fetch origin && git switch dev` first or pick a different
base via the dialog above.

## Edge cases (always stop and ask, never auto-resolve)

### Path collision

`.worktrees/planner-<slug>-<id>` already exists. Likely a partial prior
run. Surface what's there and ask: "Resume that one (read its
`.planner-state.json`), or pick a different slug?"

### Dirty BASE_BRANCH

`git -C "${MAIN_CHECKOUT}" status --porcelain` is non-empty on
`${BASE_BRANCH}`. Refuse to create the worktree until the user
commits/stashes/discards. Show the dirty paths so the user can decide.

### Nested invocation

The user re-runs `/codebase-planner` while already inside a planner
worktree. Phase 0 detects this as `inside-planner-worktree`. If
`.planner-state.json` is present → resume per
[state-and-resume.md](state-and-resume.md). Otherwise refuse and ask the
user to either remove the worktree or supply a state file.

### Untracked files in worktree on resume

Resume mode finds untracked files inside the worktree that aren't in
the state file's manifest. Refuse, list the unexpected files, and ask
the user to either delete them or commit them as a separate concern
before proceeding.

### Merge conflicts at Phase 8

Planner branch can't fast-forward or 3-way merge cleanly into
`${BASE_BRANCH}`. Refuse to merge. Surface the conflicts. Ask the user
to either: (a) update the planner branch with `git pull --rebase`
from a fresh checkout of `${BASE_BRANCH}` and re-run Phase 8, or
(b) abort the merge and decide manually. Do NOT use `--strategy=ours`
or any conflict-skipping flag.

### Default branch is `master`, not `main`

The inspector returns `default_branch=master`. Honor it for any base-branch
fallback dialog. The planner worktree itself still branches from `dev`
when present.

### Missing `dev` locally but present on `origin`

The inspector reports no local `dev` branch. Check `git branch -r` for
`origin/dev`. If found, dialog: "dev is on origin but not local. Fetch
and create local tracking branch (`git fetch origin && git switch dev`),
or treat as `on-default-needs-dev` and run the create-dev dialog above?"

## Worktree creation command sequence

The exact sequence (executed only after Phase 3 confirmation):

```bash
# Step 0 — local exclude so .worktrees/ doesn't dirty status. Resolve
# common-dir via git so the exclude lands on the real .git even if
# MAIN_CHECKOUT is itself a linked worktree. CRITICAL: --git-common-dir
# returns a RELATIVE path on older git; use --path-format=absolute (git ≥
# 2.31) and fall back to manual absolutization.
COMMON_DIR="$(git -C "${MAIN_CHECKOUT}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null \
              || git -C "${MAIN_CHECKOUT}" rev-parse --git-common-dir)"
case "${COMMON_DIR}" in /*) ;; *) COMMON_DIR="${MAIN_CHECKOUT}/${COMMON_DIR}" ;; esac
grep -qxF '.worktrees/' "${COMMON_DIR}/info/exclude" \
  || echo '.worktrees/' >> "${COMMON_DIR}/info/exclude"

# Step 1 — reuse PLANNER_ID from Phase 0.5 (stable across the entire run).
# Rationale for the entropy source is documented in references/thought-publishing.md
# under "PLANNER_ID for all lanes" — do NOT recompute here.
PROJECT_SLUG="<short-project-slug>"
git -C "${MAIN_CHECKOUT}" worktree add \
  ".worktrees/planner-${PROJECT_SLUG}-${PLANNER_ID}" \
  -b "planner/${PROJECT_SLUG}-${PLANNER_ID}" "${BASE_BRANCH}"

# Step 2 — cd into the worktree for all subsequent file ops
cd "${MAIN_CHECKOUT}/.worktrees/planner-${PROJECT_SLUG}-${PLANNER_ID}"

# Step 3 — committed gitignore so .worktrees/ + .planner-state.json
# are hidden after the merge to ${BASE_BRANCH}
for entry in '.worktrees/' '.planner-state.json'; do
  grep -qxF "${entry}" .gitignore 2>/dev/null \
    || echo "${entry}" >> .gitignore
done
```

## Forbidden git operations

Inherits the global rules from CLAUDE.md:

- No `git push`, `git push --force`
- No `git reset --hard`, `git clean -f`, `git worktree remove --force`
- No `git merge` without `--no-ff` for the planner branch
- No `git merge` or `git commit` without `-m` (would hang on `$EDITOR`)
- No `--no-verify` on commits
- No `git commit --amend` once a commit lands on the planner branch
  — create a new commit instead, even if the previous was trivially
  wrong. Amend rewrites history that `--no-ff` was meant to preserve.
