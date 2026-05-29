# Git worktree flow + edge cases

Phase 2 creates the implementer worktree. This file covers the
exact command sequence + every edge case the implementer must
handle without auto-resolution.

## Phase 2 — canonical sequence

```bash
# Step 0 — local exclude in main checkout's git common dir.
# CRITICAL: --git-common-dir returns a RELATIVE path on git < 2.31; use
# --path-format=absolute (git >= 2.31) with a fallback case-arm to absolutize.
COMMON_DIR="$(git -C "${MAIN_CHECKOUT}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || git -C "${MAIN_CHECKOUT}" rev-parse --git-common-dir)"
case "${COMMON_DIR}" in /*) ;; *) COMMON_DIR="${MAIN_CHECKOUT}/${COMMON_DIR}" ;; esac
grep -qxF '.worktrees/' "${COMMON_DIR}/info/exclude" || echo '.worktrees/' >> "${COMMON_DIR}/info/exclude"

# Step 1 — compute DOCIMPL_ID; sanitize INTENT_SLUG defensively.
# `tail -c 6` returns at most 6 bytes; command substitution strips the
# trailing newline → captured value is 5 ASCII digits, safe for branch/path.
DOCIMPL_ID="$(date +%s | tail -c 6)-$$-${RANDOM}"
raw_slug="${INTENT_SLUG}"
# Sanitize order: lowercase → strip non-[a-z0-9-] → strip leading dash (a
# leading `-` would be misread by `git worktree add -b "-foo"` as a flag) →
# collapse consecutive dashes → cap at 40 chars (keeps path lengths sane).
INTENT_SLUG="$(printf '%s' "${raw_slug}" \
  | tr 'A-Z' 'a-z' \
  | tr -cd 'a-z0-9-' \
  | sed -e 's/^-*//' -e 's/-\{2,\}/-/g' -e 's/-*$//' \
  | cut -c1-40)"
[ -z "${INTENT_SLUG}" ] && {
  echo "empty slug after sanitization — ask user for an ASCII slug"
  exit 1
}

# Step 2 — create the worktree + branch.
git -C "${MAIN_CHECKOUT}" worktree add \
  ".worktrees/docimpl-${INTENT_SLUG}-${DOCIMPL_ID}" \
  -b "docimpl/${INTENT_SLUG}-${DOCIMPL_ID}" "${BASE_BRANCH}"

# Step 3 — cd into the worktree for all subsequent file ops.
cd "${MAIN_CHECKOUT}/.worktrees/docimpl-${INTENT_SLUG}-${DOCIMPL_ID}"

# Step 4 — worktree-level gitignore. Lands on ${BASE_BRANCH} via Phase 6
# merge so future contributors never see .worktrees/ or the state file as
# untracked.
for entry in '.worktrees/' '.document-implementer-state.json'; do
  grep -qxF "${entry}" .gitignore 2>/dev/null || echo "${entry}" >> .gitignore
done
```

## Edge cases — stop and ask, never auto-resolve

### Path collision

`.worktrees/docimpl-${INTENT_SLUG}-${DOCIMPL_ID}/` already exists
(extremely unlikely given `DOCIMPL_ID` entropy, possible on
hand-crafted state):

1. Refuse to overwrite.
2. Ask the user whether to recompute `DOCIMPL_ID` and try again, OR
   remove the stale directory manually first.

### Dirty `BASE_BRANCH`

`git worktree add` fails if `BASE_BRANCH` has uncommitted changes.
Surface the failure verbatim. Do **NOT** auto-stash. Ask the user to
commit/stash manually.

### Nested invocation

The user invokes `/document-implementer` from inside an existing
`docimpl-*` worktree with a DIFFERENT intent slug. Inspector
classifies as `inside-document-implementer-worktree`, resume flow
expects matching state. The two intent_slugs won't match → refuse:

> "You're inside a docimpl-* worktree for a different intent. Either
> exit to MAIN_CHECKOUT first, or finish/discard the current
> implementer run."

### Untracked files on resume

The worktree has untracked files NOT covered by the worktree's
`.gitignore`. Could be the user's intentional notes OR accidental
half-written artifacts from a prior crash. Surface to the user
before resuming. Don't auto-`git clean`.

### Merge conflicts at Phase 6

`git merge --no-ff` fails with conflicts. Do **NOT** auto-resolve.
Print conflict status (`git status`), leave the worktree intact,
ask the user to resolve manually. The Phase 6 gate stays open until
the merge actually lands.

### `MAIN_CHECKOUT` dirty at Phase 6 (long-running impl race)

If the user edits MAIN_CHECKOUT in another shell during a
long-running implementer run, `git checkout "${BASE_BRANCH}"` from
Phase 6 could either fail mid-way on conflicting files OR silently
carry the unrelated dirty edits onto `${BASE_BRANCH}` if they don't
conflict. Defensive check (in SKILL.md Phase 6):

```bash
if [ -n "$(git -C "${MAIN_CHECKOUT}" status --porcelain)" ]; then
  echo "BLOCKER: ${MAIN_CHECKOUT} has uncommitted changes on its current branch."
  echo "Commit, stash, or discard them before merging the implementer worktree."
  git -C "${MAIN_CHECKOUT}" status --porcelain
  exit 1
fi
```

### Stale-remote planner marker

The planner marker scan in `inspect_repo_state.sh` uses `--branches`
(not `--all`) precisely because stale remote-tracking refs can
carry markers no longer reachable from a live local branch. If a
user has a stale `origin/dev` remote-tracking ref with an old marker
but their local `dev` doesn't, the inspector correctly does NOT
detect it. They must merge / pull to make it local first.

### Macos /tmp ↔ /private/tmp symlink

`pwd -P` resolves physical paths so `MAIN_CHECKOUT` matches
`git rev-parse --show-toplevel` (which always emits physical paths).
This is in `inspect_repo_state.sh` and not user-visible, but it's
why both scripts use `pwd -P` instead of `pwd`.

### macOS bash 3.2 — no associative arrays

The marker scan in `inspect_repo_state.sh` uses plain scalar
shadow-variables (`SYSTEM_COMMIT`, `FEATURE_COMMIT`, …) instead of
`declare -A`. Don't refactor to associative arrays without a guard
— macOS bash 3.2 lacks support and the script silently fails.

## After-merge cleanup

After a successful merge at Phase 6:

```bash
# Ask the user before removing the worktree (no --force).
git -C "${MAIN_CHECKOUT}" worktree remove ".worktrees/docimpl-${INTENT_SLUG}-${DOCIMPL_ID}"
```

If the user types `keep` instead, leave the worktree intact. They
can prune later with `git worktree remove` themselves.

## Honest limitations

- `git worktree` requires git ≥ 2.5; older versions can't create
  linked worktrees. The implementer doesn't check the git version
  defensively; if `git worktree add` fails on an old version, the
  user will see the native git error.
- The `.worktrees/` convention is a project-level choice (matches
  document-planner and codebase-implementer). If a project moves
  worktrees elsewhere, the inspector's classification regexes
  (`*/.worktrees/docimpl-*`) won't match and the implementer will
  refuse with `inside-other-worktree`.
