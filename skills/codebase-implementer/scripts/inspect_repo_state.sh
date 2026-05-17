#!/usr/bin/env bash
# inspect_repo_state.sh — read-only repo state inspector for codebase-implementer.
# Emits a single JSON line on stdout. Never mutates anything.
#
# Mirrors the planner inspector's discipline (physical paths via pwd -P,
# branches-only marker search to avoid stale-remote false positives, native
# git --grep with output capture to avoid pipefail+grep-q SIGPIPE bugs, zero-
# commits guard above branch-name dispatch). Implementer-specific additions:
# detects planner markers (feature + system) so SKILL.md Phase 0 can refuse
# fast if the upstream planner gate hasn't landed.

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

# 3. Current branch — symbolic-ref handles detached HEAD + empty-repo cleanly.
if CURRENT_BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null)"; then
  :
else
  CURRENT_BRANCH="DETACHED"
fi
CURRENT_BRANCH="$(printf '%s' "${CURRENT_BRANCH}" | tr -d '\r\n\t')"

# Zero-commits guard hoisted above branch dispatch so an unborn `dev`/`main`
# branch (e.g. `git init -b dev`) classifies as `repo_has_no_commits`
# rather than slipping into the on-dev-* paths.
if ! git rev-parse --verify HEAD >/dev/null 2>&1; then
  DEFAULT_BRANCH=""
  DEV_EXISTS=false
  PLANNER_MARKER_SCALE=""
  PLANNER_MARKER_COMMIT=""
  IMPLEMENTER_MARKER_PRESENT=false
  emit "$(build_json unrelated repo_has_no_commits)"
fi

# 4. Default branch
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

# 6. Worktree-root classification — works from subdirectories of a worktree.
WORKTREE_TOP="$(git rev-parse --show-toplevel 2>/dev/null || echo '')"
IS_LINKED_WORKTREE=false
if [ -n "${WORKTREE_TOP}" ] && [ "${WORKTREE_TOP}" != "${MAIN_CHECKOUT}" ]; then
  IS_LINKED_WORKTREE=true
fi

# 7. Planner marker scan — most-recent first on LOCAL branches only. `--branches`
#    (not `--all`) avoids false positives from stale remote-tracking refs that
#    may carry a force-pushed-over marker no longer reachable from a live branch.
#    Use git's native --grep + output capture (not `| grep -q`) to dodge the
#    pipefail+SIGPIPE bug, AND bound output via `-n 50` ON THE GIT SIDE rather
#    than `| head -n 50` (head would SIGPIPE git log under pipefail in repos
#    with 50+ matching commits — that's the same bug the planner script warns
#    about).
#
#    Use plain scalar variables instead of `declare -A` — bash 3.2 ships on
#    macOS by default and lacks associative-array support; the loop tracks
#    one (commit, ts) per scale with simple per-scale shadowed vars.
PLANNER_MARKER_SCALE=""
PLANNER_MARKER_COMMIT=""
SYSTEM_COMMIT="" SYSTEM_TS=0
FEATURE_COMMIT="" FEATURE_TS=0
LOCAL_COMMIT="" LOCAL_TS=0
MICRO_COMMIT="" MICRO_TS=0
while IFS=$'\t' read -r commit ts subject; do
  [ -z "${commit}" ] && continue
  case "${subject}" in
    *"(interfaces only, human-confirmed)"*)
      [ -z "${SYSTEM_COMMIT}" ] && { SYSTEM_COMMIT="${commit}"; SYSTEM_TS="${ts}"; } ;;
    *"(plan-feature, human-confirmed)"*)
      [ -z "${FEATURE_COMMIT}" ] && { FEATURE_COMMIT="${commit}"; FEATURE_TS="${ts}"; } ;;
    *"(plan-local, human-confirmed)"*)
      [ -z "${LOCAL_COMMIT}" ] && { LOCAL_COMMIT="${commit}"; LOCAL_TS="${ts}"; } ;;
    *"(plan-micro, human-confirmed)"*)
      [ -z "${MICRO_COMMIT}" ] && { MICRO_COMMIT="${commit}"; MICRO_TS="${ts}"; } ;;
  esac
done < <(git -C "${MAIN_CHECKOUT}" log -n 50 --branches \
            --grep='human-confirmed' \
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

# 8. Implementer marker — detect whether THIS skill already merged a previous
#    impl run (used by Phase 0 to warn against re-implementing the same plan).
#    Use `--fixed-strings` so the literal `(impl-` is NOT treated as a regex
#    open-paren — under `git config grep.extendedRegexp true` the bare form
#    fails with "parentheses not balanced". The `-n 1` bounds output without
#    a pipe.
IMPLEMENTER_MARKER_PRESENT=false
if [ -n "$(git -C "${MAIN_CHECKOUT}" log -n 1 --branches --fixed-strings --grep='(impl-' --format=%H 2>/dev/null)" ]; then
  IMPLEMENTER_MARKER_PRESENT=true
fi

# 9. Classify
if [ "${IS_LINKED_WORKTREE}" = "true" ]; then
  case "${WORKTREE_TOP}" in
    */.worktrees/implementer-*)  emit "$(build_json inside-implementer-worktree)" ;;
    */.worktrees/planner-*)      emit "$(build_json inside-planner-worktree)" ;;
    */.worktrees/architect-*)    emit "$(build_json inside-legacy-architect-worktree)" ;;
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

# On a non-base branch in the main checkout. The planner allows micro/local at
# this state, but the implementer is harder to reason about here because the
# branch might already contain in-progress work. Surface the state and let
# SKILL.md decide whether to refuse or proceed (micro/local with in-chat marker
# may still be allowed).
emit "$(build_json on-nonbase-main-checkout)"
