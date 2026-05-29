---
name: document-implementer
description: |
  Generate the document body (prose or slides) that a prior
  `document-planner` run gated as human-confirmed. Reads the
  scale-tagged planner handoff (micro / local / feature / system),
  creates its own git worktree, generates prose or slide content
  autonomously across all phases (no per-step confirmation), runs
  bundled validators with bounded auto-fix, emits a self-verification
  report, and merges to the base branch only after the user types
  `confirm merge`. DOCTYPE-agnostic. Body-generation only — does
  NOT re-plan, re-classify scale, or edit planner artifacts. Manual
  invocation only — `/document-implementer`.
disable-model-invocation: true
---

# Document Implementer

## Overview

Execute the plan that `document-planner` produced. The implementer is
the **downstream half** of the planner→implementer chain: it consumes
the planner's scale-tagged, human-confirmed handoff and turns it into
a real user-facing document.

| Scale lane | Upstream marker | Worktree | Artifacts produced | Downstream marker |
|---|---|---|---|---|
| **micro** | `(document-plan-micro, human-confirmed)` (chat) | yes | document at `TARGET_PATH` + `implementation-report.md` | `(document-impl-micro, human-confirmed)` |
| **local** | `(document-plan-local, human-confirmed)` (chat) | yes | document at `TARGET_PATH` + `implementation-report.md` | `(document-impl-local, human-confirmed)` |
| **feature** | `(document-plan-feature, human-confirmed)` (commit) | yes | document at `TARGET_PATH` + `implementation-report.md` | `(document-impl-feature, human-confirmed)` |
| **system** | `(document-plan-system, human-confirmed)` (commit) | yes | document at `TARGET_PATH` + `implementation-report.md` | `(document-impl-system, human-confirmed)` |

The marker family is **document-specific** — does NOT inherit
codebase-implementer's `(impl-<scale>, …)` or legacy
`(interfaces only, …)` markers. Full gate-check rubric in
[references/marker-detection.md](references/marker-detection.md).

**Autonomy boundary**: Phases 0–5 run without per-step user prompts.
Pauses are only (a) genuine blockers per
[references/implementation-loop.md](references/implementation-loop.md),
and (b) the final `confirm merge` gate at Phase 6.

**Scope discipline**: prose/slide generation only. NO re-planning, NO
adding stubs, NO editing planner artifacts, NO scale re-classification.
See [references/forbidden-actions.md](references/forbidden-actions.md).

`disable-model-invocation: true` — heavy side effects (writes files,
runs git, creates worktrees, merges branches). Never auto-trigger.

## Workflow Decision Tree

```
Phase L:  Dialog language (preamble) — see references/language-selection.md
Phase 0:  Repo state + marker verification ──┬─ on-base-with-marker ───────────── proceed (Phase 1)
                                             ├─ on-base-no-marker ───────────────── refuse unless micro/local chat-gate passes
                                             ├─ on-default-needs-dev ────────────── refuse — re-run planner
                                             ├─ on-nonbase-main-checkout ────────── refuse unless micro/local chat-gate
                                             ├─ inside-document-implementer-wt ──── resume from .document-implementer-state.json
                                             ├─ inside-document-planner-worktree ── refuse — finish planner run first
                                             ├─ inside-other-worktree ───────────── refuse
                                             └─ unrelated ──────────────────────────  refuse
Phase 1:  Work-queue extraction (per scale, read-only)
Phase 2:  Worktree creation (FIRST mutation)
Phase 3:  Autonomous generation loop (no per-step prompts)
Phase 4:  Validate + bounded auto-fix (text=3 attempts; structured=0)
Phase 5:  Self-verification report + commit
Phase 6:  Human gate + merge (ONLY user prompt: `confirm merge`)
```

State variables captured during Phases L–2 and threaded through later phases:

- `LANGUAGE` — dialog language (`Korean` default | `English`); captured at Phase L; persisted at Phase 2
- `MAIN_CHECKOUT` — absolute path to the parent main worktree
- `BASE_BRANCH` — branch the implementer worktree branches from (default `dev`)
- `DOCIMPL_ID` — short suffix used in worktree path and branch name
- `INTENT_SLUG` — inherited from planner frontmatter or chat handoff
- `SCALE` — `micro | local | feature | system` — derived from the marker
- `DOCTYPE` — `api-spec | tech-spec | runbook | ppt` — from planner contract
- `OUTPUT_STACK` — `text | structured` — derived from DOCTYPE
- `AUDIENCE` — document-level primary audience — from planner contract
- `OUTPUT_LANGUAGE` — produced-document language — from planner contract
- `TARGET_PATH` — where the user-facing document lives — from planner contract

All persisted to `.document-implementer-state.json` per
[references/state-and-resume.md](references/state-and-resume.md). State
file is gitignored at both repo and worktree levels and only written
inside the worktree (Phase 2). Phases L–1 hold values in memory;
crashes don't leave stray state on `${BASE_BRANCH}`.

---

## Phase L — Dialog language (preamble)

Detect `LANGUAGE` from invocation utterance (Korean default, English
fallback), echo + confirm. Persist at Phase 2. **`OUTPUT_LANGUAGE` is
read from the planner contract, NOT prompted here** (autonomy
boundary). Full rules: [references/language-selection.md](references/language-selection.md).

---

## Phase 0 — Repo state + marker verification

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/inspect_repo_state.sh"
```

Parse the JSON. The `state` field classifies (full rubric +
chat-gate rules + chronological pairing in
[references/marker-detection.md](references/marker-detection.md)):

| State | Action |
|---|---|
| `on-base-with-marker` | `planner_marker_scale` is `system` or `feature`. Set `SCALE`. Verify artifacts exist + parse frontmatter. Proceed. Micro/local found as commit: refuse as forged. |
| `on-base-no-marker` | Check current chat for micro/local handoff per the 4-rule pairing in marker-detection.md (chat canonical; collab-memory debug-only). If valid: set `SCALE`, capture metadata from handoff. Else refuse. |
| `on-default-needs-dev` | Refuse: "No `dev` — re-run `/document-planner`." |
| `on-nonbase-main-checkout` | Acceptable only for micro/local with chat gate. Feature/system: refuse, switch to `dev`. |
| `inside-document-implementer-worktree` | Cross-verify via `git worktree list --porcelain`. If verified: resume per state-and-resume.md. Else refuse. |
| `inside-document-planner-worktree` | Refuse: "Planner run in flight — finish it first." |
| `inside-other-worktree` | Refuse, run from `MAIN_CHECKOUT`. |
| `unrelated` | Refuse, surface `reason`. |

**Feature/system metadata source**: parse the planner-emitted YAML
frontmatter at the top of `document-plan.md` via
`parse_frontmatter.py`. Carries `doctype`, `output_stack`, `audience`,
`output_language`, `target_path`, `scale`, `intent_slug`,
`docplanner_id`. **Absence or malformed = hard refusal**.

**Micro/local metadata source**: parse the 6-field chat-handoff block
visible in the current conversation (DOCTYPE / OUTPUT_STACK /
AUDIENCE / OUTPUT_LANGUAGE / TARGET_PATH / MARKER). `intent_slug` and
`docplanner_id` come from `light/plan` collab-memory filenames if
present, otherwise prompt for `intent_slug` (only).

**TARGET_PATH extension validation** per OUTPUT_STACK — mismatch is
a refusal (re-run planner with correct path). Table in
marker-detection.md.

Hold captured values in memory; lands at Phase 2.

---

## Phase 1 — Work-queue extraction

Per [references/work-queue-extraction.md](references/work-queue-extraction.md):

- **feature / system**: parse `document-plan.md` → one queue item per
  `## stub: <id>` heading (9 YAML fields as `spec_payload`). Source
  order preserved.
- **micro / local**: parse the `light/plan` 3–7 bullet reflection
  visible in chat (located by chronological pairing) → one item per
  bullet, source order preserved.

Each item records `status: pending`. Empty queue = refusal.

**TARGET_PATH precondition (Q7)**: refuse if path already exists with
non-empty content. v1 is create-only; updates require a different
planning mode (future ticket). Print existing size; ask user to
remove or pick a different path.

**OUTPUT_STACK dispatch**:
- `text` (api-spec / tech-spec / runbook): proceed.
- `structured` (ppt): **dep check** — `python3 -c "import pptx"`.
  Failure → refuse with `pip install python-pptx`. **Never
  auto-install** (user-consent rule).

Queue held in memory until Phase 2.

---

## Phase 2 — Worktree creation (first mutation)

Order matters — only after Phases 0+1 succeeded. Edge cases in
[references/git-worktree-flow.md](references/git-worktree-flow.md).

```bash
# Step 0 — local exclude.
COMMON_DIR="$(git -C "${MAIN_CHECKOUT}" rev-parse --path-format=absolute --git-common-dir 2>/dev/null || git -C "${MAIN_CHECKOUT}" rev-parse --git-common-dir)"
case "${COMMON_DIR}" in /*) ;; *) COMMON_DIR="${MAIN_CHECKOUT}/${COMMON_DIR}" ;; esac
grep -qxF '.worktrees/' "${COMMON_DIR}/info/exclude" || echo '.worktrees/' >> "${COMMON_DIR}/info/exclude"

# Step 1 — DOCIMPL_ID + slug sanitize.
DOCIMPL_ID="$(date +%s | tail -c 6)-$$-${RANDOM}"
raw_slug="${INTENT_SLUG}"
INTENT_SLUG="$(printf '%s' "${raw_slug}" | tr 'A-Z' 'a-z' | tr -cd 'a-z0-9-' | sed -e 's/^-*//' -e 's/-\{2,\}/-/g' -e 's/-*$//' | cut -c1-40)"
[ -z "${INTENT_SLUG}" ] && { echo "empty slug after sanitization"; exit 1; }

git -C "${MAIN_CHECKOUT}" worktree add \
  ".worktrees/docimpl-${INTENT_SLUG}-${DOCIMPL_ID}" \
  -b "docimpl/${INTENT_SLUG}-${DOCIMPL_ID}" "${BASE_BRANCH}"

cd "${MAIN_CHECKOUT}/.worktrees/docimpl-${INTENT_SLUG}-${DOCIMPL_ID}"

# Step 2 — worktree-level gitignore.
for entry in '.worktrees/' '.document-implementer-state.json'; do
  grep -qxF "${entry}" .gitignore 2>/dev/null || echo "${entry}" >> .gitignore
done
```

Persist initial state per [references/state-and-resume.md](references/state-and-resume.md):
`intent_slug`, `main_checkout`, `base_branch`, `docimpl_id`, `scale`,
`doctype`, `output_stack`, `audience`, `output_language`,
`target_path`, `planner_marker_scale`, `planner_marker_commit`,
`work_queue`, `phase_completed: worktree_created`.

---

## Phase 3 — Autonomous generation loop

Iterate `work_queue` in **source order**. For each item:

1. Mark `status: in_progress`, write `started_at`.
2. **Load context** per [references/implementation-loop.md](references/implementation-loop.md):
   - The stub's 9 fields
   - For each dep in `stub.dependencies`: backward dep loads
     generated prose; forward dep loads `purpose + key_claims` summary
   - **8K-token cap** on accumulated dep context. v1 estimate:
     English `word_count × 1.3`; Hangul-heavy
     `max(word_count × 1.3, hangul_syllable_count × 1.1)`. Full
     definition (`total_chars` = non-whitespace + zero-length guard)
     in implementation-loop.md.
3. **Generate** prose (text) or slide content (structured) per the
   stub's `purpose / audience / key_claims / acceptance_criteria /
   length_budget`. Write in `OUTPUT_LANGUAGE`.
4. **Transform `[[stub-id]]` references** to target-format anchors
   per [references/output-formats.md](references/output-formats.md).
   Never ship literal `[[id]]` to the user.
5. **Apply**: text → write/append to `TARGET_PATH`; for every
   text-stack stub section, emit an explicit
   `<a id="<stub-id>"></a>` anchor immediately BEFORE the section's
   human heading (so `#<stub-id>` resolves regardless of the
   heading's slug). Structured → update state
   `work_queue[i].generated_content` (and `spec_payload.title` if
   missing) for later `render_pptx.py` invocation. Use `Edit` /
   `Write`, never shell `sed`.
6. Mark `status: completed`, write `files_touched` + `completed_at`.
7. Print one progress line: `implemented item <i>/<N>: <stub_id>`.

**No per-step user prompts.** Blocker triggers documented in
implementation-loop.md.

**Commit cadence**:
- **text**: commit every N=5 completed items OR end-of-queue. Stage
  only `files_touched`, secrets-sniff diff (refuse on match per
  forbidden-actions.md).
- **structured**: single commit at end-of-queue. Invoke
  `render_pptx.py` once on final state. Note: pptx is binary; not
  LFS-tracked.

```bash
git add -- "${FILES_TOUCHED_THIS_BATCH[@]}"
# secrets sniff per forbidden-actions.md
git commit -m "feat(implementer): items <range> for ${INTENT_SLUG}"
```

Persist after every sub-step. `impl_done` at empty queue;
`impl_in_progress` on blocker.

---

## Phase 4 — Validate + bounded auto-fix

Per [references/validation-and-autofix.md](references/validation-and-autofix.md).
Branches on SCALE (feature/system have `document-plan.md`; micro/local
are chat-only — no plan artifact):

```bash
case "${SCALE}" in
  feature|system)
    python3 "${CLAUDE_SKILL_DIR}/scripts/parse_frontmatter.py" document-plan.md
    case "${OUTPUT_STACK}" in
      text)
        python3 "${CLAUDE_SKILL_DIR}/scripts/validate_doc_completeness.py" \
          document-plan.md "${TARGET_PATH}"
        python3 "${CLAUDE_SKILL_DIR}/scripts/validate_anchors.py" --text \
          --plan document-plan.md "${TARGET_PATH}"
        ;;
      structured)
        python3 "${CLAUDE_SKILL_DIR}/scripts/validate_anchors.py" --pptx \
          --plan document-plan.md "${TARGET_PATH}"
        ;;
    esac
    ;;
  micro|local)
    # No document-plan.md — chat-only contract. Standalone target checks.
    case "${OUTPUT_STACK}" in
      text)
        python3 "${CLAUDE_SKILL_DIR}/scripts/validate_anchors.py" --text \
          "${TARGET_PATH}"
        ;;
      structured)
        python3 "${CLAUDE_SKILL_DIR}/scripts/validate_anchors.py" --pptx \
          "${TARGET_PATH}"
        ;;
    esac
    ;;
esac
```

Validators are **non-mutating** and run in **diagnostic mode** (no
`&&` chaining — surface all errors in one round; agent collects exit
codes and blocks Phase 5 if any is nonzero).

**Bounded auto-fix**:
- **text**: `max_autofix_attempts = 3`. Diagnose implicated items;
  constrain fixes; commit each as `fix(implementer): autofix attempt N`.
- **structured**: `max_autofix_attempts = 0` — pptx failures are
  rarely LLM-fixable; blocker straight to user.

Budget exhausted → blocker format (last command, exit code, items,
attempts). **Do NOT merge. Do NOT clean up the worktree.**

Persist per attempt to `validation_runs[]`. On success:
`phase_completed: validated`.

---

## Phase 5 — Self-verification report + commit

Emit `implementation-report.md` at the worktree root per
[references/self-verification.md](references/self-verification.md).
Required sections: Source / Work queue summary / Files changed /
Validation / Per-item outcomes / **Acceptance-criteria checklist (Q8
explicit per stub from `document-plan.md`)** / Scope-discipline
self-check.

```bash
git add implementation-report.md
git commit -m "docs(implementer): self-verification report"
```

Persist: `phase_completed: report_emitted`.

---

## Phase 6 — Human gate + merge

cwd may be inside the worktree. Use `git -C "${MAIN_CHECKOUT}"`.

Print: (1) Phase 5 report + acceptance-criteria checklist, (2) final
validation outcome, (3) the exact prompt:

```
Type `confirm merge` to merge docimpl/<slug>-<id> into <BASE_BRANCH>
with marker (document-impl-<scale>, human-confirmed),
or `keep` to leave the worktree intact for further iteration,
or `revise` to address something before merging.
```

- `confirm merge` →
  ```bash
  if [ -n "$(git -C "${MAIN_CHECKOUT}" status --porcelain)" ]; then
    echo "BLOCKER: ${MAIN_CHECKOUT} has uncommitted changes — refusing."
    exit 1
  fi
  git -C "${MAIN_CHECKOUT}" checkout "${BASE_BRANCH}"
  git -C "${MAIN_CHECKOUT}" merge --no-ff "docimpl/${INTENT_SLUG}-${DOCIMPL_ID}" \
    -m "feat(document-implementer): merge ${INTENT_SLUG} (document-impl-${SCALE}, human-confirmed)"
  ```
  Explicit `-m` mandatory. **Do not** `git push`.

  After merge, ask: "Remove the worktree at `.worktrees/...`?" On yes:
  `git -C "${MAIN_CHECKOUT}" worktree remove <path>` (no `--force`).

- `revise` → leave intact; ask which phase to re-enter: 3 (regenerate items), 4 (re-validate), 5 (re-emit report).
- `keep` → leave intact, no merge, exit cleanly.
- Anything else → re-ask. Silence is not yes.

Persist: `phase_completed: human_confirmed`.

---

## Upstream gate + mirror discipline

The implementer reads the planner contract from
`skills/document-planner/references/implementer-contract.md` (marker
family + chronological pairing) and the YAML frontmatter spec from
`skills/document-planner/references/state-and-resume.md`.

**Mirror discipline**: this skill's `references/marker-detection.md`
and `scripts/parse_frontmatter.py` are mirrors of the canonical
planner-side files. On any divergence, the **planner contract wins**;
bump this skill to track. Drift caught at review time; no runtime
hash check.

Downstream tooling greps `git log` for
`(document-impl-<scale>, human-confirmed)` to detect implementer
landings.

---

## Forbidden actions

Full list in [references/forbidden-actions.md](references/forbidden-actions.md).
Load-bearing — refuse even if user asks mid-flow:

- `git push`, `git push --force`, `git reset --hard`, `git clean -f`,
  `git worktree remove --force`
- `git merge` without `--no-ff` for the implementer branch
- `git merge` or `git commit` without `-m` (hangs on `$EDITOR`)
- `--no-verify` on commits; `git commit --amend` after a commit lands
- Editing planner artifacts (`document-plan.md` / `document-structure.mmd` / `.html`)
- Adding stubs the planner didn't emit; re-classifying SCALE
- Shipping literal `[[stub-id]]` references to the user-facing document
- Auto-installing python-pptx or any other Python dep
- Editing planner-side `parse_frontmatter.py` (mirror discipline)
- Treating user silence as confirmation at any gate
- Generating prose without a planner marker (or chat-gate for micro/local)

---

## Resumability

If re-invoked from inside an existing implementer worktree
(`inside-document-implementer-worktree`), read
`.document-implementer-state.json` and resume from the next phase
after `phase_completed`. Full resume map: state-and-resume.md.

If `inside-document-implementer-worktree` but no state file → refuse
and ask the user to either remove the worktree or supply a state
file.

If `source_hash` no longer matches the planner artifacts (planner
was re-run since extraction): blocker — surface the diff, ask user
whether to re-extract (discards in-progress impl) or abort.
