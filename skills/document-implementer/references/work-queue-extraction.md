# Work-queue extraction — per scale

Phase 1 normalizes the planner handoff into a flat **work queue**: a
linear list of items the autonomous loop in Phase 3 iterates. Extraction
rule differs per scale; order is **source order** (Q1 default — the TOC
order the planner emitted; documents are read top-to-bottom).

## Feature + system lane — from `${RUN_DIR}/document-plan.md` stubs

The planner emitted `document-plan.md` (under `${RUN_DIR}` —
`ai-artifacts/runs/doc/<slug>-<docplanner-id>/`, resolved from the
marker commit's trailer at Phase 0) with YAML frontmatter at the top
and `## stub: <id>` headings + fenced YAML bodies for each stub.

Extraction:

1. Verify the frontmatter parsed at Phase 0 (carries DOCTYPE,
   OUTPUT_STACK, AUDIENCE, OUTPUT_LANGUAGE, TARGET_PATH, SCALE,
   INTENT_SLUG, DOCPLANNER_ID). These become global queue context.
2. Walk the file from top to bottom. For each `## stub: <id>` heading,
   parse the immediately following fenced ` ```yaml ... ``` ` block.
   Produce a queue item:

```json
{
  "item_id": "<stub-id>",
  "kind": "stub-prose",
  "scale": "feature | system",
  "source_lineno": <line in document-plan.md>,
  "spec_payload": {
    "id": "<stub-id>",
    "purpose": "...",
    "audience": "...",
    "key_claims": ["..."],
    "evidence_sources": ["..."],
    "dependencies": ["<other-stub-id>"],
    "acceptance_criteria": ["..."],
    "length_budget": "<doctype-specific>",
    "open_questions": ["..."]
  },
  "status": "pending"
}
```

3. Cross-check against `${RUN_DIR}/document-structure.mmd`: every node
   in the `.mmd` should correspond to a declared stub. Mismatch is a planner-
   side regression — surface as a discovery blocker.

4. **Empty queue (no stubs declared) = refusal.** The planner
   shouldn't have gated through Phase 7 with an empty stub list; if it
   did, escalate to the user.

## Micro / local lane — from `light/plan` chat bullets

The planner published a 3–7 bullet reflection visible in chat (and
mirrored to a collab-memory file `docplanner-<id>-phase-light-plan.md`).
The handoff block contains the 6 metadata fields but NOT the bullets.

Extraction:

1. The pairing algorithm in [marker-detection.md](marker-detection.md)
   already located the matched `light/plan` content (chat-visible).
   Use that.
2. Parse the bullets — each bullet line (typically starts with `-` or
   `*` or numbered) becomes one queue item:

```json
{
  "item_id": "bullet-<N>",
  "kind": "bullet-prose",
  "scale": "micro | local",
  "source_lineno": <approx chat position>,
  "spec_payload": {
    "bullet_text": "<verbatim bullet>",
    "audience": "<inherited from handoff>",
    "output_language": "<inherited from handoff>"
  },
  "status": "pending"
}
```

3. Empty bullet list = refusal.

## TARGET_PATH precondition (Q7 — create-only v1)

After the queue is built but before Phase 2 worktree creation:

```bash
if [ -e "${TARGET_PATH}" ] && [ -s "${TARGET_PATH}" ]; then
  echo "BLOCKER: TARGET_PATH ${TARGET_PATH} already exists with content."
  ls -lh "${TARGET_PATH}"
  echo "v1 is create-only. Options:"
  echo "  - remove/move ${TARGET_PATH} and re-run"
  echo "  - re-run /document-planner with a different TARGET_PATH"
  exit 1
fi
```

Updates/merges of existing documents require a future
`document-updater` skill or a planner `update` mode.

## OUTPUT_STACK = structured (ppt) — dep check

```bash
if [ "${OUTPUT_STACK}" = "structured" ]; then
  python3 -c "import pptx" 2>/dev/null || {
    echo "BLOCKER: python-pptx not installed."
    echo "Install with: pip install python-pptx"
    echo "Refusing to auto-install (user-consent rule)."
    exit 1
  }
fi
```

`pptx` is the python-pptx import name. Test silently; report
clearly on failure.

## What about `intent_slug` and `docplanner_id` for micro/local?

The chat-handoff block does not include these (planner contract:
6 fields). For Phase 2 worktree path naming, the implementer needs
`INTENT_SLUG`. Options in order of preference:

1. Read the `light/plan` collab-memory filename pattern
   `docplanner-<DOCPLANNER_ID>-phase-light-plan.md` if visible.
   Extract `DOCPLANNER_ID` from the filename.
2. Ask the user for `INTENT_SLUG` (single prompt; not a per-step
   prompt — Phase 1 is bootstrap, not the autonomous loop in
   Phase 3).
3. If user declines, compute a slug from the document title or
   first bullet.

The autonomy boundary applies to Phase 3 (no per-step prompts);
Phase 1 may prompt once for bootstrap metadata. `DOCIMPL_ID` is
always computed fresh (per the codebase-implementer pattern) — not
inherited from `DOCPLANNER_ID`.

## Per-item context loading

Phase 3 loads, for each item:

- The stub's 9-field `spec_payload`
- For each dep in `spec_payload.dependencies`:
  - **Backward dep** (already generated this run): load the
    generated prose from `state.work_queue[i].generated_content`.
  - **Forward dep** (not yet generated): load only the dep stub's
    `purpose + key_claims` summary from `state.work_queue[i].spec_payload`.

The 8K-token cap rule is implemented in
[implementation-loop.md](implementation-loop.md) — Phase 3 calls
into that algorithm per-item; this file just produces the queue.

## Item ordering — source order (Q1)

Feature/system: source order = stub order in `document-plan.md` =
TOC order from planner Phase 2 = the reading order.

Micro/local: source order = bullet order in the `light/plan`
reflection.

NOT topo-sort (codebase-implementer pattern — that's leaf-first for
collaborator requirements). Documents are read top-to-bottom; later
sections may legitimately reference earlier ones via `[[stub-id]]`.
Forward references are handled by the Phase 3 fallback rule.

## Honest limitations

- v1 cannot extract from a non-canonical `document-plan.md` structure
  (e.g., stubs without the `## stub: <id>` heading convention).
- v1 micro/local bullet extraction assumes one bullet per line;
  multi-line bullets get concatenated as one item.
- Bullet → queue-item mapping is verbatim; the implementer does NOT
  re-interpret or re-classify bullets at Phase 1 (that would re-plan).
