#!/usr/bin/env bash
# inspect_repo_state.sh — read-only repo state inspector for document-implementer.
# Emits a single JSON line on stdout. Never mutates anything.
#
# Mirrors codebase-implementer's discipline (physical paths via pwd -P,
# branches-only marker search, native git --grep with output capture, zero-
# commits guard above branch-name dispatch) and document-planner's worktree-
# classification pattern (`docimpl-*` for our worktree, `docplanner-*` for
# the upstream planner's worktree which we refuse to interrupt).

set -euo pipefail

jesc() {
  printf '%s' "${1:-}" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])'
}

emit() { printf '%s\n' "$1"; exit 0; }

build_json() {
  local state="$1" reason="${2:-}"
  local reason_field=""
  [ -n "${reason}" ] && reason_field=",\"reason\":\"$(jesc "${reason}")\""
  printf '{"state":"%s"%s,"main_checkout":"%s","default_branch":"%s","current_branch":"%s","dev_exists":%s,"planner_marker_scale":"%s","planner_marker_commit":"%s","implementer_marker_present":%s}\n' \
    "${state}" "${reason_field}" \
    "$(jesc "${MAIN_CHECKOUT:-}")" \
    "$(jesc "${DEFAULT_BRANCH:-}")" \
    "$(jesc "${CURRENT_BRANCH:-}")" \
    "${DEV_EXISTS:-false}" \
    "$(jesc "${PLANNER_MARKER_SCALE:-}")" \
    "$(jesc "${PLANNER_MARKER_COMMIT:-}")" \
    "${IMPLEMENTER_MARKER_PRESENT:-false}"
}

# 1. Inside any git repo?
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  emit '{"state":"unrelated","reason":"not_in_git_repo","main_checkout":null,"default_branch":null,"current_branch":null,"dev_exists":false,"planner_marker_scale":null,"planner_marker_commit":null,"implementer_marker_present":false}'
fi

# 2. Worktree info — derive MAIN_CHECKOUT from the *physical* parent of git-common-dir.
GIT_COMMON_DIR="$(git rev-parse --git-common-dir 2>/dev/null)"
GIT_COMMON_DIR_ABS="$(cd "$(dirname "${GIT_COMMON_DIR}")" && pwd -P)/$(basename "${GIT_COMMON_DIR}")"
MAIN_CHECKOUT="$(dirname "${GIT_COMMON_DIR_ABS}")"

# 3. Current branch.
if CURRENT_BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null)"; then
  :
else
  CURRENT_BRANCH="DETACHED"
fi
CURRENT_BRANCH="$(printf '%s' "${CURRENT_BRANCH}" | tr -d '\r\n\t')"

# Zero-commits guard hoisted above branch dispatch.
if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  DEFAULT_BRANCH=""
  DEV_EXISTS=false
  PLANNER_MARKER_SCALE=""
  PLANNER_MARKER_COMMIT=""
  IMPLEMENTER_MARKER_PRESENT=false
  emit "$(build_json unrelated repo_has_no_commits)"
fi

# 4. Default branch.
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

# 6. Worktree-root classification.
WORKTREE_TOP="$(git rev-parse --show-toplevel 2>/dev/null || echo '')"
IS_LINKED_WORKTREE=false
if [ -n "${WORKTREE_TOP}" ] && [ "${WORKTREE_TOP}" != "${MAIN_CHECKOUT}" ]; then
  IS_LINKED_WORKTREE=true
fi

# 7. Planner marker scan — most-recent first, branches only. Plain scalar vars
#    (not declare -A) because macOS bash 3.2 lacks associative-array support.
PLANNER_MARKER_SCALE=""
PLANNER_MARKER_COMMIT=""
SYSTEM_COMMIT="" SYSTEM_TS=0
FEATURE_COMMIT="" FEATURE_TS=0
LOCAL_COMMIT="" LOCAL_TS=0
MICRO_COMMIT="" MICRO_TS=0
while IFS=$'\t' read -r commit ts subject; do
  [ -z "${commit}" ] && continue
  case "${subject}" in
    *"(document-plan-system, human-confirmed)"*)
      [ -z "${SYSTEM_COMMIT}" ] && { SYSTEM_COMMIT="${commit}"; SYSTEM_TS="${ts}"; } ;;
    *"(document-plan-feature, human-confirmed)"*)
      [ -z "${FEATURE_COMMIT}" ] && { FEATURE_COMMIT="${commit}"; FEATURE_TS="${ts}"; } ;;
    *"(document-plan-local, human-confirmed)"*)
      [ -z "${LOCAL_COMMIT}" ] && { LOCAL_COMMIT="${commit}"; LOCAL_TS="${ts}"; } ;;
    *"(document-plan-micro, human-confirmed)"*)
      [ -z "${MICRO_COMMIT}" ] && { MICRO_COMMIT="${commit}"; MICRO_TS="${ts}"; } ;;
  esac
done < <(git -C "${MAIN_CHECKOUT}" log -n 50 --branches \
            --grep='document-plan-.*, human-confirmed' \
            --format='%H%x09%ct%x09%s' 2>/dev/null)

# Pick the newest across scales by committer timestamp.
NEWEST_TS=0
if [ "${SYSTEM_TS}" -gt "${NEWEST_TS}" ]; then
  NEWEST_TS="${SYSTEM_TS}"; PLANNER_MARKER_SCALE="system"; PLANNER_MARKER_COMMIT="${SYSTEM_COMMIT}"
fi
if [ "${FEATURE_TS}" -gt "${NEWEST_TS}" ]; then
  NEWEST_TS="${FEATURE_TS}"; PLANNER_MARKER_SCALE="feature"; PLANNER_MARKER_COMMIT="${FEATURE_COMMIT}"
fi
if [ "${LOCAL_TS}" -gt "${NEWEST_TS}" ]; then
  NEWEST_TS="${LOCAL_TS}"; PLANNER_MARKER_SCALE="local"; PLANNER_MARKER_COMMIT="${LOCAL_COMMIT}"
fi
if [ "${MICRO_TS}" -gt "${NEWEST_TS}" ]; then
  NEWEST_TS="${MICRO_TS}"; PLANNER_MARKER_SCALE="micro"; PLANNER_MARKER_COMMIT="${MICRO_COMMIT}"
fi

# 8. Implementer marker — `--fixed-strings` so literal `(document-impl-`
#    isn't read as a regex group.
IMPLEMENTER_MARKER_PRESENT=false
if [ -n "$(git -C "${MAIN_CHECKOUT}" log -n 1 --branches --fixed-strings --grep='(document-impl-' --format=%H 2>/dev/null)" ]; then
  IMPLEMENTER_MARKER_PRESENT=true
fi

# 9. Classify
if [ "${IS_LINKED_WORKTREE}" = "true" ]; then
  case "${WORKTREE_TOP}" in
    */.worktrees/docimpl-*)      emit "$(build_json inside-document-implementer-worktree)" ;;
    */.worktrees/docplanner-*)   emit "$(build_json inside-document-planner-worktree)" ;;
    *)                           emit "$(build_json inside-other-worktree)" ;;
  esac
fi

# Main-checkout classification.
if [ "${CURRENT_BRANCH}" = "DETACHED" ]; then
  emit "$(build_json unrelated detached_head)"
fi

if [ "${CURRENT_BRANCH}" = "dev" ]; then
  if [ -n "${PLANNER_MARKER_SCALE}" ]; then
    emit "$(build_json on-base-with-marker)"
  else
    emit "$(build_json on-base-no-marker)"
  fi
fi

if [ -n "${DEFAULT_BRANCH}" ] && [ "${CURRENT_BRANCH}" = "${DEFAULT_BRANCH}" ] && [ "${DEV_EXISTS}" = "false" ]; then
  emit "$(build_json on-default-needs-dev)"
fi

emit "$(build_json on-nonbase-main-checkout)"
