# DOCTYPE: ppt

Slide deck / presentation. Stub primitive: **per-slide**.
`OUTPUT_STACK = structured`.

## When to pick this DOCTYPE

- The intent is a presentation, not a written document.
- The audience will consume it as slides (live talk, pre-read deck,
  pitch).
- The eventual deliverable is `.pptx` (preferred — produced via
  python-pptx or the bundled `pptx` skill).

## Stub primitive: per-slide

One stub = one slide. Section dividers / title slides / agenda
slides are also stubs (their `purpose` is structural, but they
still need the full 9 fields).

Slide order matters and is encoded in stub `id`s with a numeric
prefix: `slide-01-title`, `slide-02-agenda`, `slide-12-pricing`, etc.

## Field interpretations

| Field | ppt interpretation |
|---|---|
| `id` | kebab-case with slide-number prefix (2 digits): `slide-03-problem`, `slide-12-pricing-tiers` |
| `purpose` | The narrative role of the slide in the speaker's argument. NOT a description of what's on the slide — what it ADVANCES in the talk |
| `audience` | The room. If the deck will be re-used for multiple audiences, document the canonical audience here and note alternates in `open questions` |
| `key claims` | The bullet points / take-aways the audience should leave the slide with. Phase 7 rubric checks that each claim fits in the slide's `length budget` |
| `evidence sources` | Source for any number / chart / quote on the slide. Pre-Talk: where does the data come from? Post-Talk: this is the audit trail |
| `dependencies` | Earlier slides this one builds on. Most decks are linear; backreferences (e.g. an FAQ slide referencing several prior slides) are encoded as multiple dependencies |
| `acceptance criteria` | Concrete checks the implementer must hit: max bullet count, data viz type (bar/line/table), required logo placement, brand-template adherence |
| `length budget` | Bullet-slot count + speaker-time — e.g. `4 bullets / 60 sec`, `1 hero chart / 90 sec`, `title only / 15 sec` |
| `open questions` | Slot for "should this slide exist? merge with the next? cut entirely?" — slide-cutting decisions often happen during rehearsal |

## Phase 2 (outline) shape

Slide list with speaker-time and visual type:

```
01. slide-01-title            — Title slide (15 sec)
02. slide-02-hook             — Opening hook / question to the room (30 sec)
03. slide-03-problem          — Problem statement (1 min, 1 chart)
04. slide-04-stakes           — Why this matters now (1 min)
05. slide-05-thesis           — Our take in one sentence (30 sec)
06. slide-06-evidence-a       — Supporting data point 1 (1 min, 1 chart)
07. slide-07-evidence-b       — Supporting data point 2 (1 min, 1 chart)
08. slide-08-counter          — Anticipating the counter-argument (1 min)
09. slide-09-recommendation   — What we recommend (90 sec, 3 bullets)
10. slide-10-cta              — Call to action / next step (30 sec)
```

Grouping by speaker beat is encouraged — e.g. slides 06-07 form
the "evidence" beat.

## Validation hints (Phase 6)

For ppt, the Phase 7 rubric should additionally check:
- Slide count is reasonable for the speaker-time budget (rough rule:
  ≤1 slide per 60 sec of talk for content slides; ≤2 sec per slide
  for rapid-fire intro/section slides).
- No slide's `length budget` requires more bullets than fit on a
  standard slide (typically ≤6 bullets at 24pt+ font).

These are heuristics surfaced as warnings, not hard rule failures.

## Implementer handoff notes

`document-implementer` for ppt is the only DOCTYPE with
`OUTPUT_STACK = structured`. It generates `.pptx` via:
- The repo's `pptx` skill (preferred — already handles brand
  templates, layouts, and styling), OR
- Direct python-pptx invocation if `pptx` skill isn't available.

`[[stub-id]]` transformation: python-pptx `hyperlink.slide` action
referencing the target slide's index. Pre-talk Q&A jump-slides are
the main use case.

The implementer is also responsible for:
- Applying the brand template / master slide.
- Generating speaker notes from `purpose` + `key claims`.
- Sizing charts and images per the `length budget` constraint.
- Verifying the final `.pptx` opens cleanly (e.g. `unzip -l`
  smoke check that python-pptx didn't emit a corrupted file).

## Honest limitations

- v1 stub primitive is one-slide-one-stub. Multi-slide builds
  (where one logical slide animates over 3 clicks) are 3 stubs in v1
  — capture the animation intent in each stub's `acceptance criteria`.
- Speaker notes are the implementer's output, not the planner's.
  The planner's job is the talk structure, not the talk script.
- Brand-template selection and visual style are out of scope for the
  planner. Capture brand requirements in document-level `Constraints`
  at Phase 1 and let the implementer (+ optionally the `pptx` skill)
  apply them.
