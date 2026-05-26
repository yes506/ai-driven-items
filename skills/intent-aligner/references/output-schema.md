# Output schema — intent.<slug>.md + intent.<slug>.html

Phase 5 emits two artifacts at the worktree root, **slug-scoped** so
multiple intents can coexist at the repo root after merge. Both are
rendered from the same in-memory `INTENT` representation that was
confirmed in Phase 3. The two formats serve different audiences:

| Artifact | Audience | How it's used |
|---|---|---|
| `intent.<slug>.md` | AI (`codebase-planner` Phase 1 ingests it as a file-path input) | Structured seed; planner's normalization rubric maps 1:1 to its fields |
| `intent.<slug>.html` | Human (user opens in browser to verify) | Static, self-contained, print-friendly visualization |

The `<slug>` is the sanitized `PROJECT_SLUG` from Phase 4 (lowercase
ASCII, hyphens). So a slug of `payments-rewrite` produces
`intent.payments-rewrite.md` and `intent.payments-rewrite.html`.

## Field-name alignment with codebase-planner

`codebase-planner`'s Phase 1 normalization rubric (per its
`references/plan-ingestion.md`) extracts these fields from any input
source: **Goal**, **In-scope features**, **Out-of-scope**,
**Constraints**, **Success criteria**, **Open questions**.

`intent.<slug>.md` uses those exact field names (English, verbatim) so the
planner's parser ingests it natively without any translation layer.

Intent-aligner adds five fields on top of the planner's six:

- **Mode** — `feature` or `problem` (the planner ignores this; humans
  reading the HTML use it to set expectations)
- **Persona** — single sentence, who the work is for
- **Examples** — happy-path scenarios in feature mode, concrete
  incidents in problem mode
- **Counter-examples** — explicit non-examples (the boundary)
- **Root-cause** — ordered list of "why" steps; only meaningful in
  problem mode (in feature mode the HTML renders an explicit
  "not applicable" note and the markdown omits the section)

The planner gracefully ignores fields it doesn't know about — they
just don't appear in its Phase 1 synthesis. So the extras are
information for the human and the next-hop without breaking the
contract.

## intent.<slug>.md — exact structure

```markdown
# Intent — <project-slug>

## Mode

<feature | problem>

## Persona

<single sentence describing who this is for>

## Goal

For <persona-short>, <outcome / relief>. (single sentence)

## In-scope features

- <bullet>
- <bullet>

## Out-of-scope

- <non-goal> (counter-example: <reason it's NOT in scope>)
- <bullet>

## Constraints

- <bullet>
- (problem mode) Root cause: <final root-cause step from Phase 2 Pass 4>

## Success criteria

- <bullet>
- <bullet>

## Examples

- <one specific happy-path scenario (or incident, in problem mode)>
- <...>

## Counter-examples

- <one thing that should NOT happen, with the reason>
- <...>

## Root-cause

(problem mode only — omit this section entirely in feature mode)

1. <symptom>
2. <why 1>
3. <why 2>
4. <why 3 — root> ← also appears folded into Constraints above

## Open questions

- <question>
- <question>

## Provenance

- Intent ID: <intent_id>
- Confirmed at: <ISO-8601 timestamp>
- Language used during elicitation: <Korean | English>
```

### Why some content appears in two places

`codebase-planner`'s Phase 1 normalization rubric only extracts 6 named
fields (`Goal`, `In-scope features`, `Out-of-scope`, `Constraints`,
`Success criteria`, `Open questions`); the extras (`Mode`, `Persona`,
`Examples`, `Counter-examples`, `Root-cause`) survive in the file body
for the human's HTML verification and for the planner's Phase 0.5
discovery, but they do NOT appear in the planner's `confirm plan`
synthesis. So the load-bearing extras are deliberately **folded** into
planner-known fields at intent-capture time:

- **Persona** is folded into **Goal** via the "For `<persona-short>`,
  `<outcome>`" form. Matches the planner's `Goal` rubric question
  ("what does this project do for whom?"). When persona is generic
  (e.g. "any user of the system"), drop the prefix and fall back to a
  single-outcome sentence — but document why in Open Questions.
- **Counter-example reasons** are folded into **Out-of-scope** entries
  as `<non-goal> (counter-example: <reason>)`. The standalone
  `## Counter-examples` section keeps the human-readable form for the
  HTML; the Out-of-scope bullets are what the planner ingests.
- **Final root-cause step** (problem mode only) is folded into
  **Constraints** as `Root cause: <X>`. The standalone `## Root-cause`
  section keeps the full chain for the HTML; the Constraints bullet is
  what the planner ingests as causal signal.
- **Most-concrete example** (or, in problem mode, the inverse of the
  freshest incident) is folded into **Success criteria** as an
  observable scenario. The standalone `## Examples` section keeps the
  narrative form for the HTML; the Success-criteria bullet is what
  the planner ingests as a concrete realization of the goal. Fold is
  mandatory in spirit; skip ONLY if the example is already verbatim
  a success criterion (rare in practice — examples are usually
  scenarios while criteria are usually metrics).

This is the contract that makes intent-aligner a faithful seed for
`codebase-planner` despite the rubric mismatch. See
[planner-handoff.md](planner-handoff.md) for the full handoff design.

### Rules for filling fields

- **Verbatim user words**. Use the user's phrasing wherever possible,
  not a cleaner paraphrase. Paraphrasing loses specificity and the
  user can't recognize their own intent in the HTML.
- **Unspecified → `[unspecified]`**. If a field is genuinely empty
  (not just unsaid; truly empty after Phase 2 convergence), write
  `[unspecified]` rather than guessing or leaving the section blank.
  Empty bullet lists render as `(none recorded)` in the HTML.
- **One sentence ≠ one clause**. Goal and Persona are each ONE
  SENTENCE. If you can't fit the user's intent into one sentence,
  what's there isn't yet a goal/persona — it's still a topic. Loop
  back to Phase 2.
- **Examples are concrete**. Names, times, numbers, paths — whatever's
  relevant. Vague examples ("a user does something") don't count
  toward the convergence rule.
- **Counter-examples include the reason**. "Internal cache transitions
  — they'd drown out the audit log signal" is a counter-example.
  "Internal cache transitions" alone is not.
- **Root-cause is ordered**. Step 1 is the symptom as the user first
  stated it; each subsequent step is the next "why" deeper. Order
  matters for the human reading the HTML.

## intent.<slug>.html — structure

Rendered from `.intent-state.json` by
`scripts/render_html_report.py` using the bundled template at
`assets/intent-html-template.html`. Single self-contained file (no
CDN, no external JS, no Mermaid). Every user-supplied value is
HTML-escaped before substitution; the template uses single-pass
placeholder substitution to defuse the chained-replace re-substitution
class.

The HTML is a **first-class human verification document**, not a
Markdown-to-HTML conversion of `intent.<slug>.md`. It deliberately
diverges from the markdown's section list:

- **Machine-only fields are not rendered.** `intent_id`,
  `language` (the knob, not the rendered content), and the
  planner-handoff invocation text live in `intent.<slug>.md` and in
  the Phase 6 chat output — they do NOT appear in the HTML. The
  human verifying the intent doesn't need them and they create
  noise.
- **Sections are mode- and content-conditional.** A section
  renders only when it has something to say. `Root-cause` exists
  only in problem mode; `Open questions` is rendered only when
  there are unresolved items; sparse intent fields collapse rather
  than printing placeholder noise.
- **Chrome is localized.** `<html lang="…">` and all section
  labels follow `state.language` (`Korean` → `ko`, otherwise
  English fallback). Body content already follows `LANGUAGE` per
  Phase L; the chrome now matches.

Sections (top-to-bottom, all conditional except header/footer):

1. **Header** — project slug + a single mode pill (`Feature` /
   `Problem`, localized). No intent ID, no language chip.
2. **Hero card** — the goal as a hero sentence with the persona as
   a "For: …" tag. This is the one-glance "what we agreed to build"
   summary; everything below it is supporting detail. Rendered when
   either `goal` or `persona` is present.
3. **Scope grid** — side-by-side ✓ in-scope vs ✗ not-in-scope
   columns. When an out-of-scope entry follows the
   `<non-goal> (counter-example: <reason>)` form, the reason is
   split off and rendered as a small italic annotation under the
   non-goal so the boundary is visually paired with the *why*.
4. **Success criteria** — checkbox-style checklist (☐ items). One
   item per row, visually scannable.
5. **Constraints** — compact list with subtle bullet markers. In
   problem mode this list includes the folded `Root cause: <X>`
   bullet (per the schema fold) — that's redundant-with-the-flow,
   which is deliberate: humans don't always read top to bottom.
6. **Root-cause flow** (problem mode only) — horizontal chain of
   colored boxes connected by `→` arrows. First box is labeled
   `Symptom` (red tint), last is labeled `Root cause` (green tint),
   intermediates are `Why 1`, `Why 2`, etc. On narrow screens the
   flow stacks vertically with rotated arrows. Pure CSS — no inline
   SVG, no JS — keeping the surface XSS-free.
7. **Examples grid** — paired ✓ "what it looks like when it works"
   vs ✗ "what must NOT happen" columns. Each entry is a tinted card
   so the contrast lands visually.
8. **Open questions** (only when non-empty) — loud orange call-to-
   action block with a ⚠ icon, separated visually from the other
   panels so the user can't miss unresolved items before typing
   `confirm merge`.
9. **Footer** — `Verified by user at <timestamp>` only. The planner
   handoff sentence that used to live here has been removed; that
   instruction belongs in the Phase 6 chat output, not in the
   human verification doc.

### Why the HTML diverges from `intent.<slug>.md`

The two artifacts have different audiences. `intent.<slug>.md` is
the *machine handoff* — its structure is shaped 1:1 with the
planner's normalization rubric so ingestion is zero-friction. The
HTML is the *human verification artifact* — its structure is
shaped for fast scanning: hero → boundaries → criteria →
unresolved. Sharing the same section list across both formats
would have meant either (a) leaking machine fields into the human
doc or (b) starving the planner of fields it expects. The two-track
output resolves the tension by letting each side be optimized for
its reader.

## Why HTML and not PDF / Markdown-rendered

- **PDF** would require a renderer dependency (wkhtmltopdf,
  weasyprint, etc.) that isn't in scope for this skill.
- **Markdown-rendered** depends on the user's reader. The visual
  hierarchy + colored boundary blocks for examples/counter-examples
  matter for fast scanning; rendered markdown drops that.
- **Standalone HTML** opens in any browser, prints cleanly via the
  `@media print` rules in the template, and has no external
  dependencies.

## What this schema does NOT include

- **Implementation hints**. The intent is *what* and *why*, not *how*.
  The planner downstream picks tech stack, structure, packages.
- **Acceptance tests**. Success criteria suggest observable outcomes
  but don't enumerate test cases.
- **Estimates**. Sizing belongs in the planner's triage scoring, not
  in intent capture.
- **Stakeholders**. Persona captures the *user*, not the approving
  manager. Approvers go in the planner's plan, if anywhere.

If the user pushes any of these into Phase 2 ("just put it in the
intent for now"), surface it: "that fits better in the planner's
phase — would you like to capture it as an open question for now so we
don't lose it?"
