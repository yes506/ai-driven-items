#!/usr/bin/env bash
# inspect_repo_state.sh — READ-ONLY repo state inspection for project-scaffolder.
#
# Prints a JSON object describing the current repo state. Performs NO mutations.
# Used by Phase 0 of SKILL.md to classify the repo before any user dialog.
#
# Output schema:
#   {
#     "state": "greenfield" | "existing-with-dev" | "existing-without-dev"
#            | "inside-scaffold-worktree" | "inside-other-worktree" | "not-a-repo",
#     "cwd": "<absolute path>",
#     "main_checkout": "<absolute path of the parent main worktree>" | null,
#     "is_git_repo": true|false,
#     "commit_count": <int>,
#     "current_branch": "<name>" | null,
#     "default_branch": "main" | "master" | null,
#     "is_dirty": true|false,
#     "dev_local": true|false,
#     "dev_remote": true|false,
#     "main_local": true|false,
#     "master_local": true|false,
#     "scaffold_state_present": true|false,
#     "worktrees": ["<path>", ...]
#   }
#
# Exit code is always 0 unless invocation itself is broken; the JSON's "state"
# field is the actionable signal.

set -u
LC_ALL=C

# JSON-escape a single string (handles backslash, double-quote, control chars).
# Reads from stdin to avoid argv parsing issues when the value starts with `-`.
json_escape() {
  printf '%s' "$1" \
    | python3 -c 'import json,sys; sys.stdout.write(json.dumps(sys.stdin.read()))' 2>/dev/null \
    || printf '%s' "\"$(printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g')\""
}

cwd="$(pwd)"

is_git_repo=false
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  is_git_repo=true
fi

commit_count=0
current_branch_json="null"
default_branch_json="null"
is_dirty=false
dev_local=false
dev_remote=false
main_local=false
master_local=false
is_inside_worktree=false
scaffold_state_present=false
main_checkout_json="null"
worktrees_json="[]"

if [[ "$is_git_repo" == "true" ]]; then
  commit_count=$(git rev-list --count HEAD 2>/dev/null || echo 0)

  branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
  if [[ -n "$branch" && "$branch" != "HEAD" ]]; then
    current_branch_json=$(json_escape "$branch")
  fi

  # is_dirty includes untracked + tracked + staged.
  if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    is_dirty=true
  fi

  git rev-parse --verify --quiet dev >/dev/null 2>&1 && dev_local=true
  git rev-parse --verify --quiet main >/dev/null 2>&1 && main_local=true
  git rev-parse --verify --quiet master >/dev/null 2>&1 && master_local=true

  if git ls-remote --heads origin dev 2>/dev/null | grep -q "refs/heads/dev"; then
    dev_remote=true
  fi

  # Default branch detection: prefer origin/HEAD, fall back to local main/master.
  default_branch=""
  if git symbolic-ref --quiet refs/remotes/origin/HEAD >/dev/null 2>&1; then
    default_branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@')
  fi
  if [[ -z "$default_branch" ]]; then
    [[ "$main_local" == "true" ]] && default_branch="main"
    [[ -z "$default_branch" && "$master_local" == "true" ]] && default_branch="master"
  fi
  [[ -n "$default_branch" ]] && default_branch_json=$(json_escape "$default_branch")

  # Worktree detection: git_dir != git_common_dir means we are inside a linked
  # worktree (not the main checkout).
  git_dir=$(git rev-parse --git-dir 2>/dev/null || echo "")
  common_dir=$(git rev-parse --git-common-dir 2>/dev/null || echo "")
  if [[ -n "$git_dir" && -n "$common_dir" ]]; then
    # Resolve to absolute paths for safe comparison.
    git_dir_abs=$(cd "$(dirname "$git_dir")" 2>/dev/null && pwd)/$(basename "$git_dir")
    common_dir_abs=$(cd "$(dirname "$common_dir")" 2>/dev/null && pwd)/$(basename "$common_dir")
    if [[ "$git_dir_abs" != "$common_dir_abs" ]]; then
      is_inside_worktree=true
    fi
  fi

  # Resolve the parent main-checkout path for use by Phase 7 (`git -C <path>`).
  if [[ "$is_inside_worktree" == "true" ]]; then
    main_checkout_abs=$(dirname "$common_dir_abs")
    main_checkout_json=$(json_escape "$main_checkout_abs")
  else
    main_checkout_json=$(json_escape "$cwd")
  fi

  # Detect scaffold state-file (presence enables resumability).
  if [[ -f "$cwd/.scaffold-state.json" ]]; then
    scaffold_state_present=true
  fi

  # Build worktrees JSON array using --porcelain (NUL-aware via while-read).
  # `--porcelain` outputs `worktree <path>` lines; we read everything after
  # the first space, which preserves spaces in paths.
  if [[ "$is_git_repo" == "true" ]]; then
    worktrees_json="["
    first=true
    while IFS= read -r line; do
      case "$line" in
        worktree\ *)
          path="${line#worktree }"
          if $first; then first=false; else worktrees_json="${worktrees_json},"; fi
          worktrees_json="${worktrees_json}$(json_escape "$path")"
          ;;
      esac
    done < <(git worktree list --porcelain 2>/dev/null)
    worktrees_json="${worktrees_json}]"
  fi
fi

# Classify state.
# Order matters:
#   1. inside-scaffold-worktree wins (enables resumability)
#   2. inside-other-worktree (refuse)
#   3. not-a-repo (treat as greenfield candidate)
#   4. dev existence dominates commit count
#   5. >=1 commit + no dev -> existing-without-dev
#   6. else greenfield
if [[ "$is_inside_worktree" == "true" ]]; then
  case "$cwd" in
    */.worktrees/scaffold-*) state="inside-scaffold-worktree" ;;
    *) state="inside-other-worktree" ;;
  esac
elif [[ "$is_git_repo" != "true" ]]; then
  state="not-a-repo"
elif [[ "$dev_local" == "true" || "$dev_remote" == "true" ]]; then
  state="existing-with-dev"
elif [[ "$commit_count" -ge 1 ]]; then
  state="existing-without-dev"
else
  state="greenfield"
fi

cat <<EOF
{
  "state": "$state",
  "cwd": $(json_escape "$cwd"),
  "main_checkout": $main_checkout_json,
  "is_git_repo": $is_git_repo,
  "commit_count": $commit_count,
  "current_branch": $current_branch_json,
  "default_branch": $default_branch_json,
  "is_dirty": $is_dirty,
  "dev_local": $dev_local,
  "dev_remote": $dev_remote,
  "main_local": $main_local,
  "master_local": $master_local,
  "scaffold_state_present": $scaffold_state_present,
  "worktrees": $worktrees_json
}
EOF
