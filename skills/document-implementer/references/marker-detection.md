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
| feature | `(document-plan-feature, human-confirmed)` | merge commit on `${BASE_BRANCH}` | `${RUN_DIR}/document-plan.md` + `${RUN_DIR}/document-structure.mmd` + valid YAML frontmatter |
| system | `(document-plan-system, human-confirmed)` | merge commit on `${BASE_BRANCH}` | `${RUN_DIR}/document-plan.md` + `${RUN_DIR}/document-structure.mmd` + `${RUN_DIR}/document-structure.html` + valid YAML frontmatter |

A micro/local marker found in `git log` is **refused as forged** —
those scales are chat-only by contract.

`${RUN_DIR}` is the planner's run-dir under `ai-artifacts/runs/doc/`,
resolved from the marker commit's git trailer — see
[Run-dir trailer resolution](#run-dir-trailer-resolution-featuresystem) below.

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

## Run-dir trailer resolution (feature/system)

The planner emits its artifacts under a per-run directory
`ai-artifacts/runs/doc/<slug>-<docplanner-id>/` and records that path as
a git trailer (`AI-Artifacts-Run-Dir:`) on the **second `-m`** of the
merge commit that lands the marker. The implementer resolves `RUN_DIR`
from that trailer; it never hardcodes a path or falls back to repo root.

`inspect_repo_state.sh` selects `PLANNER_MARKER_COMMIT` with a scan that
emits hash+ts+subject only (`--format='%H%x09%ct%x09%s'`) — it does NOT
see the commit body, so the trailer is read with a SECOND lookup:

```bash
TRAILER_LINES="$(git -C "${MAIN_CHECKOUT}" show -s --format=%B "${PLANNER_MARKER_COMMIT}" \
  | git interpret-trailers --parse | grep '^AI-Artifacts-Run-Dir:')"
# COUNT matches — refuse on 0 or >1 (do NOT tail -1; ambiguity is a hard error).
N="$(printf '%s' "${TRAILER_LINES}" | grep -c .)"
[ "${N}" -eq 1 ] || { echo "BLOCKER: expected exactly 1 AI-Artifacts-Run-Dir trailer, got ${N}."; exit 1; }

# Strip the key, then validate with an ANCHORED, SINGLE-LINE, DOC-CHAIN allowlist.
RUN_DIR="$(printf '%s' "${TRAILER_LINES}" | sed -e 's/^AI-Artifacts-Run-Dir:[[:space:]]*//')"
case "${RUN_DIR}" in
  ai-artifacts/runs/doc/*) ;;
  *) echo "BLOCKER: run-dir outside doc chain: ${RUN_DIR}"; exit 1 ;;
esac
printf '%s' "${RUN_DIR}" | grep -Eqx 'ai-artifacts/runs/doc/[a-z0-9-]+-[A-Za-z0-9._-]+' \
  || { echo "BLOCKER: run-dir failed allowlist: ${RUN_DIR}"; exit 1; }
# The anchored regex already rejects absolute paths, '..', and embedded
# whitespace/newline/CR (no '/' beyond the fixed prefix, no '.' runs).
```

Validate the per-lane artifacts exist **at the marker commit's tree**
(not HEAD) — the worktree may have advanced:

```bash
# feature
git cat-file -e "${PLANNER_MARKER_COMMIT}:${RUN_DIR}/document-plan.md"
git cat-file -e "${PLANNER_MARKER_COMMIT}:${RUN_DIR}/document-structure.mmd"
# system — additionally:
git cat-file -e "${PLANNER_MARKER_COMMIT}:${RUN_DIR}/document-structure.html"
```

Any failure on a feature/system marker → **REFUSE** (never fall back to
a root path). Persist the resolved dir as state field
`planner_artifact_dir`; on resume reuse it instead of re-resolving the
newest marker. Micro/local lanes have no planner commit → no trailer →
no `RUN_DIR` (the implementer uses its own id-keyed sibling dir for its
report; see [state-and-resume.md](state-and-resume.md)).

## Canonical gate check (feature + system)

```bash
# feature
test -f "${RUN_DIR}/document-plan.md" && test -f "${RUN_DIR}/document-structure.mmd" \
  && git log --grep='(document-plan-feature, human-confirmed)' --format=%H | grep -q . \
  && python3 "${CLAUDE_SKILL_DIR}/scripts/parse_frontmatter.py" "${RUN_DIR}/document-plan.md"

# system
test -f "${RUN_DIR}/document-plan.md" && test -f "${RUN_DIR}/document-structure.mmd" && test -f "${RUN_DIR}/document-structure.html" \
  && git log --grep='(document-plan-system, human-confirmed)' --format=%H | grep -q . \
  && python3 "${CLAUDE_SKILL_DIR}/scripts/parse_frontmatter.py" "${RUN_DIR}/document-plan.md"
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
- Treat presence of `${RUN_DIR}/document-plan.md` alone as sufficient —
  the marker commit must be in `git log`, its `AI-Artifacts-Run-Dir:`
  trailer must resolve to exactly one allowlisted run-dir, and
  `parse_frontmatter.py` must pass for feature/system.
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
