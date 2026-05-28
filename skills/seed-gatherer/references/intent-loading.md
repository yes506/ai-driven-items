# Loading intent.<slug>.md

Phase 1 reads `intent.<intent-slug>.md` from the repo root (i.e. the
`MAIN_CHECKOUT` working tree on `${BASE_BRANCH}`) and parses out the
fields the downstream extraction (Phase 3) needs to filter resources
against.

## Discovery rule

1. List `intent.*.md` files at the repo root:
   ```bash
   ls -1 "${MAIN_CHECKOUT}"/intent.*.md 2>/dev/null
   ```
2. Cases:
   - **Zero matches** → offer the **bootstrap path** OR abort. The
     bootstrap path captures intent ad-hoc within this seed-gatherer
     run; full spec: [intent-bootstrap.md](intent-bootstrap.md). The
     Phase 1 dialog is:
     ```
     No `intent.<slug>.md` found at <MAIN_CHECKOUT>. Choose:
       1) Bootstrap intent here — paste prompt / URL / file path
       2) Abort — run `/intent-aligner` first
     ```
     `bootstrap` / `1` → enter bootstrap path; `abort` / `2` → exit
     cleanly. Silence is not yes.
   - **One match** → auto-pick. Echo the slug and the goal line back to
     the user as confirmation; wait for `confirm intent` (or
     `revise` to abort and let user manually specify a slug). The user
     can also type `bootstrap` to ignore the existing intent and
     capture a new one ad-hoc — but this is rare; warn first
     (*"`intent.<existing>.md` is at the repo root. Bootstrap will
     create a sibling intent; the two will coexist. Continue?"*).
   - **Multiple matches** → list all slugs with their `Goal:` lines as a
     numbered menu. Prompt: *"Which intent should these seeds serve?
     Type the number, `bootstrap` for a new ad-hoc intent, or `abort`."*

The chosen slug becomes `INTENT_SLUG` in memory and persists to
`.seed-state.json` at Phase 4 as `intent_slug`. The choice path also
sets `RUN_MODE`: `standard` (existing intent loaded), `bootstrap` (new
intent captured ad-hoc), or `ideation` (no resources, dialogue-driven —
see [ideation-mode.md](ideation-mode.md); set when Phase 2 termination
chooses ideation, not at Phase 1).

## Field parsing

Parse the following 6 rubric sections from
`intent.<intent-slug>.md`. The intent-aligner format uses level-2
markdown headings (`## <Field>`) followed by content:

| Markdown heading | Parsed into `intent.<field>` | Expected shape |
|---|---|---|
| `## Goal` | `goal` | single sentence (paragraph text) |
| `## In-scope features` | `in_scope` | bullet list (`- <item>`) |
| `## Out-of-scope` | `out_of_scope` | bullet list |
| `## Constraints` | `constraints` | bullet list |
| `## Success criteria` | `success_criteria` | bullet list |
| `## Open questions` | `open_questions` | bullet list |

Other sections present in `intent.<slug>.md` (`## Mode`, `## Persona`,
`## Examples`, `## Counter-examples`, `## Root-cause`, `## Provenance`)
are NOT loaded into the state file — they're not needed for resource
filtering. Examples and counter-examples *are* useful as filter signal,
so the extraction step at Phase 3 should re-read the intent file
directly if it wants them. Keeping the state file's `intent` field
focused on the 6 core rubric items keeps the resume payload lean.

## Parsing strategy

The agent can read the file with the `Read` tool and parse in-line —
no script needed. A simple lexer:

1. Read the whole file into memory.
2. Split on `\n## ` to get section blocks. The first block (text before
   the first `## `) is the document title (`# Intent — <slug>`) and is
   discarded.
3. For each block, the first line is the heading, the rest is the body.
4. Heading lookup is case-sensitive and exact. If a heading is
   abbreviated or pluralized differently (e.g. `## Constraint` instead
   of `## Constraints`), treat it as missing and surface to the user.
5. Body parsing:
   - **Goal**: collapse all non-blank lines into a single string,
     strip surrounding whitespace.
   - **Bullet lists**: collect lines starting with `- ` (after
     stripping the prefix). Lines that don't start with `- ` and
     aren't blank are part of the *previous* bullet (multi-line
     bullet body); join them with a space.
   - Empty list → `[]` (not `null`).
   - Bullet of exactly `[unspecified]` → keep verbatim; it's the
     intent-aligner's marker for "user genuinely didn't have one."

## Defensive behavior

If parsing surfaces any of the following, **stop and ask the user
before proceeding** — do NOT silently fill in:

| Defect | What to ask |
|---|---|
| Required heading absent (e.g. no `## Goal`) | *"`intent.<slug>.md` is missing the `## <Field>` section. The intent capture may be incomplete — re-run `/intent-aligner` to finish it, or proceed with the field as `[unspecified]`?"* |
| Goal section is empty or only `[unspecified]` | *"The intent's `## Goal` is unspecified. Without a goal, the seed extraction can't filter resources by relevance. Re-run `/intent-aligner` to fill it, or proceed knowing the filter will be very loose?"* |
| File can't be read (permissions, IO error) | Surface the raw error; refuse to proceed. |
| File parses but has zero content across all 6 rubric fields | *"`intent.<slug>.md` looks empty — every rubric field is unspecified. Likely the intent-aligner run was abandoned. Re-run it before continuing."* Refuse to proceed. |
| `intent.<slug>.md` exists but the slug doesn't match `^[a-z0-9-]+$` | This shouldn't happen — intent-aligner sanitizes slugs. But if it does, refuse and ask the user to rename the file. |

Do NOT attempt to repair a malformed intent file from within this
skill. Repair is the intent-aligner's job — either re-running
`/intent-aligner` (create mode) for a wholesale fix or
`/intent-aligner update <slug>` for incremental refinement. Fixing
malformed intent inside seed-gatherer would create two skills both
claiming ownership of intent structure.

**Exception**: when the user opts into the **bootstrap path** at the
zero-match branch, seed-gatherer DOES author a fresh intent — but
that's a complete capture from scratch, not a repair of an existing
file. The two operations stay distinct.

## What "intent-filtered" means downstream

Once `intent` is loaded, the Phase 3 extraction step uses these fields
as the lens for filtering each resource:

- **Goal**: the north star. Content that doesn't speak to the goal is
  noise; drop it.
- **In-scope features**: positive filter — content describing these
  features stays.
- **Out-of-scope**: negative filter — content about excluded features
  is dropped, even if technically interesting.
- **Constraints**: content that informs or contradicts a constraint
  stays (especially contradictions — those become open questions).
- **Success criteria**: content that helps measure success stays.
- **Open questions**: content that helps answer one of these stays
  with high priority.

The extraction is a judgement call, not a regex. The relevance
rationale field in each seed is where the agent shows its work —
explicitly naming which rubric fields each chunk maps to.
