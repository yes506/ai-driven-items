# Git Worktree Flow

This file documents ordering, naming, and edge-case handling for the worktree
lifecycle. Read it whenever Phase 0 or Phase 4 in `SKILL.md` is active.

## Ordering invariant

**No file mutations happen before Phase 3 confirmation.** Specifically, the
worktree is created in Phase 4, *after* the user has confirmed the stack. This
prevents orphan worktrees when the user changes their mind during stack
discussion.

## Naming scheme

Worktree path:
```
.worktrees/scaffold-<stack-slug>-<short-id>
```

Branch:
```
scaffold/<stack-slug>-<short-id>
```

`<stack-slug>` examples: `nextjs-app-router`, `spring-boot`, `fastapi`,
`go-gin`, `node-express`. `<short-id>` is the last 5 chars of `date +%s` to
avoid collision when scaffolding multiple stacks in one session.

The encoded stack lets `git worktree list` and `git branch` self-describe what
is in flight.

## Phase 0 — `dev` branch detection

```bash
git rev-parse --verify dev 2>/dev/null && echo "dev exists locally"
git ls-remote --heads origin dev | grep -q dev && echo "dev exists on origin"
```

If `dev` exists locally → use it.
If only on origin → ask: *"Track origin/dev as local dev? (y/n)"* On y:
`git fetch origin dev:dev`.
If neither → present the dialog:

```
`dev` branch not found. Options:
  1) Create dev from main (recommended for new projects)
  2) Use a different base branch (specify name)
  3) Abort — let me set up dev myself first
Type 1, 2 <branch-name>, or abort.
```

## Phase 4 — worktree edge cases

| Case | Detection | Response |
|---|---|---|
| Path collision | `test -e .worktrees/scaffold-<slug>-<id>` | Suffix path with extra timestamp segment, then ask user before proceeding |
| Dirty `dev` | `git -C <main-checkout> diff --quiet dev -- .` fails | Stop, list dirty files, ask user to commit/stash first |
| `dev` not local but on origin | see Phase 0 detection | Offer `git fetch origin dev:dev` |
| User aborts mid-scaffold | user typed `abort` or `^C` | Leave worktree intact, write current `phase_completed` to `.scaffold-state.json` |
| Merge conflict at gate | `git merge --no-ff` exits non-zero | Stop, list conflicting files, hand back to user. **Never** auto-resolve. |
| Nested invocation | `pwd` matches `*/.worktrees/scaffold-*` | Refuse with: *"This skill cannot be run from inside an existing scaffold worktree. Run it from the main checkout."* |
| Untracked files on re-run | `git status --porcelain` shows `??` lines | Preserve them. **Never** `git clean`. |

## Greenfield bootstrap

If Phase 0 returned `greenfield`:

```bash
git init
git commit --allow-empty -m "chore: initial empty commit"
git branch -M main
git branch dev
```

Then proceed to Phase 4 with `dev` as the base. Confirm with the user before
each of these commands (greenfield init is a "are you sure" moment).

## Merge gate (Phase 7)

From the **main checkout** (not the worktree):

```bash
git checkout dev
git merge --no-ff scaffold/<stack-slug>-<short-id> \
  -m "feat(scaffold): merge <stack-slug> baseline"
```

`--no-ff` is mandatory — it preserves the scaffold-as-a-unit history so the
merge commit anchors the entire baseline. The agent must reject any user
request to fast-forward or squash here without explicit override.

## What this flow never does

- `git push` (user's call after merge)
- `git push --force` (forbidden absolutely)
- `git reset --hard` (forbidden)
- `git worktree remove --force` (forbidden — only `git worktree remove` after asking)
- `git clean -f` (forbidden — would destroy untracked work)
- `--no-verify` on any commit (pre-commit hooks must run)
