# Planner handoff — feeding intent.<slug>.md into /codebase-planner

The intent-aligner deliberately does **not** auto-launch
`/codebase-planner` from Phase 6. The handoff is a manual step the
user takes when they're ready.

## Why manual

- The user may want to review `intent.<slug>.html` away from the terminal
  before continuing.
- The planner is its own side-effect skill with its own gates; chaining
  them silently would hide a decision point.
- A merged intent (with the `(intent, human-confirmed)` marker in
  `git log`) may be consumed by *several* planners over time — one
  per scale lane the user wants to plan against, for instance. There's
  no single "next planner" to auto-launch.

## What the planner ingests

`codebase-planner` Phase 1 accepts three input methods (per its
`references/plan-ingestion.md`):

1. File paths
2. URLs
3. Inline pasted text

`intent.<slug>.md` is shaped to be ingested via method 1 with zero
adaptation. The planner reads it, normalizes via its rubric, and
because intent-aligner's field names match the rubric 1:1 the
normalization is effectively a verbatim copy.

The planner's rubric extracts:

| Planner field | intent.<slug>.md field | Notes |
|---|---|---|
| Goal | Goal | One sentence, verbatim |
| In-scope features | In-scope features | Bullets, verbatim |
| Out-of-scope | Out-of-scope | Bullets, verbatim |
| Constraints | Constraints | Bullets, verbatim |
| Success criteria | Success criteria | Bullets, verbatim |
| Open questions | Open questions | Bullets, verbatim |

Intent-aligner's extras (Mode, Persona, Examples, Counter-examples,
Root-cause) are NOT in the planner's rubric. Be honest about what
happens to them — and how intent-aligner compensates:

- The planner reads `intent.<slug>.md` body verbatim into memory at
  Phase 0.5 discovery (named-file rule) AND at Phase 1 file
  ingestion (feature/system lanes only — see "Lane behavior" below).
- The planner's normalization pass extracts only the 6 rubric fields
  for its `confirm plan` synthesis block (see
  `codebase-planner/references/plan-ingestion.md:79-103`). The extras
  do NOT appear in the synthesis the user reviews at the planner gate.
- The body content still influences Phase 0.5 scope/risk/ambiguity
  scoring because the planner has the file in memory at that point,
  but the extras don't drive lane classification *as fields* — only
  as part of the read body.

So extras inform the planner's *understanding* but not its synthesis
output. The load-bearing extras are folded into planner-known fields
at intent-capture time so they survive normalization:

| Extra | Folded into | Where it's enforced |
|---|---|---|
| **Counter-examples** | `Out-of-scope` (with the "...because <reason>" intact per entry) | `references/feature-mode-questions.md` Pass 4 + `references/problem-mode-questions.md` Pass 7 + `references/output-schema.md` rules |
| **Root-cause** (problem mode) — *final step only* | `Constraints` as `Root cause: <X>` | `references/problem-mode-questions.md` Pass 4 + `references/output-schema.md` |
| **Persona** (when concrete) | `Goal` itself, via the "For <persona>, <outcome>" form | `references/output-schema.md` Goal rules + question-bank Pass 2 |

The remaining standalone sections (`Persona` as its own section,
`Examples`, full `Root-cause` chain) survive in the file body for the
HTML verification artifact and for the planner's Phase 0.5 discovery,
but the *load-bearing seed signal* lives in the 6 rubric fields by
design.

Intent-aligner deliberately doesn't try to do the planner's job
(scale + lane decisions, decomposition, package layout) — but it does
own the responsibility of shaping the 6 rubric fields so the planner
gets the full intent without re-discovering it.

## Recommended invocation — the universal block

After Phase 6 merges, the user runs a **single lane-agnostic block**
that combines the file path with a compact inline 6-field summary:

```
/codebase-planner   plan from ./intent.<slug>.md

Planner seed summary:
Goal: <one sentence — "For <persona>, <outcome>" form>
In-scope features:
- <bullets verbatim from intent.in_scope[]>
Out-of-scope:
- <bullets, each "<non-goal> (counter-example: <reason>)">
Constraints:
- <bullets, including "Root cause: <X>" if problem mode>
Success criteria:
- <bullets, including example-folded observable scenario>
Open questions:
- <bullets — or "(none)" if empty>
```

This single block works regardless of which lane the planner triages
into:

- **For feature/system lanes**: the planner ingests the file at
  Phase 1 (`plan-ingestion.md:25-77`) AND the inline paste as
  multi-source input. Since both sources match (they're rendered
  from the same INTENT), the rubric normalization yields the same
  6 fields — the inline paste is redundant-but-harmless.
- **For micro/local lanes**: the planner's verbal-only path
  (`plan-ingestion.md:7-19`) skips Phase 1 file ingestion, so the
  inline paste IS the canonical plan. Without it, the 3-7 bullet
  chat plan would be derived from a bare invocation. With it, the
  6-field intent flows through chat into the lightweight plan.

**The file path MUST be in the same message as the invocation.** Why:
the planner's Phase 0.5 triage runs *before* Phase 1, scoring
scope/risk/ambiguity. A bare invocation scores `ambiguity=3` (verbal
one-liner per `triage-and-readiness.md:38`) and blocks-and-asks
instead of ingesting the intent. Naming the path up-front triggers the
discovery-before-questions rule (`triage-and-readiness.md:73-75`:
"Read every file the user named verbatim... Not optional") which
reads the intent before scoring — so even on micro/local lanes the
lane choice is informed by the full intent content.

Tip: since intent-aligner merged into `BASE_BRANCH` (usually `dev`),
the intent file is at the repo root on `dev`. A relative path
(`./intent.<slug>.md`) works from there; an absolute path
(`${MAIN_CHECKOUT}/intent.<slug>.md`) works from any cwd.

## Lane behavior — what the planner does with the seed per scale

| Planner lane | File at Phase 1? | Inline summary at Phase 1? | Net result |
|---|---|---|---|
| **system** | yes (rubric-normalized) | yes (rubric-normalized, agrees with file) | full 6-field synthesis block at confirm-plan gate |
| **feature** | yes (rubric-normalized) | yes (rubric-normalized, agrees with file) | full 6-field synthesis block at confirm-plan gate |
| **local** | no (verbal-only path) | yes (inline IS the canonical plan) | 3-7 bullet plan derived from inline 6-field content |
| **micro** | no (verbal-only path) | yes (inline IS the canonical plan) | 3-7 bullet plan derived from inline 6-field content |

Source: `codebase-planner/references/plan-ingestion.md:7-19`
("Verbal-only path (micro & local lanes): the chat request is the
canonical plan").

So the universal block makes the seed fully self-sufficient across
all lanes. The `intent.<slug>.md` file is the audit-trail artifact
and the source of truth for the inline summary; the inline summary
is the lane-compatibility shim that lets micro/local lanes ingest
the same 6 fields through their verbal-only path.

## Phase 6 print

At Phase 6, the SKILL.md prints exactly the universal block above
(with `INTENT` field values interpolated), not a bare invocation. The
agent renders each field's bullets from the in-memory `INTENT` data.

That's the entire handoff. No magic, no chaining, no shared state
file between the two skills — the merged `intent.<slug>.md` plus the
universal invocation block are the contract.

## What if the user wants multiple plans from one intent

Encouraged. Each `/codebase-planner` invocation produces an
independent worktree (feature/system lanes) or a chat plan
(micro/local). The same `intent.<slug>.md` can seed across lanes,
but how the seed is consumed differs (see "Lane behavior" above):

- A `system` lane plan reads the file at Phase 1 and produces a
  rubric-normalized synthesis from the 6 fields
- A `feature` lane plan does the same
- A `micro` or `local` lane plan **does not ingest the file body
  into its plan synthesis** — the file informs Phase 0.5 lane
  scoring only. For those scales, the canonical plan IS the user's
  chat invocation. If the intent's load-bearing parts matter for
  the micro/local plan, paste them inline in the invocation
  message.

All four are valid downstream consumers. The `(intent, human-confirmed)`
marker in `git log` ties them all back to the same human-verified
intent.

## What if the intent needs to change

Re-run `/intent-aligner` from `dev` — it'll create a new intent
worktree under a new `<id>`. Behavior depends on whether the user
re-uses the same slug or picks a new one:

- **Same slug** — the new `intent.<slug>.md` overwrites the old one
  at the repo root on merge. The old version stays in `git log` for
  audit; the new one is what the planner sees from `HEAD` going
  forward.
- **Different slug** — both intents coexist at the repo root as
  `intent.<slug-A>.md` and `intent.<slug-B>.md` (no collision, since
  the filenames are slug-scoped). The user picks which one to hand to
  the planner per invocation.

If the user wants to *amend* (not replace) an existing intent, that's
not supported in this version — re-run from scratch is the recipe.
The Phase 2 elicitation is fast enough that the cost is reasonable,
and it forces a clean re-verification rather than smuggling drift
into a "small amendment".

## What this handoff does NOT do

- It does NOT validate that the planner ran. Once intent-aligner
  merges, the user is on their own to run the planner (or not).
- It does NOT enforce a one-intent-per-plan rule. Multiple plans
  from one intent is supported and explicit (above).
- It does NOT auto-update `intent.<slug>.md` if the planner discovers
  conflicts. Conflicts surface as the planner's Open Questions; the
  user resolves them either in the plan or by re-running
  `/intent-aligner` for a fresh intent.
