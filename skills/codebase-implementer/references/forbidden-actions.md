# Forbidden actions

The implementer is high-autonomy: no per-step confirmation. That makes
"what it must refuse to do" the load-bearing safety surface. This file
is the explicit list. The skill must refuse any of these even if the
user asks mid-flow (politely surface the request, default to refusal).

## Git operations — refuse outright

These come from the repo's `CLAUDE.md` "Hard rules when editing git
state" section and the planner's mirror:

- `git push`, `git push --force` — the user controls when to publish
- `git reset --hard`, `git clean -f`, `git worktree remove --force`
- `git merge` without `--no-ff` for the implementer branch (would
  collapse history that the merge marker is meant to mark)
- `git merge` or `git commit` without `-m` (would drop into `$EDITOR`
  and hang in non-interactive runs)
- `--no-verify` on commits (pre-commit hooks must run)
- `git commit --amend` once a commit lands on the implementer branch
  (create a new commit instead — amend rewrites history `--no-ff` was
  meant to preserve)
- `git rebase -i` (interactive — would hang non-interactively)
- Any flag with `--force` / `-f` semantics on a destructive operation

## Scope — refuse mid-loop

The implementer is **body-generation only**. These are not allowed
even if a docstring/plan seems to imply them:

- Adding new interfaces (system lane) or new files outside `files_hinted`
  (feature/micro/local) — that's re-architecting
- Renaming any committed public name (param, method, class, package)
- Changing method signatures the planner committed (system lane)
- Moving files between packages
- Adding new packages
- Re-classifying scale mid-run (e.g., "this micro is actually a
  feature") — surface as a blocker, don't silently expand
- "Polishing" code the loop did not write — out of scope
- Adding features the docstring/plan didn't ask for
- Adding error handling for cases the docstring's `failure_modes`
  field doesn't list (system lane)
- Editing `validation_command` configuration to skip failing tests
  (e.g., `package.json` scripts, `pytest.ini` markers) — this is
  silently relaxing the spec

## Gate — refuse to bypass

- Treating user silence as confirmation at any gate. Default to refusal
  on ambiguous input; re-ask.
- Generating method bodies without a planner marker (feature/system) OR
  without the chat-history gate (micro/local). Refuse with a clear
  pointer to `/codebase-planner`.
- Auto-bumping a missing-marker situation by invoking the planner
  yourself. The planner is human-gated; the implementer cannot stand
  in for that gate.
- Merging to `${BASE_BRANCH}` without the `confirm merge` token typed
  by the user in this conversation. A `confirm merge` from a prior
  session is not portable.
- Skipping the artifact-presence check at Phase 0 even if the marker
  is present (defense in depth — see
  [marker-detection.md](marker-detection.md)).

## File / repo hygiene

- Creating `README.md`, `INSTALLATION_GUIDE.md`, `QUICK_REFERENCE.md`,
  etc. inside this skill folder (the skill-creator validator rejects
  them; repeat the rule here so it's enforced when this skill
  modifies itself in some hypothetical future).
- Committing `.implementer-state.json` (gitignored per
  [git-worktree-flow.md](git-worktree-flow.md))
- Hardcoded language/framework major versions in any generated code or
  config (use placeholders; defer pinning to the user or the project's
  existing version files)
- Committing secrets. The Phase 3 commit cadence in `SKILL.md`
  includes a concrete grep against the staged diff for common
  credential signatures (`api_key`, `secret`, `password`, `bearer`,
  AWS keys, GitHub PATs `ghp_…`, Slack tokens `xox[abprs]-`). On any
  match: abort the commit and surface as a blocker. Layer a stronger
  scanner (`trufflehog`, `detect-secrets`, `gitleaks`) on top via a
  pre-commit hook if the project has one — the built-in check is a
  floor, not a ceiling.

## Pre-existing repo state — surface, don't silently fix

- Pre-existing failing tests on `${BASE_BRANCH}` — record as
  `baseline_validation_exit`, warn the user at Phase 1, do NOT "fix"
  them as part of this run
- Uncommitted local edits in files the implementer is about to touch
  — refuse, ask user to commit/stash/discard
- Detached HEAD, zero-commits repo, repo not under git — refuse
- Inside another skill's worktree (planner, scaffold, etc.) — refuse;
  the implementer's worktree must branch from `${BASE_BRANCH}`, not
  from another in-flight skill's branch

## Authority precedence (when guidance conflicts)

If a user instruction conflicts with this file:

1. The skill surfaces the conflict ("you asked X, this skill forbids
   it because Y").
2. Default to refusal.
3. The user can override only by editing this file in a separate PR,
   not via a mid-run instruction. The autonomy budget is bounded by
   the rules committed to the skill — that's the safety contract.

If the planner's `implementer-contract.md` conflicts with anything
here, **the planner contract wins** for the marker family and gate
semantics (it's the upstream spec). For everything else (git rules,
scope, hygiene), this file is authoritative.
