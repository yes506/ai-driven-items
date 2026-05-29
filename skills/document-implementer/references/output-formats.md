# Output formats — per-DOCTYPE rendering rules

Single compact reference (≤120 lines) covering: target file
extension, heading/section convention, `[[stub-id]]` transformation,
and per-doctype rendering hints. Loaded by Phase 1 (queue shape) and
Phase 3 (generation rules).

## At-a-glance table

| DOCTYPE | OUTPUT_STACK | TARGET_PATH ext | Section convention | `[[stub-id]]` → |
|---|---|---|---|---|
| api-spec | text | `.md` / `.markdown` | `<a id="<stub-id>"></a>` + `## <METHOD> <path>` (e.g. `## GET /users/{id}`); fall back `## <stub-id>` only if METHOD/path absent | markdown `[<title>](#<stub-id>)` |
| tech-spec | text | `.md` / `.markdown` | `<a id="<stub-id>"></a>` + `## <stub-title>` derived from stub `purpose` (title-case) | markdown `[<title>](#<stub-id>)` |
| runbook | text | `.md` / `.markdown` | `<a id="<stub-id>"></a>` + `### Step N — <action>` (preserve step-number prefix) | markdown `[step N](#<stub-id>)` — link text MUST include "step N" |
| ppt | structured | `.pptx` | One slide per work_queue item. Slide title = `spec_payload.title`. Speaker-notes first line = stub_id (provenance) | python-pptx slide-jump action; inline text `(see slide <N>)` |

**MANDATORY for text stacks**: emit `<a id="<stub-id>"></a>` on its
own line **immediately before** every section heading. Without this,
`validate_doc_completeness.py` cannot resolve `#<stub-id>` (heading
slugs derive from human titles, not stub-ids — `context` stub →
`## System Overview` heading → slug `system-overview` → mismatch).
The explicit anchor is the single machine target the validators
rely on.

## Per-doctype rendering hints

### api-spec (text)

- Each endpoint stub renders as a section starting with
  `<a id="<stub-id>"></a>` (mandatory anchor) then:
  - Heading: `## <METHOD> <path>` (e.g. `## POST /orders`)
  - Sub-headings: `### Request` / `### Response` / `### Errors` /
    `### Examples` as the stub's `key_claims` and `length_budget`
    dictate
  - Code fences for request/response payloads (` ```json ` / ` ```http `)
- Cross-endpoint refs (`[[stub-id]]`) → in-page anchor.
- OpenAPI YAML output is **deferred to v1.5**. v1 emits markdown
  only.

### tech-spec (text)

- Each section stub renders as `<a id="<stub-id>"></a>` (mandatory
  anchor) then `## <title>` followed by prose.
- `key_claims` become topic sentences or bullet lead-ins.
- `evidence_sources` may appear as a section-end "Sources" bullet
  list or inline citations `(see [<source>](<url>))`.
- `acceptance_criteria` are NOT shown in the rendered tech-spec
  (they're the implementer-side contract; Phase 6 reviewer sees
  them in the report). Author the section to MEET the criteria.

### runbook (text)

- Each step stub renders as `<a id="<stub-id>"></a>` (mandatory
  anchor) then `### Step N — <action>`.
- The "Step N" prefix MUST appear in the heading text AND in any
  cross-reference link text (operators reading the runbook need
  ordinal context, not just a step-id slug).
- Sub-sections within a step: `**Precondition**`, `**Action**`,
  `**Verify**` as bold inline labels or `####` sub-headings.
- Decision steps (a step that branches) get a fenced block:
  ```
  If <condition>: go to [step M](#step-M-…).
  Else: go to [step P](#step-P-…).
  ```

### ppt (structured)

- One slide per stub. Slide layout: `Title + Body` (python-pptx
  layout index 5).
- Slide title = stub `title` (sanitized for pptx character
  restrictions).
- Slide body = `generated_content` (typically bullet list rendered
  via newline-separated paragraphs in a text frame; font 18pt
  baseline).
- Speaker notes = stub_id on the first line (provenance contract —
  `validate_anchors.py --pptx` verifies this) + optional
  speaker-script content on subsequent lines.
- Cross-slide refs: inline text `(see slide N)` where N is the
  1-indexed slide number of the target. The renderer can also add a
  python-pptx `hyperlink.slide` action on the link text for
  interactive jumps.
- Charts / images: out of scope for v1. The implementer generates
  text bullets only; richer content is a Phase 6 revise iteration
  or a v1.5 enhancement.

## OUTPUT_LANGUAGE applied to body

All prose / slide content is generated in `OUTPUT_LANGUAGE`
(captured from planner contract, English or Korean):

- Headings: in `OUTPUT_LANGUAGE` (e.g. Korean `## 컨텍스트` for a
  Korean tech-spec context section).
- Stub-id slugs and `[[stub-id]]` anchors: ALWAYS English / ASCII
  (these are machine identifiers, not human-facing text).
- Cross-reference link text: in `OUTPUT_LANGUAGE` (e.g. Korean
  `[컨텍스트 참조](#context)`).
- Speaker notes (ppt): in `OUTPUT_LANGUAGE` for human-facing
  speaker-script content; the first-line stub_id stays ASCII.
- Code blocks (api-spec request/response examples): keep payload
  field names + code in their natural form (JSON/HTTP). Comments
  may follow `OUTPUT_LANGUAGE`.

## Honest limitations

- v1 heading-slug computation uses a simplified GitHub-style
  slugifier in `validate_doc_completeness.py`. Edge cases (unicode
  in headings, repeated headings) may produce unexpected anchor
  values. If validation fails on anchor resolution, surface the
  expected vs actual slug in the auto-fix attempt diagnostic.
- v1 runbook step-number prefix is human-maintained by the planner
  (stubs already use `step-N-…` ids). The implementer preserves
  what's there; it does NOT renumber.
- v1 ppt slide layouts are minimal. Brand templates, slide masters,
  custom theming are v1.5+ (or a Phase 6 `revise` cycle with the
  `pptx` skill in a separate invocation).
