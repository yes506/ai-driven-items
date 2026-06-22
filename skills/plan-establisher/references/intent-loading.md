# Loading ai-artifacts/intents/intent.<slug>.md

Phase 1 reads `ai-artifacts/intents/intent.<intent-slug>.md` from the
`MAIN_CHECKOUT` working tree on `${BASE_BRANCH}` and parses out the
6 rubric fields the verification step (Phase 2) needs to evaluate.

## Discovery rule

1. List `ai-artifacts/intents/intent.*.md` files:
   ```bash
   ls -1 "${MAIN_CHECKOUT}"/ai-artifacts/intents/intent.*.md 2>/dev/null
   ```
2. Cases:
   - **Zero matches** → refuse with: *"No
     `ai-artifacts/intents/intent.<slug>.md` found at
     `${MAIN_CHECKOUT}`. Run `/intent-aligner` first to capture your
     intent."* Exit cleanly — do NOT proceed without an intent.
   - **One match** → auto-pick. Echo the slug and the goal line back to
     the user as confirmation; wait for `confirm intent` (or
     `revise` to abort and let user manually specify a slug).
   - **Multiple matches** → list all slugs with their `Goal:` lines as a
     numbered menu. Prompt: *"Which intent should this plan serve?
     Type the number, or `abort` to exit."*

The chosen slug becomes `INTENT_SLUG` in memory and persists to
`.plan-state.json` at Phase 4 as `intent_slug`.

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
are NOT loaded into the state file's `intent` field — they're not
needed for the planner-rubric verification. The verification step at
Phase 2 *may* re-read the intent file directly to use Examples /
Counter-examples as additional consistency signal (Dim 1), but the
state file's `intent` field stays focused on the 6 core rubric items
to keep the resume payload lean.

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
     intent-aligner's marker for "user genuinely didn't have one." The
     verification step (Dim 4) flags `[unspecified]` constraints /
     success criteria as planner-rubric gaps that need user resolution.

## Defensive behavior

If parsing surfaces any of the following, **stop and ask the user
before proceeding** — do NOT silently fill in:

| Defect | What to ask |
|---|---|
| Required heading absent (e.g. no `## Goal`) | *"`intent.<slug>.md` is missing the `## <Field>` section. The intent capture may be incomplete — re-run `/intent-aligner` to finish it, or proceed with the field as `[unspecified]` (will surface as a Dim-1 finding)?"* |
| Goal section is empty or only `[unspecified]` | *"The intent's `## Goal` is unspecified. Without a goal, the plan can't articulate what the planner is supposed to plan for. Re-run `/intent-aligner` to fill it, or accept the plan will be very thin?"* |
| File can't be read (permissions, IO error) | Surface the raw error; refuse to proceed. |
| File parses but has zero content across all 6 rubric fields | *"`intent.<slug>.md` looks empty — every rubric field is unspecified. Likely the intent-aligner run was abandoned. Re-run it before continuing."* Refuse to proceed. |
| `intent.<slug>.md` exists but the slug doesn't match `^[a-z0-9-]+$` | This shouldn't happen — intent-aligner sanitizes slugs. But if it does, refuse and ask the user to rename the file. |

Do NOT attempt to repair a malformed intent file from within this
skill. Repair is the intent-aligner's job (via its Phase 6 `revise`
path). Fixing it here would create two skills both claiming ownership
of intent structure.

## What the loaded intent is used for downstream

Phase 2 (verification) uses the loaded `intent` to:

- **Dim 1 (self-consistency)**: cross-check intent fields against each
  other — does any Constraint contradict a Success criterion? Do
  Examples (re-read from the file at need) demonstrate behavior the
  Out-of-scope excludes?
- **Dim 2 (seeds vs intent)**: lens for evaluating whether each seed
  actually maps to an intent rubric field, and detecting seeds that
  contradict the intent.
- **Dim 4 (planner-rubric completeness)**: check whether the loaded
  intent (combined with any seeds) gives the planner enough signal to
  pick a scale lane — flagged gaps become needs-user findings.

The synthesis at Phase 3 then *folds* the (possibly refined) intent
values into the plan.<intent-slug>.v<N>.md's Goal / In-scope /
Out-of-scope / Constraints / Success-criteria fields. The original
intent.md is never modified.
