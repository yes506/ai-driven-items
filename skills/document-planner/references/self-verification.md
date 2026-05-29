# Phase 7 — Self-verification rubric

Runs at the end of feature + system lanes, before the human gate at
Phase 8. Outputs: (1) a 4-point × 6-criteria rubric, (2) a
human-confirmation checklist, (3) visual artifacts already emitted
by Phase 5/7 (`document-plan.md`, `document-structure.mmd`, +
`document-structure.html` for system).

The rubric scores **the planner output**, not the eventual
user-facing document. The user-facing document is `document-implementer`'s
deliverable; the planner only verifies its own stub list and graph.

## Rubric: 6 criteria × 4 points each (max 24)

Each criterion scored 0 (missing) / 1 (weak) / 2 (acceptable) /
3 (strong). Print each score with one-sentence reasoning.

### 1. Stub completeness
- 3: Every stub from Phase 3 emitted with all 9 fields per
  [stub-schema.md](stub-schema.md). Field semantics respected
  (e.g. `length budget` matches DOCTYPE convention).
- 2: All stubs present; ≤2 stubs missing 1 field each.
- 1: 1–3 stubs entirely missing OR systematic field omissions across
  the document.
- 0: >3 stubs missing OR the stub list does not cover the Phase 2
  outline.

### 2. Cross-stub references
- 3: All `[[stub-id]]` references resolve; `validate_internal_refs.py`
  passes with 0 errors and 0 warnings (no orphans).
- 2: All references resolve; ≤3 orphans warned.
- 1: 1–2 unresolved references.
- 0: >2 unresolved references OR validator failed entirely.

### 3. Dependency graph soundness
- 3: `validate_doc_structure.py` passes; the Mermaid DAG has no
  cycles; root and leaf stubs identifiable.
- 2: Validator passes; minor topology issues (e.g. duplicated
  near-equivalent edges).
- 1: Validator passes but graph has structural concerns (e.g. one
  stub depending on >6 others suggests it's overloaded).
- 0: Validator failed OR graph has cycles.

### 4. Audience coherence
- 3: Every stub's `audience` field is consistent with the
  document-level audience captured at Phase 0.5, or explicitly notes
  a per-stub deviation with reasoning.
- 2: All stubs have an audience; minor consistency gaps noted but
  not addressed.
- 1: ≥1 stub missing an `audience` field, OR conflicting audiences
  without explanation.
- 0: No audience captured at planner level.

### 5. Evidence coverage
- 3: Every `key claim` has at least one `evidence source`. No claim
  is unsupported.
- 2: Most claims have evidence; ≤2 unsupported claims acknowledged
  in `open questions`.
- 1: Multiple unsupported claims AND not surfaced as open questions.
- 0: Systematic absence of evidence sources.

### 6. Open-questions discipline
- 3: All planner-level `open questions` are localized to the stubs
  they pertain to (or explicitly noted as document-level). The
  Phase 1 plan-establisher open questions are accounted for.
- 2: Open questions captured but not consistently localized.
- 1: Some open questions dropped from Phase 1 to Phase 5 without
  resolution OR retention reasoning.
- 0: Open questions not tracked.

**Pass threshold**: total ≥ 14/24 with **no criterion at 0**.

A score of 0 on any criterion **blocks Phase 8**. Surface the failure
and offer `revise` to address it.

## Human-confirmation checklist

After the rubric, print this checklist (LANGUAGE-translated):

```
[ ] The TOC in Phase 2 matches the document I have in mind.
[ ] The stub list covers every section/slide/endpoint/step I expect.
[ ] Every stub's audience is correct.
[ ] Evidence sources point to real, accessible references.
[ ] No open questions block me from approving the plan.
[ ] document-structure.html (system only) renders without console errors
    when opened in a browser.
[ ] TARGET_PATH is correct (eventual destination for the user-facing doc).
```

Wait for the user to walk through it before showing the Phase 8
gate prompt. Silence is not yes.

## Visual artifacts

Emitted in Phase 5 (`.mmd` + `document-plan.md`) and Phase 7
(`.html` for system) via
`${CLAUDE_SKILL_DIR}/scripts/render_doc_structure.py`. All HTML is
self-contained — no CDN imports, no external CSS, all node labels and
field values HTML-escaped (per CLAUDE.md hard rule + the
`render_doc_structure.py` implementation).

## Phase 6 gates that must pass before scoring

The Phase 7 rubric scores **content** (stub completeness, evidence,
audience coherence, etc.). It does NOT re-score the validators —
those are binary gates in Phase 6 that must already have passed:

- `parse_frontmatter.py` — frontmatter present, all 8 required keys
  valid, no `---` drift in body, no `## stub:` heading before close.
- `validate_doc_structure.py` — single graph header, unique IDs,
  declared-edge resolution, no cycles.
- `validate_internal_refs.py` — every `[[stub-id]]` resolves.

If any Phase 6 gate failed, the rubric does NOT run. The planner exits
to `revise` per Phase 6's failure handling. The rubric is for content
quality, not contract compliance.

## Known v1 limitations

- **`dependencies:` ↔ Mermaid-edge drift is not auto-checked.** Both
  come from the same Phase 5 emission (state file `stubs[]` →
  rendered `.mmd`), so drift is unlikely in normal flow. But a
  hand-edited `document-plan.md` whose YAML `dependencies:` list no
  longer matches the rendered `.mmd` would pass both
  `validate_doc_structure.py` and `validate_internal_refs.py` — a
  third bundled cross-validator is out of scope for v1. Manual
  Phase 8 reviewer check covers this.

## What Phase 7 does NOT validate

- The eventual prose / slide content. That's `document-implementer`'s
  job, gated by a separate marker family.
- For `OUTPUT_STACK = structured` (ppt): the eventual `.pptx` file.
  Phase 7 validates the planner-internal `.mmd` and stub list only.
- Compliance / legal accuracy. Subject-matter review is a human gate,
  not a rubric check.
- Style guide adherence. The implementer should run a style-guide
  pass during prose generation.

## Failure → `revise`

If the rubric scores below threshold or any criterion hits 0, do NOT
proceed to Phase 8. Print:

```
Self-verification rubric scored <total>/24 with <criterion-name>
at 0. The plan does not pass the gate. Options:
  (a) `revise` — return to Phase 3 (decomposition) or Phase 5
      (stub emission) to address the issue.
  (b) `escalate` — surface the issue + your judgment on whether
      the rubric should be relaxed for this document.
```

Never auto-relax the rubric. The threshold is the contract.
