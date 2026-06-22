# Output schema — seed.<intent-slug>.<resource-slug>.md + .html

Phase 5 emits two artifacts per resource at `ai-artifacts/seeds/` (creating the
directory if it doesn't exist), both derived from the corresponding
entry in `.seed-state.json`'s `resources` list. The markdown is
written directly via `Write` (the field values from the state entry,
formatted per the schema below); the HTML is rendered by
`scripts/render_seed_html.py` which reads the same state entry plus
the bundled template. The two formats serve different audiences:

| Artifact | Audience | How it's used |
|---|---|---|
| `ai-artifacts/seeds/seed.<intent-slug>.<resource-slug>.md` | AI (downstream `plan-establisher` ingests it via glob) | Structured seed listing the source, type, extracted content, and relevance rationale |
| `ai-artifacts/seeds/seed.<intent-slug>.<resource-slug>.html` | Human (user opens in browser to verify) | Static, self-contained, print-friendly visualization |

Slug derivation rules + collision policy: see
[seed-naming.md](seed-naming.md). Both files always share the same
slug.

## seed.<intent-slug>.<resource-slug>.md — exact structure

```markdown
# Seed — <intent-slug> / <resource-slug>

## Source

<URL or absolute file path; or `ideation:<idea-slug>` for ideation type>

## Resource type

<web | youtube | pdf | image | local-doc | local-code | ideation>

## Extracted at

<ISO-8601 timestamp with timezone offset, e.g. 2026-05-27T15:30:00+09:00>

## Intent slug

<intent-slug>

## Extracted content (intent-filtered)

<the relevant excerpts and/or summary, with irrelevant material dropped;
verbatim quotes use markdown blockquote (> ); paraphrased context is
plain prose; section labels (Quote / Paraphrase / Key claim /
Section dropped: ...) are encouraged but not required.
For ideation: the refined idea description from the Phase 2i dialogue.>

## Feasibility check

(ideation type only — omit this section entirely for resource-derived seeds)

<the feasibility-check summary from Phase 2i — what tools were used,
what was found, what the verdict was. Format suggested in
[ideation-mode.md](ideation-mode.md):
  - Tool: <name> — <invocation summary>
    Finding: <quote or paraphrase>
  Verdict: <feasible | contested | needs more digging>>

## Relevance rationale

<one paragraph linking the extracted content to specific INTENT fields
— name the rubric items (Goal, Constraints, Success criteria, etc.)
explicitly, so the downstream plan-establisher can grep for which
seeds inform which planning decisions>

## Provenance

- Seed run ID: <seed_run_id>
- Language used during extraction: <Korean | English>
- Status: <confirmed | skipped-* — but skipped resources don't get seed files; this field is for symmetry with the state file and is always `confirmed` in the emitted markdown>
- Run mode: <standard | bootstrap | ideation>   # optional — useful for chain reviewers
```

## Field rules

- **Source** — the canonical URL or absolute file path. For YouTube,
  use the full canonical `https://www.youtube.com/watch?v=<ID>` form
  even if the user pasted `youtu.be/<ID>`, so the source line is
  copy-paste-able into any browser. For `ideation` type, use
  `ideation:<idea-slug>` — the slug is the same one used in the
  resource_slug (`idea-<idea-slug>`).
- **Resource type** — one of the seven values, lowercased, hyphenated.
- **Feasibility check** — present only for `ideation` type;
  omitted entirely for resource-derived seeds. The section title is
  the literal field name and must stay English; the body follows
  `LANGUAGE`. See [ideation-mode.md](ideation-mode.md) for the
  format and the tool-palette rules.
- **Extracted at** — ISO-8601 with user's local timezone offset.
  Matches the format used in `intent.<slug>.md`'s Provenance.
- **Intent slug** — the chosen slug from Phase 1; redundant with the
  filename but convenient for `plan-establisher` to read without
  parsing the filename.
- **Extracted content (intent-filtered)** — see
  [resource-extraction.md](resource-extraction.md) for what "intent-
  filtered" means and how to format quote vs paraphrase. The section
  title is the literal field name and must stay English; the section
  body follows `LANGUAGE`. Source quotes stay in the source's own
  language.
- **Relevance rationale** — one paragraph (not a bullet list).
  Explicitly name which intent rubric fields each piece of content
  informs. Example: *"The 200-word excerpt above directly informs
  Constraint #2 ('must work behind CloudFront') by documenting Next.js's
  cache-control header behavior at edge. It does NOT speak to Success
  criterion #3 ('< 300ms p95'); pairing with a separate seed about
  CloudFront's TTFB would be needed."*
- **Provenance** — three sub-fields, hyphenated bullets, all English
  field names. Body values can mix languages per the language-selection
  rules.

## Field names stay English

Even when `LANGUAGE=Korean`, the section headings (`## Source`,
`## Resource type`, etc.) stay English. The downstream `plan-establisher`
reads them as machine grammar. Body values follow `LANGUAGE` for prose;
verbatim source quotes stay in the source's language regardless of
`LANGUAGE`.

## seed.<intent-slug>.<resource-slug>.html — structure

Rendered from one `resources[i]` entry in `.seed-state.json` by
`scripts/render_seed_html.py` using the bundled template at
`assets/seed-html-template.html`. Single self-contained file (no CDN,
no external JS). Every user-supplied value is HTML-escaped before
substitution; the template uses single-pass placeholder substitution to
defuse the chained-replace re-substitution class (same approach as
intent-aligner).

Sections (top-to-bottom):

1. **Header** — intent slug + resource slug + a type pill (`Web`,
   `YouTube`, `PDF`, `Image`, `Local doc`, `Local code`, `Ideation`,
   localized).
2. **Source card** — the source URL/path as a large monospace block.
   For web/youtube types whose value begins with `http://` or
   `https://` (lowercase), the URL is rendered as a clickable
   `<a href>` (HTML-escaped). Any other scheme (`javascript:`,
   `data:`, `mailto:`, etc.) falls back to a plain `<div>` text
   block — defense-in-depth even though Phase 2 classification
   already rejects non-http(s) inputs for `web`/`youtube` types. For
   local types, plain text only (no `file://` link — local paths in
   HTML are unreliable across browsers).
3. **Extracted content panel** — the field body rendered with
   blockquote support (markdown `> ` lines become `<blockquote>`),
   inline `<code>` for backticked tokens, and `<p>` for plain prose.
   Bold (`**text**`) and italic (`*text*`) supported. Lists supported
   if present. No HTML in the input is honored — everything is
   escaped.
4. **Feasibility check panel** (ideation type only — omitted entirely
   for resource-derived seeds) — muted-amber tinted panel rendering the
   `feasibility_check` field (same markdown subset as the extracted
   panel: blockquotes, inline `<code>`, bold/italic, lists).
5. **Relevance rationale panel** — single paragraph, soft-tinted
   background to visually distinguish from the extract content.
6. **Footer** — `Extracted at <timestamp> · seed run <seed_run_id>`.

### Chrome localization

`<html lang="…">` and the type-pill label follow `state.language`
(`Korean` / `ko` / `kr` → ko; missing/empty → ko; anything else → en).
Body content (extract, feasibility check, rationale) follows `LANGUAGE`
for prose and the source's own language for verbatim quotes.

## What this schema does NOT include

- **Word counts, character counts, token counts**. The seed is a
  content unit, not a metric unit. If `plan-establisher` wants to
  budget tokens it can count them itself.
- **Hashes / checksums of source content**. Tempting for "did this
  resource change since extraction?" but creates a maintenance burden
  (when does the hash update? does re-extraction overwrite the
  seed?). Skip until concrete need.
- **Author / publication date of the source**. Sometimes useful but
  often not extractable reliably (Open Graph metadata is
  inconsistent). If the user wants it in the seed, they can include
  it in the rationale paragraph.
- **Links between seeds**. Each seed is standalone. Cross-references
  (seed A informs the same constraint as seed B) are
  `plan-establisher`'s job to surface.
- **Implementation hints**. The seed extracts *what* and *why this
  matters for the intent*, not *how* the plan should respond. The
  planner picks structure, packages, tech stack.

If the user pushes any of these into Phase 3 ("just include the
author in the seed"), surface it: *"author / date / hash isn't in the
seed schema by design — would you like to include it in the relevance
rationale paragraph instead?"*
