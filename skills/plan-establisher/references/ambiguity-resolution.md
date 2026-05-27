# Phase 3 — Ambiguity resolution + synthesis

Phase 3 takes the `FINDINGS` list from Phase 2 and drives it to
resolution via an interactive dialog, then builds the in-memory plan
representation and gates on `confirm plan` before any disk write.

## Dialog protocol

1. **Open with auto-resolved summary** (silent in the chat-thread
   sense — they get a one-line acknowledgement, not a per-item
   dialog):

   > Auto-resolved \<M\> findings: \<N₁\> dead-weight seeds dropped,
   > \<N₂\> duplicate seeds collapsed. Logged in the plan's Resolved
   > ambiguities section. Moving to \<K\> findings that need your
   > input.

2. **Iterate `needs-user` findings**, in order: Dim 1 first, then Dim
   2 contradictions, then Dim 3 conflicts, then Dim 4 gaps. Within
   each dimension: blocker → major → minor.

3. **For each finding**, echo it with 1–3 candidate resolutions:

   ```
   [<dim> · <severity>] <locus>
   Issue: <description>

   Candidate resolutions:
     (a) <option> — <one-line consequence>
     (b) <option> — <one-line consequence>
     (c) Other — type your resolution verbatim
     (d) Defer to Remaining open questions

   Type a/b/c/d (and a one-line resolution if c), or `accept remaining`
   to defer ALL remaining findings to Remaining open questions.
   ```

   **`(d) Defer` is always available** alongside the dimension-specific
   candidates (a)/(b)/(c) — it's the per-finding deferral primitive
   (vs. `accept remaining` which is the batch-deferral short-circuit).
   Selecting `(d)` marks just this one finding as `mode=deferred`; it
   surfaces in the plan's `Remaining open questions` section with its
   original description and the resolution text `"(deferred — user
   chose (d) at finding <i> of <total>)"`. Other findings in the
   queue still get their own dialog turn. The Forbidden actions
   section enforces this: silently dropping unresolved findings is
   prohibited; every unresolved finding must be either resolved via
   (a)/(b)/(c), explicitly deferred via (d), or batch-deferred via
   `accept remaining`.

4. **Record the resolution** in `FINDINGS[i].resolution`. Each
   resolution has a `mode` (selected-candidate | user-typed |
   deferred) and a `text` (the chosen / typed / "(deferred)"
   resolution prose).

5. **Loop until** every finding has a `resolution` OR the user typed
   `accept remaining`. After `accept remaining`, mark all remaining
   findings as `mode=deferred`.

## Crafting candidate resolutions

Per dimension:

- **Dim 1 (intent self-consistency)**: usually 3 candidates — (a)
  drop one of the conflicting fields, (b) drop the other, (c) reword
  both to coexist. Avoid candidates that materially expand scope
  (don't suggest "add a new feature to bridge the gap" — that's
  intent-aligner's job; surface as deferred instead).
- **Dim 2 (seeds vs intent — needs-user only, i.e., out-of-scope
  contradictions)**: 3 candidates — (a) drop the seed, (b) re-scope
  the intent's Out-of-scope, (c) keep the seed but log the
  contradiction in Remaining open questions. Don't auto-strip the
  seed even if option (a) seems obvious; let the user decide.
- **Dim 3 (seeds vs seeds)**: 2 substantive candidates — (a) trust
  seed A and drop the conflict from B's Evidence-inventory
  contribution, (b) trust seed B. Plus the universal `(c) Other`
  (type-verbatim) and `(d) Defer`. Avoid synthesizing a third
  substantive option ("trust both, average them") unless the
  conflict is numeric and averaging is meaningful — usually it's not.
- **Dim 4 (planner-rubric gaps)**: 2 substantive candidates plus the
  universal `(c) Other` and `(d) Defer`. For scope gaps: (a) provide
  a concrete file/module name, (b) name a broader area; `(d) Defer`
  routes the gap to Remaining open questions for codebase-planner
  to probe. For `[unspecified]` markers: (a) provide a value
  verbatim, (b) confirm there's truly none (log as "user confirmed
  no value"); `(d) Defer` again routes to Remaining open questions.

**Convention note**: the canonical dialog template (above) shows
`(a)/(b)` as 2 substantive candidate slots, `(c) Other` for
type-verbatim, `(d) Defer` for routing to Remaining open questions.
Dimensions with a clearly-distinct 3rd substantive option (Dim 1
and Dim 2 below) use `(a)/(b)/(c)` for the substantives; in those
dimensions the verbatim custom-resolution escape hatch is invoked
by typing `other: <resolution>` (no letter slot, since `(c)` is
taken by the 3rd substantive). `(d) Defer` remains the universal
defer primitive across all dimensions. The skill must accept
`other: <text>` as a valid response in Dim 1/2 dialog turns and
record the resolution as `mode=user-typed, text="<text>"` (same as
the canonical `(c) Other` path).

## Handling user-typed resolutions

When the user picks (c) and types a verbatim resolution:

- Echo it back wrapped in quotes for confirmation: *"Recording: '\<their text\>'. Type `confirm` to accept or re-type to revise."*
- Wait for `confirm` (verbatim English token). Silence is not yes.
- Once confirmed, store the verbatim text.

This guards against typos / accidental enter — the verbatim text
will land in the plan's Resolved ambiguities section and the
codebase-planner will read it, so we want exactly what the user
intended.

## `accept remaining` semantics

The user can short-circuit the loop at any point by typing `accept
remaining`. Effect:

- Every finding without a `resolution` becomes `mode=deferred,
  text="(deferred — user chose to defer at finding <N> of <total>)"`.
- The deferred findings will populate the plan's `Remaining open
  questions` section verbatim (one bullet per deferred finding,
  carrying the original `description`).
- Phase 3 proceeds to synthesis preview.

This is an escape hatch for when the verification list is long and
the user wants codebase-planner to handle the rest. It's NOT silent
deferral — every deferred finding shows up explicitly in the plan.

## Synthesis preview

After all findings are resolved or deferred, render a preview block
in chat covering every field the plan.md will emit:

```
PLAN — synthesis (intent <slug>, version v<N>)
==============================================
Goal: <resolved goal, post-Dim-1 refinements>

In-scope:
  - <bullet>
  ...

Out-of-scope:
  - <bullet>
  ...

Constraints (deduped, conflicts resolved):
  - <bullet>
  ...

Success criteria:
  - <bullet>
  ...

Proposed scale lane: <micro | local | feature | system>

  Lane reasoning: <paragraph — based on the scope/risk/ambiguity
  signals collected in Dim 4>

Evidence inventory:
  - Goal: <seed_slug> (one-line relevance), <seed_slug>...
  - Constraint #1: <seed_slug>...
  - ... (or "(intent-only)" entries if no contributing seeds)

Resolved ambiguities (<N>):
  - <finding description> → <resolution>
  - ...

Remaining open questions (<K>):
  - <deferred finding description>
  - ...

Provenance:
  - Intent slug: <slug>
  - Plan version: v<N>
  - Seed batch IDs: <comma-list, or "(none)">
  - plan-establisher format version: 1.0

Type `confirm plan` to lock and emit, or `revise` to re-enter
verification (you can revise resolutions, or re-run a dimension).
```

Wait for `confirm plan` (verbatim English) or `revise`. Silence is
not yes.

- `confirm plan` → record `verified_at` ISO-8601 in memory, proceed
  to Phase 4.
- `revise` → ask the user *which* aspect to revise (a specific
  finding's resolution; re-run Dim 1/2/3/4; re-load intent; re-load
  seeds). Re-enter the appropriate phase step. Do not guess.
- Anything else → re-ask.

## Picking the proposed scale lane

The proposed lane is plan-establisher's best guess based on the
verified inputs. codebase-planner may override.

Heuristics (informational only — codebase-planner is authoritative):

| Signal | Suggests lane |
|---|---|
| Goal names ≤1 function and 0 modules | micro |
| Goal names ≤3 files in 1 module | local |
| Goal names ≥1 module or a cross-module surface (an endpoint, a UI page) | feature |
| Goal names ≥3 modules, or introduces an interface, or has a deferred design open question | system |

If the inputs are too thin to even guess (intent-only with no
file/module hints), default to `system` and note "(low-confidence —
codebase-planner should re-assess)" in the lane reasoning. Better to
over-budget than under-budget when ambiguity is high.

## Honest limitations

- Dim 2 plausibility checks are judgement calls. The skill can't
  prove a rationale is dead-weight; it can only flag obvious
  mismatches. Borderline cases should be surfaced as `needs-user`,
  not auto-dropped.
- Dim 3 conflict detection is text-pattern based (does seed-A
  mention "X version V₁" while seed-B mentions "X version V₂"?). It
  misses semantic conflicts (two seeds describe the same thing in
  different vocabulary without explicit numeric/factual collision).
- The lane suggestion is a heuristic, not authoritative. If the user
  disagrees, they can `revise` and propose their own lane during the
  synthesis preview; the eventual plan documents the
  human-confirmed proposal, and codebase-planner still gets the
  final say.
- `accept remaining` is a blunt instrument. There's no "accept
  remaining of THIS dimension only" — it accepts all remaining
  across all dimensions. If the user wants finer granularity, they
  should resolve one-by-one.
