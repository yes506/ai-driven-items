# Phase 4 — Validate + bounded auto-fix

Phase 4 runs after Phase 3 empties the work queue. Validators are
bundled, **non-mutating**, and run in **diagnostic mode** (no `&&`
chaining — surface all errors in one round; agent collects exit
codes and blocks Phase 5 if any is nonzero).

## Validators — branched by SCALE

Feature/system runs have a committed `document-plan.md`; micro/local
runs are chat-only by planner contract and have NO document-plan.md.
Phase 4 branches accordingly.

### feature / system

```bash
# Frontmatter integrity (no tampering with planner artifact)
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
```

- `parse_frontmatter.py`: planner-emitted frontmatter is still valid.
- `validate_doc_completeness.py`: every `## stub: <id>` from
  document-plan.md must have a corresponding `#<stub-id>` anchor in
  TARGET_PATH. The implementer MUST emit explicit
  `<a id="<stub-id>"></a>` anchors before each section's human
  heading — heading slugs rarely match stub-ids
  (see implementation-loop.md).
- `validate_anchors.py --text --plan ...`: every markdown
  `[…](#anchor)` link resolves; no literal `[[stub-id]]` wikilinks
  remain.
- `validate_anchors.py --pptx --plan ...`: .pptx parses; slide count
  ≥ declared stub count; each slide's speaker-notes first line is
  a declared stub-id (provenance contract injected by
  `render_pptx.py`).

### micro / local (no document-plan.md)

```bash
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
```

- `parse_frontmatter.py` and `validate_doc_completeness.py` are
  **skipped** — no document-plan.md exists for the chat-only
  planner contract.
- `validate_anchors.py` (without `--plan`): standalone target
  checks — **text**: no literal `[[…]]` wikilinks + all `#anchor`
  links resolve within the file. **pptx**: file parses + has at
  least one slide. Provenance / declared-stub checks are skipped
  (no plan to declare against).

## Bounded auto-fix policy

### text (max_autofix_attempts = 3)

```
attempt = 1
while attempt <= 3:
  1. Capture stderr+stdout (cap at 200 tail lines)
  2. Diagnose: which queue items' files are implicated?
     - validate_doc_completeness FAIL → missing stub section → re-generate that stub
     - validate_anchors FAIL on anchor → fix the broken link in the section that contains it
     - validate_anchors FAIL on `[[stub-id]]` wikilink → re-run transformation on that section
  3. Generate fix(es), constrained to files_touched of implicated items
  4. Apply, stage only those files, secrets sniff, commit:
     git commit -m "fix(implementer): autofix attempt ${attempt}"
  5. Re-run all validators in diagnostic mode; exit 0 → done
  attempt += 1
```

Auto-fix scope discipline mirrors the main loop: same prohibitions on
re-planning, re-classifying, adding stubs, editing planner
artifacts.

### structured (max_autofix_attempts = 0)

PPTX failures are rarely LLM-fixable:
- python-pptx threw on malformed data → data bug or library issue
- slide count mismatch → state.work_queue[] was malformed
- speaker-notes mismatch → render_pptx.py provenance contract bug

The implementer reports the failure directly to the user without
auto-fix attempts. Treating these as LLM-fixable risks producing
malformed pptx files repeatedly.

## Blocker format on budget exhaustion

```
BLOCKER: validation auto-fix budget exhausted.
Last command: <command>
Last exit code: <code>
Tail of stderr/stdout (20 lines):
<fenced block>
Implicated items: <stub-ids>
Attempted fixes: <N>/<max>

Next steps:
  - Re-enter Phase 3 manually to fix the implicated stubs, OR
  - `revise` at Phase 6 (when reached) to inspect, OR
  - Re-run the planner if the underlying stubs are wrong.
```

**Do NOT merge. Do NOT clean up the worktree.** The state file lets
the user resume after manual intervention.

## State persistence

Per attempt, append to `state.validation_runs[]`:

```json
{
  "attempt": <N>,
  "ts": "<ISO-8601>",
  "validators_run": ["parse_frontmatter", "validate_doc_completeness", "validate_anchors"],
  "exit_codes": [0, 1, 0],
  "implicated_items": ["<stub-id>"],
  "tail": "<200-line capped stderr+stdout>"
}
```

On success: `phase_completed: validated`.

## What Phase 4 does NOT validate

- **Prose quality** — Phase 6 reviewer's judgment.
- **Acceptance-criteria satisfaction** — surfaced as a checklist in
  Phase 5 report; reviewer ticks at Phase 6.
- **Accuracy of factual claims** — out of scope; relies on the
  evidence_sources field at stub-level being correct.
- **Style guide adherence** — out of scope for v1 (no external
  linter dep).
- **OpenAPI YAML correctness for api-spec** — Q11 deferred .yaml
  extension to v1.5; v1 generates markdown api-specs only.

## Honest limitations

- v1 validators are structural, not semantic. A "complete" document
  per validator could still be substantively wrong.
- The auto-fix loop assumes the LLM can re-generate a stub correctly
  given the validator error message; success rate depends on how
  specific the validator's failure message is.
- For structured (ppt), python-pptx exceptions are sometimes opaque
  (e.g., XML schema violations). The blocker format captures
  stderr; reviewer may need to inspect the .pptx in a tool.
