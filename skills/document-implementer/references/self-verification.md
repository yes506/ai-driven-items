# Phase 5 — Self-verification report

Emits the self-verification report after Phase 4 validators succeed.
The report is the artifact the human reviewer inspects at Phase 6
before typing `confirm merge`.

**Report path** (`REPORT_PATH`):
- **feature / system**: `"${RUN_DIR}/report.${DOCIMPL_ID}.md"` — the
  planner's run-dir, resolved from the marker commit's trailer at
  Phase 0 and reused from state (`planner_artifact_dir`).
- **micro / local** (no planner run-dir, hence no trailer):
  `"ai-artifacts/runs/doc/${REPORT_SLUG}-docimpl-${DOCIMPL_ID}/report.${DOCIMPL_ID}.md"`,
  where `REPORT_SLUG` is the sanitized `TARGET_PATH`/project basename
  persisted in state (`report_slug`).

`mkdir -p "$(dirname "${REPORT_PATH}")"` before writing. The report is
committed inside the worktree and merged via the normal Phase 5/6 flow
for ALL lanes (no carve-out). `TARGET_PATH` is unaffected — the
user-facing document stays at its user-chosen path, NOT under
`ai-artifacts/`.

## Report schema

```markdown
# Implementation report — ${INTENT_SLUG}

## Source
- Planner marker: `<scale>` from commit `<sha-short>` (or "chat" for micro/local)
- Planner run-dir: `<RUN_DIR>` (feature/system; resolved from marker trailer) — `<empty>` for micro/local
- Planner artifacts: `<list of paths under RUN_DIR>` (e.g. `${RUN_DIR}/document-plan.md`, `${RUN_DIR}/document-structure.mmd`)
- Source hash: `<sha256-short>` (computed at Phase 1 extraction over the union of planner artifacts; surfaces if planner is re-run mid-implementer)
- Frontmatter values (feature/system): DOCTYPE, OUTPUT_STACK, AUDIENCE, OUTPUT_LANGUAGE, TARGET_PATH

## Work queue summary
- Total items: <N>
- Completed: <M>
- Blocked: <K> (with reasons)

## Files changed
<bullet list of relative paths with line-count deltas; for structured, just `<TARGET_PATH>` and the report at `<REPORT_PATH>`>

## Validation
- Validators run: parse_frontmatter, validate_doc_completeness (text), validate_anchors (text or pptx)
- Final exit codes per validator
- Auto-fix attempts used: <i>/<max> (text only; structured is always 0)
- Tail of last validation run (20 lines): <fenced block>

## Per-item outcomes
| item_id | status | files_touched | dep_context_degraded | notes |
|---|---|---|---|---|
| <stub-id> | completed | docs/x.md | [] | — |
| <stub-id> | completed | docs/x.md | ["forward-dep-id"] | forward dep summary used |
| <stub-id> | blocked | — | — | <blocker_reason> |

## Acceptance-criteria checklist (Q8 — explicit per stub)

For each stub from `${RUN_DIR}/document-plan.md`, list every entry in
the stub's `acceptance_criteria` field as a checkbox. Reviewer ticks
each at Phase 6 before `confirm merge`.

### stub: context
- [ ] Numbers verified against last 7 days
- [ ] Audience scope explicitly named

### stub: approach
- [ ] Approach explained in <500 words
- [ ] At least one trade-off acknowledged

(...one section per stub...)

## Scope-discipline self-check
- [ ] No edits to `document-plan.md` / `document-structure.mmd` / `document-structure.html`
- [ ] No new stubs added (`document-plan.md` stub-id set unchanged)
- [ ] No scale re-classification
- [ ] No literal `[[stub-id]]` shipped to TARGET_PATH (`grep -n '\[\[' "${TARGET_PATH}"` returns nothing)
- [ ] No edits to planner-side `parse_frontmatter.py`
- [ ] No `git push` performed
- [ ] No `--no-verify` on any commit
- [ ] All commits use explicit `-m` flag

## Known limitations (if any apply to this run)
- Mark whichever of these limitations affected this run:
  - [ ] Dep-context cap triggered degradation on <K> items (see Per-item outcomes column)
  - [ ] Auto-fix budget partially consumed (<i>/<max> attempts)
  - [ ] Forward-dep fallback used for stubs without backward generation available
  - [ ] OUTPUT_LANGUAGE = Korean; token estimates used Hangul-heavy path

## Open questions for Phase 6 reviewer
<list of any `open_questions` from stubs whose criteria are
ambiguous or whose answers depend on subjective judgment; reviewer
must decide before merge>
```

## Why an explicit acceptance-criteria checklist (Q8)

The planner emits each stub's `acceptance_criteria` field as the
contract for what makes the implementer's prose "correct." Without
an explicit checklist, the reviewer would have to flip back to
`document-plan.md` and trace each stub's criteria against the
generated prose. The explicit checklist:

- Forces the reviewer to consciously tick each criterion (no
  silent "looks fine" passes).
- Catches implementer mistakes the validators can't catch (e.g.,
  "section is present but doesn't actually address the claim").
- Surfaces the planner-side contract directly at the human gate.

If the reviewer cannot tick a criterion, the correct response is
`revise` at Phase 6, not `confirm merge`.

## Auto-tickable vs human-only criteria (v1 vs v1.5)

v1 makes NO attempt to auto-check criteria. Phase 5 surfaces them
as un-ticked checkboxes; the human reviewer is responsible.

v1.5 enhancement: parse each criterion for patterns the implementer
can verify cheaply (e.g., `"<=500 words"` → word_count check;
`"includes ≥1 worked example"` → fence-block count). Auto-tick the
mechanically-checkable ones; leave subjective criteria
("clarity", "accuracy") for the human.

Until v1.5, all criteria are presented as un-ticked checkboxes for
explicit human ratification.

## Commit

```bash
mkdir -p "$(dirname "${REPORT_PATH}")"
# write the report to "${REPORT_PATH}" via the Write tool, then stage it:
git add -- "${REPORT_PATH}"
git commit -m "docs(implementer): self-verification report"
```

Persist: `phase_completed: report_emitted`.

## What Phase 5 does NOT do

- Score the prose quality (no rubric).
- Auto-validate acceptance criteria (deferred to v1.5).
- Send notifications / publish to anywhere outside the worktree
  (collab-memory thought publish happens at Phase 5 checkpoint per
  [thought-publishing.md](thought-publishing.md), but the report
  itself is local to the worktree until merge).
