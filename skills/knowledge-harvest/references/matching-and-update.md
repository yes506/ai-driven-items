# Matching, confidence model, update semantics, and lifecycle

Table of contents:
- [3-tier matching](#3-tier-matching)
- [Confidence model + gate table](#confidence-model--gate-table)
- [Update semantics](#update-semantics)
- [Lifecycle: supersede, deprecate, consolidation](#lifecycle)
- [needs-review kinds and drain](#needs-review-kinds-and-drain)

## 3-tier matching

create-vs-update is decided in three tiers, cheapest first:

1. **Fast (deterministic).** `scripts/match_candidates.py` slugifies
   `canonical_title` and looks for an existing note with that `concept-id` across
   ALL categories, comparing against every note's `aliases[]` (as slugs). Exact
   hit → `match_confidence: exact`. This is real code, not left to the LLM.
2. **Fuzzy (LLM-judge, bounded).** No exact hit → the same script returns a
   **top-k** candidate set from `index.jsonl` ranked by alias/tag/lexical overlap
   and capped by `max_index_entries_per_category` (never a flat scan of the whole
   vault); `prompts/match.md` judges those. Produces `match_confidence`
   high/medium/low/none. `deprecated` notes are excluded from candidates.
3. **Gate.** `match_confidence` × `knowledge_confidence` → `write_action` (below).

Because slugs drift (the same idea gets worded differently across sessions),
**aliases are the workhorse** — distill emits them generously and they feed both
the Fast tier and the top-k pre-filter.

## Confidence model + gate table

Three orthogonal fields, never collapsed into one:
- `knowledge_confidence` — is this durable, reusable knowledge? (from distill)
- `match_confidence` — does it correspond to an existing note? (from match)
- `write_action` — the decision the scripts execute.

| match | knowledge | write_action | note |
|---|---|---|---|
| exact/high | high | `update` | append-delta under lock+CAS |
| medium | any | `propose` | → `_needs-review`, existing note untouched |
| none/low | high | `create` | `ln` collision-refusal write |
| any | medium/low | `propose` or `skip` | never touches an active note |
| any (hook mode) fuzzy | high | `propose` | hook restricts updates to `exact`+high |

**Invariant: `low` knowledge_confidence never creates or updates.** New canonical
notes are not free; duplicates are expensive to clean up.

## Update semantics

- **Append-delta only, on the automated path.** An update appends an additive
  `## Update YYYY-MM-DD` section (Adds / Supersedes / Open-question). The
  `## Current conclusion` head is **never rewritten by hook mode**, and only
  rewritten in manual/`--review` when the change is a pure clarification the user
  approves. This resolves the head-vs-hook contradiction: automated = append,
  human-gated = head edit.
- **Contradiction ⇒ never auto-append.** If new knowledge reverses the current
  conclusion, the match step emits `propose` (not `update`), parking the conflict
  in `_needs-review` for a human.
- **Write primitive:** `apply_plan.py` reads the note, verifies
  `expected_current_sha256` (CAS — **required** for every update), merges, and
  `mv`-replaces atomically. A missing OR mismatched sha (e.g. someone edited the
  note in Obsidian meanwhile) means the plan was built on stale content → the
  unit is dropped to a `conflict` stub in `_needs-review`, never force-written.
- **Boundary owns the gate table.** These decisions are enforced in
  `apply_plan.py`, not just requested in the prompt: `create` requires
  `match_confidence` none/low, `update` requires exact/high + valid CAS, and
  `knowledge_confidence` must be high — anything else becomes a review candidate,
  even if a malformed/adversarial plan says otherwise.

## Lifecycle

Knowledge ages. The schema carries this so stale "truth" stops winning matches:
- `status: deprecated` — kept as history, excluded from match candidates.
- `status: superseded` + `superseded-by: <concept-id>` — matches redirect to the
  successor.
- **Consolidation trigger:** when a note exceeds `consolidation_delta_threshold`
  update sections (config, default 8) or a contradiction is detected, the
  pipeline files a consolidation proposal in `_needs-review`. It never auto-rewrites
  the note — a human runs `--review` to merge the chronology into a clean head.

## needs-review kinds and drain

`_needs-review/` entries are typed by `kind:` so they aren't an undifferentiated
graveyard:
- `candidate` — a `propose`d new note awaiting confirmation.
- `conflict` — an update that contradicted the current conclusion.
- `security-redaction` — a write blocked by the denylist (masked stub only; the
  raw payload is NEVER stored here — see `references/hook-automation.md` and the
  redaction gate).

**Drain:** `/knowledge-harvest --review` walks `_needs-review/`, groups entries by
`concept-id` (so repeated proposals for one concept merge rather than pile up),
and lets the user apply, edit, or discard each. Applying a candidate performs the
same locked write as the main path. For `security-redaction` entries, the user
can `allow-once` a specific finding (by its `span_hash`) when it is a false
positive — e.g. a note that legitimately documents a token *format* rather than a
live secret.
