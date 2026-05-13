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
| feature | `(plan-feature, human-confirmed)` | merge commit on `${BASE_BRANCH}` | `plan.md` + `plan.mmd` committed on the merged branch |
| system | `(interfaces only, human-confirmed)` | merge commit on `${BASE_BRANCH}` | `architecture.html` + `architecture.mmd` committed on the merged branch |

The `system` marker is **unchanged from the pre-rename codebase-architect
skill** — that's deliberate. The downstream-gate semantic ("a committed
interface contract reviewed by a human") is load-bearing for any
implementer that already grep's for it. Other scales use the new
`plan-<scale>` family.

## Canonical gate check (feature + system)

```bash
test -f architecture.html && test -f architecture.mmd \
  && git log --grep='(interfaces only, human-confirmed)' --format=%H | grep -q .
```

OR

```bash
test -f plan.md && test -f plan.mmd \
  && git log --grep='(plan-feature, human-confirmed)' --format=%H | grep -q .
```

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
