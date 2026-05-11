#!/usr/bin/env bash
# inspect_repo_state.sh — READ-ONLY repo state inspection for project-scaffolder.
#
# Prints a JSON object describing the current repo state. Performs NO mutations.
# Used by Phase 0 of SKILL.md to classify the repo before any user dialog.
#
# Output schema:
#   {
#     "state": "greenfield" | "existing-with-dev" | "existing-without-dev" | "inside-worktree" | "not-a-repo",
#     "cwd": "<absolute path>",
#     "is_git_repo": true|false,
#     "commit_count": <int>,
#     "current_branch": "<name>" | null,
#     "is_dirty": true|false,
#     "dev_local": true|false,
#     "dev_remote": true|false,
#     "main_local": true|false,
#     "is_inside_worktree": true|false,
#     "worktrees": ["<path>", ...]
#   }
#
# Exit code is always 0 unless invocation itself is broken; the JSON's "state"
# field is the actionable signal.

set -u
LC_ALL=C

cwd="$(pwd)"

is_git_repo=false
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  is_git_repo=true
fi

commit_count=0
current_branch="null"
is_dirty=false
dev_local=false
dev_remote=false
main_local=false
is_inside_worktree=false
worktrees_json="[]"

if [[ "$is_git_repo" == "true" ]]; then
  commit_count=$(git rev-list --count HEAD 2>/dev/null || echo 0)

  branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
  if [[ -n "$branch" && "$branch" != "HEAD" ]]; then
    current_branch="\"$branch\""
  fi

  if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    is_dirty=true
  fi

  git rev-parse --verify --quiet dev >/dev/null 2>&1 && dev_local=true
  git rev-parse --verify --quiet main >/dev/null 2>&1 && main_local=true

  if git ls-remote --heads origin dev 2>/dev/null | grep -q "refs/heads/dev"; then
    dev_remote=true
  fi

  # Detect "inside a worktree managed by another main checkout":
  # `git worktree list` from inside a linked worktree still works; we check
  # whether the cwd's git common dir differs from the worktree dir.
  git_dir=$(git rev-parse --git-dir 2>/dev/null || echo "")
  common_dir=$(git rev-parse --git-common-dir 2>/dev/null || echo "")
  if [[ -n "$git_dir" && -n "$common_dir" && "$git_dir" != "$common_dir" ]]; then
    is_inside_worktree=true
  fi

  # Also flag if the cwd path contains "/.worktrees/scaffold-" (this skill's pattern).
  case "$cwd" in
    */.worktrees/scaffold-*) is_inside_worktree=true ;;
  esac

  # Build worktrees JSON array.
  wt_paths=$(git worktree list --porcelain 2>/dev/null | awk '/^worktree /{print $2}')
  if [[ -n "$wt_paths" ]]; then
    worktrees_json="["
    first=true
    while IFS= read -r p; do
      [[ -z "$p" ]] && continue
      if $first; then first=false; else worktrees_json="${worktrees_json},"; fi
      worktrees_json="${worktrees_json}\"${p}\""
    done <<< "$wt_paths"
    worktrees_json="${worktrees_json}]"
  fi
fi

# Classify state.
# Order matters: dev-existence dominates commit-count, because the workflow
# branches off `dev`. A repo with only an initial commit but a real `dev` is
# still "existing-with-dev" for our purposes.
if [[ "$is_inside_worktree" == "true" ]]; then
  state="inside-worktree"
elif [[ "$is_git_repo" != "true" ]]; then
  state="not-a-repo"
elif [[ "$dev_local" == "true" || "$dev_remote" == "true" ]]; then
  state="existing-with-dev"
elif [[ "$commit_count" -ge 2 ]]; then
  state="existing-without-dev"
else
  state="greenfield"
fi

cat <<EOF
{
  "state": "$state",
  "cwd": "$cwd",
  "is_git_repo": $is_git_repo,
  "commit_count": $commit_count,
  "current_branch": $current_branch,
  "is_dirty": $is_dirty,
  "dev_local": $dev_local,
  "dev_remote": $dev_remote,
  "main_local": $main_local,
  "is_inside_worktree": $is_inside_worktree,
  "worktrees": $worktrees_json
}
EOF
