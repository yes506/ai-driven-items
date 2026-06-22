# Implementer contract — downstream gate per lane

Skills, subagents, and Claude sessions that intend to write
**implementation** code based on a `codebase-planner` run MUST honor the
scale-tagged marker family below. This replaces the single-marker gate
from the pre-rename `codebase-architect` skill.

## Marker family

All markers follow the form `(<scale-tag>, human-confirmed)` and appear
verbatim in the merge commit message that lands the planner branch on
`${BASE_BRANCH}`.

| Scale | Marker | Where it lives | Artifacts that satisfy the gate |
|---|---|---|---|
| micro | `(plan-micro, human-confirmed)` | chat history only — no commit | the in-chat confirmation token from the user |
| local | `(plan-local, human-confirmed)` | chat history only — no commit | the in-chat confirmation token |
| feature | `(plan-feature, human-confirmed)` | merge commit on `${BASE_BRANCH}` | `$RUN_DIR/plan.md` + `$RUN_DIR/plan.mmd` committed on the merged branch |
| system | `(interfaces only, human-confirmed)` | merge commit on `${BASE_BRANCH}` | `$RUN_DIR/architecture.html` + `$RUN_DIR/architecture.mmd` committed on the merged branch |

`$RUN_DIR` is `ai-artifacts/runs/code/<slug>-<planner-id>`, carried as
the `AI-Artifacts-Run-Dir:` git trailer on the merge commit's body. The
implementer resolves it by parsing that trailer (the marker scan emits
subject only), validates it against an anchored allowlist
(`^ai-artifacts/runs/code/[a-z0-9-]+-[A-Za-z0-9._-]+$`; reject absolute,
`..`, whitespace), then checks the artifacts at the marker commit's tree.

The `system` marker is **unchanged from the pre-rename codebase-architect
skill** — that's deliberate. The downstream-gate semantic ("a committed
interface contract reviewed by a human") is load-bearing for any
implementer that already grep's for it. Other scales use the new
`plan-<scale>` family.

## Canonical gate check (feature + system)

Select the marker commit **once** as `PLANNER_MARKER_COMMIT`, resolve
`$RUN_DIR` from THAT commit's `AI-Artifacts-Run-Dir:` trailer, then check
the artifacts at THAT same commit's tree. Do **not** re-query `git log`
per artifact — pairing a `$RUN_DIR` from one marker commit with another
commit's tree is a false-pass/false-fail bug when more than one planner
run exists in history. This mirrors
`codebase-implementer/references/marker-detection.md` (the gold reference):

```bash
# 1. select the marker commit ONCE. System lane shown; for the feature lane
#    swap the grep to '(plan-feature, human-confirmed)' AND set
#    PLANNER_MARKER_SCALE=feature. (A real implementer derives both from the
#    inspector's single marker scan — see the codebase-implementer mirror.)
PLANNER_MARKER_COMMIT="$(git -C "${MAIN_CHECKOUT}" log \
  --grep='(interfaces only, human-confirmed)' --format=%H | head -1)"
PLANNER_MARKER_SCALE=system
[ -n "${PLANNER_MARKER_COMMIT}" ] || { echo "BLOCKER: no confirmed planner marker in git log"; exit 1; }

# 2. resolve $RUN_DIR from the SECOND -m (git trailer) on THAT commit
TRAILER="$(git -C "${MAIN_CHECKOUT}" show -s --format=%B "${PLANNER_MARKER_COMMIT}" \
  | git interpret-trailers --parse | grep '^AI-Artifacts-Run-Dir:' || true)"
[ "$(printf '%s' "${TRAILER}" | grep -c .)" -eq 1 ] \
  || { echo "BLOCKER: expected exactly 1 AI-Artifacts-Run-Dir trailer"; exit 1; }   # never tail -1
RUN_DIR="$(printf '%s' "${TRAILER}" | sed 's/^AI-Artifacts-Run-Dir:[[:space:]]*//')"
printf '%s' "${RUN_DIR}" | grep -Eqx '^ai-artifacts/runs/code/[a-z0-9-]+-[A-Za-z0-9._-]+$' \
  || { echo "BLOCKER: run-dir failed code-chain allowlist"; exit 1; }   # rejects absolute, '..', whitespace

# 3. verify per-lane artifacts at the MARKER COMMIT's tree (not test -f on
#    HEAD — a later commit could move/delete them). Branch by the marker
#    scale (system for the '(interfaces only)' marker, feature for
#    '(plan-feature)') so a verbatim copy checks only that lane's artifacts.
case "${PLANNER_MARKER_SCALE}" in
  system)
    git cat-file -e "${PLANNER_MARKER_COMMIT}:${RUN_DIR}/architecture.html" 2>/dev/null \
      && git cat-file -e "${PLANNER_MARKER_COMMIT}:${RUN_DIR}/architecture.mmd" 2>/dev/null \
      || { echo "BLOCKER: architecture.{html,mmd} missing at ${PLANNER_MARKER_COMMIT}:${RUN_DIR}"; exit 1; }
    ;;
  feature)
    git cat-file -e "${PLANNER_MARKER_COMMIT}:${RUN_DIR}/plan.md" 2>/dev/null \
      && git cat-file -e "${PLANNER_MARKER_COMMIT}:${RUN_DIR}/plan.mmd" 2>/dev/null \
      || { echo "BLOCKER: plan.{md,mmd} missing at ${PLANNER_MARKER_COMMIT}:${RUN_DIR}"; exit 1; }
    ;;
  *)
    # Fail closed: an unset/unexpected scale must never skip artifact checks.
    echo "BLOCKER: unexpected planner marker scale: ${PLANNER_MARKER_SCALE:-<unset>}"; exit 1
    ;;
esac
```

Any failure on a feature/system marker → REFUSE; never fall back to a
root path.

## Canonical gate check (micro + local)

No file-system check. The implementer must verify the chat history
contains BOTH:

1. A planner output block tagged with `scale: micro` or `scale: local`,
   AND
2. A user confirmation token (`confirm plan` typed by the user) within
   the same conversation.

If the implementer can't see the planner output (e.g., running in a
fresh session), the gate fails and the implementer must refuse.

## What downstream agents must NOT do

- Generate method bodies for any planner output that has no marker —
  this includes a planner that crashed before Phase 8 (system) or one
  that printed a plan but never received `confirm plan` (micro/local).
- Treat presence of `architecture.html` alone as sufficient — the
  marker commit must also be reachable in `git log` history.
- Auto-bump a missing-marker situation by re-running the planner — the
  planner is gated on human confirmation, not on AI judgment.

## Honest limitations

The marker is a **documented social contract, not a cryptographic one**.
A determined user can hand-craft the marker files and a fake merge
commit to bypass any of these checks; the goal is to catch accidental
misuse and make any deliberate bypass visible in git history. Stronger
enforcement (signed commits, git notes verified against a maintainer
key, an external attestation service) is out of scope for this skill
and the implementer contract — layer it on top if your project needs it.

## Backward compatibility note

The pre-rename `codebase-architect` skill emitted the marker
`(interfaces only, human-confirmed)`. This skill preserves that exact
marker for the system scale, so any in-flight branches or repos that
already landed an architect-merge commit continue to pass the gate.

There is intentionally NO compatibility shim for the lower scales (they
didn't exist before the rename); they are new and additive.
