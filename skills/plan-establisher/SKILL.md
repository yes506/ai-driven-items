---
name: plan-establisher
description: |
  Sits between `seed-gatherer` and the downstream planners
  (`codebase-planner` for code; `document-planner` for documents)
  in the chain. Reads `intent.<slug>.md` (required) and
  `seeds/seed.<intent-slug>.*.md` (optional), runs 4 verification
  dimensions (intent self-consistency, seeds-vs-intent,
  seeds-vs-seeds, planner-rubric completeness), resolves ambiguities
  via interactive Socratic dialog, then emits a folded planner-ready
  `plan.<intent-slug>.v<N>.md` + `plan.<intent-slug>.v<N>.html` at
  repo root. The downstream planner reads ONLY the plan; the intent
  and seeds become raw source material it doesn't touch directly.
  Iteratively re-runnable — each invocation emits the next version,
  prior versions preserved as audit trail. Manual invocation only —
  `/plan-establisher`.
disable-model-invocation: true
---

# Plan Establisher

## Overview

Take the intent (and any gathered seeds) and produce a single planner-
ready doc. The skill verifies the inputs across 4 dimensions, drives
ambiguity resolution through interactive Q&A, then folds the verified
material into a `plan.<intent-slug>.v<N>.md` that codebase-planner
reads as its only active input:

| Output | Audience | Purpose |
|---|---|---|
| `plan.<intent-slug>.v<N>.md` | AI (`codebase-planner` reads ONLY this) | Folded planner-ready doc — Goal, scope, constraints, success criteria, proposed scale lane + reasoning, evidence inventory, resolved ambiguities, remaining open questions |
| `plan.<intent-slug>.v<N>.html` | Human (browser-openable) | Self-contained verification doc, no CDN, HTML-escaped |

The skill is **iteratively re-runnable**: each invocation runs in its
own worktree+merge cycle, emits the next monotonic version, and
preserves prior versions (audit trail of how the plan evolved).
codebase-planner reads `max(N)`.

`disable-model-invocation: true` — the skill has side effects (writes
files, creates a git worktree, merges branches). Never auto-trigger.

## Workflow Decision Tree

```
Phase L: Dialog language (preamble) — see references/language-selection.md
Phase 0: Detect repo state ──┬─ on-dev ──────────────────── proceed
                             ├─ on-default-needs-dev ────── create-dev dialog
                             ├─ on-nonbase-main-checkout ── refuse, ask user to switch to dev
                             ├─ inside-plan-worktree ────── resume from .plan-state.json
                             ├─ inside-other-worktree ───── refuse, run from MAIN_CHECKOUT
                             └─ unrelated ────────────────── refuse, surface reason
Phase 1: Intent selection + seed loading + version pick (N = max(existing) + 1)
Phase 2: Verification — 4 dimensions → in-memory FINDINGS list
Phase 3: Iterative ambiguity resolution + synthesis + `confirm plan` gate
Phase 4: Worktree creation (FIRST mutation) — .worktrees/plan-<intent-slug>-<id>/
Phase 5: Emit plan.<intent-slug>.v<N>.{md,html} at repo root (race-guard re-scan) + commit
Phase 6: Human gate + merge (`confirm merge` → marker `(plan, human-confirmed)`)
```

## State variables

Captured during Phases L–4 and threaded through later phases:

- `LANGUAGE` — dialog language (`Korean` default | `English`); captured
  at Phase L per [references/language-selection.md](references/language-selection.md);
  held in memory through Phases 0–3, persisted at Phase 4.
- `MAIN_CHECKOUT` — absolute path to the parent main worktree.
- `BASE_BRANCH` — branch the plan worktree branches from (default `dev`).
- `INTENT_SLUG` — chosen at Phase 1.
- `INTENT` — parsed 6 rubric fields from `intent.<INTENT_SLUG>.md`.
- `SEEDS` — loaded from `seeds/seed.<INTENT_SLUG>.*.md` (may be `[]`).
- `N` — tentative plan version (`max(existing) + 1`), possibly bumped
  at Phase 5 race-guard.
- `PLAN_RUN_ID` — stable run handle; computed at end of Phase 1.
- `FINDINGS` — per Phase 2; resolutions added at Phase 3.
- `PROPOSED_SCALE_LANE` + `LANE_REASONING` + `EVIDENCE_INVENTORY` —
  computed at Phase 3 synthesis.

All persisted per [references/state-and-resume.md](references/state-and-resume.md).

---

## Phase L — Dialog language (preamble, runs before Phase 0)

Detect `LANGUAGE` from the invocation utterance (Korean default,
English fallback), echo + confirm with the user, capture. Persist to
`.plan-state.json` at Phase 4; hold in memory until then. Mid-flow
switches supported. Full rules — echo strings, override behavior, what
is / isn't translated (plan-markdown field NAMES stay English for the
codebase-planner parser; field VALUES follow `LANGUAGE`; merge marker
`(plan, human-confirmed)` stays English):
[references/language-selection.md](references/language-selection.md).

---

## Phase 0 — Repo state detection

Run the read-only inspector via the skill-directory variable (the
bundled script is **not** at the user's project root):

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/inspect_repo_state.sh"
```

Parse the JSON. The `state` field classifies into:

| State | Meaning | Action |
|---|---|---|
| `on-dev` | on `dev` branch in `MAIN_CHECKOUT` | proceed to Phase 1 |
| `on-default-needs-dev` | on `main`/`master`, no local `dev` | run the create-dev dialog from [references/git-worktree-flow.md](references/git-worktree-flow.md) |
| `on-nonbase-main-checkout` | on a non-`dev` non-default branch | refuse and ask user to switch to `dev` |
| `inside-plan-worktree` | cwd inside `*/.worktrees/plan-*` | resume from `.plan-state.json` if present, else refuse |
| `inside-other-worktree` | inside a non-plan linked worktree | refuse, instruct user to run from `MAIN_CHECKOUT` |
| `unrelated` | not in git / detached HEAD / zero commits | refuse, surface `reason` field |

Capture from JSON: `MAIN_CHECKOUT`, `default_branch`. Set
`BASE_BRANCH=dev` by default.

**Gate**: capture `MAIN_CHECKOUT` + `BASE_BRANCH` before Phase 1.

---

## Phase 1 — Intent selection + seed loading + version pick

**1a — Intent selection.** Discover `intent.*.md` files at repo root:

```bash
ls -1 "${MAIN_CHECKOUT}"/intent.*.md 2>/dev/null
```

| Match count | Action |
|---|---|
| 0 | refuse: *"No `intent.<slug>.md` found. Run `/intent-aligner` first."* exit cleanly |
| 1 | auto-pick; echo slug + goal line; wait for `confirm intent` |
| ≥2 | numbered menu; prompt: *"Which intent should this plan serve?"* |

Parse the chosen `intent.<INTENT_SLUG>.md` per
[references/intent-loading.md](references/intent-loading.md). Surface
parse defects (missing required section, empty Goal) and ask before
proceeding — do NOT silently fill in.

**1b — Seed loading.** Discover seeds for the chosen intent:

```bash
ls -1 "${MAIN_CHECKOUT}"/seeds/seed."${INTENT_SLUG}".*.md 2>/dev/null
```

| Match count | Action |
|---|---|
| 0 | warn: *"No seeds for intent `<slug>`. Planning will be intent-only (Dim 2 + Dim 3 verification skipped). Type `proceed` to continue, or `abort` to run `/seed-gatherer` first."* |
| ≥1 | echo count + slugs; load all (read-only — no gate) |

Load each seed per [references/seed-loading.md](references/seed-loading.md).
Skip malformed seeds with a warning; do NOT crash.

**1c — Version pick.** Scan for existing plans:

```bash
existing="$(ls -1 "${MAIN_CHECKOUT}"/plan."${INTENT_SLUG}".v*.md 2>/dev/null \
  | sed -nE 's|.*/plan\.[a-z0-9-]+\.v([0-9]+)\.md$|\1|p' \
  | sort -n | tail -1)"
N=$(( ${existing:-0} + 1 ))
```

`N = max(existing) + 1`, starts at 1. Held in memory through Phase 5
(where a race-guard re-scan may bump it). Full rules:
[references/plan-naming-and-versioning.md](references/plan-naming-and-versioning.md).

**1d — `PLAN_RUN_ID`**: compute
`PLAN_RUN_ID="$(date +%s | tail -c 6)-$$-${RANDOM}"` at the end of
this phase (stable across the run; reused as worktree/branch suffix
at Phase 4).

---

## Phase 2 — Verification (4 dimensions)

Run all four dimensions on `INTENT` + `SEEDS`, build in-memory
`FINDINGS` list per
[references/verification-dimensions.md](references/verification-dimensions.md).
No mutations.

Order: Dim 1 → Dim 2 → Dim 3 → Dim 4 (Dim 4 depends on Dim 1/3
findings counts for ambiguity signal).

| Dim | What it checks | Empty-SEEDS behavior |
|---|---|---|
| **1** Intent self-consistency | Constraint vs Success-criterion conflicts, Examples vs Out-of-scope, Open questions that block planning, empty critical fields, mutually exclusive bullets | Always runs |
| **2** Seeds vs intent | Each seed's rationale plausibility, contradictions with intent (out-of-scope conflicts), stale-source flags | Skipped if SEEDS == [] |
| **3** Seeds vs seeds | Pairwise factual / API contract / version / pricing conflicts; use seed `Source` for attribution | Skipped if len(SEEDS) < 2 |
| **4** Planner-rubric completeness | Scope / risk / ambiguity signals present? `[unspecified]` markers flagged | Always runs |

Each finding has `{dimension, severity, locus, description,
resolution_mode}`. `resolution_mode=auto` for dead-weight seeds and
duplicates; `needs-user` for everything else.

---

## Phase 3 — Iterative ambiguity resolution + synthesis

Full protocol — dialog template, candidate-resolution shaping per
dimension, `accept remaining` semantics, synthesis-preview format:
[references/ambiguity-resolution.md](references/ambiguity-resolution.md).

Summary:

1. **Auto-resolved summary** — one-line ack of dead-weight / duplicate
   seeds dropped or merged (these get logged in Resolved ambiguities
   without per-item dialog).
2. **Iterate `needs-user` findings** in order: Dim 1 → Dim 2 → Dim 3 →
   Dim 4; within each dimension, blocker → major → minor. For each:
   echo the finding + 1–3 candidate resolutions; record user's pick
   (or verbatim `(c) Other` text, confirmed by typing `confirm`).
3. **`accept remaining`** — user can short-circuit at any point;
   remaining findings become `mode=deferred`, will populate the
   plan's `Remaining open questions`.
4. **Compute `PROPOSED_SCALE_LANE` + `LANE_REASONING`** based on
   verified inputs (heuristics in
   [references/ambiguity-resolution.md#picking-the-proposed-scale-lane](references/ambiguity-resolution.md)).
   codebase-planner may override; we just propose with reasoning.
5. **Build `EVIDENCE_INVENTORY`** — map each plan rubric field path
   (`Goal`, `in_scope[0]`, ...) to the list of contributing seed
   slugs. Empty list = intent-only.
6. **Synthesis preview** — render all the plan.md fields in chat for
   the user to scan.
7. **Gate**: `confirm plan` to lock and proceed; `revise` to re-enter
   (user picks which aspect — a specific finding's resolution, a
   dimension re-run, or re-loading intent/seeds); anything else →
   re-ask. Silence is not yes.

No mutations in this phase. `verified_at` ISO-8601 recorded in memory
on `confirm plan`.

---

## Phase 4 — Worktree creation (first mutation)

Order matters — only after Phase 3 `confirm plan`. Full command
sequence, sanitization, and edge cases:
[references/git-worktree-flow.md](references/git-worktree-flow.md).
Summary:

```bash
# Step 0 — local exclude so .worktrees/ doesn't dirty status. CRITICAL:
# --git-common-dir returns a RELATIVE path on older git; use
# --path-format=absolute (git >= 2.31) with fallback.
COMMON_DIR="$(git -C "${MAIN_CHECKOUT}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null \
              || git -C "${MAIN_CHECKOUT}" rev-parse --git-common-dir)"
case "${COMMON_DIR}" in /*) ;; *) COMMON_DIR="${MAIN_CHECKOUT}/${COMMON_DIR}" ;; esac
grep -qxF '.worktrees/' "${COMMON_DIR}/info/exclude" \
  || echo '.worktrees/' >> "${COMMON_DIR}/info/exclude"

# Step 1 — INTENT_SLUG positive whitelist (defensive — intent-aligner
# already sanitizes to [a-z0-9-]+, but re-check in case it ever loosens)
case "${INTENT_SLUG}" in
  ""|*[!a-z0-9-]*|-*) echo "BLOCKER: intent slug failed [a-z0-9-]+ whitelist: '${INTENT_SLUG}'"; exit 1 ;;
esac

git -C "${MAIN_CHECKOUT}" worktree add \
  ".worktrees/plan-${INTENT_SLUG}-${PLAN_RUN_ID}" \
  -b "plan/${INTENT_SLUG}-${PLAN_RUN_ID}" "${BASE_BRANCH}"

# Step 2 — cd into the worktree
cd "${MAIN_CHECKOUT}/.worktrees/plan-${INTENT_SLUG}-${PLAN_RUN_ID}"

# Step 3 — committed gitignore so .worktrees/ + .plan-state.json
# stay hidden after the merge to ${BASE_BRANCH}
for entry in '.worktrees/' '.plan-state.json'; do
  grep -qxF "${entry}" .gitignore 2>/dev/null \
    || echo "${entry}" >> .gitignore
done

# Step 4 — initial commit on the plan branch. Guard with diff-cached
# because on re-invocation after a prior plan merge, `.worktrees/` and
# `.plan-state.json` are already in the committed `.gitignore`. Step 3
# correctly no-ops in that case, so `git add` stages nothing and a bare
# `git commit` would fail with "nothing to commit" and abort the run.
git add .gitignore
if ! git diff --cached --quiet; then
  git commit -m "chore(plan): initialize ${INTENT_SLUG} v${N} worktree"
fi
```

Then **write the initial `.plan-state.json`** at the worktree root
with `phase_completed: synthesis_confirmed` (Phase 3 already finished
in memory before Phase 4 began), plus `language`, `intent_slug`,
`plan_run_id`, `plan_version`, `intent` (possibly Dim-1-refined),
`seeds` (loaded at Phase 1; large bodies redacted to a path reference
per state-and-resume.md), `findings` (with resolutions),
`proposed_scale_lane`, `lane_reasoning`, `evidence_inventory`,
`main_checkout`, `base_branch`, `verified_at`. Schema:
[references/state-and-resume.md](references/state-and-resume.md).

Edge cases (path collision, dirty `BASE_BRANCH`, nested invocation,
untracked files on resume, merge conflicts at the gate) are
documented in [references/git-worktree-flow.md](references/git-worktree-flow.md).
Stop and ask the user — never auto-resolve.

---

## Phase 5 — Emit plan + commit

**Version-race guard FIRST**: re-scan `plan.<INTENT_SLUG>.v*.md` at
`MAIN_CHECKOUT`; if `max(existing) ≥ N`, bump `N` to
`max(existing) + 1` and notify the user in chat (mandatory — never
silent). Persist the new `plan_version` to the state file BEFORE
writing the files, so a crash mid-write leaves state pointing at the
actually-used N. Full algorithm + notification strings:
[references/plan-naming-and-versioning.md#at-phase-5-race-guard-re-scan](references/plan-naming-and-versioning.md).

Then (all **plan-file** writes happen at the **worktree root**, not
at `MAIN_CHECKOUT` — Phase 6's `git merge --no-ff` is what brings
the files to the repo root on `${BASE_BRANCH}` where
`codebase-planner` reads them; the `.plan-state.json` written by
Phase 4 / updated by Phase 5 also lives at the worktree root but
stays gitignored throughout):

1. **Write `plan.<INTENT_SLUG>.v<N>.md`** at the worktree root via
   `Write` per the schema in
   [references/output-schema.md](references/output-schema.md). Use a
   relative path `"plan.${INTENT_SLUG}.v${N}.md"` — the file becomes
   part of the worktree's working tree, gets committed at step 3,
   and Phase 6 merge brings it to `MAIN_CHECKOUT`. Field NAMES
   English; VALUES follow `LANGUAGE`.

2. **Render `.html`** at the worktree root:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/render_plan_html.py" \
     .plan-state.json > "plan.${INTENT_SLUG}.v${N}.html"
   ```

   Renderer is self-contained (no CDN, HTML-escapes all user content).
   Template at `${CLAUDE_SKILL_DIR}/assets/plan-html-template.html`.

3. **Commit** with single batch commit. The `diff --cached --quiet`
   guard handles resume — re-rendered identical artifacts stage
   nothing; the skip prevents a "nothing to commit" abort:

   ```bash
   git add "plan.${INTENT_SLUG}.v${N}.md" "plan.${INTENT_SLUG}.v${N}.html"
   if ! git diff --cached --quiet; then
     git commit -m "feat(plan): emit ${INTENT_SLUG} v${N}"
   fi
   ```

State file is gitignored (Phase 4 step 3) so it doesn't appear in the
commit. Finally set `phase_completed: artifacts_emitted` and persist
— a crash after this leaves the resume target as Phase 6.

---

## Phase 6 — Human gate + merge

The agent's cwd may be inside the worktree. Use `git -C
"${MAIN_CHECKOUT}"` so subsequent commands are cwd-independent.

Print:

1. Absolute paths to the **gate-time** artifacts inside the worktree
   — the user opens the HTML to verify *before* deciding whether to
   merge:
   `${MAIN_CHECKOUT}/.worktrees/plan-${INTENT_SLUG}-${PLAN_RUN_ID}/plan.${INTENT_SLUG}.v${N}.html`
   and the `.md` next to it. Note that *after* `confirm merge` the
   same files land at `${MAIN_CHECKOUT}/plan.${INTENT_SLUG}.v${N}.{md,html}`
   on `${BASE_BRANCH}` — that's the post-merge path codebase-planner
   reads from. Both paths point at the same content; the worktree
   path is what's verifiable *now*.

2. Next-step pointer:

   ```
   Next step: run `/codebase-planner` (for code) or `/document-planner`
   (for documents) when ready. It reads
   ${MAIN_CHECKOUT}/plan.${INTENT_SLUG}.v${N}.md (the latest version
   for this intent) as its only active input. The intent.md and seeds/
   become background source material the planner doesn't re-read by
   default. To revise: re-run `/plan-establisher` for a v${next} that
   supersedes this one.
   ```

3. The exact prompt:

```
Type `confirm merge` to merge plan/<intent-slug>-<id> into <BASE_BRANCH>
with marker (plan, human-confirmed),
or `keep` to leave the worktree intact for further iteration,
or `revise` to address something before merging.
```

Behavior per response:

- `confirm merge` → run the dirty-MAIN_CHECKOUT guard + `git checkout
  "${BASE_BRANCH}"` + `git merge --no-ff -m "feat(plan): merge
  ${INTENT_SLUG} v${N} (plan, human-confirmed)"` per the exact
  sequence in [references/git-worktree-flow.md#merge-command-sequence-phase-6](references/git-worktree-flow.md).
  After the merge, ask: *"Remove the worktree at
  `.worktrees/plan-${INTENT_SLUG}-${PLAN_RUN_ID}`?"* On yes: **first
  `cd "${MAIN_CHECKOUT}"`** (the agent's cwd may still be inside the
  worktree from Phase 4 step 2; removing it without `cd` out leaves
  the shell with a deleted cwd). Then `git -C "${MAIN_CHECKOUT}"
  worktree remove <path>` (no `--force`). On no: leave it.

- `keep` → leave worktree intact, no merge, exit cleanly.
- `revise` → leave worktree intact, ask the user **which** phase to
  re-enter (Phase 3 to revise resolutions, Phase 5 to re-render).
  Do not guess.
- Anything else → re-ask. Silence is not yes.

Update state: `phase_completed: human_confirmed`, record `merged_at`.

---

## Downstream contract

The merge commit message `feat(plan): merge <intent-slug> v<N> (plan,
human-confirmed)` makes the plan landing visible in `git log` — the
same pattern the rest of the chain uses. The marker is a social
contract, not cryptographic; the goal is catching accidental misuse
and making deliberate bypass visible in git history.

`codebase-planner` reads the **highest-N** `plan.<intent-slug>.v<N>.md`
for the chosen intent and treats it as the only active input. The
plan's `Proposed scale lane` is a hint; the planner may override but
must justify in its own plan.

The skill does NOT auto-launch any downstream skill. The user runs
`/codebase-planner` (code) or `/document-planner` (documents) — or
repeats `/plan-establisher` to emit a new version — explicitly when
ready.

---

## Forbidden actions

The skill must refuse to execute any of these even if the user
requests them mid-flow (politely surface the forbidden item and ask
for confirmation to deviate, but default to refusal):

- `git push`, `git push --force`
- `git merge` without the `--no-ff` flag for the plan branch
- `git merge` or `git commit` without the `-m` flag (would hang on
  `$EDITOR`)
- `git reset --hard`, `git clean -f`, `git worktree remove --force`
- `git commit --amend` once a commit has landed on the plan branch
  (create a new commit instead — amend rewrites history that
  `--no-ff` was meant to preserve)
- `--no-verify` on commits (pre-commit hooks must run)
- Treating user silence as confirmation at any gate (intent
  selection, `confirm plan`, `confirm merge`, "remove worktree?")
- Modifying `intent.<slug>.md` or any file under `seeds/` in any
  way other than reading — those are read-only inputs owned by
  upstream skills
- Emitting a plan with `Remaining open questions` that the user
  didn't explicitly defer via `(d) Defer` or `accept remaining`
  (silent skip is forbidden — every unresolved finding must be
  either resolved or explicitly accepted)
- Auto-launching `/codebase-planner` or any downstream skill from
  Phase 6 (the user runs the next-hop explicitly when ready)
- Inventing intent fields, seeds, or rubric content the inputs
  don't support (the plan is a *fold* of inputs, not an authoring
  step)
- Overwriting an existing `plan.<intent-slug>.v<N>.md` (versioning
  is monotonic; collisions auto-bump N at Phase 5 with chat
  notification — never silent overwrite)
- Skipping Phase 2 verification when seeds are absent (intent-only
  verification is lighter — only Dim 1 + Dim 4 apply — but still
  runs; "no verification" is forbidden)
- Auto-resolving slug collisions silently — the chat notification
  is mandatory per [references/plan-naming-and-versioning.md](references/plan-naming-and-versioning.md)
- Loading or persisting raw verbatim seed content beyond what's
  needed for verification — the state file's `seeds` field redacts
  large bodies to path-references (see state-and-resume.md). The
  plan.md's Evidence inventory cites seed slugs, not seed content.
- Creating `README.md`, `INSTALLATION_GUIDE.md`, or similar docs
  inside this skill folder

---

## Resumability

If re-invoked from inside an existing plan worktree
(`inside-plan-worktree`), read `.plan-state.json` and resume from the
next phase after `phase_completed`. See
[references/state-and-resume.md#resume-map](references/state-and-resume.md)
for the full mapping.

If `inside-plan-worktree` but no state file → refuse and ask the user
to either delete the worktree or supply a state file.

If the state file's `language` field is missing (defensive guard —
should never happen since Phase 4 always writes it): default
`LANGUAGE` to Korean (matching Phase L's default) and continue without
prompting.
