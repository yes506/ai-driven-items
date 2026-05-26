# Output schema — intent.<slug>.md + intent.<slug>.html

Phase 5 emits two artifacts at the worktree root, **slug-scoped** so
multiple intents can coexist at the repo root after merge. Both are
rendered from the same in-memory `INTENT` representation that was
confirmed in Phase 3. The two formats serve different audiences:

| Artifact | Audience | How it's used |
|---|---|---|
| `intent.<slug>.md` | AI (downstream skills ingest it as a file-path input) | Structured seed listing the user's goal, scope, constraints, and reasoning |
| `intent.<slug>.html` | Human (user opens in browser to verify) | Static, self-contained, print-friendly visualization |

The `<slug>` is the sanitized `PROJECT_SLUG` from Phase 4 (lowercase
ASCII, hyphens). So a slug of `payments-rewrite` produces
`intent.payments-rewrite.md` and `intent.payments-rewrite.html`.

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

- <bullet>
- <bullet>

## Constraints

- <bullet>
- <bullet>

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
4. <why 3 — root>

## Open questions

- <question>
- <question>

## Provenance

- Intent ID: <intent_id>
- Confirmed at: <ISO-8601 timestamp>
- Language used during elicitation: <Korean | English>
```

## Fields

Notes on the three fields that have shape rules beyond "bullet list of
user's words":

- **Mode** — `feature` or `problem`. Sets expectations for downstream
  skills and gates whether the Root-cause section appears.
- **Goal** — single sentence in **"For `<persona>`, `<outcome>`" form**.
  The persona prefix answers "what is this for whom?" in one read.
  When persona is generic (e.g. "any user of the system"), drop the
  prefix, fall back to a single-outcome sentence, and document the
  genericness in Open questions.
- **Root-cause** — ordered list; problem mode only. Step 1 is the
  symptom as the user first stated it; each subsequent step is the
  next "why" deeper. In feature mode the markdown omits the section
  entirely.

All other fields (In-scope features, Out-of-scope, Constraints,
Success criteria, Examples, Counter-examples, Open questions) are
plain bullet lists. Standalone — no folds, no cross-references between
fields. The downstream `plan-establisher` skill is responsible for
re-shaping these into whatever the next-hop planner needs.

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

- **Machine-only fields are not rendered.** `intent_id` and
  `language` (the knob, not the rendered content) live in
  `intent.<slug>.md` but do NOT appear in the HTML. The human
  verifying the intent doesn't need them and they create noise.
- **Sections are mode- and content-conditional.** A section
  renders only when it has something to say. `Root-cause` exists
  only in problem mode; `Open questions` is rendered only when
  there are unresolved items; sparse intent fields collapse rather
  than printing placeholder noise.
- **Chrome is localized.** `<html lang="…">` and all section
  labels follow `state.language` (`Korean` → `ko`, otherwise
  English fallback). Body content already follows `LANGUAGE` per
  Phase L; the chrome matches.

Sections (top-to-bottom, all conditional except header/footer):

1. **Header** — project slug + a single mode pill (`Feature` /
   `Problem`, localized). No intent ID, no language chip.
2. **Hero card** — the goal as a hero sentence with the persona as
   a "For: …" tag. This is the one-glance "what we agreed to build"
   summary; everything below it is supporting detail. Rendered when
   either `goal` or `persona` is present.
3. **Scope grid** — side-by-side ✓ in-scope vs ✗ not-in-scope
   columns.
4. **Success criteria** — checkbox-style checklist (☐ items). One
   item per row, visually scannable.
5. **Constraints** — compact list with subtle bullet markers.
6. **Root-cause flow** (problem mode only) — horizontal chain of
   colored boxes connected by `→` arrows. First box is labeled
   `Symptom` (red tint), last is labeled `Root cause` (green tint),
   intermediates are `Why 1`, `Why 2`, etc. On narrow screens the
   flow stacks vertically with rotated arrows. Pure CSS — no inline
   SVG, no JS — keeping the surface XSS-free.
7. **Examples grid** — paired columns with mode-aware labels.
   - *Feature mode*: ✓ "What it looks like when it works" vs ✗
     "What must NOT happen" — happy path vs forbidden behavior.
   - *Problem mode*: "Recent incidents (the pain we're solving)" vs
     "Adjacent areas that must not break" — past incidents are
     evidence; counter-examples are guardrails for the fix.

   The two columns share the same green/red styling regardless of
   mode (a styling concession; the labels carry the semantic load).
   Each entry is a tinted card so the contrast lands visually.
8. **Open questions** (only when non-empty) — loud orange call-to-
   action block with a ⚠ icon, separated visually from the other
   panels so the user can't miss unresolved items before typing
   `confirm merge`.
9. **Footer** — `Verified by user at <timestamp>` only.

### Why the HTML diverges from `intent.<slug>.md`

The two artifacts have different audiences. `intent.<slug>.md` is
the *machine handoff* — its structure is a flat list of
named sections so downstream parsers can read it deterministically.
The HTML is the *human verification artifact* — its structure is
shaped for fast scanning: hero → boundaries → criteria →
unresolved. Sharing the same section ordering across both formats
would have meant leaking the machine-only Provenance fields into the
human doc; the two-track output resolves that by letting each side
be optimized for its reader.

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
  Downstream skills pick tech stack, structure, packages.
- **Acceptance tests**. Success criteria suggest observable outcomes
  but don't enumerate test cases.
- **Estimates**. Sizing belongs in downstream triage, not in intent
  capture.
- **Stakeholders**. Persona captures the *user*, not the approving
  manager. Approvers go in downstream plans, if anywhere.

If the user pushes any of these into Phase 2 ("just put it in the
intent for now"), surface it: "that fits better in a downstream
planning phase — would you like to capture it as an open question
for now so we don't lose it?"
