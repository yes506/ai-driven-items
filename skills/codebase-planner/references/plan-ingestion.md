# Plan ingestion — auto-discovery (Phase 0.5) + multi-method input (Phase 1)

Plan ingestion runs across two phases. **Phase 0.5** (triage) scans for
plan-establisher output and, if found and confirmed, uses that as the
canonical plan + a `Proposed scale lane` prior for the lane decision.
**Phase 1** (feature & system lanes only) falls back to multi-method input
when no plan-establisher output was accepted at Phase 0.5. The user may
supply zero, one, or many of each Phase-1 method.

## Phase 0.5 — Plan-establisher auto-discovery (all lanes, preferred when available)

Before any other discovery or scoring, scan the plans directory for
plan-establisher output:

```bash
ls -1 "${MAIN_CHECKOUT}"/ai-artifacts/plans/plan.*.v*.md 2>/dev/null \
  | sed -nE 's|.*/plan\.([a-z0-9-]+)\.v([0-9]+)\.md$|\1 \2 &|p' \
  | sort -k1,1 -k2,2n | awk '{print $3}'
```

This lists every `plan.<intent-slug>.v<N>.md`, sorted so each slug's
versions group together with the highest-`N` last per slug. Group by
`<intent-slug>` and keep the highest `<N>` per group (per
plan-establisher's monotonic-versioning contract — see
`plan-establisher/references/plan-naming-and-versioning.md`). The
numeric secondary sort (`-k2,2n`) is essential — without it, `v10`
sorts before `v2` lexicographically.

Three cases:

| Match count | Action |
|---|---|
| 0 | No plan-establisher output. Continue Phase 0.5 discovery + scoring as usual; for feature/system lanes Phase 1 falls back to the manual methods below. (Chain-independence: this skill MUST still work when plan-establisher hasn't run.) |
| 1 intent slug | Auto-pick the highest-N. Echo `intent_slug + plan_version + Goal line`; wait for `confirm plan`. User can type `revise` to bypass auto-discovery — Phase 0.5 then proceeds without the plan, and Phase 1 (feature/system) prompts for manual input. |
| ≥2 intent slugs | Numbered menu listing each `(slug, highest-v<N>, Goal-line)`; prompt: *"Which plan should drive this planning run? Type a number to use it, type `manual` to bypass auto-discovery, or `abort`."* |

When an auto-discovered plan is accepted, the rubric **maps directly**
— plan-establisher's headings map to codebase-planner's rubric fields
with one rename (its `## In-scope` → this skill's `In-scope features`):

| plan-establisher heading | codebase-planner rubric field |
|---|---|
| `## Goal` | `Goal` |
| `## In-scope` | `In-scope features` |
| `## Out-of-scope` | `Out-of-scope` |
| `## Constraints` | `Constraints` |
| `## Success criteria` | `Success criteria` |
| `## Remaining open questions` | `Open questions` (folded verbatim) |

Three extras from plan-establisher carry useful signal but are not part
of the canonical rubric:

- **`## Proposed scale lane`** + **`### Lane reasoning`** — feeds
  directly into Phase 0.5 step 3's lane-resolution: the proposal is the
  default; if the `(scope, risk, ambiguity)` tuple disagrees,
  codebase-planner overrides but **must record the rationale**. The
  destination depends on the *resolved* lane (not the proposed lane):
  for **feature / system** lanes, write to the state file's
  `plan.lane_override_reason` field (declared in
  [state-and-resume.md](state-and-resume.md)); for **micro / local**
  lanes (which are stateless — no `.planner-state.json` is created),
  include the override rationale in the chat classification output and
  the lightweight-lane 3–7 bullet plan reflection (so it lands in chat
  history as the audit trail). When the planner accepts the proposed
  lane as-is, `lane_override_reason` stays null/absent (state) or is
  simply not mentioned (chat).
- **`## Evidence inventory`** + **`## Resolved ambiguities`** — both
  live in the source plan file (`plan.<slug>.v<N>.md` at the
  `plan.sources[*].ref` path) and are NOT duplicated into state. The
  state file records the source path; if Phase 2/3 or a downstream
  audit needs the evidence or the resolved ambiguities, re-read them
  from `plan.sources[*].ref` directly. (Avoiding the duplication keeps
  state lean and prevents drift between two sources of truth.) Resolved
  ambiguities are NOT surfaced as live questions during planning —
  they're already resolved per plan-establisher's `confirm plan` gate.

Record the source in `plan.sources[]` (matching the existing schema in
[state-and-resume.md](state-and-resume.md), with two optional fields
added for plan-establisher provenance):

```
{kind: "plan-establisher", ref: "<absolute-path>",
 fetched_at: "<ISO-8601>", intent_slug: "<slug>", plan_version: <N>}
```

For feature/system lanes, an accepted plan means Phase 1's manual
multi-method ingestion is skipped entirely. For micro/local lanes, the
verbal-only path below uses the accepted plan as the canonical input
instead of the chat request. (User-driven override via `revise` /
`manual` at the gate falls back to the chat request or the multi-method
methods, respectively.)

## Verbal-only path (micro & local lanes, when no plan was accepted)

For `micro` and `local` lanes WITHOUT an accepted plan-establisher
plan, the chat request **is** the canonical plan. Do NOT prompt for
file paths, URLs, or pasted text. Skip the multi-method ingestion
below and proceed directly to the 3–7 bullet plan reflection.

If a plan WAS accepted at Phase 0.5, use the plan as the canonical
input — but still do NOT prompt for additional manual input methods
in lightweight lanes (the plan already covers what would be there).

The verbal request (or accepted plan) is captured in chat history; no
`plan.sources[]` entry is recorded for the verbal case because
lightweight lanes don't create a state file. If an accepted plan
exists, its provenance is mentioned in chat for traceability but isn't
persisted (no state file for micro/local).

If the request is too vague to plan (ambiguity ≥ 2 per
[triage-and-readiness.md](triage-and-readiness.md)), Phase 0.5 will
have already blocked and asked one consolidated question round before
this point — so by the time the planner reaches Phase 1 with a
micro/local lane, the verbal request or accepted plan is sufficient
by construction.

For `feature` and `system` lanes WITHOUT an accepted plan, proceed
with the multi-method ingestion below.

## Accepted input methods (feature & system lanes, fallback when no plan accepted)

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
