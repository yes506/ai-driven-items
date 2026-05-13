# Feature-lane spec

The `feature` lane is a middle ground between local (chat-only) and
system (full interface-skeleton workflow). It runs in a worktree, emits
committed artifacts, and lands a merge marker — but its artifact set is
a **plan**, not an interface contract. Skeletons are emitted only when
Phase 3 decomposition discovers a real cross-boundary contract.

## Artifact set

| File | Required | Contents |
|---|---|---|
| `plan.md` | yes | Plan synthesis (goal, in-scope, out-of-scope, constraints, success criteria, open questions from Phase 1) + Phase 2 package layout + Phase 3 decomposition table |
| `plan.mmd` | yes | Mermaid DAG of the same nodes from Phase 3. Same renderer as system lane (`render_mermaid_dag.py` reads `.planner-state.json`) — just redirected to `plan.mmd` |
| Interface skeletons | optional | Only when Phase 3 finds a genuine cross-boundary contract; user confirms via `emit skeletons` token before Phase 5 runs |

Merge marker (Phase 8): `(plan-feature, human-confirmed)`.

## Phase-by-phase deltas vs. the system lane

### Phase 2 — Package/directory plan

Optional. If the feature is contained in existing packages, skip Phase 2
entirely and proceed to Phase 3 with `packages = []` in state. Document
the decision in the plan.md "Package layout" section as "no new packages
introduced — feature lives in <existing-package>".

### Phase 5 — Skeleton generation (conditional)

```
if SCALE == "feature":
    if cross_boundary_contract_detected (from Phase 3):
        ask user: "Phase 3 found <N> new cross-boundary contracts. Emit
                   interface skeletons for them? (emit skeletons / skip)"
        if user types `emit skeletons`:
            run Phase 5 as documented (9-field docstrings required for the emitted ones)
        else:
            skip Phase 5 entirely
    else:
        skip Phase 5 entirely
```

When Phase 5 is skipped, no commit is created at this step. The plan
artifacts will land in Phase 7's commit instead.

### Phase 6 — Validate (conditional)

- If skeletons were emitted: run the language-appropriate compile/type
  check as documented in SKILL.md Phase 6.
- If skeletons were skipped: validate `plan.md` and `plan.mmd` instead:
  - `plan.md` is non-empty and contains the required headers
    (`## Goal`, `## Package layout`, `## Decomposition`).
  - `plan.mmd` parses as valid Mermaid (smoke-check: `head -1` returns
    `flowchart` or `graph`).

### Phase 7 — Self-verification artifacts

Emit `plan.mmd` from the state file (same renderer as system, different
filename) and `plan.md` manually composed from the state file's
`plan.*` and decomposition fields. **Do NOT emit `architecture.html`** —
that filename is system-lane-only and signals a different downstream
contract.

Rubric: drop the "Docstring quality" and "Interface cohesion" criteria
(they don't apply when no methods/interfaces were emitted). The
remaining 4 criteria are: decomposition completeness, dependency
direction, validation status, plan coverage.

If user opted into `emit skeletons`, the full 6-criterion system-lane
rubric applies AND `plan.md` lists the emitted interfaces in an
"Interfaces emitted" appendix.

Commit:

```bash
git add plan.md plan.mmd
git commit -m "docs(planner): self-verification artifacts (feature lane)"
```

### Phase 8 — Merge marker

Use the feature marker, not the system marker:

```bash
git -C "${MAIN_CHECKOUT}" merge --no-ff "planner/${PROJECT_SLUG}-${PLANNER_ID}" \
  -m "feat(planner): merge ${PROJECT_SLUG} plan (plan-feature, human-confirmed)"
```

Downstream implementers reading the gate per
[implementer-contract.md](implementer-contract.md) require both:

- `plan.md` + `plan.mmd` exist on `${BASE_BRANCH}`
- `(plan-feature, human-confirmed)` marker appears in `git log`

## What plan.md contains (templated)

```markdown
# Feature plan — <project-slug>

## Goal
<from .planner-state.json plan.goal>

## In scope
- <item 1>
- <item 2>

## Out of scope
- <item 1>

## Constraints
- <item 1>

## Success criteria
- <item 1>

## Open questions
- <item 1> (if any remain after Phase 1 confirmation)

## Package layout
<directory tree from Phase 2, OR "no new packages" if Phase 2 was skipped>

## Decomposition
| Node # | Stage | Belongs to package | Notes |
|---|---|---|---|
| 1 | <stage> | <package> | <notes> |

## Interfaces emitted
<empty / N/A if Phase 5 was skipped>
<otherwise: list interface names + method count, with link to source path>

## Validation
<output of Phase 6 check>
```

## Lane-variable shortcut for Phase 7/8 bash

The SKILL.md body uses these lane-conditional variables in Phase 7/8:

```bash
case "${SCALE}" in
  system)  ARTIFACTS="architecture.mmd architecture.html"; MARKER="(interfaces only, human-confirmed)" ;;
  feature) ARTIFACTS="plan.mmd plan.md";                   MARKER="(plan-feature, human-confirmed)" ;;
esac
```

System-lane behavior is unchanged from the pre-rename codebase-architect
skill; this lane is purely additive.
