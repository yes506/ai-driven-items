# Match prompt — knowledge unit vs candidate index (JSON only)

For each distilled unit, decide whether it maps to an EXISTING note or is a NEW
concept, and how safe it is to act. Input: one unit + a bounded candidate list
(top-k from `build_index.py`, pre-filtered by alias/tag/lexical overlap — you do
NOT see the whole vault). Output: one action-plan entry.

## Two independent confidences (do not conflate)

- `match_confidence`: `exact` (concept-id/alias identical) · `high` · `medium` ·
  `low` · `none`. How sure you are this unit corresponds to a candidate note.
- `knowledge_confidence`: carried from distill (durability of the knowledge).

## Decision table (produce `proposed_action` accordingly)

| Situation | match | knowledge | proposed_action |
|---|---|---|---|
| Same concept as a candidate, unmistakable | exact/high | high | `update` |
| Plausibly the same, not certain | medium | any | `propose` (→ _needs-review) |
| No candidate fits, genuinely new & durable | none/low | high | `create` |
| Ambiguous, weak, or not real reusable knowledge | any | medium/low | `propose` or `skip` |

Rules:
- **`low` knowledge_confidence never becomes `create` or `update`.** It is
  `propose` (park in `_needs-review`) or `skip`. New canonical notes are not free.
- In **hook mode**, only `exact`+`high` may `update`; every fuzzy match becomes
  `propose`. (The scripts enforce mode policy, but produce plans that respect it.)
- **You never choose the target path.** Emit `target_concept_id` for updates
  (copy the candidate's `concept_id`) or leave it null for creates (the pipeline
  slugifies `canonical_title`).

## Output schema (one JSON object per unit)

```json
{
  "unit_id": "<carried through by the pipeline>",
  "proposed_action": "create|update|propose|skip",
  "target_concept_id": "gemini-hook-sanitized-env",   // update: candidate's id; create: null
  "category": "Pitfalls",
  "knowledge_confidence": "high",
  "match_confidence": "exact",
  "reason": "Matches candidate by alias 'gemini env sentinel'; same failure mode.",
  "note_body": "<full note markdown incl frontmatter — create only>",
  "delta": "## Update 2026-07-08\n\n### Adds\n...\n### Supersedes\n(none)\n",  // update only
  "expected_current_sha256": "<copy candidate.content_sha256 verbatim — REQUIRED for update>",
  "related": ["existing-concept-id-only"]
}
```

The write engine enforces the gate table deterministically, so emit a consistent
plan: `create` only with `match_confidence` `none`/`low`; `update` only with
`exact`/`high` AND a valid `expected_current_sha256` (the sha of the note you
read to judge the match). An `update` without that sha, or a `create` that
actually matched an existing note, is downgraded to a review candidate — so get
the action right rather than relying on the downgrade.

For `update`, write the `delta` as an **additive** section only. If the new
knowledge *contradicts or reverses* the existing note's current conclusion, do
NOT silently overwrite — set `proposed_action: propose` with `reason` noting the
conflict, so a human resolves it in `--review`. The current-conclusion head is
never rewritten by the automated path.
