# Phase 2 — Synthesis & optional web research

After the finish signal, the AI synthesizes the buffered chunks into a
publishable note. Web research is **optional and AI-discretionary** —
the budget is small and the rule is "only when the user would clearly
benefit", not "always".

## Phase 2 prelude — final orphan-recovery sweep

Before reading the buffer/draft, run the same orphan-recovery sweep
documented in [capture-mode.md → Operating contract rule 0](capture-mode.md#operating-contract-during-phase-1).
The motivation: a user who types `finish` immediately after a turn
that crashed between `Write(tmp)` and `cat tmp >> draft` would
otherwise synthesize a draft that's missing the last captured chunk
— rule 0 catches this on every Phase 1 turn, and the Phase 2 prelude
covers the edge case where Phase 2 is entered directly from a stale
`recover` path (no Phase 1 turn happened in this invocation). Run it
once, idempotently:

```bash
{ setopt null_glob 2>/dev/null || shopt -s nullglob 2>/dev/null; } || true
for f in "${NOTES_DIR}/.live-notes-drafts/${SESSION_ID}.chunk."*.tmp; do
  [ -e "$f" ] || continue
  cat "$f" >> "${NOTES_DIR}/.live-notes-drafts/${SESSION_ID}.draft.md" \
    && rm "$f"
done
```

## Inputs

- The in-memory buffer (canonical) **and** the on-disk draft (parity
  check on resume). If they diverge — should only happen on a resumed
  session — the draft wins for any chunks the in-memory buffer is
  missing. The Phase 2 prelude sweep above must have already ensured
  no orphan tmp files contributed-to-but-not-merged remain.
- `LANGUAGE` (set in Phase L, possibly mid-flow switched).
- The Phase 1 tentative category (if any), and any explicit category
  hint from a mid-capture `category <slug>` meta-command.
- ISO timestamps `started`, `finished` (current time at finish).

## Zero-chunks early-exit

Decide using the in-memory `BUFFER` (canonical) — Phase 2's first
gate, ahead of title derivation. The buffer's content-chunk count is
the source of truth; the on-disk draft is a defensive secondary
signal but may not exist at all, because the draft header Write is
gated on the **first content message** (see
[capture-mode.md → Step 1](capture-mode.md#append-mechanics--byte-safe-two-step-recipe)),
so a user who types `finish` immediately after the Phase 0 ACK has
neither chunks nor a draft file.

**Precondition — BUFFER must be canonical when this gate fires.**
For Phase 2 entered from Phase 1 (fresh session that finishes after
≥0 chunks), BUFFER is already populated by the per-turn appends. For
Phase 2 entered directly from the stale-draft `recover` path,
BUFFER **must be rehydrated from the post-sweep draft** before this
check runs — see
[capture-mode.md → recover bootstrap step 5](capture-mode.md#phase-0--resume-orphan-integration).
Without that rehydration, the check fires spuriously and the
cleanup below wipes the user's recovered content (an empirically
verified data-loss bug — do not regress).

**Trigger**: if (post-rehydration) `BUFFER` has zero content chunks
(any `section` meta-command dividers don't count — those are
structural markers, not content), do NOT synthesize an empty note.
Instead, surface a one-line message and stop cleanly:

- **Korean**: `📭 캡처된 내용이 없습니다. 다시 호출해서 메모를 입력하거나, 이미 호출했다면 메모를 먼저 입력한 뒤 finish를 보내 주세요.`
- **English**: `📭 No content was captured. Re-invoke and type some notes first, or send your notes before "finish".`

**Cleanup** (defensive — all `rm -f` so the snippet is silent when a
path is already absent, which is the common case for the
finish-before-any-content path):

```bash
rm -f "${NOTES_DIR}/.live-notes-drafts/${SESSION_ID}.draft.md"
{ setopt null_glob 2>/dev/null || shopt -s nullglob 2>/dev/null; } || true
rm -f "${NOTES_DIR}/.live-notes-drafts/${SESSION_ID}.chunk."*.tmp
```

This refuses-rather-than-saves-empty preserves the user's intent
(they almost certainly hit `finish` by accident or to test the skill),
and prevents an empty `{YYYY-MM-DD}-{HHmm}-notes.md` from littering
the notes directory.

## Synthesis steps

1. **Parse the buffer.** Strip chunk markers; reassemble the raw
   prose. Note where the user inserted `## <name>` section dividers
   via meta-command — those are intentional structure hints.

2. **Title derivation.** Generate a concise title (≤ 12 words, ≤ 80
   chars) capturing the session's topic. Prefer nouns over verbs;
   prefer specific over generic. Examples:
   - Buffer about "the Q3 planning sync where we agreed to ship X" →
     `Q3 planning sync — agreed scope and owners`
   - Buffer of Rust iterator notes → `Rust iterator combinators —
     map, filter, collect`
   - Buffer with no obvious topic → fall back to
     `Notes {YYYY-MM-DD HH:MM}` (timestamp-as-title; safe default)

3. **TL;DR draft.** 3–5 bullets. Each bullet is one
   independently-readable sentence summarizing a key fact, decision,
   or takeaway. Order by importance, not chronology. Never invent
   facts — every bullet must trace to specific buffer content.

4. **Detail organization.** Group the buffer into 2–6 H2 sections.
   - If the user inserted explicit `## <name>` section dividers
     during capture, **honor those exactly** as the H2 boundaries.
     Don't override the user's structure.
   - Otherwise, infer sections from topic shifts in the buffer. Use
     descriptive nouns as section headings.
   - Within each section, preserve the user's wording. Light editing
     allowed (fix typos, expand obvious abbreviations); heavy
     rewriting forbidden — these are the user's notes, not yours.
   - Lists, code blocks, and quoted passages from the buffer stay as
     they were (markdown fences, blockquotes preserved).

5. **Identify research gaps.** Scan the synthesized note for items
   the AI should verify or supplement. Eligibility rules below.

## Web research — eligibility and budget

### Trigger rules

The AI may invoke `WebSearch` / `WebFetch` to supplement the note
when, and only when:

- The note contains a **factual claim that would be wrong if
  misremembered** (specific date, version number, named statute,
  named person's title) AND the buffer indicated uncertainty (e.g.
  "I think it was…", "Q3 2024?", "around 5h").
- The note contains a **named entity** (library, product, person,
  paper) the user referenced but didn't define, AND a one-paragraph
  definition would meaningfully improve the note for later re-reading.
- The note contains a **URL the user pasted** as a reference but
  didn't summarize — fetching that URL and adding a one-line synopsis
  to the References section helps future-self.

The AI must NOT invoke web research when:

- The buffer is entirely opinion, reflection, or planning. There's
  nothing to verify.
- The buffer is about company-internal systems, internal jargon, or
  private projects. Web research won't help; it might even surface
  irrelevant external results that mislead.
- The user explicitly said `no research` (or `리서치 안함`) at any
  point during capture or at the synthesis preview. Honor that.

### Budget

Hard caps per session:

- `WebSearch` calls: **≤ 3**
- `WebFetch` calls: **≤ 3** (including any URL the user pasted)
- Total wall-clock spent on research: target ≤ 60s, hard cap ≤ 120s.
  If research is taking longer, finalize the note without the in-flight
  lookup and surface a `(research truncated)` note in References.

If the AI determines research is needed but anticipates exceeding the
budget, prefer **0 research** over partial — a half-verified fact is
worse than an honest "I think it was…" the user can verify later.

### Citation format

Every research-derived addition must be cited. The skill's references
section is the dedicated place:

```markdown
## References

- [HMAC RFC 2104](https://datatracker.ietf.org/doc/html/rfc2104) — defines the HMAC construction.
- [Tokio runtime docs](https://docs.rs/tokio/latest/tokio/runtime/index.html) — flavored runtimes and `Builder`.
```

If a research finding **contradicts** something in the user's note,
preserve the user's original wording in the body, and add a marginal
note in italics:

> _Note: per [source], this is actually X (the buffer said Y). Verify
> if accuracy matters._

Never silently overwrite a user-stated claim with a "corrected" one.

### Failure handling

A failed `WebSearch` / `WebFetch` (network error, 404, paywall):

- Log nothing to the note's body.
- Surface in References as `_(failed to fetch <URL>: <reason>)_` if
  the user originally pasted that URL. Otherwise omit silently.
- Continue synthesis. Never block save on research failure.

## Preview render (in chat, before Phase 3)

Render the synthesized note's preview in chat for the user to review.
The preview shows:

- Proposed file path: `${NOTES_DIR}/${CATEGORY}/${FILENAME}.md`
- Proposed frontmatter (compact YAML)
- The note body, abbreviated to the first ~40 lines with `…` for
  truncation. If the body is short, show the whole thing.
- References section in full (small, and the user needs to see what
  the AI fetched).
- A summary line: `Research: <N> searches, <M> fetches, <skipped|none>`.

Then the Phase 3 gate prompt — see [output-schema.md](output-schema.md)
for the frontmatter spec and `SKILL.md` Phase 3 for the gate tokens.

## Honest limitations

- "AI judgment" on what to research is fuzzy — the AI may
  occasionally over-research (wasting tokens) or under-research
  (leaving an obvious gap). The `no research` opt-out and the small
  budget bound the worst case.
- The skill does not cache prior research. A second `/live-notes`
  session on the same topic will re-fetch.
- The skill cannot verify deep claims (academic papers, paywalled
  sources, internal-system behavior). Research is best-effort
  public-web only.
- Citations point to the URL fetched, not to a canonical archival
  snapshot — if the source changes later, the citation is stale.
  Adding archival URLs (web.archive.org) is out-of-scope; the user
  who needs that does it themselves.
