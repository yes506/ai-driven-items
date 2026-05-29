---
name: document-planner
description: |
  Decide how much planning a document needs, then produce the right
  weight of plan — from a 3-bullet sketch for a one-section memo to a
  fully decomposed section/slide structure with 9-field stubs and human
  gate. First-class decisions are **planning scale** (micro / local /
  feature / system) and **DOCTYPE** (api-spec | tech-spec | runbook |
  ppt). Lane drives whether a worktree is created and whether stubs are
  emitted; DOCTYPE drives per-doctype reference loading + the eventual
  stub primitive (per-endpoint, per-section, per-step, per-slide).
  Document-format-agnostic. Manual invocation only —
  `/document-planner`.
disable-model-invocation: true
---

# Document Planner

## Overview

Plan a document at the **lightest sufficient weight** for the task.
Classify the request into one of four scale lanes and one of the v1
DOCTYPEs before any mutation, then run only the phases that lane
needs.

| Scale lane | Worktree | Artifacts | Stubs emitted | Downstream marker |
|---|---|---|---|---|
| **micro** | no | none | no | `(document-plan-micro, human-confirmed)` — chat only |
| **local** | no | none | no | `(document-plan-local, human-confirmed)` — chat only |
| **feature** | yes | `document-plan.md` + `document-structure.mmd` | yes (9-field stubs) | `(document-plan-feature, human-confirmed)` |
| **system** | yes | `document-plan.md` + `document-structure.mmd` + `document-structure.html` | yes (full 9-field stubs + HTML preview) | `(document-plan-system, human-confirmed)` |

The marker family is a **new choice** for document-planner — it does
NOT inherit `codebase-planner`'s legacy `(interfaces only, …)` system
marker. See [implementer-contract.md](references/implementer-contract.md)
for the full marker contract, chat-adjacency pairing rule, and
`[[stub-id]]` transformation contract.

`disable-model-invocation: true` — the skill spans read-only (micro,
local) and side-effect (feature, system) lanes; uniform manual
invocation prevents mode confusion. Never auto-trigger.

**Thought publishing** — each meaningful checkpoint writes to
canvas-terminal's collab-memory for peer agents (silent no-op when no
session resolves; see [thought-publishing.md](references/thought-publishing.md)).

## Workflow Decision Tree

```
Phase L:   Dialog language (preamble) — see references/language-selection.md
Phase 0:   Detect repo state ──┬─ on-dev ──────────────────────────── proceed
                               ├─ on-default-needs-dev ────────────── feature/system: create-dev dialog
                               ├─ on-nonbase-main-checkout ────────── feature/system refuse; micro/local proceed
                               ├─ inside-document-planner-worktree ── resume from .document-planner-state.json
                               ├─ inside-other-worktree ──────────── refuse, run from MAIN_CHECKOUT
                               └─ unrelated ─────────────────────────  refuse, surface reason
Phase 0.5: Triage + DOCTYPE ───┬─ discovery (plan-establisher output, intent, CLAUDE.md)
                               ├─ classify DOCTYPE (infer → confirm → select-from-list)
                               ├─ score (scope, risk, ambiguity)
                               ├─ derive OUTPUT_STACK from DOCTYPE
                               ├─ capture TARGET_PATH + AUDIENCE + OUTPUT_LANGUAGE
                               └─ pick lane: micro | local | feature | system
                                  └─→ rubric in references/triage-and-readiness.md
```

State variables captured during Phases L/0/0.5 and threaded through later phases:

- `MAIN_CHECKOUT` — absolute path to the parent main worktree
- `BASE_BRANCH` — branch the planner worktree branches from (default `dev`); only feature+system
- `DOCPLANNER_ID` — stable run handle; all lanes; reused as worktree/branch suffix in feature+system Phase 4
- `LANGUAGE` — `Korean` default | `English`; captured at Phase L; persisted at Phase 4 (feature+system); memory-only otherwise
- `SCALE` — `micro | local | feature | system` — chosen in Phase 0.5
- `DOCTYPE` — `api-spec | tech-spec | runbook | ppt` — chosen in Phase 0.5; drives per-doctype reference loading + stub primitive
- `OUTPUT_STACK` — `text | structured` — derived from DOCTYPE (`ppt → structured`; others → text); routes downstream implementer toolchain
- `TARGET_PATH` — where the user-facing document will live (e.g. `docs/api/v2/spec.md`); captured in Phase 0.5
- `AUDIENCE` — document-level primary audience (e.g. `internal SREs`, `partner engineers`); captured in Phase 0.5; default for each stub's `audience` field; persisted for resume + included in chat-handoff
- `OUTPUT_LANGUAGE` — produced-document language (`Korean | English`); may differ from dialog `LANGUAGE`; captured in Phase 0.5; persisted everywhere AUDIENCE is
- `INTENT_SLUG` — set if a plan-establisher `plan.<intent-slug>.v<N>.md` was accepted; else empty

---

## Phase L — Dialog language (preamble, runs before Phase 0)

Detect `LANGUAGE` from invocation utterance (Korean default, English fallback), echo + confirm. Persist at Phase 4 (feature+system); memory-only otherwise. Spec — including resume + mid-flow switches: [references/language-selection.md](references/language-selection.md).

---

## Phase 0 — Repo state detection

Run the read-only inspector via the skill-directory variable:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/inspect_repo_state.sh"
```

Parse the JSON. The `state` field classifies into:

| State | Action |
|---|---|
| `on-dev` | proceed to Phase 0.5 |
| `on-default-needs-dev` | feature/system: run create-dev dialog (see [state-and-resume.md](references/state-and-resume.md)). micro/local: skip — no worktree |
| `on-nonbase-main-checkout` | micro/local: **proceed** (read-only). feature/system: refuse, ask user to switch to `dev` |
| `inside-document-planner-worktree` | resume from `.document-planner-state.json` if present, else refuse |
| `inside-other-worktree` | refuse, instruct user to run from `MAIN_CHECKOUT` |
| `unrelated` | refuse, surface `reason` from JSON |

Capture from JSON: `MAIN_CHECKOUT`, `default_branch`. Set `BASE_BRANCH`
to `dev` by default for feature/system lanes; micro/local don't use it.

**Gate**: capture `MAIN_CHECKOUT` + `default_branch` before Phase 0.5.

---

## Phase 0.5 — Triage, DOCTYPE classification & readiness

See [triage-and-readiness.md](references/triage-and-readiness.md) for
full rubric, and [doctype-dispatch.md](references/doctype-dispatch.md)
for the DOCTYPE classification flow.

1. **Discovery first** (no user questions yet): scan for plan-establisher
   `plan.<intent-slug>.v<N>.md` per [plan-ingestion.md](references/plan-ingestion.md);
   read CLAUDE.md / AGENTS.md / README.md, the intent doc if present,
   `git log -n 20 --oneline -- <related-path>`. Surface what you found.
2. **Classify DOCTYPE** per
   [doctype-dispatch.md](references/doctype-dispatch.md): infer from
   plan-establisher `Goal` → confirm with user → select-from-list on
   miss → friendly refuse on unknown.
3. **Derive `OUTPUT_STACK`** from DOCTYPE.
4. **Capture `TARGET_PATH`** — ask the user where the eventual
   user-facing document will live (absolute or repo-relative).
   Required for all lanes.
5. **Capture `AUDIENCE`** — infer the document-level primary audience
   from the plan-establisher `Goal` / `In scope` if available;
   confirm with a single yes/no, or ask if no inference. Required
   for all lanes — drives per-stub `audience` defaults and the
   Phase 7 audience-coherence rubric criterion.
6. **Capture `OUTPUT_LANGUAGE`** — default inherits dialog `LANGUAGE`;
   ask explicitly when `AUDIENCE` implies a different language.
   Heuristics in [doctype-dispatch.md](references/doctype-dispatch.md).
7. **Score** `(scope, risk, ambiguity)` each 0–3, with reasoning.
   `scope` is content-volume only (no format-complexity weighting).
8. **Resolve lane**: `final_scale = max(scope, risk)`; accepted plan's
   `Proposed scale lane` is the default → `micro|local|feature|system`.
9. **Block if `ambiguity >= 2` AND `final_scale <= 1`**: one
   consolidated question round; re-score with answers. No silent
   upgrades.
10. Print classification (SCALE, DOCTYPE, OUTPUT_STACK, AUDIENCE,
    OUTPUT_LANGUAGE, TARGET_PATH) + prompt `confirm scale` /
    suggest different lane (upgrade free; downgrade needs
    `confirm downgrade`) / `revise`.
11. Compute `DOCPLANNER_ID="$(date +%s | tail -c 6)-$$-${RANDOM}"`;
    publish each checkpoint via
    `${CLAUDE_SKILL_DIR}/scripts/publish_thought.sh` (**heredoc body**
    per [thought-publishing.md](references/thought-publishing.md)).

Persist `SCALE`, `DOCTYPE`, `OUTPUT_STACK`, `AUDIENCE`,
`OUTPUT_LANGUAGE`, `TARGET_PATH`, and the three scores to
`.document-planner-state.json` (feature/system only).

**After Phase 0.5:**
- micro / local → "Lightweight lanes" below
- feature / system → Phase 1 (full pipeline)

---

## Lightweight lanes (micro & local)

Read-only. No worktree, no commits, no stubs, no state file. Chat is
the entire artifact. The 9-field stub schema does NOT apply.

1. **Verbal-or-plan ingestion** — accepted plan-establisher plan if
   present; else the chat request is the plan.
2. **3–7 bullet plan reflection** — outline, audiences, evidence
   sources, open questions, risks. No Mermaid DAG.
3. **Prompt** `confirm plan` / `revise` / `escalate`. On each prompt
   publish `light/plan` via
   `publish_thought.sh "${DOCPLANNER_ID}" light plan` (heredoc body
   required per
   [thought-publishing.md](references/thought-publishing.md)).
4. **Chat-handoff block on confirm** — chat-only equivalent of the
   Phase 8 merge gate. Emit as a fenced block:

   ```
   --- document-planner handoff (chat-only, micro/local) ---
   DOCTYPE: <api-spec|tech-spec|runbook|ppt>
   OUTPUT_STACK: <text|structured>
   AUDIENCE: <document-level primary audience>
   OUTPUT_LANGUAGE: <Korean|English>
   TARGET_PATH: <absolute or repo-relative>
   MARKER: (document-plan-<scale>, human-confirmed)
   ---
   ```

   `document-implementer` reads this from chat history; pairing
   discipline in [implementer-contract.md](references/implementer-contract.md).
   Also publish `8/outcome` (body = the handoff block; heredoc).

---

## Phase 1 — Plan ingestion (no mutations)

Accept the project plan via multiple inputs, presented separately so
each can be normalized in isolation before synthesis:

- **plan-establisher output** — `plan.<intent-slug>.v<N>.md` at repo
  root (preferred; auto-discovered in Phase 0.5)
- **File paths** — markdown / text / PDF references on disk
- **URLs** — wiki / GitHub issue / spec page
- **Inline pasted text** — content pasted directly in chat

Read [plan-ingestion.md](references/plan-ingestion.md) for
plan-establisher schema reuse + document-shaped normalization rubric
(goal, audience, in-scope sections, out-of-scope, constraints,
success criteria, evidence sources, open questions).

Reflect the normalized synthesis back as a single fenced block. Wait
for `confirm plan` before Phase 2. Silence is not yes.

---

## Phase 2 — Document outline (no mutations)

Propose a TOC consistent with `references/<doctype>.md`. Show as a
numbered list + a one-line audience-and-purpose summary per section.
Justify each section by linking back to a goal/feature from Phase 1.

For `OUTPUT_STACK = structured` (ppt): the TOC is a slide list, not a
section list. Per-slide grouping by speaker beat is allowed.

Wait for `confirm outline` before Phase 3.

---

## Phase 3 — Stub decomposition (no mutations)

Read [stub-schema.md](references/stub-schema.md) for the 9-field
contract. Per the DOCTYPE-specific primitive:

| DOCTYPE | Stub primitive |
|---|---|
| api-spec | per-endpoint |
| tech-spec | per-section |
| runbook | per-step |
| ppt | per-slide |

Enumerate every stub as a table, then render the same data as a
Mermaid DAG so dependencies are visible. Wait for
`confirm decomposition` before Phase 4.

---

## Phase 4 — Worktree creation (first mutation, feature+system only)

Order matters — only after Phase 3 confirmation:

0. **Locally** ignore `.worktrees/` in the main checkout:
   ```bash
   COMMON_DIR="$(git -C "${MAIN_CHECKOUT}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || git -C "${MAIN_CHECKOUT}" rev-parse --git-common-dir)"
   case "${COMMON_DIR}" in /*) ;; *) COMMON_DIR="${MAIN_CHECKOUT}/${COMMON_DIR}" ;; esac
   grep -qxF '.worktrees/' "${COMMON_DIR}/info/exclude" || echo '.worktrees/' >> "${COMMON_DIR}/info/exclude"
   ```
1. **Reuse `DOCPLANNER_ID`** from Phase 0.5 (stable across the run):
   ```bash
   raw_slug="<intent-slug-or-short-doc-slug>"
   INTENT_SLUG="$(printf '%s' "${raw_slug}" | tr 'A-Z' 'a-z' | tr -cd 'a-z0-9-' | sed -e 's/^-*//' -e 's/-\{2,\}/-/g' -e 's/-*$//' | cut -c1-40)"
   [ -z "${INTENT_SLUG}" ] && { echo "Empty slug after sanitization — ask user for an ASCII slug"; exit 1; }

   git -C "${MAIN_CHECKOUT}" worktree add \
     ".worktrees/docplanner-${INTENT_SLUG}-${DOCPLANNER_ID}" \
     -b "docplanner/${INTENT_SLUG}-${DOCPLANNER_ID}" "${BASE_BRANCH}"
   ```
2. `cd` into the new worktree for subsequent file operations.
3. Append `.worktrees/` and `.document-planner-state.json` to the
   **worktree's** `.gitignore` if either is missing. Lands on
   `${BASE_BRANCH}` via Phase 8's merge so future contributors never
   see those paths as untracked.
4. **Write the initial `.document-planner-state.json`** with
   `phase_completed: worktree_created`, plus `intent_slug`,
   `main_checkout`, `base_branch`, `docplanner_id`, `doctype`,
   `output_stack`, `audience`, `output_language`, `target_path`,
   `language`. This is what makes resume work if the skill crashes
   between Phase 4 and Phase 5.

Edge cases (path collision, dirty `BASE_BRANCH`, nested invocation,
merge conflicts) are documented in
[state-and-resume.md](references/state-and-resume.md). Stop and ask —
never auto-resolve.

---

## Phase 5 — Stub emission (feature+system)

**First, write the frontmatter** at the top of `document-plan.md`
per the 8-key spec in [state-and-resume.md](references/state-and-resume.md),
using captured state values. Then run
`parse_frontmatter.py document-plan.md` to verify the 4 boundary
checks pass before appending stubs.

For each stub from Phase 3, emit the 9-field stub per
[stub-schema.md](references/stub-schema.md), using the machine-readable
`## stub: <id>` heading + YAML body convention (so
`validate_internal_refs.py` can parse deterministically).

**Every stub MUST carry all 9 fields.** No exceptions. A stub missing
any field fails Phase 7 self-verification rubric. The `length budget`
field has per-doctype semantics (word count, endpoint complexity, step
count, bullet-slot + speaker-time) — see stub-schema.md.

**In lockstep with each `## stub: <id>` heading emitted in
`document-plan.md`**, append a matching entry to the state file's
`stubs[]` array: `{"id", "title", "dependencies"}` (snake_case,
matching the YAML body's `dependencies:` list). The renderer
(`render_doc_structure.py`) reads this array to emit the Mermaid DAG.
Write `.document-planner-state.json` **incrementally** after each
sub-step per [state-and-resume.md](references/state-and-resume.md), so
a mid-run failure stays resumable.

After all stubs are emitted, render the Mermaid DAG:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/render_doc_structure.py" \
  .document-planner-state.json --format mmd > document-structure.mmd
```

The renderer fails non-zero on undeclared dependencies — fix the
state file before retrying. Then commit both artifacts (explicit
`-m` — a bare `git commit` would drop into `$EDITOR` and hang):

```bash
git add -A
git commit -m "chore(document-planner): initialize ${INTENT_SLUG} stub list (no prose)"
```

The state file is gitignored (Phase 4 step 3) so it does not appear
in the commit.

---

## Phase 6 — Validate (feature+system)

Run bundled structural validators on the emitted artifacts:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/parse_frontmatter.py" \
  document-plan.md
python3 "${CLAUDE_SKILL_DIR}/scripts/validate_doc_structure.py" \
  document-structure.mmd
python3 "${CLAUDE_SKILL_DIR}/scripts/validate_internal_refs.py" \
  document-plan.md
```

Validator scope: `parse_frontmatter.py` enforces the 8-key frontmatter
contract (4 boundary checks); `validate_doc_structure.py` checks `graph`
header + unique IDs + edge-resolution + DFS cycle detection;
`validate_internal_refs.py` resolves every `[[stub-id]]` to a declared
`## stub: <id>` heading (orphans warned, not failed).

For `OUTPUT_STACK = structured` (ppt): validation runs on the
planner-internal `.mmd` and stub list, NOT on the eventual `.pptx`
(document-implementer produces that). See
[self-verification.md](references/self-verification.md).

On failure: stop, report, **never auto-prune the worktree**. Update
`.document-planner-state.json` `phase_completed: validated` on success.

---

## Phase 7 — Self-verification artifacts (feature+system)

Outputs per [self-verification.md](references/self-verification.md):
rubric (4-point × 6 criteria), checklist, visual artifacts. The
renderer HTML-escapes stub IDs and titles against `click ... href`
injection.

```bash
case "${SCALE}" in
  system)  ARTIFACTS="document-plan.md document-structure.mmd document-structure.html"
           MARKER="(document-plan-system, human-confirmed)"
           python3 "${CLAUDE_SKILL_DIR}/scripts/render_doc_structure.py" \
             .document-planner-state.json --format html > document-structure.html ;;
  feature) ARTIFACTS="document-plan.md document-structure.mmd"
           MARKER="(document-plan-feature, human-confirmed)" ;;
esac
```

`document-structure.mmd` and `document-plan.md` are emitted in Phase
5 (the renderer step + stub-list step). System adds
`document-structure.html` here in Phase 7 (self-contained, no CDN,
HTML-escaped per CLAUDE.md hard rule).

**Agent step**: compose the human-readable rubric + checklist in the
chat message before:

```bash
git add ${ARTIFACTS}
git commit -m "docs(document-planner): self-verification artifacts"
```

Update state: `phase_completed: artifacts_emitted`.

---

## Phase 8 — Human gate + merge (feature+system)

The agent's cwd may be inside the worktree. Use
`git -C "${MAIN_CHECKOUT}"` so subsequent commands are
cwd-independent.

Print: (1) rubric scores from Phase 7, (2) human-confirmation
checklist, (3) artifact paths (`${ARTIFACTS}`), (4) the exact prompt:

```
Type `confirm plan` to mark this document-planner output human-confirmed
(unlocks the implementation gate), or `revise` to iterate.
```

- `confirm plan` →
  - Update `.document-planner-state.json` locally:
    `phase_completed: human_confirmed`, record reviewer + ISO-8601 ts.
  - Then prompt:
    ```
    Type `confirm merge` to merge docplanner/<intent-slug>-<id> into <BASE_BRANCH>,
    or `keep` to leave the worktree intact for further iteration.
    ```
  - On `confirm merge`:
    ```bash
    git -C "${MAIN_CHECKOUT}" checkout "${BASE_BRANCH}"
    git -C "${MAIN_CHECKOUT}" merge --no-ff "docplanner/${INTENT_SLUG}-${DOCPLANNER_ID}" \
      -m "feat(document-planner): merge ${INTENT_SLUG} ${MARKER}"
    ```
    Explicit `-m` mandatory. **Do not** `git push` — user's call.
- `revise` → leave worktree intact, return to relevant phase.
- Anything else → re-ask.

After merge, ask: "Remove the worktree at `.worktrees/...`?" On yes:
`git -C "${MAIN_CHECKOUT}" worktree remove <path>` (no `--force`). On
no: leave it.

After any prompt resolves, publish `8/outcome` via
`publish_thought.sh "${DOCPLANNER_ID}" 8 outcome` (heredoc per
[thought-publishing.md](references/thought-publishing.md)).

---

## Implementation gate (downstream contract)

Skills, subagents, and Claude sessions that intend to write
**document prose / slides** based on a document-planner run MUST honor
the scale-tagged `(document-plan-<scale>, human-confirmed)` marker
family. Full table, chat-adjacency pairing rule for micro/local, and
the `[[stub-id]]` → target-format anchor transformation contract live
in [implementer-contract.md](references/implementer-contract.md).

This marker family is a **new choice** — it does NOT inherit
codebase-planner's legacy `(interfaces only, human-confirmed)` system
marker. document-implementer greps for `document-plan-*` only.

**Honest limitations**: documented social contract, not cryptographic.
A determined user can fake marker files / commit messages; the goal
is catching accidental misuse and making deliberate bypass visible in
git history.

---

## Forbidden actions

Refuse these even if requested mid-flow (surface + ask, default refuse):

- `git push`, `git push --force`
- `git merge` without `--no-ff` for the docplanner branch
- `git merge` or `git commit` without `-m` (would hang on `$EDITOR`)
- `git commit --amend` once a commit has landed on the docplanner
  branch (create a new commit instead)
- `git reset --hard`, `git clean -f`, `git worktree remove --force`
- `--no-verify` on commits (pre-commit hooks must run)
- Generating prose body content — defer to the implementer skill
  (gated by tracked artifacts + merge marker per "Implementation gate"
  above, NOT by `.document-planner-state.json` which is gitignored)
- Writing fewer than the 9 stub fields on any emitted stub
  (feature+system lanes only — micro/local emit no stubs)
- Hardcoded version pins in references — use placeholders per CLAUDE.md
- Treating user silence as confirmation at any gate
- Creating `README.md`, `INSTALLATION_GUIDE.md`, etc. inside this skill
- Loading a `references/<doctype>.md` for a DOCTYPE not in the v1
  roster (`api-spec / tech-spec / runbook / ppt`) — refuse + offer
  to add as follow-up ticket

---

## Resumability

If re-invoked from inside an existing document-planner worktree
(`inside-document-planner-worktree`), read
`.document-planner-state.json` and resume from the next phase after
`phase_completed`. See
[state-and-resume.md](references/state-and-resume.md) for the full
mapping.

If `inside-document-planner-worktree` but no state file → refuse and
ask the user to either delete the worktree or supply a state file.
