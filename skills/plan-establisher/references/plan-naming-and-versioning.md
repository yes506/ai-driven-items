# Plan naming and versioning

Each invocation emits one plan pair:
`plan.<intent-slug>.v<N>.md` and `plan.<intent-slug>.v<N>.html` at
the repo root (sibling to `intent.<slug>.md` and `seeds/`).

The `<intent-slug>` part is fixed for the run (chosen at Phase 1, see
[intent-loading.md](intent-loading.md)). The `v<N>` part is
**monotonic**: each invocation gets the next free N, prior versions
are preserved.

## Version-number computation

### At Phase 1 (tentative pick)

After loading the intent, scan for existing plans:

```bash
existing="$(ls -1 "${MAIN_CHECKOUT}"/plan."${INTENT_SLUG}".v*.md 2>/dev/null \
  | sed -nE 's|.*/plan\.[a-z0-9-]+\.v([0-9]+)\.md$|\1|p' \
  | sort -n | tail -1)"
N="${existing:-0}"
N=$((N + 1))
```

If no `plan.<INTENT_SLUG>.v*.md` exists → `N = 1`.
Otherwise → `N = max(existing) + 1`.

This tentative `N` is held in memory through Phases 2–4 and persisted
to `.plan-state.json` at Phase 4 as `plan_version`.

### At Phase 5 (race-guard re-scan)

Re-scan `plan.<INTENT_SLUG>.v*.md` at the start of Phase 5, just
before computing the target filename:

```bash
existing_at_emit="$(ls -1 "${MAIN_CHECKOUT}"/plan."${INTENT_SLUG}".v*.md 2>/dev/null \
  | sed -nE 's|.*/plan\.[a-z0-9-]+\.v([0-9]+)\.md$|\1|p' \
  | sort -n | tail -1)"
MAX_EXISTING="${existing_at_emit:-0}"

if [ "${MAX_EXISTING}" -ge "${N}" ]; then
  NEW_N=$((MAX_EXISTING + 1))
  # Notify user in chat about the bump (mandatory — never silent):
  #   English: "Plan version race detected — another plan v<N>...v<MAX_EXISTING>
  #             landed since Phase 1. Bumping this plan's version from v<N>
  #             to v<NEW_N> to preserve all prior plans."
  #   Korean:  "플랜 버전 충돌 감지 — Phase 1 이후 다른 플랜 v<N>...v<MAX_EXISTING>이
  #             병합되었습니다. 모든 이전 플랜을 보존하기 위해 이 플랜의 버전을
  #             v<N>에서 v<NEW_N>로 올립니다."
  N="${NEW_N}"
  # Update state's plan_version field BEFORE writing the file so a crash
  # leaves state pointing at the actually-used version.
fi
```

**Why re-scan**: the worktree-creation pattern (Phase 4) isolates *this
worktree's branch* from concurrent edits to `dev`, but the user can
manually run `/plan-establisher` from a separate terminal in parallel,
or another seed/intent/plan worktree could merge a `plan.<slug>.v*.md`
between this run's Phase 1 and Phase 5. Worktree isolation doesn't
protect the version-number namespace; the re-scan does.

In practice: parallel plan runs for the same intent are rare. The
re-scan adds a few milliseconds and almost always confirms the Phase-1
pick. When it doesn't, the bump-and-notify path is safe (preserves
prior plans, surfaces the bump to the user).

## Filename format

- Markdown: `plan.<intent-slug>.v<N>.md`
- HTML:     `plan.<intent-slug>.v<N>.html`

Where:
- `<intent-slug>` is `[a-z0-9-]+` (already sanitized by intent-aligner; this skill applies a positive whitelist as a defensive re-check at Phase 4)
- `<N>` is a decimal integer ≥ 1, no leading zeros (so `v1`, `v2`, ..., `v10`, ..., `v100`)

Both files share the same `<intent-slug>` and `<N>` so they're a
pair. The `.html` is regenerated from `.plan-state.json` by the
renderer; the `.md` is written directly by the skill.

## What codebase-planner reads

`codebase-planner` reads the **highest-N** `plan.<intent-slug>.v<N>.md`
at the repo root for the chosen intent. Implementation hint for the
downstream planner (it picks this up from its own SKILL.md when it
ships, not this file):

```bash
latest="$(ls -1 "${REPO_ROOT}"/plan."${INTENT_SLUG}".v*.md 2>/dev/null \
  | sed -nE 's|.*/plan\.[a-z0-9-]+\.v([0-9]+)\.md$|\1|p' \
  | sort -n | tail -1)"
plan_file="${REPO_ROOT}/plan.${INTENT_SLUG}.v${latest}.md"
```

If the planner finds no plan: it should refuse with *"No
`plan.<intent-slug>.v*.md` found — run `/plan-establisher` first."*

## Why monotonic versions (not overwrite)

Three reasons:

1. **Audit trail**: when a plan evolves across runs (the user added
   seeds, refined intent, ran establisher again), prior versions
   show how the thinking changed. Useful for both human reviewers
   and the downstream codebase-implementer if it ever needs to
   compare scope drift between planner runs.

2. **Recovery from regressions**: if v3 introduces a wrong scale-lane
   recommendation that the planner accepts and the implementer
   builds against, the user can quickly diff v3 vs v2 to see what
   changed and roll back the planning decision without re-running
   the whole chain.

3. **Consistency with seed-gather-for-plan's append-only contract**:
   the seed accumulation model is "preserve, don't replace". Plans
   follow the same pattern, so the chain's storage model is
   consistent — every skill in the chain accumulates rather than
   overwrites.

## Escape hatch: replacing a prior plan

If the user wants to **replace** rather than preserve a prior plan
version (e.g., v3 was a thinko, they want v4 to be the canonical
starting point), the path is:

1. On `${BASE_BRANCH}` (NOT inside the plan worktree), `rm` both
   `plan.<intent-slug>.v<N>.md` AND `plan.<intent-slug>.v<N>.html`
   for every version the user wants gone. **Both files in the pair**
   — removing only the `.md` leaves an orphan `.html` until the next
   emit.
2. **Commit the removal**. (Skipping the commit trips Phase 4's
   dirty-`BASE_BRANCH` guard, which refuses to create the new
   worktree until the working tree is clean.)
3. Re-run `/plan-establisher`. The Phase 1 scan now sees only the
   surviving versions, and the new run's `N` will pick up from
   `max(survivors) + 1` (or `1` if no survivors).

If the user wants the new emit to actually pick up `vN` where N is
the previously-deleted number (collapsing the gap), they need to
also `rm` every higher version on `${BASE_BRANCH}` — the scan picks
`max + 1`, so leaving `v5` in place forces the next emit to be `v6`
even if `v3` and `v4` are gone.

This escape hatch is documented but rarely needed; the default
append-only behavior is the recommended path.

## Honest limitations

- **No content-based dedup**: if the user re-runs `/plan-establisher`
  with the same intent and seeds and gets identical content, the
  skill still emits a new version (v(N+1)) rather than detecting "no
  change". This is intentional — change-detection would need a
  semantic diff that's beyond this skill's scope, and the cost of
  an extra version is low.
- **No format-version drift handling**: the `plan-establisher
  format version` field in Provenance starts at `1.0`. If a future
  version bumps the schema, codebase-planner reads the field and
  *can* warn on mismatch — but plan-establisher itself doesn't
  produce or consume cross-version plans. Each version of this
  skill assumes its own schema.
- **`N` is global per (intent, repo)** — not per-user, per-branch,
  or per-anything-else. Two collaborators planning the same intent
  in parallel will collide in their N picks; the Phase 5 race-guard
  catches that on the second one's emit, but they should coordinate
  out-of-band to avoid wasted plan iterations.
