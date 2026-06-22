# Plan ingestion — reading plan-establisher output

`document-planner`'s preferred upstream input is a
`plan-establisher`-emitted `ai-artifacts/plans/plan.<intent-slug>.v<N>.md`.
Phase 0.5 discovery auto-scans for it; Phase 1 reads it as the
canonical synthesis.

## Auto-discovery

At Phase 0.5 step 1:

```bash
ls -1 "${MAIN_CHECKOUT}"/ai-artifacts/plans/plan.*.v*.md 2>/dev/null
```

If multiple plans exist for distinct intent slugs, ask the user which
intent applies. If multiple versions exist for the same intent slug
(`plan.foo.v1.md`, `plan.foo.v2.md`), **read `max(N)`** — that's the
plan-establisher convention.

If no plan-establisher file is present, fall back to the chat request
as the plan (still pass through Phase 1 normalization).

## Schema reuse (v1)

`plan-establisher`'s schema was tuned for codebase-planner but is
generic enough to reuse verbatim for v1:

| Field | document-planner reads it as |
|---|---|
| `Goal` | The "what's this document for" line. Also drives DOCTYPE keyword inference per [doctype-dispatch.md](doctype-dispatch.md) |
| `In scope` | The set of topics / sections / claims / endpoints that must appear |
| `Out of scope` | Explicit exclusions — surfaces in the lightweight-lane reflection and (for feature/system) feeds the stub list's "what we deliberately don't cover" |
| `Constraints` | Length budgets, format constraints, deadline notes, compliance/style guides — these inform per-stub `length budget` and `acceptance criteria` |
| `Success criteria` | What "this document works" looks like — feeds Phase 7 rubric items |
| `Proposed scale lane` | Default for Phase 0.5 triage lane (overridden only by upgrade or `confirm downgrade`) |
| `Evidence inventory` | Pre-collected evidence sources — informs per-stub `evidence sources` field |
| `Open questions` | Carries forward to per-stub `open questions` and the document-plan's top-level open-questions section |

## Document metadata NOT in plan-establisher's schema (capture in Phase 0.5)

plan-establisher does not yet have first-class fields for
document-shaped metadata. Capture these in Phase 0.5 dialog, then
persist:

- **audience** — primary audience(s) for the document. Required for
  every stub's `audience` field. Ask once at Phase 0.5 if not
  inferrable from `Goal` / `In scope`.
- **format** — markdown / HTML / pptx (derived from `OUTPUT_STACK`
  + `DOCTYPE`; usually not user-asked but confirm if ambiguous).
- **delivery target** — `TARGET_PATH` (where the eventual
  user-facing document will live). Mandatory in Phase 0.5.
- **style guide** — optional pointer to a repo style guide
  (e.g. `docs/style.md`). If named, surface in Phase 7 rubric.
  **v1 deliberate skip**: not promoted to a top-level state variable
  like `AUDIENCE` was. Style guides are typically project-wide
  constants (CLAUDE.md or repo-level style doc) rather than
  per-document-plan inputs; Phase 7 rubric can rely on the
  `Constraints` field from plan-establisher output instead. Revisit
  if multiple per-plan style guides become a real need.

These could become optional plan-establisher fields in a future
`output_kind=document` extension; for v1, the planner is responsible
for collecting them.

## Normalization rubric (Phase 1 reflection)

When reflecting the plan back as a single fenced block, normalize to
this shape (LANGUAGE-translated for prose fields; English for
machine-readable fields):

```
Goal:               <one paragraph>
DOCTYPE:            <api-spec|tech-spec|runbook|ppt>
OUTPUT_STACK:       <text|structured>
TARGET_PATH:        <path>
Audience:           <one paragraph>
In scope:           <bullet list>
Out of scope:       <bullet list>
Constraints:        <bullet list>
Success criteria:   <bullet list>
Evidence sources:   <bullet list>
Open questions:     <bullet list — may be empty>
```

Wait for `confirm plan` before Phase 2. Silence is not yes. If the
user types `revise`, re-enter Phase 1 with any new material they
provide.

## Multiple input sources at Phase 1

If the user provides additional input sources beyond the
plan-establisher plan (file paths, URLs, inline pasted text),
**normalize each separately first**, then synthesize:

1. Echo each source as a labeled fenced block before merging.
2. Surface conflicts between sources to the user — do NOT pick a
   side silently.
3. Only after the user has acknowledged conflicts (either resolved
   them or accepted both perspectives) emit the single normalized
   synthesis block.

This guarantees the user sees the contributing material, not just the
planner's synthesized view.

## Handling stale plan-establisher output

If `ai-artifacts/plans/plan.<intent-slug>.v<N>.md` exists but its `last-modified` is
older than the most recent commit touching code/docs the plan
references, surface that gap:

```
The plan-establisher output is from <date>, but
<related-file>.md has been modified since. Should I (a) proceed
with the older plan, (b) ask you to re-run plan-establisher, or
(c) note the staleness in `open questions` and proceed?
```

Don't silently auto-pick (a). Stale upstream is a real readiness
signal.

## Honest limitations

- v1 plan-establisher has no `output_kind=document` field; the
  schema is shared with codebase-planner. Some `In scope` items
  may not map cleanly to document stubs.
- Per-stub `audience` is captured at Phase 0.5 globally, then refined
  per-stub during Phase 3 decomposition. If the document has
  qualitatively different per-section audiences (e.g. an api-spec
  with one section for partners and one for internal users), the
  per-stub `audience` field overrides the global default — note this
  to the user.
