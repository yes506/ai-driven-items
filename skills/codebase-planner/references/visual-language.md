# Visual Language (Chain Ubiquitous Vocabulary)

This file defines the **shared visual vocabulary** used in HTML output by the
five chain skills:

```
intent-aligner → seed-gatherer → plan-establisher → document-planner → codebase-planner
   (Intent)        (Seed)           (Plan)            (Doc Stub)         (Interface)
```

When you regenerate any of those HTML outputs, the glyph, color, and label
for each stage **must match this file exactly** — that is the "ubiquitous
language" guarantee. A reviewer who opens any one of the five HTML reports
sees the same five-stage breadcrumb at the top, with the current stage
highlighted, and immediately knows where the artifact sits in the pipeline.

## Stage table

| Stage     | Glyph       | Primary color | Bg-soft  | Meaning                                                  |
|-----------|-------------|---------------|----------|----------------------------------------------------------|
| Intent    | ◆ (diamond) | `#2b5fb5`     | `#e8f0fb`| Captured user goal / problem; what we agreed to build.   |
| Seed      | ● (circle)  | `#2f7c4f`     | `#e6f4ec`| Resources / constraints / ideas to feed planning.        |
| Plan      | ▲ (triangle)| `#7a3fb5`     | `#f1e8fb`| Concrete plan: phases, decisions, verification points.   |
| Doc Stub  | ▤ (page)    | `#b87900`     | `#fff4d6`| PRD / tech-spec / runbook scaffolds to be filled in.     |
| Interface | ◫ (block)   | `#0f7a83`     | `#dff3f5`| Package + interface contracts + dependency DAG.          |

Hex colors are repeated in CSS as `--stage-{name}` and `--stage-{name}-soft`.

## Pipeline breadcrumb SVG (rendered at top of every chain HTML)

Render a horizontal 5-node breadcrumb in a single `<svg>` element. The
current stage is rendered with a filled glyph + bold label; the other four
are outlines + muted label. Connecting arrows are simple `→` glyphs in
text. The whole thing is one inline `<svg>` — no JS, no CDN.

Schematic (each renderer emits exact-equivalent SVG):

```
[◆ Intent] → [● Seed] → [▲ Plan] → [▤ Doc Stub] → [◫ Interface]
   active     pending      pending      pending          pending
```

Width: 100% of `.page`, fixed height ~64px. Nodes ~120px wide. Use
`<circle>` / `<polygon>` / `<rect>` for glyphs; `<text>` for labels. All
strings (slug, etc.) must be HTML-escaped before being interpolated.

## Status palette (for badges, dots, panels)

| Status     | Glyph | Color     | Bg-soft  |
|------------|-------|-----------|----------|
| Captured   | ✓    | `#2f7c4f` | `#e6f4ec`|
| Pending    | ◌    | `#888`    | `#f4f4f2`|
| Blocked    | ✗    | `#b53737` | `#fbeaea`|
| Verified   | ⬢    | `#2b5fb5` | `#e8f0fb`|
| Open Q     | ?    | `#b87900` | `#fff4d6`|

## Stat-bar SVG (at-a-glance counts)

Each renderer that has counts (in-scope items, success criteria, etc.)
emits a single horizontal `<svg>` "tape" of stat tiles. One tile per stat:
big number on top, tiny label below, color taken from the **status
palette** (not stage palette — these are within-stage measurements).

## Mode badge SVG (intent-aligner only)

Two glyphs: ⚙ (gear) = Feature mode, ⚠ (warning) = Problem mode. Renders
as one inline `<svg>` with the glyph in stage-intent color + the mode
name + a one-line tagline.

## XSS-safety rules (do not relax these)

- **No external scripts**, no `<script>`, no `<iframe>`. Everything is
  inline SVG + CSS.
- **No `<foreignObject>`** with user-supplied HTML.
- **All `<text>` content must be HTML-escaped** before being interpolated
  into the SVG source. The renderers' `_esc()` helper is the only path.
- **Color / size / structural attributes are renderer-controlled**, never
  user-supplied. Reviewers don't supply pixel values.

A prior code-review round documented in the repo memory caught XSS via
external Mermaid CDN + `click "javascript:"` directives. The cure was to
remove the live JS renderer. Inline SVG built in Python preserves the
visual richness without re-opening that hole, because there is no JS
execution at all in the rendered HTML.

## When to add to this file

- A new stage joins the chain → new row in the stage table + new glyph.
- A new status semantic emerges → new row in the status palette.
- A new universally-applicable visual primitive emerges → new section.

Do **not** add stage- or skill-specific visuals here. Those live in the
owning skill's renderer; this file is the chain-level contract.

## Cross-cutting visual conventions reviewers should expect

- **Same-name dedup in the Interface stage**: codebase-planner's
  dependency DAG (both inline SVG and Mermaid source) merges interfaces
  with the same `name` into a **single node**, while the textual
  interface listing below the graph faithfully shows each instance as
  its own `<details>` block. This is intentional: collaborator
  references are name-based, so two interfaces named `Foo` cannot be
  distinguished as edge targets. A reviewer who sees N rows in the
  interface table but N − k nodes in the graph is looking at this
  dedup, not a renderer bug. The contract lives in
  `codebase-planner/scripts/_iface_graph.py:build_id_map`.
- **Language fallback**: `state["language"]` absent / empty / `ko` /
  `kr` / `korean` (case-insensitive) → Korean labels. Any other
  non-empty value (e.g. `english`, `fr`, `Spanish`) → English labels.
  This is the Phase L contract documented in each skill's
  `references/language-selection.md`. The intent-aligner,
  seed-gatherer, plan-establisher, and document-planner renderers
  honor this. The codebase-planner renderer does **not** read
  `state["language"]` at all — its output is technical English by
  design (architecture reports are read by code reviewers; the
  technical lexicon doesn't translate cleanly).
- **No JS in the rendered HTML**: every visual is inline SVG. Mermaid
  source is preserved in `architecture.mmd` (codebase-planner) and in a
  collapsed `<details>` block inside the HTML for reviewer convenience —
  no JS is executed in the reviewer's browser.
