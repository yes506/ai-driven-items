#!/usr/bin/env bash
# inspect_repo_state.sh — read-only repo state inspector for codebase-planner.
# Emits a single JSON line on stdout. Never mutates anything.

set -euo pipefail

# Escape a string for safe JSON-string interpolation: backslash, quote, control chars.
jesc() {
  printf '%s' "${1:-}" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])'
}

emit() { printf '%s\n' "$1"; exit 0; }

build_json() {
  local state="$1" reason="${2:-}"
  local reason_field=""
  [ -n "${reason}" ] && reason_field=",\"reason\":\"$(jesc "${reason}")\""
  printf '{"state":"%s"%s,"main_checkout":"%s","default_branch":"%s","current_branch":"%s","dev_exists":%s,"scaffold_marker_present":%s}\n' \
    "${state}" "${reason_field}" \
    "$(jesc "${MAIN_CHECKOUT:-}")" \
    "$(jesc "${DEFAULT_BRANCH:-}")" \
    "$(jesc "${CURRENT_BRANCH:-}")" \
    "${DEV_EXISTS:-false}" "${SCAFFOLD_MARKER_PRESENT:-false}"
}

# 1. Inside any git repo?
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  MAIN_CHECKOUT="" DEFAULT_BRANCH="" CURRENT_BRANCH="" DEV_EXISTS=false SCAFFOLD_MARKER_PRESENT=false
  emit '{"state":"unrelated","reason":"not_in_git_repo","main_checkout":null,"default_branch":null,"current_branch":null,"dev_exists":false,"scaffold_marker_present":false}'
fi

# 2. Worktree info — derive MAIN_CHECKOUT from the *physical* parent of git-common-dir.
#    `pwd -P` resolves symlinks (e.g. macOS /tmp -> /private/tmp) so the result
#    matches `git rev-parse --show-toplevel`, which always emits physical paths.
GIT_COMMON_DIR="$(git rev-parse --git-common-dir 2>/dev/null)"
GIT_COMMON_DIR_ABS="$(cd "$(dirname "${GIT_COMMON_DIR}")" && pwd -P)/$(basename "${GIT_COMMON_DIR}")"
MAIN_CHECKOUT="$(dirname "${GIT_COMMON_DIR_ABS}")"

# 3. Current branch — symbolic-ref handles detached HEAD and empty-repo states cleanly,
#    and (unlike rev-parse) returns a single line or fails silently.
if CURRENT_BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null)"; then
  : # real branch name captured
else
  # Detached HEAD or zero-commits repo — distinguishable but treat as a single bucket.
  CURRENT_BRANCH="DETACHED"
fi
# Defensive: collapse any stray whitespace/newlines that would corrupt JSON.
CURRENT_BRANCH="$(printf '%s' "${CURRENT_BRANCH}" | tr -d '\r\n\t')"

# Zero-commits guard — hoisted ABOVE the branch-name dispatch in step 8 so
# that an unborn `dev`/`main`/`master` branch (created via `git init -b dev`
# or similar) is correctly classified as `repo_has_no_commits` rather than
# being short-circuited into the `on-dev-no-scaffold` / `on-default-needs-dev`
# paths. symbolic-ref above succeeded with the unborn branch name, so the
# DETACHED bucket below also doesn't catch this case — must be checked here.
# 4-reviewer round-3 convergence (D1).
if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  DEFAULT_BRANCH=""
  DEV_EXISTS=false
  SCAFFOLD_MARKER_PRESENT=false
  emit "$(build_json unrelated repo_has_no_commits)"
fi

# 4. Default branch (main / master) — read from MAIN_CHECKOUT, not cwd.
DEFAULT_BRANCH=""
for candidate in main master; do
  if git -C "${MAIN_CHECKOUT}" show-ref --verify --quiet "refs/heads/${candidate}" 2>/dev/null; then
    DEFAULT_BRANCH="${candidate}"
    break
  fi
done

# 5. Does dev exist locally?
DEV_EXISTS=false
if git -C "${MAIN_CHECKOUT}" show-ref --verify --quiet "refs/heads/dev" 2>/dev/null; then
  DEV_EXISTS=true
fi

# 6. Worktree-root for path classification — works even when cwd is a subdirectory.
WORKTREE_TOP="$(git rev-parse --show-toplevel 2>/dev/null || echo '')"
IS_LINKED_WORKTREE=false
if [ -n "${WORKTREE_TOP}" ] && [ "${WORKTREE_TOP}" != "${MAIN_CHECKOUT}" ]; then
  IS_LINKED_WORKTREE=true
fi

# 7. Scaffold marker — search commit messages on LOCAL branches only.
#    Using `--branches` (not `--all`) avoids false positives from stale
#    remote-tracking refs that may carry a force-pushed-over scaffold commit
#    no longer reachable from any live branch.
#    Use git's native --grep + output capture (not `| grep -q`); under `pipefail`,
#    `grep -q` short-circuits and gives `git log` SIGPIPE, which propagates as a
#    pipeline failure and silently miscategorizes existing scaffold commits.
SCAFFOLD_MARKER_PRESENT=false
if [ -n "$(git -C "${MAIN_CHECKOUT}" log --branches --grep='chore(scaffold): initialize' --format=%H 2>/dev/null)" ]; then
  SCAFFOLD_MARKER_PRESENT=true
fi

# 8. Classify
if [ "${IS_LINKED_WORKTREE}" = "true" ]; then
  case "${WORKTREE_TOP}" in
    */.worktrees/planner-*)  emit "$(build_json inside-planner-worktree)" ;;
    *)                          emit "$(build_json inside-other-worktree)" ;;
  esac
fi

# Main checkout — classify by current branch + dev presence + scaffold marker.
if [ "${CURRENT_BRANCH}" = "dev" ]; then
  if [ "${SCAFFOLD_MARKER_PRESENT}" = "true" ]; then
    emit "$(build_json on-dev-with-scaffold)"
  else
    emit "$(build_json on-dev-no-scaffold)"
  fi
fi

if [ "${CURRENT_BRANCH}" = "DETACHED" ]; then
  emit "$(build_json unrelated detached_head)"
fi

# (Zero-commits guard now lives above step 4 so the dev-branch dispatch can't
#  short-circuit it for repos initialized via `git init -b dev`.)

# On the default branch but `dev` doesn't exist — surface so Phase 0 can run the
# "create dev from <default_branch>?" dialog from references/git-worktree-flow.md.
if [ -n "${DEFAULT_BRANCH}" ] && [ "${CURRENT_BRANCH}" = "${DEFAULT_BRANCH}" ] && [ "${DEV_EXISTS}" = "false" ]; then
  emit "$(build_json on-default-needs-dev)"
fi

emit "$(build_json unrelated not_on_dev_in_main_checkout)"
