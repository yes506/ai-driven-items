# Output schema — plan.<intent-slug>.v<N>.{md,html}

Phase 5 emits two artifacts per plan run under
`ai-artifacts/plans/` at the **plan worktree root**
(`.worktrees/plan-<intent-slug>-<id>/ai-artifacts/plans/`); Phase 6's
`git merge --no-ff` brings them to
`${MAIN_CHECKOUT}/ai-artifacts/plans/` on `${BASE_BRANCH}` (where
`codebase-planner` reads them from). Both are derived from the
in-memory plan representation that
was confirmed at Phase 3. The markdown is written directly via
`Write` (the field values from the in-memory plan, formatted per the
schema below); the HTML is rendered by `scripts/render_plan_html.py`
which reads the state file plus the bundled template. Audiences:

| Artifact | Audience | How it's used |
|---|---|---|
| `ai-artifacts/plans/plan.<intent-slug>.v<N>.md` | AI (`codebase-planner` reads ONLY this) | Folded planner-ready doc; planner picks a scale lane and proceeds. intent.md + seeds/ become raw source material, not active inputs |
| `ai-artifacts/plans/plan.<intent-slug>.v<N>.html` | Human (browser-openable) | Self-contained verification doc, no CDN, HTML-escaped |

`<N>` is the version number (see [plan-naming-and-versioning.md](plan-naming-and-versioning.md)).

## plan.<intent-slug>.v<N>.md — exact structure

```markdown
# Plan — <intent-slug> · v<N>

## Goal

<from intent, possibly refined via Phase 3 dialog — single sentence>

## In-scope

- <bullet>
- <bullet>

## Out-of-scope

- <bullet>
- <bullet>

## Constraints

- <bullet (intent + seed-derived, deduped, conflicts resolved)>
- <bullet>

## Success criteria

- <bullet>
- <bullet>

## Proposed scale lane

<micro | local | feature | system>

### Lane reasoning

<paragraph explaining scope/risk/ambiguity assessment that drove the
lane choice. Names the signals: which files/modules were
identifiable, what test coverage / blast radius was inferred, what
ambiguity remains.>

## Evidence inventory

- Goal: informed by seed.<intent-slug>.<resource-slug> — <one-line relevance>; seed.<intent-slug>.<other> — <relevance>
- In-scope #1 (<short label>): seed.<intent-slug>.<slug> — <relevance>
- Constraint #1 (<short label>): seed.<intent-slug>.<slug>
- Success criterion #1 (<short label>): (intent-only — no seed coverage)
- ...

(Includes "intent-only" entries for fields with no contributing seeds.
If `SEEDS == []` entirely, the whole inventory reads:
`(intent-only — no seeds available)`.)

## Resolved ambiguities

- <finding description from Phase 2> → <user's resolution from Phase 3>
- <finding description> → <resolution>
- (auto) <finding description> → <auto-resolution explanation>

(If no ambiguities were found, this section reads `(none recorded)`.)

## Remaining open questions

- <unresolved finding description (only items the user explicitly chose to `accept remaining` or `(d) defer`)>
- <unresolved finding description>

(If no open questions remain, this section reads `(none — all
ambiguities resolved)`. Items here are NOT silently dropped findings
— silent skip is forbidden per SKILL.md Forbidden actions.)

## Provenance

- Intent slug: <slug>
- Intent ID: <intent_id from intent.<slug>.md if available, else "(none)">
- Plan version: v<N>
- Plan run ID: <plan_run_id>
- Seed batch IDs: <comma-separated list from each seed's seed_run_id, or "(none)" if intent-only>
- Confirmed at: <ISO-8601 timestamp with timezone offset>
- plan-establisher format version: 1.0
```

## Field rules

- **Goal** — single sentence. If Phase 3 refined it (Dim 1
  resolution), the refined version lands here. The original intent's
  Goal is preserved in intent.<slug>.md and the plan's Provenance
  references the intent slug, so the original is recoverable. If
  Goal is `[unspecified]` and the user deferred resolution, write
  `[unspecified]` and surface it in Remaining open questions.
- **In-scope / Out-of-scope / Constraints / Success criteria** —
  bullet lists. Deduped (multiple seeds informing the same constraint
  → one bullet). Conflicts resolved (Dim 1 resolutions reshape these
  fields). Each bullet is the user's own words or the intent's
  original words, never paraphrased.
- **Proposed scale lane** — one of `micro | local | feature |
  system` (lowercase, exact). codebase-planner reads this as a hint
  but may override. The reasoning paragraph below it must justify the
  choice with concrete scope/risk/ambiguity signals.
- **Lane reasoning** — a single paragraph. Avoid bullet-listing
  signals; the rubric for the lane is described in prose so the
  human verifier can scan it. Cite specific seeds where they
  contributed scope/risk signal.
- **Evidence inventory** — bulleted, one bullet per rubric field
  (Goal, each In-scope item, each Constraint, each Success
  criterion). For each: list contributing seed_slugs with a one-line
  relevance note OR write "(intent-only — no seed coverage)" if no
  seeds informed that field. This is the key traceability artifact —
  codebase-planner uses it to know which seeds matter for which
  planning decisions; the user uses it to verify nothing was
  smuggled in unsupported.
- **Resolved ambiguities** — each entry is `<finding description> →
  <resolution>` or `(auto) <finding description> → <auto-resolution
  explanation>`. Phrase the finding in the same wording as the
  Phase 3 dialog echo (the user already saw it; familiar wording).
- **Remaining open questions** — bullet list of the deferred
  findings. Verbatim from Phase 3.
- **Provenance** — six sub-fields, bulleted. Required: Intent slug,
  Plan version, Plan run ID, Confirmed at, plan-establisher format
  version. Optional / "(none)" if absent: Intent ID, Seed batch IDs.

## Field names stay English

Even when `LANGUAGE=Korean`, the section headings (`## Goal`,
`## In-scope`, `## Proposed scale lane`, etc.) stay English. The
downstream `codebase-planner` reads them as machine grammar. Body
values follow `LANGUAGE` for prose; carried-through content from
intent / seeds stays in their original languages.

## plan.<intent-slug>.v<N>.html — structure

Rendered from `.plan-state.json` by `scripts/render_plan_html.py`
using the bundled template at `assets/plan-html-template.html`.
Single self-contained file (no CDN, no external JS). Every
user-supplied value is HTML-escaped before substitution; the
template uses single-pass placeholder substitution to defuse the
chained-replace re-substitution class.

Sections (top-to-bottom):

1. **Header** — intent slug + version pill (`v<N>`) + scale-lane
   pill (`Micro` / `Local` / `Feature` / `System`, localized).
2. **Hero card** — Goal as a hero sentence.
3. **Scope grid** — side-by-side ✓ In-scope vs ✗ Out-of-scope.
4. **Constraints panel** — bulleted with subtle markers.
5. **Success criteria checklist** — checkbox-style (☐ items).
6. **Lane reasoning callout** — tinted block containing the
   reasoning paragraph; emphasises the lane decision.
7. **Evidence inventory table** — two-column rendering: rubric
   field → contributing seeds. Each seed in the right column renders
   as `<code>seed_slug</code> — relevance text` (one row per seed,
   visually separated by a dashed divider when multiple seeds inform
   the same field). Renders only when at least one entry has seed
   coverage; if all entries are intent-only, render a single
   placeholder card *"(intent-only plan — no seeds informed any
   rubric field)"*. State schema for the inventory:
   [state-and-resume.md](state-and-resume.md) — each entry is
   `{seed_slug, relevance}`; legacy string-only entries render with
   a `(no relevance recorded)` placeholder.
8. **Resolved ambiguities** — only renders when non-empty;
   collapsed list of `finding → resolution`.
9. **Remaining open questions** — only renders when non-empty; loud
   orange call-to-action block with a ⚠ icon (mirrors intent-aligner's
   open-questions treatment) so the user can't miss unresolved items
   before typing `confirm merge`.
10. **Provenance footer** — intent slug, version, run ID, confirmed
    timestamp, format version. Compact.

### Chrome localization

`<html lang="…">` and section labels follow `state.language`
(`Korean` / `ko` / `kr` → ko; missing/empty → ko; anything else →
en). Body content (refined Goal, resolution texts) follows the
language they were recorded in.

## Why HTML and not PDF / Markdown-rendered

- **PDF** would require a renderer dependency (wkhtmltopdf,
  weasyprint, etc.) that isn't in scope for this skill.
- **Markdown-rendered** depends on the user's reader. The visual
  hierarchy + colored boundary blocks (scope grid, lane callout,
  open-questions warning) matter for fast scanning; rendered
  markdown drops that.
- **Standalone HTML** opens in any browser, prints cleanly via the
  `@media print` rules in the template, and has no external
  dependencies.

## Versioning

Each plan run emits a new version (`v1`, `v2`, ...). Prior versions
are preserved as an audit trail of how the plan evolved.
codebase-planner reads the latest (highest N). Full rules + race
handling: [plan-naming-and-versioning.md](plan-naming-and-versioning.md).

## What this schema does NOT include

- **Implementation hints**. The plan establishes *what* the planner
  should plan for, not *how*. Downstream codebase-planner picks
  structure; codebase-implementer picks libraries / packages / code
  shape.
- **Test cases / acceptance criteria**. Success criteria suggest
  observable outcomes but don't enumerate test cases.
- **Time estimates**. Sizing belongs in codebase-planner's lane
  selection, not in plan-establisher's output.
- **Risk scoring / probability values**. Lane reasoning may *name*
  risks but doesn't assign numeric probabilities or impact scores
  (that's downstream).
- **References to specific external tools / libraries / vendors**
  unless they're carried through from intent or seeds. plan-
  establisher doesn't introduce new technology choices.

If the user pushes any of these into Phase 3 ("just put the test
cases in the plan"), surface it: *"that fits better in a downstream
planning phase — would you like to capture it as a Remaining open
question for codebase-planner to address?"*
