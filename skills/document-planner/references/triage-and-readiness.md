# Phase 0.5 — Triage & readiness (document-shaped)

Picks the right **scale lane** (micro / local / feature / system) for
the document and surfaces readiness blockers before any worktree
mutation. Mirrors codebase-planner's structure, but every axis is
re-grounded in document semantics — the code-shaped `(scope, risk,
ambiguity)` tuple does NOT transfer verbatim.

## Discovery first (no user questions yet)

Before scoring, scan and surface what's already known:

1. `plan.<intent-slug>.v<N>.md` at repo root (highest `N`) — per
   [plan-ingestion.md](plan-ingestion.md). If present, its
   `Proposed scale lane` is the default.
2. The intent doc (`intent.<intent-slug>.md`) if present.
3. `CLAUDE.md`, `AGENTS.md`, `README.md` at repo root + nearest
   ancestor.
4. `git log -n 20 --oneline -- <related-path>` if the user named a
   path during invocation.

Print a 3-bullet "discovery summary" before scoring. This is the
shared evidence base for the score.

## Score tuple: (scope, risk, ambiguity)

Each axis scored 0–3 with reasoning shown. `scope` is content-volume
only — format complexity does NOT enter scope (it's handled
orthogonally by `OUTPUT_STACK`).

### scope — content volume + audience breadth

| Score | Heuristic |
|---|---|
| 0 | 1 stub (one section / one slide / one endpoint / one step), single internal audience |
| 1 | 2–5 stubs, single audience, no cross-stub dependencies |
| 2 | 6–15 stubs, OR mixed audiences, OR meaningful cross-stub dependencies |
| 3 | >15 stubs, OR multiple external/regulated audiences, OR deep dependency graph |

Stub counts are estimates from Phase 1 discovery — don't ask the user
for an exact count, infer it from the surfaced material.

### risk — accuracy / compliance / reputational

Document risk is NOT runtime-failure risk. It's the cost of being
wrong about a claim, missing evidence for a regulated audience, or
shipping something that misrepresents the product.

| Score | Heuristic |
|---|---|
| 0 | Internal-only, advisory, easily revisable |
| 1 | Internal-canonical (becomes the reference), but no external audience |
| 2 | External audience (partner, customer, regulator) OR irrevocable claims (commitments, SLOs) |
| 3 | Regulated/compliance content (security, financial, medical), legal review required, or contractual obligations |

### ambiguity — unresolved claims / evidence / audience

Document ambiguity is about **what to say** and **to whom** — not
about runtime behavior.

| Score | Heuristic |
|---|---|
| 0 | Goal, audience, claims, evidence all clear from plan-establisher output |
| 1 | One open question (e.g. unclear audience scope, or one evidence gap) |
| 2 | Multiple open questions, OR conflicting evidence sources, OR audience not yet defined |
| 3 | Goal itself is unclear; substantive product-level questions need answering before planning can proceed |

## Lane resolution

```
final_scale = max(scope, risk)
```

Then map:

| `final_scale` | Lane |
|---|---|
| 0 | `micro` |
| 1 | `local` |
| 2 | `feature` |
| 3 | `system` |

The accepted plan-establisher plan's `Proposed scale lane` is the
default unless `final_scale` strictly exceeds it (upgrade allowed
freely). Downgrade from the plan's recommendation requires explicit
user `confirm downgrade`.

## Block-and-resolve rule

If `ambiguity >= 2` AND `final_scale <= 1`, do NOT proceed silently.
One consolidated question round addresses the unresolved items; then
re-score with the answers. Silent upgrades from a high-ambiguity
state to a heavy lane mask product questions the user should answer.

Run at most ONE block-and-resolve round. If ambiguity remains after,
escalate to the user: "Multiple open questions remain. I recommend
the **feature** lane so the plan captures them as `open_questions`
in stubs; or you can `revise` and answer them first." Accept either
choice.

## Worked examples

**A. Lightweight refresh of an internal onboarding doc**
- discovery: existing `onboarding.md` + one bullet of changes
- scope=0 (1–2 sections touched), risk=0 (internal), ambiguity=0
- `final_scale=0` → `micro`. Chat-only handoff block at end.

**B. New tech-spec for a feature shipping next quarter**
- discovery: plan-establisher plan present; ~8 sections projected
- scope=2, risk=1 (internal canonical), ambiguity=0
- `final_scale=2` → `feature`. Worktree + `document-plan.md` +
  `document-structure.mmd`.

**C. Customer-facing API reference v2**
- discovery: ~30 endpoints, customer-facing, contract-affecting
- scope=3, risk=2 (external + irrevocable), ambiguity=1 (auth scheme
  still under review)
- `final_scale=3` → `system`. Full structure package + HTML preview.

**D. Compliance runbook for incident response**
- discovery: regulated content, SLA-bound
- scope=1, risk=3 (regulated/compliance), ambiguity=2 (escalation
  path unclear)
- `final_scale=3` → `system` (driven by risk). Block-and-resolve
  triggered because ambiguity≥2.

## Worked anti-pattern — what NOT to do

Don't let `OUTPUT_STACK = structured` (ppt) auto-promote a 3-slide
deck to `system`. A short deck for an internal audience is
scope=0–1, risk=0, → `micro` or `local`, regardless of toolchain.
The implementer toolchain choice is orthogonal to planning weight.

## Output

After scoring, print:

```
SCALE:         <micro|local|feature|system>
DOCTYPE:       <api-spec|tech-spec|runbook|ppt>
OUTPUT_STACK:  <text|structured>
TARGET_PATH:   <path>
scope=<n> risk=<n> ambiguity=<n> — <one-line reasoning>
```

Then prompt: `confirm scale` to proceed, suggest a different lane
(upgrades free, downgrades need `confirm downgrade`), or `revise`
to re-do classification.
