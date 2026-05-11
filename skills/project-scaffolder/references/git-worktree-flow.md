# Git Worktree Flow

This file documents ordering, naming, and edge-case handling for the worktree
lifecycle. Read it whenever Phase 0 or Phase 4 in `SKILL.md` is active.

## State variables

These are captured in Phase 0 from the inspector JSON and threaded through
Phase 4 / Phase 7:

| Variable | Source | Used by |
|---|---|---|
| `MAIN_CHECKOUT` | inspector `main_checkout` field | Phase 4 worktree-add, Phase 7 merge |
| `BASE_BRANCH` | `dev` for `existing-with-dev`; user choice for `existing-without-dev`; `dev` newly created for `greenfield` | Phase 4 worktree base, Phase 7 merge target |
| `SCAFFOLD_ID` | `$(date +%s | tail -c 6)` computed once in Phase 4 | Worktree path AND branch name (must match) |
| `STACK_SLUG` | from Phase 3 confirmation | Worktree path AND branch name |
| `default_branch` | inspector `default_branch` field | Greenfield bootstrap, dialog wording |

## Ordering invariant

**No file mutations happen before Phase 3 confirmation.** Specifically, the
worktree is created in Phase 4, *after* the user has confirmed the stack. This
prevents orphan worktrees when the user changes their mind during stack
discussion.

## Naming scheme

Worktree path:
```
.worktrees/scaffold-${STACK_SLUG}-${SCAFFOLD_ID}
```

Branch:
```
scaffold/${STACK_SLUG}-${SCAFFOLD_ID}
```

`STACK_SLUG` examples: `nextjs-app-router`, `spring-boot`, `fastapi`,
`go-gin`, `node-express`. `SCAFFOLD_ID` is the last 5 chars of `date +%s`,
**computed once** and reused — never recompute, or path and branch will drift.

The encoded stack lets `git worktree list` and `git branch` self-describe what
is in flight.

## Phase 0 — `BASE_BRANCH` resolution

```bash
git -C "${MAIN_CHECKOUT}" rev-parse --verify --quiet dev >/dev/null 2>&1 \
  && echo "dev exists locally"
git -C "${MAIN_CHECKOUT}" ls-remote --heads origin dev 2>/dev/null \
  | grep -q "refs/heads/dev" && echo "dev exists on origin"
```

- `dev` exists locally → `BASE_BRANCH=dev`.
- `dev` only on origin → ask: *"Track origin/dev as local dev? (y/n)"*
  On y: `git -C "${MAIN_CHECKOUT}" fetch origin dev:dev`.
- Neither → present the dialog (see Phase 0 of SKILL.md).

## Phase 4 — pre-creation: local exclude

Before `git worktree add` runs, append `.worktrees/` to the **main checkout's**
`.git/info/exclude`. This is local-only and never committed; it covers the
pre-merge interval where the worktree directory would otherwise show as
`?? .worktrees/` in `git status` on the main checkout.

```bash
grep -qxF '.worktrees/' "${MAIN_CHECKOUT}/.git/info/exclude" \
  || echo '.worktrees/' >> "${MAIN_CHECKOUT}/.git/info/exclude"
```

The committed `.gitignore` entry on the scaffold branch (Phase 4 step 3 in
`SKILL.md`) handles the post-merge interval. Both are needed: the local
exclude disappears with the repo, the committed entry persists for future
contributors.

## Phase 4 — worktree edge cases

| Case | Detection | Response |
|---|---|---|
| Path collision | `test -e .worktrees/scaffold-${STACK_SLUG}-${SCAFFOLD_ID}` | Recompute `SCAFFOLD_ID` once, ask user before retry |
| Dirty `BASE_BRANCH` | see "Dirty base-branch detection" below | Stop, list dirty files, ask user to commit/stash first |
| `dev` not local but on origin | see Phase 0 detection | Offer `git -C "${MAIN_CHECKOUT}" fetch origin dev:dev` |
| User aborts mid-scaffold | user typed `abort` or `^C` | Leave worktree intact, write current `phase_completed` to `.scaffold-state.json` |
| Merge conflict at gate | `git merge --no-ff` exits non-zero | Stop, list conflicting files, hand back to user. **Never** auto-resolve. |
| Nested invocation (other worktree) | inspector returns `inside-other-worktree` | Refuse with: *"This skill cannot be run from a non-scaffold worktree. Run it from the main checkout (`${MAIN_CHECKOUT}` from inspector output)."* |
| Re-entry into scaffold worktree | inspector returns `inside-scaffold-worktree` + state file present | Resume per SKILL.md Resumability section |
| Untracked files on re-run | `git status --porcelain` shows `??` lines | Preserve them. **Never** `git clean`. |
| Default branch is `master` not `main` | inspector `default_branch == "master"` | Use `master` everywhere `main` would appear in greenfield bootstrap |

### Dirty base-branch detection

The agent must verify `BASE_BRANCH` is clean *as a workspace*, not "different
from current checkout". Wrong check (compares branches, not dirtiness):

```bash
# WRONG — fails whenever current branch differs from dev
git diff --quiet dev -- .
```

Correct check:

```bash
# Right — checks the actual working tree of MAIN_CHECKOUT for tracked + untracked changes
[[ -z "$(git -C "${MAIN_CHECKOUT}" status --porcelain)" ]] || echo "MAIN_CHECKOUT is dirty"
```

Note: this checks the **main checkout's** working tree. If the main checkout
sits on a different branch than `BASE_BRANCH`, that is fine — `git worktree
add ... ${BASE_BRANCH}` operates on the named branch directly without
touching the main checkout's index. The dirtiness check just protects the
user's in-flight edits in the main checkout.

## Greenfield bootstrap

If Phase 0 returned `greenfield`:

```bash
# Use git ≥2.28's -b flag to set the initial branch directly.
# (Older git rejects -b; if you suspect git <2.28, run `git --version` first
# and fall back to `git init && git checkout -b "${default_branch:-main}"`.)
git init -b "${default_branch:-main}"
git commit --allow-empty -m "chore: initial empty commit"
git branch dev
```

If `default_branch` came back as `master` (older convention), substitute that
in. Confirm with the user before each command — greenfield init is a
"are you sure" moment.

After bootstrap, set `BASE_BRANCH=dev`.

## `not-a-repo` → greenfield handoff

If Phase 0 returned `not-a-repo` and the user chose to `git init` here:

1. Run **only** `git init -b "${default_branch:-main}"` first (this is the
   minimum to make the inspector usable — the empty commit and `dev` branch
   come later, gated by the greenfield bootstrap dialog above).
2. **Re-run** `inspect_repo_state.sh`. `MAIN_CHECKOUT` and `default_branch`
   will refresh from `null` to real values; `state` will become `greenfield`.
3. Follow the greenfield bootstrap section above (with per-command user
   confirmation), then set `BASE_BRANCH=dev`.

This sequencing preserves the per-command confirmation gate that bundling all
three commands into the `not-a-repo` decision would bypass.

## Merge gate (Phase 7)

Use the `git -C` form so the merge is cwd-independent:

```bash
git -C "${MAIN_CHECKOUT}" checkout "${BASE_BRANCH}"
git -C "${MAIN_CHECKOUT}" merge --no-ff "scaffold/${STACK_SLUG}-${SCAFFOLD_ID}" \
  -m "feat(scaffold): merge ${STACK_SLUG} baseline"
```

`--no-ff` is mandatory — it preserves the scaffold-as-a-unit history so the
merge commit anchors the entire baseline. The agent must reject any user
request to fast-forward or squash here without explicit override.

The explicit `-m` is mandatory — without it `git merge` drops into `$EDITOR`,
which hangs in non-interactive agent runs.

## What this flow never does

- `git push` (user's call after merge)
- `git push --force` (forbidden absolutely)
- `git reset --hard` (forbidden)
- `git worktree remove --force` (forbidden — only `git worktree remove` after asking)
- `git clean -f` (forbidden — would destroy untracked work)
- `--no-verify` on any commit (pre-commit hooks must run)
- Recompute `SCAFFOLD_ID` between path-creation and branch-creation (would drift)
