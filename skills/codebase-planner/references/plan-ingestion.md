# Plan ingestion — multi-method input

Phase 1 of the skill collects the project plan via multiple input methods,
**presented separately** so each can be normalized in isolation before
synthesis. The user may supply zero, one, or many of each kind.

## Verbal-only path (micro & local lanes)

For `micro` and `local` lanes, the chat request **is** the canonical
plan. Do NOT prompt for file paths, URLs, or pasted text. Skip the
multi-method ingestion below and proceed directly to the 3–7 bullet
plan reflection.

The verbal request is captured in chat history; no `plan.sources[]`
entry is recorded because the lightweight lanes don't create a state
file. If the request is too vague to plan (ambiguity ≥ 2 per
[triage-and-readiness.md](triage-and-readiness.md)), Phase 0.5 will
have already blocked and asked one consolidated question round before
this point — so by the time the planner reaches Phase 1 with a
micro/local lane, the verbal request is sufficient by construction.

For `feature` and `system` lanes, proceed with the multi-method
ingestion below.

## Accepted input methods (feature & system lanes)

### Files on disk

User provides one or more file paths. Read each, capturing:

- **Markdown** — read body verbatim
- **Plain text** — read verbatim
- **PDF** — use the `Read` tool's PDF support; for files >10 pages,
  request page ranges from the user before reading

Track each file's path and read timestamp in
`.planner-state.json`'s `plan.sources[]` for the audit trail.

### URLs (Notion / wiki / GitHub issue / spec page)

User provides a URL. Fetch with the `WebFetch` tool. Extract:

- Page title
- Body text (strip nav/footer chrome)
- Embedded code or diagrams (preserve as fenced blocks)

Track each URL and fetch timestamp in `plan.sources[]`. If the URL
returns 401/403/redirect-to-login, surface to user — do not proceed
guessing what's behind the wall.

### Inline pasted text

User pastes plan content directly in chat. Track each paste with a
timestamp in `plan.sources[]`. Inline content is NOT automatically
authoritative over file/URL sources — conflicts are surfaced as Open
Questions per the conflict policy below, not silently resolved by
recency.

## Normalization rubric

For each input source separately, extract these fields. If a field is
absent in the input, write `[unspecified]` rather than guessing.

| Field | What to extract |
|---|---|
| **Goal** | One sentence: what does this project do for whom? |
| **In-scope features** | Bulleted list of features the user expects to be built |
| **Out-of-scope** | Bulleted list of explicit non-goals |
| **Constraints** | Compliance, performance, deployment target, team familiarity |
| **Success criteria** | How will we know this works? Measurable if possible |
| **Open questions** | Anything ambiguous that needs maintainer input |

## Synthesis presentation

After normalizing each source, present a single fenced block to the
user covering ALL sources combined:

```
PROJECT PLAN — synthesis of N sources
=====================================
Goal: <one sentence>

In-scope features:
  - ...
  - ...

Out-of-scope:
  - ...

Constraints:
  - ...

Success criteria:
  - ...

Open questions:
  - ... (each tagged with the source it came from)

Sources:
  [1] file: ./docs/spec.md (read 2026-05-12T14:00:00+09:00)
  [2] url:  https://notion.so/abc (fetched 2026-05-12T14:01:00+09:00)
  [3] inline (pasted in chat at 2026-05-12T14:02:00+09:00)
```

Conflict policy across sources: if two sources disagree on a field,
list both values with their source tags `[1]`/`[2]` and add the
disagreement to `Open questions`. Do not silently pick one.

## Confirmation gate

Wait for `confirm plan` before Phase 2. Silence is not yes. If the user
modifies any field in their reply, re-render the synthesis and re-ask.

## Persistence

The normalized synthesis goes into `.planner-state.json`'s `plan` field
(see [state-and-resume.md](state-and-resume.md) for the schema) at the
moment Phase 4 creates the worktree — not before, since Phase 1 has no
mutations. Re-resume picks up the synthesis from there.
