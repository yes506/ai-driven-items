# Verification dimensions (Phase 2)

Phase 2 runs **four** verification dimensions on the loaded `INTENT`
+ `SEEDS`, building an in-memory `FINDINGS` list. Each finding has:

```
{
  dimension:        1 | 2 | 3 | 4,
  severity:         "blocker" | "major" | "minor",
  locus:            "intent.<field>" | "seed.<resource-slug>" | "seed-pair[<slug-A>,<slug-B>]" | "planner-rubric.<gap>",
  description:      "<one-sentence statement of the issue>",
  resolution_mode:  "auto" | "needs-user"
}
```

`severity` is informational only — it sequences the Phase 3 dialog
(blockers first, minors last) but doesn't gate anything.

`resolution_mode = "auto"` is reserved for findings whose resolution
the skill can default-handle without user input — currently only:
- Dim 2 dead-weight seed (rationale claims to inform a field but
  content is clearly unrelated): default action is "drop from
  Evidence inventory" — logged as auto-resolved.
- Dim 2 duplicate seeds (two seeds with identical
  `extracted_content` for the same intent field): default action is
  "keep first, log second as duplicate of first" — logged as
  auto-resolved.

All other findings (contradictions, gaps, conflicts) are
`needs-user`.

## Dim 1 — Intent self-consistency

**Inputs**: `INTENT` (parsed 6 rubric fields). Optionally re-read
intent.md for `## Examples` and `## Counter-examples` (which the
state file doesn't load, per intent-loading.md).

**Checks**:

| Check | What to flag |
|---|---|
| Constraint vs Success criterion conflict | A Constraint forbids X; a Success criterion requires X. (E.g., Constraint "must work offline" + Success criterion "real-time collaboration with remote peers".) |
| Examples vs Out-of-scope conflict | An Example demonstrates behavior the Out-of-scope explicitly excludes. (E.g., Out-of-scope: "third-party login providers"; Example: "user signs in with Google".) |
| Open question blocking | An Open question whose unresolved status would make any plan ambiguous. (E.g., "should we support iOS Safari?" left open → planner can't decide scope.) |
| Empty critical fields | `goal` is empty / `[unspecified]`; OR both `in_scope` AND `success_criteria` are empty. |
| Mutually exclusive bullets | Two bullets in the same field that can't both be true. (E.g., In-scope: "must work as PWA" + "must work without service workers".) |

**Sample findings**:

- *"Constraint #2 ('must work offline') conflicts with Success criterion #1 ('real-time collaboration with remote peers'). Resolve by: (a) drop the constraint, (b) drop the success criterion, (c) reword both to coexist (e.g., 'offline-tolerant with sync-on-reconnect')."*
- *"Open question 'should we support iOS Safari?' blocks the planner from picking a scale lane — Safari support is a scope signal. Resolve with: (a) yes, include iOS Safari, (b) no, exclude it, (d) defer (will add to remaining open questions)."*

## Dim 2 — Seeds vs intent

**Inputs**: `SEEDS` + `INTENT`. Skipped entirely if `SEEDS == []`
(intent-only mode).

**Checks per seed**:

| Check | What to flag |
|---|---|
| Plausibility of rationale | The seed's `relevance_rationale` claims to inform intent.field-X. Read the `extracted_content` — does it actually inform field-X? If not, flag as "rationale mismatch" (likely dead weight). |
| Contradiction with intent | The seed advocates / cites a feature the intent's `out_of_scope` explicitly excludes. (E.g., intent excludes OAuth providers; seed cites a Google OAuth integration tutorial.) |
| Stale-source signal | The seed's `source` is a known-stale resource (older than 2 years on a fast-moving topic, or a deprecated API doc URL). This is heuristic and `severity: minor` — don't refuse, surface for user awareness. |

**Auto-resolvable**:

- Dead-weight seed (rationale-mismatch) → auto-mark "drop from Evidence inventory; log under Resolved ambiguities as 'seed dropped: dead weight'".
- Duplicate seeds (same `extracted_content` for the same intent field) → auto-mark "kept first; second logged as duplicate".

**Needs-user**:

- Out-of-scope contradiction (the seed pushes excluded behavior) →
  ask: *"Seed `<slug>` advocates `<X>` which intent's Out-of-scope
  excludes. Resolve by: (a) drop the seed (it's noise), (b) re-scope
  the intent's Out-of-scope (the user changed their mind), (c) keep
  the seed but log the contradiction in the plan's Remaining open
  questions."*

## Dim 3 — Seeds vs seeds

**Inputs**: `SEEDS` (pairwise). Skipped if `len(SEEDS) < 2`.

**Checks** (pairwise per `(seed_A, seed_B)` where A ≠ B):

| Check | What to flag |
|---|---|
| Factual claim conflict | seed_A's extracted_content cites fact-X one way; seed_B cites fact-X differently. Use `source` for attribution. |
| API contract conflict | seed_A documents an API signature one way; seed_B documents it differently. (Common when a library version bumped between extractions.) |
| Version-number conflict | seed_A cites version V₁; seed_B cites V₂; both for the same library/spec. |
| Pricing / quota conflict | seed_A says service costs $X / has quota Y; seed_B says $Z / quota W. |

**Sample finding**:

- *"Conflict between seed `nextjs-caching` (source: https://nextjs.org/docs/app/.../caching, claims default cache TTL = 1y) and seed `nextjs-blog-post` (source: https://example.com/blog/nextjs-caching-deep-dive, claims default cache TTL = 30d). Resolve by: (a) trust the official docs (drop the blog claim from Evidence inventory), (b) trust the blog (likely more recent), (d) defer — log both in Remaining open questions for codebase-planner to investigate."*

**No auto-resolution**: every Dim 3 finding is `needs-user` — the
skill can't know which source is authoritative.

## Dim 4 — Planner-rubric completeness

**Inputs**: `INTENT` + `SEEDS`. Always runs (even intent-only).

**Background**: `codebase-planner` picks a scale lane based on a
scored `(scope, risk, ambiguity)` tuple. Plan-establisher's job here
is to make sure that tuple is computable from the plan — not to
compute it (codebase-planner does that), but to flag gaps where the
inputs are missing.

**Checks**:

| Check | What to flag |
|---|---|
| Scope signal | Do INTENT + SEEDS together name (or hint at) which files / modules / surfaces will be touched? "the dashboard UI" is a hint; "src/components/Dashboard.tsx" is concrete. If neither: flag as scope gap. |
| Risk signal | Test coverage of the touched area? Blast radius if the change breaks? Both either named in INTENT.Constraints or in seed extracts? If neither: flag as risk gap. |
| Ambiguity signal | Remaining open questions count, contradictions found in Dim 1, conflicts in Dim 3 — these are the ambiguity inputs. Phase 3 surfaces these in `Remaining open questions`; codebase-planner reads that to size ambiguity. No action needed unless ALL open questions resolved AND no Dim 1/3 findings AND the plan is still hand-wavy on what concretely changes — then flag as "ambiguity signal absent but scope/risk also weak; planner will have nothing to size against." |
| `[unspecified]` markers | Any field in INTENT that's still `[unspecified]` after the user finishes intent-aligner is a planner-rubric gap. Flag each one for user resolution OR explicit `accept remaining`. |

**Sample findings**:

- *"Scope gap: intent says 'speed up the search page' but no INTENT field or seed extract names which files / modules implement the search page. Resolve by: (a) name the file(s) — type the path, (b) name the module — type the module name, (d) defer to codebase-planner — it can `grep` for 'search' and propose (will be logged in Remaining open questions)."*
- *"Constraint #3 is `[unspecified]`. The planner needs constraints to size risk. Resolve by: (a) provide a constraint — type it verbatim, (b) confirm there really are no constraints — log under Resolved ambiguities as 'no constraints by user confirmation'."*

## Empty-SEEDS mode (intent-only)

If `SEEDS == []`, Phase 2 runs **only Dim 1 + Dim 4**. Dim 2 and Dim
3 record no findings. The synthesis at Phase 3 fills `Evidence
inventory` with the placeholder `(intent-only — no seeds available)`
and codebase-planner reads that and adjusts (likely asks the user
more questions itself, or recommends running `/seed-gatherer`).

This is a documented mode, not an error path — the user may want
intent-only planning for small or quickly-shaped tasks.

## Ordering at Phase 2

Run dimensions in order: 1 → 2 → 3 → 4. Reasons:

- Dim 1 findings may make Dim 2/3 redundant (if intent's Out-of-scope
  is a contradiction, no point evaluating seeds against it until the
  contradiction is resolved). Default behavior: still run all four,
  but surface Dim 1 findings first at Phase 3 so the user resolves
  them before being asked about downstream issues.
- Dim 4 needs the count of unresolved Dim 1/3 findings to assess
  ambiguity signal — so it must run last.

## What this dimension list does NOT cover

- **Code-level verification** (does the proposed plan compile / pass
  tests?) — that's `codebase-implementer`'s job, not plan-establisher.
- **Schema validation** of intent.md / seeds/ — that's
  intent-aligner / seed-gatherer's job (their loaders refuse
  malformed inputs).
- **External truth-checking** (is the cited fact actually true?) —
  plan-establisher can only check internal consistency. The
  responsibility for source-truth lies with whoever curated the
  seeds in the first place.
- **Estimate verification** (is the proposed scale lane realistic?) —
  plan-establisher proposes the lane; codebase-planner may override.
  We don't second-guess the planner's lane logic.
