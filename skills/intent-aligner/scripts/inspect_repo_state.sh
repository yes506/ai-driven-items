#!/usr/bin/env bash
# inspect_repo_state.sh — read-only repo state inspector for intent-aligner.
# Emits a single JSON line on stdout. Never mutates anything.
#
# Contract (referenced from SKILL.md Phase 0):
#
#   {
#     "state": "<one-of-the-states-below>",
#     "reason": "<optional, only present for 'unrelated'>",
#     "main_checkout": "<absolute path or empty>",
#     "default_branch": "main|master|''",
#     "current_branch": "<branch-name or DETACHED>",
#     "dev_exists": true|false
#   }
#
# States:
#   on-dev                  — on `dev` in MAIN_CHECKOUT, ready to proceed
#   on-default-needs-dev    — on main/master, `dev` doesn't exist locally
#   on-nonbase-main-checkout — on a non-base branch in main checkout
#   inside-intent-worktree  — cwd is inside .worktrees/intent-* (resume target)
#   inside-other-worktree   — inside a non-intent linked worktree (planner,
#                             implementer, scaffold, unknown — refuse)
#   unrelated               — not in a git repo / detached HEAD / zero commits

set -euo pipefail

jesc() {
  printf '%s' "${1:-}" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])'
}

emit() { printf '%s\n' "$1"; exit 0; }

build_json() {
  local state="$1" reason="${2:-}"
  local reason_field=""
  [ -n "${reason}" ] && reason_field=",\"reason\":\"$(jesc "${reason}")\""
  printf '{"state":"%s"%s,"main_checkout":"%s","default_branch":"%s","current_branch":"%s","dev_exists":%s}\n' \
    "${state}" "${reason_field}" \
    "$(jesc "${MAIN_CHECKOUT:-}")" \
    "$(jesc "${DEFAULT_BRANCH:-}")" \
    "$(jesc "${CURRENT_BRANCH:-}")" \
    "${DEV_EXISTS:-false}"
}

# 1. Inside any git repo?
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  MAIN_CHECKOUT="" DEFAULT_BRANCH="" CURRENT_BRANCH="" DEV_EXISTS=false
  emit '{"state":"unrelated","reason":"not_in_git_repo","main_checkout":null,"default_branch":null,"current_branch":null,"dev_exists":false}'
fi

# 2. Worktree info — derive MAIN_CHECKOUT from the *physical* parent of
#    git-common-dir. `pwd -P` resolves symlinks (e.g. macOS /tmp ->
#    /private/tmp) so the result matches `git rev-parse --show-toplevel`,
#    which always emits physical paths.
GIT_COMMON_DIR="$(git rev-parse --git-common-dir 2>/dev/null)"
GIT_COMMON_DIR_ABS="$(cd "$(dirname "${GIT_COMMON_DIR}")" && pwd -P)/$(basename "${GIT_COMMON_DIR}")"
MAIN_CHECKOUT="$(dirname "${GIT_COMMON_DIR_ABS}")"

# 3. Current branch — symbolic-ref handles detached HEAD cleanly.
if CURRENT_BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null)"; then
  :
else
  CURRENT_BRANCH="DETACHED"
fi
CURRENT_BRANCH="$(printf '%s' "${CURRENT_BRANCH}" | tr -d '\r\n\t')"

# Zero-commits guard — hoisted above the branch-name dispatch so that an
# unborn `dev`/`main`/`master` branch (created via `git init -b dev`) is
# correctly classified as `repo_has_no_commits` rather than short-circuiting
# into on-dev / on-default-needs-dev paths.
if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  DEFAULT_BRANCH=""
  DEV_EXISTS=false
  emit "$(build_json unrelated repo_has_no_commits)"
fi

# 4. Default branch (main / master) — read from MAIN_CHECKOUT.
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

# 6. Worktree-root for path classification — works even when cwd is a subdir.
WORKTREE_TOP="$(git rev-parse --show-toplevel 2>/dev/null || echo '')"
IS_LINKED_WORKTREE=false
if [ -n "${WORKTREE_TOP}" ] && [ "${WORKTREE_TOP}" != "${MAIN_CHECKOUT}" ]; then
  IS_LINKED_WORKTREE=true
fi

# 7. Classify
if [ "${IS_LINKED_WORKTREE}" = "true" ]; then
  case "${WORKTREE_TOP}" in
    */.worktrees/intent-*)   emit "$(build_json inside-intent-worktree)" ;;
    *)                       emit "$(build_json inside-other-worktree)" ;;
  esac
fi

# Main checkout classification.
if [ "${CURRENT_BRANCH}" = "dev" ]; then
  emit "$(build_json on-dev)"
fi

if [ "${CURRENT_BRANCH}" = "DETACHED" ]; then
  emit "$(build_json unrelated detached_head)"
fi

if [ -n "${DEFAULT_BRANCH}" ] && [ "${CURRENT_BRANCH}" = "${DEFAULT_BRANCH}" ] && [ "${DEV_EXISTS}" = "false" ]; then
  emit "$(build_json on-default-needs-dev)"
fi

emit "$(build_json on-nonbase-main-checkout)"
