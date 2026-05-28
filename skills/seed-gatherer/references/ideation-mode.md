# Ideation mode — seeds from dialogue + feasibility checks (no external resources)

Phase 2's resource intake loop normally collects URLs / PDFs / images
/ local files. When the user has **no external material** to provide
but still wants to grow seeds, ideation mode lets them ideate with the
agent through back-and-forth dialogue. Each idea that survives
crystallization becomes its own seed file with a feasibility-check
summary attached.

| Trigger | Path |
|---|---|
| Phase 2 user types `done` with **zero** resources accumulated | Skill offers ideation; user accepts → enter ideation mode |
| Phase 2 user types `ideate` (or `ideation`) at any point | Skill optionally enters ideation mode mid-intake |
| Phase 2 has resources AND user wants extra ideated seeds | Same — ideation appends ideated seeds alongside resource-derived ones |

Ideation is **not bootstrap**. Bootstrap captures intent; ideation
produces seeds. They can coexist (Phase 1 bootstrap → Phase 2 ideation
gives a fresh intent + ideated seeds in a single run), or run
independently.

## Phase 2 termination dialog (zero-resource case)

When the user types `done` with `RESOURCES` empty (per SKILL.md Phase 2),
instead of the standard *"No resources gathered — exit without doing
anything?"*, ask:

```
No external resources gathered. You have two options:
  1) Enter ideation mode — let's crystallize ideas through dialogue,
     with feasibility checks. Each accepted idea becomes a seed.
  2) Exit without doing anything.
Type `1` (or `ideate`) or `2` (or `exit`). Silence is not yes.
```

`ideate` / `1` → set `RUN_MODE` to `ideation` (or `bootstrap, ideation`
if the run started from bootstrap), enter Phase 2i. `exit` / `2` →
exit cleanly. Silence is not yes.

## Phase 2i — Ideation dialogue loop

The agent drives a back-and-forth ("tiki-taka") with the user. Each
round has the shape:

1. **Agent proposes or invites.** Either:
   - Open-ended: *"Given your goal `<goal>`, what's the first
     concrete idea you'd want to test?"* (when round 1 and user is
     leading)
   - Suggest-and-probe: *"One direction I see from `<goal>` +
     `<constraint X>`: <idea sketch>. Does that fit, or are you
     thinking of something different?"* (when agent is helping shape)
2. **User responds.** A new idea, a refinement, a rejection, or
   another direction.
3. **Agent feasibility-checks the idea.** Before crystallizing into a
   seed, the agent runs **one or more** of these checks (the choice
   is judgment — match the idea's nature):

   | Check | Tool | When to use |
   |---|---|---|
   | Prior art search | `WebSearch` | The idea involves a well-known pattern, library, or technique — check for known pitfalls, alternatives, current consensus |
   | Reference doc lookup | `WebFetch` | A specific authoritative source could confirm/refute (e.g., the framework's docs for a feature the idea relies on) |
   | Local code reconnaissance | `Bash` (grep/find) + `Read` | The idea touches an existing local codebase — does the pattern already exist? are the integration points feasible? |
   | Local file reference | `Read` | The idea references a local document that the user mentioned |
   | Estimation reasoning | (no tool — agent reasoning) | The idea is abstract; agent reasons through complexity, scale, dependencies |

   The feasibility check is **not** trying to prove the idea correct;
   it's surfacing what we know AND what we don't. Cap checks at
   ~2 tool calls per idea to keep latency reasonable. If a check
   surfaces a fatal flaw, name it explicitly — the user decides
   whether to drop the idea or refine it.

4. **Agent surfaces the feasibility summary.** Format:
   ```
   Idea: <one-sentence description>
   Feasibility check:
     - Tool: WebSearch — searched "<query>"
       Finding: <summary; quote or paraphrase as appropriate>
     - Tool: Bash grep — checked "<pattern>" in <path>
       Finding: <summary>
     Verdict: <feasible / contested / needs more digging>
   ```
5. **Crystallization prompt.** Ask:
   ```
   Accept this idea as a seed? (`yes` / `revise <description>` /
   `drop` / `keep ideating` to continue the dialogue without
   crystallizing yet)
   ```
6. **On `yes`**: derive an `idea_slug` (short ASCII keyword from the
   idea's description per [seed-naming.md](seed-naming.md));
   append to `RESOURCES[]`:
   ```json
   {
     "type": "ideation",
     "location": "ideation:<idea_slug>",
     "resource_slug": "idea-<idea_slug>",
     "status": "extracted",
     "extracted_at": "<iso>",
     "extracted_content": "<refined idea description, intent-filtered>",
     "relevance_rationale": "<paragraph linking to intent fields>",
     "feasibility_check": "<the feasibility summary from step 4>"
   }
   ```

Iterate until the user types `done` (or `exit`). If `RESOURCES` is
still empty after the user types `done` → exit cleanly with *"No ideas
crystallized — exiting without emitting any seeds."*

## Convergence + cap

| Rule | Reason |
|---|---|
| Max **5 ideas per ideation run** (soft cap; the agent gently surfaces *"we've crystallized 5 ideas — keep going or wrap up?"* at 5) | Prevents runaway sessions; each seed has cost |
| Max **2 feasibility tool calls per idea** | Tool-call latency dominates the dialogue cadence |
| Min **1 feasibility check per idea** (even if just `Estimation reasoning`) | The "feasibility-checked" promise is the seed's value; skipping it produces low-quality seeds |
| Each crystallized idea MUST link to ≥1 intent rubric field in its rationale | Ideation seeds are still intent-filtered; an idea unrelated to the intent isn't a useful seed |

## Phase 3 (ideation variant)

Phase 3's standard pre-fetch gate doesn't apply to `ideation` resources
(no fetch). The ideation resources arrive at Phase 3 with their
extracted content already populated (the dialogue + feasibility check
happened during Phase 2i). Phase 3 still renders each ideation
resource in the per-resource preview block and asks for `confirm seeds`
the same way:

```
Resource <N of M> — ideation
Idea: <description>
Resource slug: idea-<idea_slug>

Feasibility check:
  <the feasibility summary>

Extracted content (intent-filtered):
  <refined idea description>

Relevance rationale:
  <paragraph linking to intent fields>

Type `next` to preview the next resource, `redo <n>` to re-feasibility-
check resource N, `drop <n>` to remove, or `confirm seeds` to lock all.
```

`redo <n>` for an `ideation` resource re-runs the feasibility check
(not the dialogue — the dialogue produced the idea description and
that's locked once crystallized). To replace the idea itself, drop it
and re-enter Phase 2i.

## Phase 5 (ideation variant)

Each ideation resource emits a seed pair with the additional
`## Feasibility check` section in the markdown (between
`## Extracted content (intent-filtered)` and `## Relevance rationale`).
The HTML renderer (`render_seed_html.py`) renders the feasibility
section as a tinted panel similar to the rationale panel. See
[output-schema.md](output-schema.md) for the section ordering and the
HTML renderer's handling.

## Phase 6 (ideation variant)

The merge marker is **distinct** from the standard `(seeds,
human-confirmed)`:

| Upstream mode | Phase 2 termination | Merge marker |
|---|---|---|
| `standard` (existing intent) | resources only | `(seeds, human-confirmed)` |
| `standard` | ideation only OR mixed | `(seeds, ideation, human-confirmed)` |
| `bootstrap` | resources only | `(intent+seeds, bootstrap, human-confirmed)` |
| `bootstrap` | ideation only OR mixed | `(intent+seeds, bootstrap, ideation, human-confirmed)` |

The audit-trail layering — `bootstrap` first (intent origin), then
`ideation` (seed origin) — is grepable in `git log` for chain reviewers.
**Mixed batches** (some resources + some ideated seeds) share the
ideation marker; the resource/ideation split is recorded in the
per-seed `Resource type` field, not in the merge subject. Source of
truth for marker strings: [git-worktree-flow.md](git-worktree-flow.md).

## Forbidden actions (ideation-specific)

In addition to seed-gatherer's standard forbidden actions:

- **Crystallizing an idea without a feasibility check.** The
  feasibility-checked promise is what makes ideation seeds different
  from "just a brainstorm." If a tool-based check isn't appropriate,
  use reasoned estimation, but record SOMETHING under
  `feasibility_check`.
- **Running >2 feasibility tool calls per idea.** Latency budget.
- **Looping on the same idea indefinitely.** If the user keeps
  revising without converging after 3 rounds, surface the loop and
  ask whether to drop it or accept a refined version.
- **Treating ideation as a substitute for intent capture.** If the
  user's intent is genuinely unknown (Phase 1 bootstrap surfaced
  too many `[unspecified]` fields and the user didn't fill them),
  redirect to `/intent-aligner` rather than ideating on a vague
  goal. Ideation operates *within* an established intent.
- **Persisting failed-feasibility ideas as seeds.** If the agent's
  feasibility check turns up a fatal flaw and the user accepts
  anyway, mark the seed with a prominent warning in
  `feasibility_check` (*"FLAG: <reason> — user accepted regardless"*);
  do NOT bury the finding.
- **Auto-suggesting ideas without user prompt at round 1.** Open
  with a question, not a pre-canned idea — the user's first
  framing is signal.

## Honest limitations

- **Ideation quality scales with intent specificity.** A
  bootstrapped thin intent + ideation produces thinner seeds than a
  thoroughly-elicited intent + ideation. The pre-condition for good
  ideation is a usable intent.
- **Feasibility checks are not proof.** They surface known risks +
  prior art; they don't substitute for prototyping. Plan-establisher
  and codebase-planner downstream may reverse a "feasible" verdict
  once architecture is concrete.
- **No multi-turn within feasibility.** Each feasibility check is a
  single round of tool calls + summary; the agent doesn't iterate
  "let me check one more thing." That keeps latency bounded; if a
  check needs deeper digging the user can `redo <n>` at Phase 3.
- **Mixed resources + ideation runs accumulate context fast.** Cap
  yourself: 4-5 ideated seeds is a comfortable session size; more
  than that and quality degrades.
