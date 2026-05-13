# Phase 0.5 — Triage & Readiness

Decide **how much planning** the request needs before any mutation. This
reference defines the scoring tuple, the lane mapping, and the
discovery-before-questions rule that fires every run.

## Scoring tuple

Compute three independent scores 0–3 from the user's request plus any
discovery already done. **Reasoning must be shown to the user** before
proceeding — never silently classify.

### scope_score — how much code the change touches

| Score | Heuristic |
|---|---|
| 0 | one existing file, one known function/method; no new file |
| 1 | ≤3 existing files in one module; no new interface, no new package |
| 2 | multi-module OR ≥1 new interface OR new package, but bounded |
| 3 | greenfield, near-greenfield, OR new subsystem spanning the repo |

### risk_score — how dangerous a wrong plan is

| Score | Heuristic |
|---|---|
| 0 | pure rename / comment / formatting change |
| 1 | local logic; tests + rollback both cheap |
| 2 | public API shape, data shape, or behavior visible to other modules |
| 3 | auth, payment, security, data migration, concurrency, or production cutover |

### ambiguity_score — how much the request leaves open

| Score | Heuristic |
|---|---|
| 0 | request fully specifies what + where + acceptance criteria |
| 1 | one open question that can be inferred from named files/tests |
| 2 | multiple gaps OR conflicting hints in the request |
| 3 | verbal one-liner with no anchored target ("make signup better") |

## Lane resolution rule

```
final_scale = max(scope_score, risk_score)

if ambiguity_score >= 2 AND final_scale <= 1:
    BLOCK → emit consolidated clarification question block (one round only)
    re-score with the user's answers; do NOT silently upgrade scale

scale_lane =
    "micro"   if final_scale == 0
    "local"   if final_scale == 1
    "feature" if final_scale == 2
    "system"  if final_scale == 3
```

**Why max(scope, risk) instead of average:** a one-line auth change has
`scope=0, risk=3` and must NOT receive the micro lane. Average would
collapse it to scope=1.5 → local; max preserves risk-driven escalation.

**Why block-on-ambiguity instead of upgrade:** if the user asked
vaguely for a function-sized change, silently inflating to feature/system
is exactly the over-engineering failure the scale-adaptive design exists
to prevent. Ask, don't assume.

## Discovery-before-questions rule

Before asking the user **any** clarification question, the planner MUST
perform the following local discovery, in this order, and surface what
each step revealed:

1. **Read repo guidance** — CLAUDE.md, AGENTS.md, README.md at repo root
   if present. These often state conventions that change the plan.
2. **Read every file the user named verbatim** — if the request says
   "the signup form's email validation," `Read` the signup form. Not
   optional.
3. **Grep call sites + tests** for any named function/method. Reveals
   blast radius before asking the user to estimate it.
4. **`git log -n 20 --oneline -- <path>`** — recent intent on the same
   code. Often answers "why does this exist this way?" without the user
   having to retype context.

Questions to the user are permitted only for facts that are
**(a) not derivable** from those four sources AND **(b) materially
change the plan**. If a question fails (b), don't ask it — note the
assumption you're making, run with it, and surface for confirmation in
the plan reflection.

## Question budget

| Lane | Question rounds | Rationale |
|---|---|---|
| micro | 0–1 (consolidated only if blocked by ambiguity) | one round is the cap; further questions belong in the next request |
| local | 0–1 | same |
| feature | 0–2 | allow a second focused round for cross-module concerns surfaced during decomposition |
| system | 0–2 | same |

A "consolidated round" means: one chat turn, bullet-listed questions,
each tagged with `(needed for: scope|risk|ambiguity)` so the user sees
*why* it's being asked.

## Tier downgrade discipline

The user may override the lane the planner picks. Two directions:

- **Upgrade** (e.g., micro → feature): accept without confirmation. Costs
  more planning effort but doesn't lose audit trail.
- **Downgrade** (e.g., system → local): require explicit
  `confirm downgrade` token. Skipping system-lane artifacts loses the
  human-confirmed merge marker and the rubric record — only valid when
  the user has a clear reason ("this is much smaller than your AI
  thought, just plan it").

Record both the AI's classification AND the user's final choice in
`.planner-state.json` under `scale` and `scale_overridden`.

## Worked examples

### Example A — micro

> "Add a null-check to `User.fromJson()` in `auth/user.dart`."

| Score | Value | Reasoning |
|---|---|---|
| scope | 0 | one file, one known method |
| risk | 1 | local logic, tests cheap |
| ambiguity | 0 | fully specified |

→ `final_scale = 1 → local`. Wait, max(0, 1) = 1. So this is local, not
micro. That's correct — touching auth-adjacent code earns one notch up
even with bounded scope.

### Example B — risk-escalated

> "Make `validate_password()` return a richer error message."

| Score | Value | Reasoning |
|---|---|---|
| scope | 0 | one method |
| risk | 3 | auth — leaking validation details has security impact |
| ambiguity | 1 | "richer" is fuzzy but inferable from the function |

→ `final_scale = max(0, 3) = 3 → system`. The risk score escalates a
trivially-scoped change to the strict lane. The discovery step should
read `validate_password()` first to confirm the security context before
proceeding; the user might then downgrade to feature if the function is
already non-sensitive (e.g. it validates a non-auth password field).

### Example C — ambiguity-blocked

> "Improve the signup flow."

| Score | Value | Reasoning |
|---|---|---|
| scope | ? | unbounded |
| risk | ? | unbounded |
| ambiguity | 3 | verbal one-liner, no anchored target |

→ Ambiguity ≥ 2 AND nothing constrains final_scale. **Block and ask.**
Don't silently classify as system (over-engineering); don't silently
classify as micro (will likely miss the actual ask). Re-score after the
user pins down scope.

### Example D — clean system

> "Stand up a new analytics service that ingests events from the API
> gateway and exposes a query endpoint."

| Score | Value | Reasoning |
|---|---|---|
| scope | 3 | new subsystem |
| risk | 2 | new service, but isolated; data layer is the risk |
| ambiguity | 1 | shape is clear; storage choice is the open question |

→ `final_scale = 3 → system`. Run the full current architect workflow
(worktree + interface skeletons + Mermaid DAG + HTML report + merge
marker).

## How this hooks into SKILL.md

Phase 0.5 in SKILL.md:

1. Run discovery steps 1–4 above (reads only, no mutation).
2. Compute tuple, derive lane.
3. Print to the user: `Classified as <lane> because scope=N risk=N ambiguity=N. Reasoning: ...`
4. If blocked, emit consolidated question block; re-score after answers.
5. If user wants to downgrade, require `confirm downgrade`.
6. Persist `scale`, `scope_score`, `risk_score`, `ambiguity_score`,
   `scale_overridden` to `.planner-state.json` (system/feature lanes
   only; micro/local don't create the file).
