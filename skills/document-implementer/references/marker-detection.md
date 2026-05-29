# Marker detection + upstream gate

**MIRROR DISCIPLINE**: this file mirrors the canonical contract at
`skills/document-planner/references/implementer-contract.md`. On any
divergence, **the planner contract wins** — update the planner-side
first, then mirror here. Drift caught at review time (no runtime
hash check). This rule exists to prevent the F-R4-1 + F-V4-1
bug-propagation pattern documented in the chain's review-discipline notes.

## Upstream marker family (planner-side)

| Scale | Upstream marker | Where it lives | Artifacts to verify |
|---|---|---|---|
| micro | `(document-plan-micro, human-confirmed)` | chat history — no commit | chat-handoff block (6 fields) + `confirm plan` token |
| local | `(document-plan-local, human-confirmed)` | chat history — no commit | chat-handoff block (6 fields) + `confirm plan` token |
| feature | `(document-plan-feature, human-confirmed)` | merge commit on `${BASE_BRANCH}` | `document-plan.md` + `document-structure.mmd` + valid YAML frontmatter |
| system | `(document-plan-system, human-confirmed)` | merge commit on `${BASE_BRANCH}` | `document-plan.md` + `document-structure.mmd` + `document-structure.html` + valid YAML frontmatter |

A micro/local marker found in `git log` is **refused as forged** —
those scales are chat-only by contract.

## Downstream marker family (this skill)

| Scale | Downstream marker | Where it lives |
|---|---|---|
| micro | `(document-impl-micro, human-confirmed)` | merge commit on `${BASE_BRANCH}` |
| local | `(document-impl-local, human-confirmed)` | merge commit on `${BASE_BRANCH}` |
| feature | `(document-impl-feature, human-confirmed)` | merge commit on `${BASE_BRANCH}` |
| system | `(document-impl-system, human-confirmed)` | merge commit on `${BASE_BRANCH}` |

The implementer-side merges to `${BASE_BRANCH}` for ALL scales
(unlike the planner which keeps micro/local chat-only). This is the
implementer's contract output — downstream tooling greps `git log`
for `(document-impl-` to detect implementer landings.

## Canonical gate check (feature + system)

```bash
# feature
test -f document-plan.md && test -f document-structure.mmd \
  && git log --grep='(document-plan-feature, human-confirmed)' --format=%H | grep -q . \
  && python3 "${CLAUDE_SKILL_DIR}/scripts/parse_frontmatter.py" document-plan.md

# system
test -f document-plan.md && test -f document-structure.mmd && test -f document-structure.html \
  && git log --grep='(document-plan-system, human-confirmed)' --format=%H | grep -q . \
  && python3 "${CLAUDE_SKILL_DIR}/scripts/parse_frontmatter.py" document-plan.md
```

## Canonical gate check (micro + local) — chronological pairing

The chat-only gate uses the planner's emission order:

```
[earliest] light/plan content (3–7 bullet reflection)
           ↓
           [user revises → planner re-emits light/plan; 0..N revise cycles]
           ↓
           User token: `confirm plan`
           ↓
[latest]   Handoff block (6 fields) — emitted ON confirm
```

Pairing algorithm:

1. **Locate the handoff block** visible in the current conversation
   (not pasted). Must have 6 fields: DOCTYPE, OUTPUT_STACK, AUDIENCE,
   OUTPUT_LANGUAGE, TARGET_PATH, MARKER.
2. **Walk backward** to the nearest preceding `confirm plan` token.
3. **Walk further backward** to the nearest preceding `light/plan`
   content before that `confirm plan` — these are the bullets the
   user confirmed.

Older `light/plan` blocks before a `revise` / earlier confirm are
**superseded, not ambiguous**.

**Refuse only when** (each rule fires the matching worked-example
case below):

- **(a)** Multiple plausible `light/plan` blocks at the same
  chronological position (two consecutive with no `revise` /
  `escalate` between them).
- **(b)** No `confirm plan` token between the matched `light/plan`
  and the handoff block.
- **(c)** A `revise` / `escalate` token appears AFTER the matched
  `light/plan` and BEFORE the matched `confirm plan` (later
  `light/plan` should have been emitted).
- **(d)** Any `light/plan` token appears AFTER the matched
  `confirm plan` AND BEFORE the handoff block (planner emitted a
  later reflection never user-confirmed).

### Worked examples

| Transcript pattern | Decision | Rule fired |
|---|---|---|
| `light/plan` → `confirm plan` → handoff | Pair. Normal path. | — |
| `light/plan` → `revise` → `light/plan` → `confirm plan` → handoff | Pair 2nd light/plan. 1st superseded. | — |
| `light/plan` → `light/plan` → `confirm plan` → handoff | Refuse — ambiguous. | (a) |
| `light/plan` → `confirm plan` → `light/plan` → handoff | Refuse — orphan after confirm. | (d) |
| Handoff with no `light/plan` visible | Refuse — fresh session / pasted. | (b) |
| `light/plan` in chat, no `confirm plan` | Refuse — user never confirmed. | (b) |

**Chat is canonical.** The `publish_thought.sh`-emitted collab-memory
file `docplanner-<DOCPLANNER_ID>-phase-light-plan.md` MAY be
consulted as a debug aid (e.g., disambiguate two visually similar
runs in the same conversation by `DOCPLANNER_ID`) but cannot
substitute for missing chat content.

Pasted transcripts do not satisfy the gate.

## TARGET_PATH extension validation

Phase 0 cross-checks `TARGET_PATH` extension against `OUTPUT_STACK`:

| OUTPUT_STACK | DOCTYPE | Acceptable extensions |
|---|---|---|
| text | api-spec | `.md`, `.markdown` |
| text | tech-spec | `.md`, `.markdown` |
| text | runbook | `.md`, `.markdown` |
| structured | ppt | `.pptx` |

Mismatch → refuse: re-run document-planner with the correct path.
(OpenAPI YAML for api-spec deferred to v1.5 — text-stack rules
can't generate valid OpenAPI.)

## What downstream agents MUST NOT do

- Generate prose for a planner output with no marker (or no chat-gate
  for micro/local).
- Treat presence of `document-plan.md` alone as sufficient — the
  marker commit must be in `git log`, and `parse_frontmatter.py` must
  pass for feature/system.
- Reuse codebase-planner's `(plan-<scale>, …)` or
  `(interfaces only, …)` markers. Those are code markers.
- Ship literal `[[stub-id]]` references to the user-facing document.
- Auto-bump a missing-marker situation by re-running the planner.

## Honest limitations

The gate is a **documented social contract**, not cryptographic. A
determined user can hand-craft markers + fake merge commits to
bypass; the goal is to catch accidental misuse and make deliberate
bypass visible in git history. Signed commits / git notes /
external attestation are out of scope.
