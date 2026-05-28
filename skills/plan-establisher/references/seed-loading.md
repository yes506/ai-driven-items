# Loading seeds/seed.<intent-slug>.*.md

Phase 1 (after loading the intent) discovers and loads all seeds
emitted by `/seed-gatherer` for the chosen `INTENT_SLUG`. The
loaded seeds become `SEEDS` in memory and feed Phase 2 verification
dimensions 2 and 3 (seeds-vs-intent and seeds-vs-seeds).

## Discovery rule

```bash
ls -1 "${MAIN_CHECKOUT}"/seeds/seed."${INTENT_SLUG}".*.md 2>/dev/null
```

Three cases:

| Match count | Action |
|---|---|
| 0 | warn the user: *"No seeds found for intent `<slug>`. Planning will be intent-only (Dim 1 + Dim 4 verification only; Dim 2 + Dim 3 skipped). Type `proceed` to continue, or `abort` to run `/seed-gatherer` first."* If the user proceeds, `SEEDS = []` and Phase 2 skips Dim 2/3. |
| ≥1 | echo: *"Loaded N seeds for intent `<slug>`: \<resource_slug\>, \<resource_slug\>, ... Proceeding to verification."* (No confirmation gate needed — loading is read-only.) |

The optional-seeds path is a real use case: the user may want to plan
from intent alone (no external research material) or may have run
`/intent-aligner` without `/seed-gatherer` yet. Don't refuse —
warn and proceed.

## Field parsing per seed

Each `seeds/seed.<intent-slug>.<resource-slug>.md` follows the schema
documented in `seed-gatherer/references/output-schema.md`. The
relevant fields for verification are:

| Markdown heading | Parsed into `seed.<field>` | Used by |
|---|---|---|
| (filename) | `resource_slug` | identification, evidence-inventory keying |
| `## Source` | `source` | provenance attribution in Dim 3 findings |
| `## Resource type` | `type` | (informational; not actively used in verification but useful in evidence-inventory) |
| `## Extracted at` | `extracted_at` | (informational only) |
| `## Intent slug` | `intent_slug` | sanity check — must match `INTENT_SLUG`; mismatch → skip this seed and warn |
| `## Extracted content (intent-filtered)` | `extracted_content` | the actual content to verify against intent (Dim 2) and against other seeds (Dim 3) |
| `## Relevance rationale` | `relevance_rationale` | self-described mapping to intent fields — Dim 2 uses this as the seed's own claim of which intent fields it informs (we then verify the claim is plausible) |

`## Provenance` is parsed but not loaded into `SEEDS` (similar to the
intent-loader's discarded-extras list); it stays in the seed file for
the human verification HTML if anyone re-renders.

## Parsing strategy

Same lexer pattern as intent-loading.md:

1. Read the whole file into memory.
2. Split on `\n## ` to get section blocks.
3. For each block, the first line is the heading, the rest is the body.
4. Case-sensitive, exact heading lookup.
5. Body parsing:
   - **Single-paragraph fields** (Source, Resource type, Extracted at,
     Intent slug, Relevance rationale): collapse non-blank lines into
     a single string, strip whitespace.
   - **`Extracted content (intent-filtered)`**: preserve the body
     verbatim including markdown structure (blockquotes, lists, inline
     code). Dim 3 needs the structure for fact-claim extraction.

## Defensive behavior

If a seed fails to parse cleanly, **skip it and warn** — do NOT crash
the whole verification run:

| Defect | Action |
|---|---|
| Required heading absent (missing `## Source` or `## Extracted content (intent-filtered)`) | Skip; warn: *"Seed `<resource_slug>` is missing the `## <Field>` section — skipping. Re-run `/seed-gatherer` to regenerate."* Continue loading remaining seeds. |
| `## Intent slug` mismatch (seed claims a different intent slug) | Skip; warn: *"Seed `<resource_slug>` claims intent `<other-slug>` but we're planning for `<INTENT_SLUG>` — skipping. (This usually means the seed file was renamed or moved between intents.)"* |
| File can't be read (permissions, IO error) | Skip; warn with raw error. |
| Body of `Extracted content (intent-filtered)` is empty or only whitespace | Load with `extracted_content=""`; flag as a Dim 2 finding (dead-weight seed) in Phase 2 — don't skip at load time. |
| Source is missing or doesn't look like a URL/path (per seed-gatherer's strict awk) | Load with `source=""`; flag as a Dim 3 attribution gap in Phase 2 (without source we can't attribute conflicts). |

Do NOT modify any seed file. Repair is the seed-gatherer skill's job
(via its Phase 6 `revise` path, or by re-running the skill for that
resource). Editing a seed in-place from here would break the
upstream contract.

## What the loaded seeds are used for downstream

Phase 2:

- **Dim 2 (seeds vs intent)**: for each seed, check that the
  `extracted_content` + `relevance_rationale` actually map to ≥1
  intent rubric field. Flag seeds where the claim is implausible
  (the seed says "informs Goal" but the content is unrelated). Also
  flag seeds that contradict intent (source advocates a feature
  intent's Out-of-scope explicitly excludes).
- **Dim 3 (seeds vs seeds)**: pairwise scan for factual conflicts.
  Use each seed's `source` for provenance: *"seed-A (source: <url>)
  says X; seed-B (source: <url>) says Y."*

Phase 3 synthesis then builds the `Evidence inventory` field of the
plan by mapping each rubric field to the list of contributing seed
slugs (a seed informs a Constraint? list it under that Constraint in
the inventory).

## Honest limitations

- The optional-seeds path means Dim 2 + Dim 3 don't run. The
  resulting plan is intent-only and may be thinner — codebase-planner
  may need to ask more questions of its own. The `Evidence inventory`
  section of the plan will say "(intent-only — no seeds available)".
- Seeds may be stale relative to their source — the seed file
  captures a point-in-time extract. This skill doesn't re-fetch; it
  trusts the extract. If the user knows a seed is stale, they should
  re-run `/seed-gatherer` for that resource before re-running
  `/plan-establisher`.
- Cross-intent seeds (seeds with a different `## Intent slug`) are
  skipped, not auto-recovered. If the user genuinely wants a seed
  cross-applied, they can manually `cp` it to the right slug and
  re-emit — but that's outside this skill's contract.
