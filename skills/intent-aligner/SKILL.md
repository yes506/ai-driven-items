---
name: intent-aligner
description: |
  Extract what's actually in the user's head and make it concrete before any
  planning starts. Runs an interactive elicitation dialog (Socratic loops +
  5 Whys + example/counter-example disambiguation), auto-detects whether the
  user brings a feature/product idea or a problem/pain, and emits a dual-
  format artifact: `intent.<slug>.md` (structured AI-parseable seed) and
  `intent.<slug>.html` (static, self-contained, human-verifiable).
  Slug-scoped filenames let multiple intents coexist at the repo root
  after merge. Bidirectional with `seed-gatherer`: the initial intent is
  not immutable — `/intent-aligner update <slug>` refines an existing
  intent from accumulated seeds, bumping its revision until the intent
  is solid enough to plan against. Chain: intent-aligner ⇄ seed-gatherer
  → plan-establisher → codebase-planner → codebase-implementer. Manual
  invocation only — `/intent-aligner` (create) or `/intent-aligner
  update <slug>` (refine).
disable-model-invocation: true
---

# Intent Aligner

## Overview

Surface what the user *means* before anyone plans how to build it. The skill
runs an interactive dialog tuned to the **mode** the user shows up in
(feature-shape vs. problem-shape), uses Socratic loops, 5 Whys, and
example/counter-example to converge on a faithful representation of intent,
then emits two artifacts:

| Output | Audience | Purpose |
|---|---|---|
| `intent.<slug>.md` | AI (next-hop is `seed-gatherer`, then `plan-establisher`) | Structured seed listing the user's goal, scope, constraints, and reasoning |
| `intent.<slug>.html` | Human | Static, self-contained, print-friendly verification doc — the user reads it and confirms "yes, that's what I meant" |

Artifact names are **slug-scoped** so multiple intents can coexist at
the repo root after merge — running `/intent-aligner` for two different
projects produces `intent.foo.md` and `intent.bar.md` without
overwriting each other.

The skill sits at the head of the chain and is **bidirectional** with
`seed-gatherer`:

```
[/intent-aligner] ⇄ /seed-gatherer → /plan-establisher → /codebase-planner → /codebase-implementer
       ▲                  │
       └── update mode ───┘  (refine intent from accumulated seeds)
```

Two invocations:

| Invocation | `RUN_MODE` | Result |
|---|---|---|
| `/intent-aligner` | `create` | New `intent.<slug>.md` at revision 1 |
| `/intent-aligner update <slug>` | `update` | Refines existing intent from seeds; revision bumps by 1. Full spec: [references/update-mode.md](references/update-mode.md) |

`seed-gatherer` (optional) also has a **bootstrap path** that creates
the initial `intent.<slug>.md` when none exists. Either origin yields
the same artifact format; update mode reads provenance to detect
bootstrap intents. Intent-aligner is stack-, planner-, and lane-agnostic.

`disable-model-invocation: true` — the skill has side effects (writes
files, creates a git worktree, merges branches). Never auto-trigger.

## Workflow Decision Tree

```
Phase L: Dialog language (preamble) — references/language-selection.md
Phase 0: Arg-parse (RUN_MODE=update if `update <slug>`, else `create`)
         + Repo state detection — full table in Phase 0 section below
Phase 1: Mode detection (feature-shape vs problem-shape) — echo + confirm
Phase 2: Elicitation loop (Socratic + 5 Whys + example/counter-example)
Phase 3: Synthesis + `confirm intent` gate (no mutations yet)
Phase 4: Worktree creation (FIRST mutation) — .worktrees/intent-<slug>-<id>/
Phase 5: Emit intent.<slug>.md + intent.<slug>.html + commit
Phase 6: Human gate + merge (marker `(intent, human-confirmed)`)
```

Update flow (`/intent-aligner update <slug>`) — Phases 1u-6u: load existing
intent + glob seeds; per-field refinement; worktree at `intent-update-<slug>-<id>/`;
revision bump; marker `(intent, updated-from-seeds, human-confirmed)`.
Full spec: [references/update-mode.md](references/update-mode.md).

State variables captured during Phases L–4 and threaded through later phases:

- `LANGUAGE` — dialog language (`Korean` default | `English`); captured at
  Phase L per [references/language-selection.md](references/language-selection.md);
  held in memory through Phases 0–3, persisted at Phase 4.
- `MAIN_CHECKOUT` — absolute path to the parent main worktree.
- `BASE_BRANCH` — branch the intent worktree branches from (default `dev`).
- `INTENT_ID` — stable run handle; computed at Phase 1, reused as
  worktree/branch suffix in Phase 4.
- `PROJECT_SLUG` — short ASCII identifier captured from the user at
  Phase 3 synthesis (sanitized at Phase 4 before use).
- `MODE` — `feature` | `problem` — chosen in Phase 1.
- `INTENT` — the in-memory normalized representation (Goal,
  In-scope features, Out-of-scope, Constraints, Success criteria,
  Open questions, plus mode-specific extras); persisted to
  `.intent-state.json` at Phase 4.
- `RUN_MODE` — `create` or `update`; set in Phase 0 from invocation arg.
  Update-mode adds `BASE_REVISION`, `TARGET_REVISION`, `BASE_INTENT_ID`,
  `REFINING_SEED_SLUGS` — [references/update-mode.md](references/update-mode.md).

All persisted per
[references/state-and-resume.md](references/state-and-resume.md).

---

## Phase L — Dialog language (preamble, runs before Phase 0)

Detect `LANGUAGE` from the invocation utterance (Korean default, English
fallback), echo + confirm with the user, capture. Persist to
`.intent-state.json` at Phase 4; hold in memory until then. Mid-flow
switches supported. Full rules — echo strings, override behavior, what
is/isn't translated (notably: the intent-markdown field NAMES stay English so the
planner's parser reads them; field VALUES follow `LANGUAGE`; merge marker
`(intent, human-confirmed)` stays English):
[references/language-selection.md](references/language-selection.md).

---

## Phase 0 — Arg-parse + repo state detection

**Arg-parse**: `/intent-aligner` ⇒ `RUN_MODE=create`. `/intent-aligner
update <slug>` or `--update <slug>` ⇒ `RUN_MODE=update` (verify
`intent.<slug>.md` exists after repo-state check; if not, refuse with
list of existing intents). Bare `update` with no slug ⇒ refuse. Update-
mode specifics: [references/update-mode.md](references/update-mode.md).

Then run the read-only inspector:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/inspect_repo_state.sh"
```

Parse the JSON. The `state` field classifies into:

| State | Meaning | Action |
|---|---|---|
| `on-dev` | on `dev` branch in `MAIN_CHECKOUT` | proceed (Phase 1 / 1u) |
| `on-default-needs-dev` | on `main`/`master`, no local `dev` | run create-dev dialog — [references/git-worktree-flow.md](references/git-worktree-flow.md) |
| `on-nonbase-main-checkout` | non-`dev` non-default branch in main checkout | refuse, ask user to switch to `dev` |
| `inside-intent-worktree` | cwd inside `*/.worktrees/intent-*` (covers create AND update worktrees) | resume per `.intent-state.json`, honor `run_mode`. Refuse if state missing or `run_mode` mismatches the invocation arg. |
| `inside-other-worktree` | inside non-intent linked worktree | refuse, run from `MAIN_CHECKOUT` |
| `unrelated` | not in a git repo / detached HEAD / no commits | refuse, surface `reason` field |

Capture from JSON: `MAIN_CHECKOUT`, `default_branch`. Default
`BASE_BRANCH=dev`. Stack-agnostic.

**Gate**: capture `RUN_MODE` + `MAIN_CHECKOUT` + `BASE_BRANCH` before
Phase 1 / 1u. In update mode, also verify `intent.<slug>.md` exists at
`MAIN_CHECKOUT` and parse `BASE_REVISION` from its Provenance (default `1`).

---

## Phase 1 — Mode detection

Classify the user's input shape to pick the right elicitation question
bank. Two modes:

| Mode | Signal | Question bank |
|---|---|---|
| `feature` | User brings a thing they want to build (a feature, app, system, screen, endpoint). Nouns dominate. "I want a dashboard that shows X." | [references/feature-mode-questions.md](references/feature-mode-questions.md) |
| `problem` | User brings a pain or frustration with no fixed solution yet. Verbs of suffering dominate. "I'm tired of X / can't do Y / Z is slow." | [references/problem-mode-questions.md](references/problem-mode-questions.md) |

Full signal table, classification rules, and ambiguity-resolution dialog:
[references/mode-detection.md](references/mode-detection.md).

Echo the classification + one-line reason to the user. Wait for `confirm
mode` (or a re-classification request). Silence is not yes.

Compute `INTENT_ID="$(date +%s | tail -c 6)-$$-${RANDOM}"` at the end of
this phase (stable for the rest of the run, reused in worktree path/branch
at Phase 4).

---

## Phase 2 — Elicitation loop

Iterate the question passes from the mode-specific question bank
([feature-mode-questions.md](references/feature-mode-questions.md) or
[problem-mode-questions.md](references/problem-mode-questions.md)),
mixing the three techniques per
[references/elicitation-techniques.md](references/elicitation-techniques.md):

- **Socratic question loops** — open-ended, surface assumptions, never
  yes/no.
- **5 Whys / root-cause drilling** — when the user states a *what*, drill
  to *why*. Especially load-bearing in `problem` mode.
- **Example & counter-example** — ask for one concrete happy path AND for
  things that should explicitly NOT happen. Strongest disambiguator;
  always include at least one round.

Run the passes in the order the question bank specifies. After each pass,
echo a short reflection ("here's what I'm hearing: …") and ask for
correction before moving on. Do NOT batch all questions up front — the
user's earlier answers shape later questions.

**Convergence rule**: stop iterating when (a) the user has confirmed each
pass's reflection without further correction, AND (b) you have at least
one concrete example and one counter-example. If after three full passes
the intent is still ambiguous, stop and surface the residual ambiguity as
`Open questions` rather than guessing.

Hold the accumulating `INTENT` representation in memory; nothing on disk
yet.

---

## Phase 3 — Synthesis + confirm intent

Render the in-memory `INTENT` as a single fenced block in chat covering
all fields from [references/output-schema.md](references/output-schema.md):

```
INTENT — synthesis
==================
Mode: <feature | problem>
Project slug (proposed): <short-ascii-slug>

Goal: For <persona-short>, <outcome / relief>. (one sentence,
      persona-prefix form — answers "what is this for whom?" in one
      read. See references/output-schema.md)

User persona: <who, what they do — single sentence>

In-scope features:
  - ...

Out-of-scope:
  - ...

Constraints:
  - ...

Success criteria:
  - ...

Concrete examples (happy paths):
  - ...

Counter-examples (must NOT happen, with the reason):
  - ...

Root-cause (problem mode only — full chain):
  - ...

Open questions:
  - ...
```

Ask the user for a `PROJECT_SLUG` if not yet supplied (short ASCII
identifier; sanitization happens at Phase 4 before use). Then prompt:

```
Type `confirm intent` to lock this synthesis and emit intent.<slug>.md + intent.<slug>.html,
or `revise` to iterate further.
```

- `confirm intent` → record `verified_at` (ISO-8601 local time) in memory,
  proceed to Phase 4. Silence is not yes.
- `revise` → return to Phase 2 with the user's specific corrections.
- Anything else → re-ask.

---

## Phase 4 — Worktree creation (first mutation)

Order matters — only after Phase 3 `confirm intent`. Full command sequence,
sanitization, and edge cases:
[references/git-worktree-flow.md](references/git-worktree-flow.md).
Summary:

```bash
# Step 0 — local exclude so .worktrees/ doesn't dirty status.
COMMON_DIR="$(git -C "${MAIN_CHECKOUT}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null \
              || git -C "${MAIN_CHECKOUT}" rev-parse --git-common-dir)"
case "${COMMON_DIR}" in /*) ;; *) COMMON_DIR="${MAIN_CHECKOUT}/${COMMON_DIR}" ;; esac
grep -qxF '.worktrees/' "${COMMON_DIR}/info/exclude" \
  || echo '.worktrees/' >> "${COMMON_DIR}/info/exclude"

# Step 1 — sanitize PROJECT_SLUG, branch + add worktree.
# (Create mode: intent-<slug>-<id>; update mode: intent-update-<slug>-<id> —
# the rest of the snippet uses ${WORKTREE_PREFIX} for the variant.)
PROJECT_SLUG="$(printf '%s' "${raw_slug}" | tr 'A-Z' 'a-z' | tr -cd 'a-z0-9-' \
  | sed -e 's/^-*//' -e 's/-\{2,\}/-/g' -e 's/-*$//' | cut -c1-40)"
[ -z "${PROJECT_SLUG}" ] && { echo "empty slug after sanitization"; exit 1; }
WORKTREE_PREFIX="intent"; [ "${RUN_MODE}" = "update" ] && WORKTREE_PREFIX="intent-update"
BRANCH_PREFIX="intent";   [ "${RUN_MODE}" = "update" ] && BRANCH_PREFIX="intent/update"
git -C "${MAIN_CHECKOUT}" worktree add \
  ".worktrees/${WORKTREE_PREFIX}-${PROJECT_SLUG}-${INTENT_ID}" \
  -b "${BRANCH_PREFIX}/${PROJECT_SLUG}-${INTENT_ID}" "${BASE_BRANCH}"

# Step 2 — cd into the new worktree.
cd "${MAIN_CHECKOUT}/.worktrees/${WORKTREE_PREFIX}-${PROJECT_SLUG}-${INTENT_ID}"

# Step 3 — committed gitignore so worktree state stays hidden post-merge.
for entry in '.worktrees/' '.intent-state.json'; do
  grep -qxF "${entry}" .gitignore 2>/dev/null || echo "${entry}" >> .gitignore
done

# Step 4 — initial commit on the intent branch (explicit -m to avoid $EDITOR).
git add .gitignore
git commit -m "chore(intent): initialize ${PROJECT_SLUG} ${RUN_MODE} worktree"
```

Then **write the initial `.intent-state.json`** at the worktree root with
`phase_completed: worktree_created`, plus `language`, `mode`, `intent`,
`project_slug`, `main_checkout`, `base_branch`, `intent_id`,
`verified_at`. This is what makes resume work if the skill crashes between
Phase 4 and Phase 5's artifact emission. Schema:
[references/state-and-resume.md](references/state-and-resume.md).

Edge cases (path collision, dirty `BASE_BRANCH`, nested invocation,
untracked files on resume, merge conflicts at the gate) are documented in
[references/git-worktree-flow.md](references/git-worktree-flow.md). Stop
and ask the user — never auto-resolve.

---

## Phase 5 — Emit intent.<slug>.md + intent.<slug>.html + commit

Render both artifacts at the worktree root. Filenames are
**slug-scoped** (`intent.${PROJECT_SLUG}.md` and
`intent.${PROJECT_SLUG}.html`) so multiple intents can coexist at the
repo root after merge without overwriting each other.

1. **`intent.${PROJECT_SLUG}.md`** — the AI-parseable seed. Structure
   per [references/output-schema.md](references/output-schema.md).
   Field NAMES stay in English (machine grammar — downstream parsers
   read them); field VALUES follow `LANGUAGE` per Phase L. Write
   directly with `Write` (not shell).

2. **`intent.${PROJECT_SLUG}.html`** — the human-verifiable doc. Generate via:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/render_html_report.py" \
     .intent-state.json > "intent.${PROJECT_SLUG}.html"
   ```

   The renderer is self-contained (no CDN, no external JS) and
   HTML-escapes all user-supplied content. The HTML template lives at
   `${CLAUDE_SKILL_DIR}/assets/intent-html-template.html` — the renderer
   resolves it relative to its own path; no need to pass.

Provenance MUST include `- Revision: ${REVISION}` (1 in create, else
`TARGET_REVISION`). Update mode also emits `Refined from seeds` +
`Prior revision intent ID` — [references/output-schema.md](references/output-schema.md).
Commit with `--cached --quiet` guard (resume-safe):

```bash
git add "intent.${PROJECT_SLUG}.md" "intent.${PROJECT_SLUG}.html"
if ! git diff --cached --quiet; then
  [ "${RUN_MODE}" = "update" ] \
    && SUBJECT="feat(intent): refine ${PROJECT_SLUG} rev ${BASE_REVISION}→${TARGET_REVISION}" \
    || SUBJECT="feat(intent): synthesize ${PROJECT_SLUG} intent (mode=${MODE})"
  git commit -m "${SUBJECT}"
fi
```

The state file is gitignored (Phase 4 step 3) so it does not appear in
the commit.

Update state: `phase_completed: artifacts_emitted`.

---

## Phase 6 — Human gate + merge

The agent's cwd may be inside the worktree. Use `git -C "${MAIN_CHECKOUT}"`
so subsequent commands are cwd-independent.

Print:

1. Paths to `intent.${PROJECT_SLUG}.md` and
   `intent.${PROJECT_SLUG}.html` (absolute, so the user can open the
   HTML in a browser without computing the path themselves).
2. The next-step pointer (transition-safe):
   ```
   Next step: run `/seed-gatherer` to grow an evidence corpus from
   external research material (or to ideate/feasibility-check seeds
   when there's no external material), then `/plan-establisher` to
   fold intent + seeds into a planner-ready handoff. To refine THIS
   intent later from accumulated seeds, run `/intent-aligner update
   ${PROJECT_SLUG}` — that bumps the revision. If downstream skills
   aren't installed, you can also pass intent.${PROJECT_SLUG}.md
   directly to `/codebase-planner` (the 6 rubric fields are readable
   as-is; you lose the plan-establisher folds).
   ```
3. The exact prompt:

```
Type `confirm merge` to merge into <BASE_BRANCH>
   (create marker: (intent, human-confirmed)
    update marker: (intent, updated-from-seeds, human-confirmed)),
or `keep` to leave the worktree intact for further iteration,
or `revise` to address something before merging.
```

Behavior per response:

- `confirm merge` →
  Before checkout, refuse if `MAIN_CHECKOUT`'s current branch has any
  uncommitted changes. Marker + branch differ by `RUN_MODE`:

  ```bash
  if [ -n "$(git -C "${MAIN_CHECKOUT}" status --porcelain)" ]; then
    echo "BLOCKER: ${MAIN_CHECKOUT} has uncommitted changes — refusing to merge."
    git -C "${MAIN_CHECKOUT}" status --porcelain
    exit 1
  fi
  if [ "${RUN_MODE}" = "update" ]; then
    BRANCH="intent/update-${PROJECT_SLUG}-${INTENT_ID}"
    MERGE_MSG="feat(intent): merge ${PROJECT_SLUG} refinement (intent, updated-from-seeds, human-confirmed)"
  else
    BRANCH="intent/${PROJECT_SLUG}-${INTENT_ID}"
    MERGE_MSG="feat(intent): merge ${PROJECT_SLUG} (intent, human-confirmed)"
  fi
  git -C "${MAIN_CHECKOUT}" checkout "${BASE_BRANCH}"
  git -C "${MAIN_CHECKOUT}" merge --no-ff "${BRANCH}" -m "${MERGE_MSG}"
  ```
  The explicit `-m` is mandatory. **Do not** `git push` — user's call.

  After successful merge, ask: "Remove the worktree?" On yes: `git -C
  "${MAIN_CHECKOUT}" worktree remove <path>` (no `--force`).

- `keep` → leave worktree intact, no merge, exit cleanly.
- `revise` → leave worktree intact, ask the user **which** phase to
  re-enter (Phase 2 to re-elicit, Phase 3 to re-synthesize, Phase 5 to
  re-render artifacts). Do not guess.
- Anything else → re-ask. Silence is not yes.

Update state: `phase_completed: human_confirmed`, record `merged_at`.

---

## Downstream contract

The merge commit message `feat(intent): merge <slug> (intent,
human-confirmed)` makes the intent landing visible in `git log` — the
same pattern the planner+implementer chain uses. The marker is a social
contract, not cryptographic; the goal is catching accidental misuse and
making deliberate bypass visible in git history.

The intent-aligner does NOT auto-launch any downstream skill. The user
runs `/seed-gatherer`, `/plan-establisher`, and any further planners
explicitly when ready. Intent-aligner's job ends at the merged
`intent.<slug>.md` — gathering seeds and shaping for the planner's
rubric are seed-gatherer's and plan-establisher's concerns.

---

## Forbidden actions

The skill must refuse to execute any of these even if the user requests
them mid-flow (politely surface the forbidden item and ask for
confirmation to deviate, but default to refusal):

- `git push`, `git push --force`
- `git merge` without the `--no-ff` flag for the intent branch
- `git merge` or `git commit` without the `-m` flag (would hang on
  `$EDITOR`)
- `git reset --hard`, `git clean -f`, `git worktree remove --force`
- `git commit --amend` once a commit has landed on the intent branch
  (create a new commit instead — amend rewrites history that
  `--no-ff` was meant to preserve)
- `--no-verify` on commits (pre-commit hooks must run)
- Treating user silence as confirmation at any gate
- Skipping the example/counter-example pass in Phase 2 (it's the
  strongest disambiguator; without it the synthesis is guessing)
- Inventing intent fields the user didn't confirm — leave them as
  `[unspecified]` instead
- Hardcoding the user's intent into a tech-stack recommendation
  (that's a downstream concern; intent-aligner is stack-agnostic)
- Auto-launching `/plan-establisher` or `/codebase-planner` from
  Phase 6 (the user runs the next-hop explicitly when ready)
- In update mode: changing `Mode` (feature ↔ problem), `PROJECT_SLUG`,
  or wholesale-rewriting the intent (those are new-intent operations,
  not refinements — refuse and ask user to run plain `/intent-aligner`)
- In update mode: rolling back a revision (use `git revert` or a manual
  edit, not a refinement step)
- Creating `README.md`, `INSTALLATION_GUIDE.md`, or similar docs inside
  this skill folder

---

## Resumability

If re-invoked from inside an existing intent worktree
(`inside-intent-worktree`), read `.intent-state.json` and resume from
the next phase after `phase_completed`, honoring `run_mode` (`create`
or `update`). Full create + update resume map:
[references/state-and-resume.md](references/state-and-resume.md).

- No state file → refuse, ask user to delete the worktree or supply state.
- `run_mode` mismatches invocation arg → refuse, ask user to resume the
  original mode or remove the worktree.
- `language` missing (predates Phase L) → default `LANGUAGE` to Korean.
- `run_mode` missing (predates update mode) → default to `create`.
