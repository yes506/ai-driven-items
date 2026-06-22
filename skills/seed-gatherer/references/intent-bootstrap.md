# Intent bootstrap — capturing intent ad-hoc within seed-gatherer

When the user runs `/seed-gatherer` and **no `intent.<slug>.md` exists**
at `MAIN_CHECKOUT/ai-artifacts/intents/`, the skill can capture intent ad-hoc and emit
`ai-artifacts/intents/intent.<slug>.{md,html}` alongside seeds in the same worktree+merge
cycle. This is the **bootstrap path** — the second of three Phase 1
branches.

| Match count at `MAIN_CHECKOUT/ai-artifacts/intents/` for `intent.*.md` | Phase 1 branch |
|---|---|
| 0 | offer bootstrap OR abort — full spec in this file |
| 1 | auto-pick (standard path) |
| ≥2 | numbered menu (standard path) |

The bootstrap path is purposefully **lighter** than a full
`/intent-aligner` run. It's optimized for users who want to jump
straight into seed work but happen not to have run intent-aligner
first. The intent it produces is valid (revision 1, same schema), and
`/intent-aligner update <slug>` can refine it later from accumulated
seeds — see the chain narrative in SKILL.md.

## When to use bootstrap vs. redirect

| Situation | Path |
|---|---|
| User has a clear prompt + concrete resources to extract from | **Bootstrap** — capture intent, then proceed normally to Phase 2 resource intake |
| User wants to ideate from scratch (no resources, no clear ask) | **Bootstrap + ideation** — capture rough intent, then Phase 2 ideation mode crystallizes ideas into seeds (see [ideation-mode.md](ideation-mode.md)) |
| User has zero idea what they want | Redirect — *"Bootstrap mode needs a starting point (a prompt, URL, or file). Try `/intent-aligner` for full Socratic elicitation instead."* |
| User has a vague feeling but is happy to be questioned | **Bootstrap** with focused gap-filling — the elicitation loop below |

## Phase 1b — Bootstrap dialog (no-intent branch)

Phase 1's zero-match case opens with:

```
No `intent.<slug>.md` found at <MAIN_CHECKOUT>/ai-artifacts/intents/.

You have two options:
  1) Bootstrap intent here — paste a prompt / URL / file path
     describing what you want to build or fix, and I'll capture it
     as `ai-artifacts/intents/intent.<slug>.md` (revision 1) alongside the seeds we collect.
  2) Abort — run `/intent-aligner` first for a more thorough capture,
     then come back to `/seed-gatherer`.

Type `1` (or `bootstrap`) or `2` (or `abort`).
```

`bootstrap` / `1` → enter bootstrap. `abort` / `2` → exit cleanly.
Silence is not yes.

## Phase 1b.1 — Capture the seed-of-intent

After the user opts to bootstrap, prompt:

```
Paste your starting intent. Any of these works:
  · prompt text (a paragraph or sentence describing the goal)
  · URL (web page, blog post, PRD link — we'll fetch + synthesize)
  · absolute file path (md/txt/pdf — we'll read + synthesize)
You can also combine them — paste a URL then add prompt text in the
same message.

Type `done` when you've provided everything you have.
```

For each input the user pastes, classify:

| Input | Action |
|---|---|
| Free text (no URL / no absolute path) | Treat as prompt text — append to in-memory `BOOTSTRAP_PROMPT` |
| `http://` or `https://` URL | `WebFetch` the URL; append the returned content (truncated to a reasonable cap) to `BOOTSTRAP_SOURCES[]` with `type=web`, `location=<url>` |
| Absolute path (`/...`) ending in `.pdf` | `Read` with `pages` (≤20); append to `BOOTSTRAP_SOURCES[]` with `type=pdf` |
| Absolute path ending in `.md` / `.txt` / `.rst` | `Read`; append with `type=local-doc` |
| Absolute path ending in image extension | `Read` (vision); append with `type=image` |
| Anything else | refuse: *"Not a recognized starting point. Paste prompt text, an http(s) URL, or an absolute file path."* |

**Pre-fetch gate** — before any `WebFetch` or `Read`, list the
classified items and require explicit `proceed`:

```
Ready to fetch <N> sources to bootstrap intent:
  1. web: <url>
  2. pdf: <path>
Plus prompt text: <first 100 chars>...
Type `proceed` (advance to synthesis), `revise <n>` (re-classify), or
`drop <n>` (remove).
```

This catches mistyped URLs the same way Phase 3's standard pre-fetch
gate does.

## Phase 1b.2 — Synthesize the 6 rubric fields

Once `BOOTSTRAP_PROMPT` and `BOOTSTRAP_SOURCES[]` are gathered, the
agent does AI synthesis:

1. **Goal** — single sentence in the "For `<persona>`, `<outcome>`" form
   (matching intent-aligner's output-schema). If the persona is
   implicit, use a generic "any user" fallback and surface it as an
   open question.
2. **Mode** — `feature` (user describes a thing to build) or
   `problem` (user describes a pain). Heuristic — echo it back to the
   user for confirmation, like intent-aligner's Phase 1.
3. **Persona** — single sentence; from prompt or sources, or `[unspecified]`.
4. **In-scope features** — bullet list, verbatim from prompt/sources.
5. **Out-of-scope** — bullet list. Often empty in bootstrap; if so,
   echo *"Nothing in your input explicitly excluded anything — flag this
   as an Open question?"*
6. **Constraints** — bullet list. Bootstrap intents tend to be thin
   on constraints; the elicitation loop below surfaces gaps.
7. **Success criteria** — bullet list. Bootstrap intents are usually
   weak here too.
8. **Open questions** — bullet list. Every field that came up
   `[unspecified]` becomes an open question.

## Phase 1b.3 — Focused gap-filling elicitation

Bootstrap is intentionally lighter than `/intent-aligner`'s Socratic
loop. Run a **single focused pass** asking only about the fields that
are critically thin:

| Field state | Action |
|---|---|
| `Goal` is empty or `[unspecified]` | Ask 1 Socratic question — *"What's the outcome you want? Who feels the difference if this works?"* — must be filled before exit |
| `Constraints` is empty AND `Out-of-scope` is empty | Ask once — *"Anything this should NOT do? Any hard requirements (budget, deadline, stack, compliance)?"* — accept `none` |
| `Success criteria` is empty | Ask once — *"How will you know this worked? What changes for the user?"* — accept `[unspecified]` if user is stuck |
| Anything else thin | Surface as an Open question and move on |

Cap: **3 focused questions total**, not the 3-pass loop of full
elicitation. If the user has more to say, they can rerun
`/intent-aligner update <slug>` later for deeper refinement.

This is by design — bootstrap is for users who want to *get to seed
gathering quickly*, not those who want a thorough capture. Recommend
`/intent-aligner` (create mode) up front if the user wants depth.

## Phase 1b.4 — Slug capture + confirm intent

Ask the user for `PROJECT_SLUG` (same rule as intent-aligner Phase 3 —
short ASCII; sanitized at Phase 4). Then render the synthesized intent
in chat in the same format as intent-aligner's Phase 3 synthesis block.
Add a banner:

```
INTENT (bootstrap synthesis)
=============================
This intent was bootstrapped from your starting inputs. It will be
captured at revision 1 alongside the seeds we collect, with provenance
`Bootstrapped by: seed-gatherer`. You can refine it later with
`/intent-aligner update <slug>`.

Type `confirm intent` to lock this synthesis and proceed to seed
gathering, or `revise` to iterate.
```

`confirm intent` → set `RUN_MODE=bootstrap`, record `verified_at`,
proceed to Phase 2 (resource intake — possibly ending in ideation
mode). Silence is not yes.

## Phase 2 onward (bootstrap variant)

Phase 2 resource intake runs as normal. The only behavioral difference
is that **typing `done` with zero resources** in Phase 2 does NOT
refuse — instead it offers ideation mode (see
[ideation-mode.md](ideation-mode.md)). In standard mode (intent loaded
from a pre-existing file) the same offer applies — ideation is not
bootstrap-specific.

## Phase 5 (bootstrap variant)

Phase 5 emits BOTH intent and seed artifacts in the same per-resource
loop's prefix and suffix:

1. **Pre-loop**: `mkdir -p ai-artifacts/intents`, then write
   `ai-artifacts/intents/intent.${INTENT_SLUG}.md` and
   `ai-artifacts/intents/intent.${INTENT_SLUG}.html` at the worktree root. The HTML is
   rendered by the bundled `scripts/render_intent_html.py` (copied
   from intent-aligner — see "HTML renderer provenance" below):

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/render_intent_html.py" \
     .seed-state.json > "ai-artifacts/intents/intent.${INTENT_SLUG}.html"
   ```

   The script reads `.seed-state.json` looking for an `intent` object
   matching intent-aligner's state schema. Bootstrap state populates
   the intent object with all required fields so the renderer is
   format-compatible.

2. **Per-resource loop**: emit `ai-artifacts/seeds/seed.${INTENT_SLUG}.*.{md,html}`
   exactly as the standard flow (see SKILL.md Phase 5).

3. **Single batch commit** subject:
   ```
   feat(seeds+intent): bootstrap ${INTENT_SLUG} (rev 1 + ${SEED_COUNT} seeds)
   ```

   The commit stages `ai-artifacts/intents/intent.${INTENT_SLUG}.{md,html}` AND
   `ai-artifacts/seeds/seed.${INTENT_SLUG}.*.{md,html}` together.

The intent.md MUST include in its Provenance section:

```markdown
- Intent ID: <seed_run_id-like-value>
- Revision: 1
- Confirmed at: <verified_at>
- Language used during elicitation: <Korean | English>
- Bootstrapped by: seed-gatherer
```

`Refined from seeds` and `Prior revision intent ID` are absent on
revision 1 (those land on the first `/intent-aligner update` run).

## Phase 6 (bootstrap variant)

Merge marker is **distinct** from the standard `(seeds,
human-confirmed)`:

```
feat(seeds+intent): merge ${INTENT_SLUG} bootstrap (rev 1 + ${SEED_COUNT} seeds) (intent+seeds, bootstrap, human-confirmed)
```

The `(intent+seeds, bootstrap, human-confirmed)` marker is the audit-
trail signal that this single commit pair landed both intent.md AND
seeds. It's grepable from `git log` for reviewers tracing the chain.

## HTML renderer provenance

`scripts/render_intent_html.py` and `assets/intent-html-template.html`
are **copied from intent-aligner** so seed-gatherer's bootstrap path
is self-contained. The two skills are siblings in the chain and share
the intent artifact format.

If intent-aligner's renderer ever drifts, the seed-gatherer copy may
fall behind — this is a known maintenance concern, **mitigated** by
the fact that the renderer is functionally stable (it's a templating
script, not a feature surface). When updating either, mirror the
change in both.

## State-file additions for bootstrap

`.seed-state.json` gains the following when `RUN_MODE == "bootstrap"`:

```json
{
  "run_mode": "bootstrap",
  "intent_slug": "<chosen at Phase 1b.4 from PROJECT_SLUG>",
  "intent": {
    "mode": "feature | problem",
    "persona": "<string or [unspecified]>",
    "goal": "<single sentence>",
    "in_scope": ["..."],
    "out_of_scope": ["..."],
    "constraints": ["..."],
    "success_criteria": ["..."],
    "examples": ["..."],
    "counter_examples": ["..."],
    "root_cause": [],
    "open_questions": ["..."]
  },
  "bootstrap_sources": [
    {"type": "web", "location": "<url>", "extracted_at": "<iso>"},
    {"type": "pdf", "location": "<absolute-path>", "extracted_at": "<iso>"},
    {"type": "prompt", "location": "(inline prompt text)", "content": "<the prompt>", "extracted_at": "<iso>"}
  ],
  "bootstrap_intent_id": "<seed_run_id reused as the intent's Intent ID>",
  "bootstrap_verified_at": "<iso — when user typed confirm intent at Phase 1b.4>"
}
```

The `intent` object's schema matches what intent-aligner writes to its
own state file, so the HTML renderer reads it identically.

## Forbidden actions (bootstrap-specific)

In addition to seed-gatherer's standard forbidden actions:

- **Fetching bootstrap sources before the Phase 1b.1 pre-fetch
  `proceed` gate.** Same protection as Phase 3 — accidentally pasted
  private URLs should not be fetched silently.
- **Bypassing the 3-question elicitation cap.** Bootstrap is
  deliberately lighter than `/intent-aligner`. If the user wants
  depth, redirect them.
- **Setting `revision` to anything other than `1` in bootstrap output.**
  Bootstrap always produces a fresh revision-1 intent. Updates are
  `/intent-aligner update`'s job.
- **Treating `prompt` ad-hoc input as a fetchable source.** Prompt
  text is the user's own words; record it verbatim in
  `bootstrap_sources[]` with `type=prompt` but do not pass it to any
  fetch tool.
- **Falling back from bootstrap to "no-intent" silently.** If the
  user types `abort` at the Phase 1b dialog, exit cleanly — don't
  proceed without an intent.

## Honest limitations

- **Bootstrap intents are thinner than create-mode intents** by
  design. The 3-question cap means real ambiguities will land in
  `Open questions` rather than being teased out. Update mode is the
  remediation path.
- **No mid-flow switch to /intent-aligner.** If during bootstrap the
  user realizes they want full Socratic elicitation, they have to
  abort, run `/intent-aligner` from a clean checkout, then return to
  `/seed-gatherer`. We don't try to hand off mid-flow.
- **WebFetch and Read limits apply** to bootstrap sources too — the
  ingest is best-effort. A truncated source produces a thinner
  intent, which lands in `Open questions` if anything was lost.
- **HTML renderer drift risk** — if intent-aligner's renderer evolves
  before seed-gatherer's copy is refreshed, bootstrap intents render
  with the older layout. The maintainer is responsible for keeping the
  pair synced.
