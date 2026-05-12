#!/usr/bin/env bash
# inspect_repo_state.sh — read-only repo state inspector for codebase-architect.
# Emits a single JSON line on stdout. Never mutates anything.

set -euo pipefail

emit() {
  printf '%s\n' "$1"
  exit 0
}

# 1. Inside any git repo?
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  emit '{"state":"unrelated","reason":"not_in_git_repo","main_checkout":null,"default_branch":null,"current_branch":null,"scaffold_marker_present":false}'
fi

# 2. Worktree info — derive MAIN_CHECKOUT from git-common-dir's parent.
GIT_COMMON_DIR="$(git rev-parse --git-common-dir 2>/dev/null)"
MAIN_CHECKOUT="$(cd "$(dirname "${GIT_COMMON_DIR}")" && pwd)"

CWD="$(pwd)"
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'HEAD')"

# 3. Default branch (main / master)
DEFAULT_BRANCH=""
for candidate in main master; do
  if git -C "${MAIN_CHECKOUT}" show-ref --verify --quiet "refs/heads/${candidate}"; then
    DEFAULT_BRANCH="${candidate}"
    break
  fi
done

# 4. Linked-worktree detection (a linked worktree has .git as a file, not dir)
IS_LINKED_WORKTREE="false"
if [ "${CWD}" != "${MAIN_CHECKOUT}" ] && [ -f "${CWD}/.git" ]; then
  IS_LINKED_WORKTREE="true"
fi

# 5. Has the project ever been scaffolded? Search commit messages.
SCAFFOLD_MARKER_PRESENT="false"
if git -C "${MAIN_CHECKOUT}" log --oneline --all 2>/dev/null \
    | grep -q 'chore(scaffold): initialize'; then
  SCAFFOLD_MARKER_PRESENT="true"
fi

# 6. Classify
if [ "${IS_LINKED_WORKTREE}" = "true" ]; then
  case "${CWD}" in
    */.worktrees/architect-*)
      emit "{\"state\":\"inside-architect-worktree\",\"main_checkout\":\"${MAIN_CHECKOUT}\",\"default_branch\":\"${DEFAULT_BRANCH}\",\"current_branch\":\"${CURRENT_BRANCH}\",\"scaffold_marker_present\":${SCAFFOLD_MARKER_PRESENT}}"
      ;;
    *)
      emit "{\"state\":\"inside-other-worktree\",\"main_checkout\":\"${MAIN_CHECKOUT}\",\"default_branch\":\"${DEFAULT_BRANCH}\",\"current_branch\":\"${CURRENT_BRANCH}\",\"scaffold_marker_present\":${SCAFFOLD_MARKER_PRESENT}}"
      ;;
  esac
fi

# In main checkout: classify by branch + scaffold marker.
if [ "${CURRENT_BRANCH}" = "dev" ]; then
  if [ "${SCAFFOLD_MARKER_PRESENT}" = "true" ]; then
    emit "{\"state\":\"on-dev-with-scaffold\",\"main_checkout\":\"${MAIN_CHECKOUT}\",\"default_branch\":\"${DEFAULT_BRANCH}\",\"current_branch\":\"${CURRENT_BRANCH}\",\"scaffold_marker_present\":true}"
  else
    emit "{\"state\":\"on-dev-no-scaffold\",\"main_checkout\":\"${MAIN_CHECKOUT}\",\"default_branch\":\"${DEFAULT_BRANCH}\",\"current_branch\":\"${CURRENT_BRANCH}\",\"scaffold_marker_present\":false}"
  fi
fi

emit "{\"state\":\"unrelated\",\"reason\":\"not_on_dev_in_main_checkout\",\"main_checkout\":\"${MAIN_CHECKOUT}\",\"default_branch\":\"${DEFAULT_BRANCH}\",\"current_branch\":\"${CURRENT_BRANCH}\",\"scaffold_marker_present\":${SCAFFOLD_MARKER_PRESENT}}"
