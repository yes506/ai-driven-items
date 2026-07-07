# The six fixed categories

Category = the note's **primary folder**, chosen for retrieval convenience. It is
NOT the concept's identity (that's the global-flat `concept-id`), so a note can be
re-categorized without spawning a duplicate. When an insight straddles two
categories, pick the primary folder and add the other as a `tag`.

The set is **fixed** — do not invent top-level categories. Emergent lower-level
grouping goes in `tags[]`, not new folders.

| Category | Holds | Example concept |
|---|---|---|
| `Patterns` | Reusable techniques / approaches — "how to do X well" | "optimistic-concurrency for vault writes" |
| `Pitfalls` | Gotchas, failure modes — "X breaks when Y" | "Gemini hooks run with a sanitized environment" |
| `Decisions` | Chose X over Y because Z (ADR-flavored) | "ledger as single idempotency authority vs per-note scan" |
| `Tools` | Tool / config / CLI knowledge | "`claude --bare` skips hooks but still resolves skills" |
| `Domain` | Business / domain knowledge specific to the project | "how the billing cycle boundary is defined" |
| `Reference` | Links / resources actually encountered **during this cycle** | "MCP Streamable-HTTP spec URL" |

Notes:
- `Reference` is only for resources the cycle genuinely surfaced. This skill does
  **not** run web research to pad it — it captures what you already touched.
- If a unit doesn't clearly fit any category, that is a signal its
  `knowledge_confidence` is low → it should `propose`/`skip`, not force a folder.
