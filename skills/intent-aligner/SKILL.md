---
name: intent-aligner
description: |
  Extract what's actually in the user's head and make it concrete before any
  planning starts. Runs an interactive elicitation dialog (Socratic loops +
  5 Whys + example/counter-example disambiguation), auto-detects whether the
  user brings a feature/product idea or a problem/pain, and emits a dual-
  format artifact: `intent.<slug>.md` (AI-parseable seed, shaped 1:1 with
  `codebase-planner`'s Phase 1 normalization rubric) and
  `intent.<slug>.html` (static, self-contained, human-verifiable).
  Slug-scoped filenames let multiple intents coexist at the repo root
  after merge. Upstream of `codebase-planner`
  in the chain: intent-aligner → planner → implementer. Manual invocation
  only — `/intent-aligner`.
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
| `intent.<slug>.md` | AI (next-hop is `codebase-planner`) | Structured seed, shaped to match planner's Phase 1 normalization rubric so it ingests with zero translation |
| `intent.<slug>.html` | Human | Static, self-contained, print-friendly verification doc — the user reads it and confirms "yes, that's what I meant" |

Artifact names are **slug-scoped** so multiple intents can coexist at
the repo root after merge — running `/intent-aligner` for two different
projects produces `intent.foo.md` and `intent.bar.md` without
overwriting each other.

The skill sits **upstream** of `codebase-planner`. Chain position:

```
[/intent-aligner] → /codebase-planner → /codebase-implementer
       │                    │                     │
intent.<slug>.md       plan.md /             impl + report
intent.<slug>.html     architecture.html
```

`disable-model-invocation: true` — the skill has side effects (writes
files, creates a git worktree, merges branches). Never auto-trigger.

## Workflow Decision Tree

```
Phase L: Dialog language (preamble) — see references/language-selection.md
Phase 0: Detect repo state ──┬─ on-dev ────────────────────── proceed
                             ├─ on-default-needs-dev ──────── create-dev dialog
                             ├─ on-nonbase-main-checkout ──── refuse, ask user to switch to dev
                             ├─ inside-intent-worktree ────── resume from .intent-state.json
                             ├─ inside-other-worktree ─────── refuse, run from MAIN_CHECKOUT
                             └─ unrelated ─────────────────── refuse, surface reason
Phase 1: Mode detection (feature-shape vs problem-shape) — echo + confirm
Phase 2: Elicitation loop (Socratic + 5 Whys + example/counter-example)
Phase 3: Synthesis + `confirm intent` gate (no mutations yet)
Phase 4: Worktree creation (FIRST mutation) — .worktrees/intent-<slug>-<id>/
Phase 5: Emit intent.<slug>.md + intent.<slug>.html + commit
Phase 6: Human gate + merge (`confirm merge` → marker `(intent, human-confirmed)`)
```

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
- `INTENT` — the in-memory normalized representation (Goal, In-scope,
  Out-of-scope, Constraints, Success criteria, Open questions, plus
  mode-specific extras); persisted to `.intent-state.json` at Phase 4.

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

## Phase 0 — Repo state detection

Run the read-only inspector via the skill-directory variable (the bundled
script is **not** at the user's project root):

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/inspect_repo_state.sh"
```

Parse the JSON. The `state` field classifies into:

| State | Meaning | Action |
|---|---|---|
| `on-dev` | on `dev` branch in `MAIN_CHECKOUT` | proceed to Phase 1 |
| `on-default-needs-dev` | on `main`/`master`, no local `dev` | run the "create dev from `<default_branch>`?" dialog from [references/git-worktree-flow.md](references/git-worktree-flow.md) |
| `on-nonbase-main-checkout` | on a non-`dev` non-default branch (e.g. a feature branch) in the main checkout | refuse and ask user to switch to `dev` (or run with explicit `BASE_BRANCH` override via the dialog) |
| `inside-intent-worktree` | cwd is inside an `*/.worktrees/intent-*` worktree | resume from `.intent-state.json` if present, else refuse |
| `inside-other-worktree` | inside a non-intent linked worktree (planner / implementer / scaffold / unknown) | refuse, instruct user to run from `MAIN_CHECKOUT` — those are downstream or unrelated runs |
| `unrelated` | not in a git repo, detached HEAD, repo with no commits, or otherwise unclassifiable | refuse, surface the `reason` field from the JSON to the user |

Capture from JSON: `MAIN_CHECKOUT`, `default_branch`. Set `BASE_BRANCH=dev`
by default (configurable via dialog if the user objects). The skill does
NOT detect a language stack — that's the planner's concern downstream;
intent-aligner is stack-agnostic.

**Gate**: capture `MAIN_CHECKOUT` + `BASE_BRANCH` before Phase 1.

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
      persona-prefix form — makes the planner's "for whom?" rubric
      survive normalization; see references/output-schema.md)

User persona: <who, what they do — single sentence>

In-scope:
  - ...

Out-of-scope:                   ← fold counter-example reasons in
  - <non-goal> (counter-example: <reason>)
  - ...

Constraints:                    ← (problem mode) fold final root-cause step
  - ...
  - Root cause: <X>             ← problem mode only

Success criteria:               ← fold most-concrete example as observable scenario
  - ...
  - <example-folded scenario>   ← skip ONLY if example is already a success criterion

Concrete examples (happy paths):
  - ...

Counter-examples (must NOT happen):
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
# Step 0 — local exclude so .worktrees/ doesn't dirty status. CRITICAL:
# --git-common-dir returns a RELATIVE path on older git; use
# --path-format=absolute (git >= 2.31) with fallback, otherwise the exclude
# lands at "<cwd>/.git/info/exclude" not MAIN_CHECKOUT's.
COMMON_DIR="$(git -C "${MAIN_CHECKOUT}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null \
              || git -C "${MAIN_CHECKOUT}" rev-parse --git-common-dir)"
case "${COMMON_DIR}" in /*) ;; *) COMMON_DIR="${MAIN_CHECKOUT}/${COMMON_DIR}" ;; esac
grep -qxF '.worktrees/' "${COMMON_DIR}/info/exclude" \
  || echo '.worktrees/' >> "${COMMON_DIR}/info/exclude"

# Step 1 — reuse INTENT_ID from Phase 1. Sanitize PROJECT_SLUG defensively.
raw_slug="<from-user-at-Phase-3>"
PROJECT_SLUG="$(printf '%s' "${raw_slug}" \
  | tr 'A-Z' 'a-z' \
  | tr -cd 'a-z0-9-' \
  | sed -e 's/^-*//' -e 's/-\{2,\}/-/g' -e 's/-*$//' \
  | cut -c1-40)"
[ -z "${PROJECT_SLUG}" ] && { echo "empty slug after sanitization — ask user for an ASCII slug"; exit 1; }

git -C "${MAIN_CHECKOUT}" worktree add \
  ".worktrees/intent-${PROJECT_SLUG}-${INTENT_ID}" \
  -b "intent/${PROJECT_SLUG}-${INTENT_ID}" "${BASE_BRANCH}"

# Step 2 — cd into the new worktree for all subsequent file ops
cd "${MAIN_CHECKOUT}/.worktrees/intent-${PROJECT_SLUG}-${INTENT_ID}"

# Step 3 — committed gitignore so .worktrees/ + .intent-state.json
# stay hidden after the merge to ${BASE_BRANCH}
for entry in '.worktrees/' '.intent-state.json'; do
  grep -qxF "${entry}" .gitignore 2>/dev/null \
    || echo "${entry}" >> .gitignore
done

# Step 4 — initial commit on the intent branch (explicit -m form — a bare
# `git commit` would drop into $EDITOR and hang in non-interactive runs)
git add .gitignore
git commit -m "chore(intent): initialize ${PROJECT_SLUG} worktree"
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
   per [references/output-schema.md](references/output-schema.md),
   which is shaped to match `codebase-planner`'s Phase 1 normalization
   rubric 1:1. Field NAMES stay in English (machine grammar — the
   planner's parser reads them); field VALUES follow `LANGUAGE` per
   Phase L. Write directly with `Write` (not shell).

2. **`intent.${PROJECT_SLUG}.html`** — the human-verifiable doc. Generate via:

   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/render_html_report.py" \
     .intent-state.json > "intent.${PROJECT_SLUG}.html"
   ```

   The renderer is self-contained (no CDN, no external JS) and
   HTML-escapes all user-supplied content. The HTML template lives at
   `${CLAUDE_SKILL_DIR}/assets/intent-html-template.html` — the renderer
   resolves it relative to its own path; no need to pass.

Commit on the intent branch (explicit `-m` form). The `git diff
--cached --quiet` guard handles the Phase 5 resume edge case: if the
agent crashed between a prior commit and this state update, the
re-rendered (identical) artifacts won't stage anything; commit-skip
prevents the bare `git commit` from failing with "nothing to commit"
and trapping resume:

```bash
git add "intent.${PROJECT_SLUG}.md" "intent.${PROJECT_SLUG}.html"
if ! git diff --cached --quiet; then
  git commit -m "feat(intent): synthesize ${PROJECT_SLUG} intent (mode=${MODE})"
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
2. The **lane-agnostic copy-pasteable invocation block** — works
   regardless of which lane the planner triages into. The path MUST
   be in the same message as the invocation so Phase 0.5's
   discovery-before-questions rule reads it before scoring (a bare
   invocation scores ambiguity=3 and blocks). The inline 6-field
   summary is redundant-but-harmless for feature/system lanes (planner
   ingests both file and inline as multi-source per
   `plan-ingestion.md`) AND load-bearing for micro/local lanes (where
   the verbal-only path uses the chat request as the canonical plan).
   Full rationale:
   [references/planner-handoff.md](references/planner-handoff.md).
   Interpolate `${PROJECT_SLUG}` and the actual `INTENT` field values
   before printing:
   ```
   /codebase-planner   plan from ${MAIN_CHECKOUT}/intent.${PROJECT_SLUG}.md

   Planner seed summary:
   Goal: <intent.goal verbatim — single sentence in "For <persona>, <outcome>" form>
   In-scope features:
   <intent.in_scope[*] as bullets>
   Out-of-scope:
   <intent.out_of_scope[*] as bullets, each "<non-goal> (counter-example: <reason>)" form>
   Constraints:
   <intent.constraints[*] as bullets, including "Root cause: <X>" if problem mode>
   Success criteria:
   <intent.success_criteria[*] as bullets, including example-folded observable scenario>
   Open questions:
   <intent.open_questions[*] as bullets — or "(none)" if empty>
   ```
3. The exact prompt:

```
Type `confirm merge` to merge intent/<slug>-<id> into <BASE_BRANCH>
with marker (intent, human-confirmed),
or `keep` to leave the worktree intact for further iteration,
or `revise` to address something before merging.
```

Behavior per response:

- `confirm merge` →
  Before checkout, refuse if `MAIN_CHECKOUT`'s current branch has any
  uncommitted changes (a long-running intent session can be overtaken
  by the user editing `MAIN_CHECKOUT` in another shell — `git checkout
  "${BASE_BRANCH}"` would either fail mid-way on conflicting files, or
  silently carry the unrelated dirty edits onto `${BASE_BRANCH}` if they
  don't conflict, then pull them into the merge change-set):

  ```bash
  if [ -n "$(git -C "${MAIN_CHECKOUT}" status --porcelain)" ]; then
    echo "BLOCKER: ${MAIN_CHECKOUT} has uncommitted changes on its current branch — refusing to merge. Commit/stash/discard first."
    git -C "${MAIN_CHECKOUT}" status --porcelain
    exit 1
  fi
  git -C "${MAIN_CHECKOUT}" checkout "${BASE_BRANCH}"
  git -C "${MAIN_CHECKOUT}" merge --no-ff "intent/${PROJECT_SLUG}-${INTENT_ID}" \
    -m "feat(intent): merge ${PROJECT_SLUG} (intent, human-confirmed)"
  ```
  The explicit `-m` is mandatory — without it git drops into `$EDITOR`
  and hangs in non-interactive use. **Do not** `git push` — that's the
  user's call.

  After successful merge, ask: "Remove the worktree at
  `.worktrees/intent-${PROJECT_SLUG}-${INTENT_ID}`?" On yes: `git -C
  "${MAIN_CHECKOUT}" worktree remove <path>` (no `--force`). On no:
  leave it.

- `keep` → leave worktree intact, no merge, exit cleanly.
- `revise` → leave worktree intact, ask the user **which** phase to
  re-enter (Phase 2 to re-elicit, Phase 3 to re-synthesize, Phase 5 to
  re-render artifacts). Do not guess.
- Anything else → re-ask. Silence is not yes.

Update state: `phase_completed: human_confirmed`, record `merged_at`.

---

## Downstream contract (planner handoff)

The merge commit message `feat(intent): merge <slug> (intent,
human-confirmed)` makes the intent landing visible in `git log` — the
same pattern the planner+implementer chain uses. The marker is a social
contract, not cryptographic; the goal is catching accidental misuse and
making deliberate bypass visible in git history.

The intent-aligner does NOT auto-launch `/codebase-planner` — the user
runs it explicitly when ready. Phase 6 prints the suggested invocation
line so it's one copy-paste away. Full guidance:
[references/planner-handoff.md](references/planner-handoff.md).

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
- Hardcoding the user's intent into a tech-stack recommendation (that's
  the planner's job; intent-aligner is stack-agnostic)
- Auto-launching `/codebase-planner` from Phase 6 (the user runs it
  explicitly when ready)
- Creating `README.md`, `INSTALLATION_GUIDE.md`, or similar docs inside
  this skill folder

---

## Resumability

If re-invoked from inside an existing intent worktree
(`inside-intent-worktree`), read `.intent-state.json` and resume from
the next phase after `phase_completed`. See
[references/state-and-resume.md](references/state-and-resume.md) for
the full mapping.

If `inside-intent-worktree` but no state file → refuse and ask the user
to either delete the worktree or supply a state file.

If the state file's `language` field is missing (predates Phase L on
older builds): default `LANGUAGE` to Korean (matching Phase L's default)
and continue without prompting.
