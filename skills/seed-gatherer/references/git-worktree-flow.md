# Git worktree flow for seed-gatherer

Mirrors `intent-aligner`, `codebase-planner`, and `codebase-implementer`
exactly to keep mental overhead low for maintainers familiar with those
skills.

## Worktree path + branch name

```
.worktrees/seed-<intent-slug>-<id>/   ← physical path
seed/<intent-slug>-<id>                 ← branch name
```

`<id>` is `date +%s | tail -c 6`-`$$`-`${RANDOM}` — short epoch suffix +
shell PID + RANDOM. The PID distinguishes host-shell runs; `$RANDOM`
covers PID-namespaced containers where `$$` is always `1`.

`<intent-slug>` is the slug of the chosen `intent.<slug>.md` from
Phase 1. It's already sanitized by intent-aligner (lowercase ASCII,
hyphens, ≤40 chars), so Phase 4 doesn't re-sanitize — but does
double-check for empty/whitespace/path-traversal defensively.

## Base branch resolution

Default `BASE_BRANCH=dev`. If `dev` doesn't exist:

| State | Action |
|---|---|
| `main`/`master` exists, `dev` doesn't | inspector emits `state: on-default-needs-dev`; SKILL.md Phase 0 runs the dialog "Create dev from `<default_branch>`? Or pick a different base?" |
| Neither exists | inspector emits `state: unrelated`; refuse — repo isn't shaped for this skill |

Whatever branch results becomes `BASE_BRANCH` and is persisted in
`.seed-state.json` for Phase 4 worktree creation and Phase 6 merge.

## `on-default-needs-dev` dialog

```
`dev` branch not found. Options:
  1) Create dev from <default_branch> (recommended)
  2) Use a different base branch (specify name, must already exist)
  3) Abort — let me set up dev myself first
Type 1, 2 <branch-name>, or abort.
```

If option 1: run BOTH commands — creating the branch alone leaves the
checkout on `<default_branch>`, and the inspector would then return
`on-nonbase-main-checkout` (not `on-dev`), trapping bootstrap:

```bash
git -C "${MAIN_CHECKOUT}" branch dev "${DEFAULT_BRANCH}"
git -C "${MAIN_CHECKOUT}" checkout dev
```

Then re-run the inspector to confirm `on-dev`.

## Edge cases (always stop and ask, never auto-resolve)

### Path collision

`.worktrees/seed-<intent-slug>-<id>` already exists. Likely a partial
prior run for the same intent. Surface what's there and ask: "Resume
that one (read its `.seed-state.json`), or pick a different intent
slug and start fresh?"

### Dirty BASE_BRANCH

`git -C "${MAIN_CHECKOUT}" status --porcelain` is non-empty on
`${BASE_BRANCH}`. Refuse to create the worktree until the user
commits/stashes/discards. Show the dirty paths so the user can decide.

### Nested invocation

The user re-runs `/seed-gatherer` while already inside a seed
worktree. Phase 0 detects this as `inside-seed-worktree`. If
`.seed-state.json` is present → resume per
[state-and-resume.md](state-and-resume.md). Otherwise refuse and ask
the user to either remove the worktree or supply a state file.

### Untracked files in worktree on resume

Resume mode finds untracked files inside the worktree that aren't in
the state file (other than the expected `.seed-state.json` and any
already-emitted `seeds/seed.*.{md,html}`). Refuse, list the unexpected
files, and ask the user to either delete them or commit them as a
separate concern before proceeding.

### Merge conflicts at Phase 6

Seed branch can't fast-forward or 3-way merge cleanly into
`${BASE_BRANCH}`. Most likely cause: a prior seed run for the same
intent merged a `seeds/seed.<intent-slug>.<resource-slug>.md` with the
same resource slug. Refuse to merge. Surface the conflicts. Ask the
user to either: (a) update the seed branch with `git pull --rebase`
from a fresh checkout of `${BASE_BRANCH}` and resolve the slug
collision (see [seed-naming.md](seed-naming.md) — auto-suffix `-2`,
`-3`), or (b) abort the merge and decide manually. Do NOT use
`--strategy=ours` or any conflict-skipping flag.

### Default branch is `master`, not `main`

The inspector returns `default_branch=master`. Honor it for any
base-branch fallback dialog. The seed worktree itself still branches
from `dev` when present.

### Sibling seed run for the same intent

User has an in-flight seed worktree at
`.worktrees/seed-<intent-slug>-<id-A>/` and tries to start a new run
for the same intent. The new `<id-B>` differs so the path doesn't
collide, but two seed runs for the same intent at once usually means
the user lost track. Surface the existing path and ask explicitly:
*"There's already an in-flight seed run for `<intent-slug>` at
`<path>`. Resume that one, or start fresh under a new run id?"*

## Worktree creation command sequence

The exact sequence (executed only after Phase 3 `confirm seeds`):

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

# Step 1 — reuse SEED_RUN_ID from Phase 1 (stable across the entire run).
# INTENT_SLUG was loaded from intent.<slug>.md and is already sanitized
# to [a-z0-9-]+ by intent-aligner; positive whitelist re-checks defensively
# (catches whitespace, shell metachars, non-ASCII, and any future loosening
# of intent-aligner's sanitization).
INTENT_SLUG="<chosen-at-Phase-1>"
case "${INTENT_SLUG}" in
  ""|*[!a-z0-9-]*|-*) echo "BLOCKER: intent slug failed [a-z0-9-]+ whitelist: '${INTENT_SLUG}'"; exit 1 ;;
esac

git -C "${MAIN_CHECKOUT}" worktree add \
  ".worktrees/seed-${INTENT_SLUG}-${SEED_RUN_ID}" \
  -b "seed/${INTENT_SLUG}-${SEED_RUN_ID}" "${BASE_BRANCH}"

# Step 2 — cd into the worktree for all subsequent file ops
cd "${MAIN_CHECKOUT}/.worktrees/seed-${INTENT_SLUG}-${SEED_RUN_ID}"

# Step 3 — committed gitignore so .worktrees/ + .seed-state.json
# stay hidden after the merge to ${BASE_BRANCH}
for entry in '.worktrees/' '.seed-state.json'; do
  grep -qxF "${entry}" .gitignore 2>/dev/null \
    || echo "${entry}" >> .gitignore
done

# Step 4 — initial commit on the seed branch. Guard with diff-cached
# because on re-invocation after a prior seed merge, `.worktrees/` and
# `.seed-state.json` are already in the committed `.gitignore`. Step 3
# correctly no-ops in that case, so `git add` stages nothing and a bare
# `git commit` would fail with "nothing to commit" and abort the run.
# Phase 5's `feat(seeds): emit ...` commit becomes the first commit on
# the branch in that resumed-after-merge case; `git merge --no-ff` still
# proceeds normally.
git add .gitignore
if ! git diff --cached --quiet; then
  git commit -m "chore(seeds): initialize ${INTENT_SLUG} worktree"
fi
```

## Merge command sequence (Phase 6)

Run from a clean `MAIN_CHECKOUT`. Refuse if MAIN_CHECKOUT is dirty —
a long-running seed session can be overtaken by the user editing
`MAIN_CHECKOUT` in another shell, and a mid-merge checkout would
either fail or silently pull unrelated edits onto `${BASE_BRANCH}`:

```bash
if [ -n "$(git -C "${MAIN_CHECKOUT}" status --porcelain)" ]; then
  echo "BLOCKER: ${MAIN_CHECKOUT} has uncommitted changes on its current branch — refusing to merge. Commit/stash/discard first."
  git -C "${MAIN_CHECKOUT}" status --porcelain
  exit 1
fi
git -C "${MAIN_CHECKOUT}" checkout "${BASE_BRANCH}"
git -C "${MAIN_CHECKOUT}" merge --no-ff "seed/${INTENT_SLUG}-${SEED_RUN_ID}" \
  -m "feat(seeds): merge ${INTENT_SLUG} batch ${SEED_RUN_ID} (seeds, human-confirmed)"
```

Explicit `-m` is mandatory — without it git drops into `$EDITOR` and
hangs in non-interactive use. Do **not** `git push` — that's the user's
call.

After successful merge, ask: *"Remove the worktree at
`.worktrees/seed-${INTENT_SLUG}-${SEED_RUN_ID}`?"* On yes: first
`cd "${MAIN_CHECKOUT}"` (the agent's cwd is likely still inside the
worktree from Phase 4 step 2 — removing the worktree without `cd`
out first leaves the shell process with a deleted cwd). Then
`git -C "${MAIN_CHECKOUT}" worktree remove <path>` (no `--force`).
On no: leave it.

## Forbidden git operations

Inherits the global rules from CLAUDE.md:

- No `git push`, `git push --force`
- No `git reset --hard`, `git clean -f`, `git worktree remove --force`
- No `git merge` without `--no-ff` for the seed branch
- No `git merge` or `git commit` without `-m` (would hang on `$EDITOR`)
- No `--no-verify` on commits
- No `git commit --amend` once a commit lands on the seed branch —
  create a new commit instead, even if the previous was trivially
  wrong. Amend rewrites history that `--no-ff` was meant to preserve.
