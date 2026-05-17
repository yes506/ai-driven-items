# Git worktree flow for codebase-implementer

Mirrors the codebase-planner worktree flow (which itself mirrors
project-scaffolder) so maintainers see one consistent pattern. The only
differences vs the planner: path prefix (`implementer-` vs `planner-`),
branch prefix (`implementer/` vs `planner/`), state file
(`.implementer-state.json` vs `.planner-state.json`), and merge-marker
family (`(impl-<scale>, human-confirmed)`).

## Worktree path + branch name

```
.worktrees/implementer-<project-slug>-<id>/   ← physical path
implementer/<project-slug>-<id>                 ← branch name
```

`<id>` is `date +%s | tail -c 6`-`$$`-`${RANDOM}` — short epoch
suffix + shell PID + RANDOM. The PID distinguishes host-shell runs;
`$RANDOM` covers PID-namespaced containers where `$$` is always `1`.

`<project-slug>` is inherited from the planner run when possible. The
planner committed `feat(planner): merge <slug> <marker>`, so split
the merge-commit subject on whitespace and take the token immediately
after `merge` (3rd whitespace-separated token of the form above; the
1st is `feat(planner):`, the 2nd is `merge`). If unparseable (e.g.,
the pre-rename architect committed under a different subject
template), prompt the user for a slug at Phase 2. Sanitize
defensively:

```bash
raw_slug="<from-planner-commit-or-user>"
# Sanitization order: lowercase → strip non-[a-z0-9-] → strip leading and
# trailing dashes (leading `-` would be misread by `git worktree add -b "-foo"`
# as a flag) → collapse `--+` to `-` → cap length at 40 chars.
PROJECT_SLUG="$(printf '%s' "${raw_slug}" \
  | tr 'A-Z' 'a-z' \
  | tr -cd 'a-z0-9-' \
  | sed -e 's/^-*//' -e 's/-\{2,\}/-/g' -e 's/-*$//' \
  | cut -c1-40)"
[ -z "${PROJECT_SLUG}" ] && { echo "empty slug after sanitization — ask user for an ASCII slug"; exit 1; }
```

## Base branch resolution

Default `BASE_BRANCH=dev`. The implementer requires the planner marker
on `BASE_BRANCH` (feature/system) so the resolution rules are simpler
than the planner's: if `dev` doesn't exist locally the inspector
already returns `on-default-needs-dev` and the implementer refuses
(planner should have created it).

For micro/local lanes there's no commit-based marker — the chat-history
gate is what authorizes the run — but the worktree still branches from
`dev` if present, else from the default branch (`main`/`master`).

## Worktree creation command sequence

Executed only AFTER marker verification (Phase 0) and queue extraction
(Phase 1) have succeeded:

```bash
# Step 0 — local exclude. Resolve common-dir via git so the exclude lands on
# the real .git even if MAIN_CHECKOUT is itself a linked worktree. CRITICAL:
# --git-common-dir returns a RELATIVE path on older git; use
# --path-format=absolute (git ≥ 2.31) with manual absolutization fallback —
# otherwise the exclude appends to "<cwd>/.git/info/exclude", not MAIN_CHECKOUT's.
COMMON_DIR="$(git -C "${MAIN_CHECKOUT}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || git -C "${MAIN_CHECKOUT}" rev-parse --git-common-dir)"
case "${COMMON_DIR}" in /*) ;; *) COMMON_DIR="${MAIN_CHECKOUT}/${COMMON_DIR}" ;; esac
grep -qxF '.worktrees/' "${COMMON_DIR}/info/exclude" || echo '.worktrees/' >> "${COMMON_DIR}/info/exclude"

# Step 1 — compute IMPLEMENTER_ID once, interpolate consistently
IMPLEMENTER_ID="$(date +%s | tail -c 6)-$$-${RANDOM}"
PROJECT_SLUG="<sanitized>"
git -C "${MAIN_CHECKOUT}" worktree add \
  ".worktrees/implementer-${PROJECT_SLUG}-${IMPLEMENTER_ID}" \
  -b "implementer/${PROJECT_SLUG}-${IMPLEMENTER_ID}" "${BASE_BRANCH}"

# Step 2 — cd into the worktree for all subsequent file ops
cd "${MAIN_CHECKOUT}/.worktrees/implementer-${PROJECT_SLUG}-${IMPLEMENTER_ID}"

# Step 3 — committed gitignore so .worktrees/ + .implementer-state.json
# stay hidden after the merge
for entry in '.worktrees/' '.implementer-state.json'; do
  grep -qxF "${entry}" .gitignore 2>/dev/null \
    || echo "${entry}" >> .gitignore
done
```

## Edge cases (always stop and ask, never auto-resolve)

### Path collision

`.worktrees/implementer-<slug>-<id>` already exists. Likely a partial
prior run. Surface what's there and ask: "Resume that one (read its
`.implementer-state.json`), or pick a different slug?"

### Dirty BASE_BRANCH

`git -C "${MAIN_CHECKOUT}" status --porcelain` is non-empty on
`${BASE_BRANCH}`. Refuse to create the worktree until the user
commits/stashes/discards. Show the dirty paths.

### Nested invocation

The user re-runs `/codebase-implementer` while already inside an
implementer worktree. Phase 0 detects this as
`inside-implementer-worktree`. If `.implementer-state.json` is present
→ resume per [state-and-resume.md](state-and-resume.md). Otherwise
refuse and ask the user to either remove the worktree or supply a
state file.

### Inside a planner worktree

Inspector returns `inside-planner-worktree`. Refuse with: "Planner
worktree is still in flight — finish that one (merge or discard) before
running the implementer." The implementer relies on the planner
marker being on `${BASE_BRANCH}`; running from inside the planner's
own worktree would skip the gate.

### Untracked files in worktree on resume

Resume mode finds untracked files inside the worktree that aren't in
the state file's manifest. Refuse, list the unexpected files, and ask
the user to either delete them or commit them as a separate concern
before proceeding.

### Merge conflicts at Phase 6

Implementer branch can't fast-forward or 3-way merge cleanly into
`${BASE_BRANCH}`. Refuse to merge. Surface the conflicts. Ask the user
to either: (a) update the implementer branch with `git pull --rebase`
from a fresh checkout of `${BASE_BRANCH}` and re-run Phase 6, or
(b) abort the merge and decide manually. Do NOT use `--strategy=ours`
or any conflict-skipping flag.

### Pre-existing implementer marker for the same plan

`implementer_marker_present` is `true` AND the existing impl-marker
commit references the same `<slug>` we're about to use. Surface to
user: "Same plan appears already-implemented at `<impl commit>`.
Continuing will produce a second branch off current `${BASE_BRANCH}`.
This is supported (e.g., for revising), but rare — proceed only if
intentional. Type `proceed` to continue or `abort` to bail."

### Default branch is `master`, not `main`

Honor it via the inspector's `default_branch` field. The implementer
worktree still branches from `dev` when present.

## Forbidden git operations

Inherits the global rules from CLAUDE.md and from
[forbidden-actions.md](forbidden-actions.md):

- No `git push`, `git push --force`
- No `git reset --hard`, `git clean -f`, `git worktree remove --force`
- No `git merge` without `--no-ff` for the implementer branch
- No `git merge` or `git commit` without `-m` (would hang on `$EDITOR`)
- No `--no-verify` on commits
- No `git commit --amend` once a commit lands on the implementer branch
  — create a new commit instead, even if the previous was trivially
  wrong. Amend rewrites history that `--no-ff` was meant to preserve.

## Merge command at Phase 6

```bash
# Pre-merge dirty-check on the main checkout's CURRENT branch (whatever
# it is — not necessarily ${BASE_BRANCH}). A long-running implementer can
# be overtaken by the user editing files in MAIN_CHECKOUT in another shell;
# `git checkout ${BASE_BRANCH}` would either fail mid-way on conflicting
# files, or silently carry unrelated dirty edits across, then pull them
# into the merge change-set.
if [ -n "$(git -C "${MAIN_CHECKOUT}" status --porcelain)" ]; then
  echo "BLOCKER: ${MAIN_CHECKOUT} has uncommitted changes on its current branch — refusing to merge. Commit/stash/discard first."
  git -C "${MAIN_CHECKOUT}" status --porcelain
  exit 1
fi
git -C "${MAIN_CHECKOUT}" checkout "${BASE_BRANCH}"
git -C "${MAIN_CHECKOUT}" merge --no-ff "implementer/${PROJECT_SLUG}-${IMPLEMENTER_ID}" \
  -m "feat(implementer): merge ${PROJECT_SLUG} (impl-${SCALE}, human-confirmed)"
```

After successful merge, ask: "Remove the worktree at `.worktrees/...`?"
On yes: `git -C "${MAIN_CHECKOUT}" worktree remove <path>` (no
`--force`). On no: leave it.
