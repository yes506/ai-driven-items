# DOCTYPE: runbook

Operational procedure — incident response, deployment, on-call
playbook, recurring SOP. Stub primitive: **per-step**.
`OUTPUT_STACK = text`.

## When to pick this DOCTYPE

- The intent is a sequence of actions to be executed in a specific
  order, typically under time pressure or operational stress.
- The audience is on-call engineers, SREs, operators, support staff.
- The eventual deliverable is markdown — usually rendered as a
  numbered checklist or a step-by-step procedure.

## Stub primitive: per-step

One stub = one executable step. Steps must be **atomic** — an
operator should be able to complete or abort a step before moving
on. A step that "either does A or B depending on X" should be split
into a decision step followed by two action steps.

Order matters. Step IDs should encode position (e.g. `step-1-…`,
`step-2-…`, `step-99-escalation` for the rollback/escalation step
that can be triggered from anywhere).

## Field interpretations

| Field | runbook interpretation |
|---|---|
| `id` | kebab-case with step-number prefix: `step-1-page-oncall`, `step-2-check-canary`, `step-99-escalation` |
| `purpose` | What this step accomplishes operationally. State the operational outcome, not the mechanism |
| `audience` | `[primary on-call]` / `[secondary on-call]` / `[incident commander]` / `[any operator]` |
| `key claims` | The preconditions, expected outputs, and post-state of the step. E.g. "after this step, the canary reports the rollback commit SHA" |
| `evidence sources` | Pointers to scripts, dashboards, monitor URLs, internal tools that the step uses |
| `dependencies` | Steps that must complete before this one. Typically linear (step-3 depends on step-2), but escalation/fallback paths can introduce branches |
| `acceptance criteria` | The concrete checks the operator runs to confirm the step succeeded. These often become assertions in the rendered doc |
| `length budget` | Step count + estimated execution time — e.g. `3-substep / ~5 min`, `single-command / ~30 sec` |
| `open questions` | Edge cases not yet covered (e.g. "what if the canary doesn't respond within 60s?"), automation gaps, ownership gaps |

## Phase 2 (outline) shape

Numbered step list in execution order, with audience and est. time:

```
1. step-1-detect            — Detect the issue (on-call, ~1 min)
2. step-2-acknowledge        — Acknowledge the page (on-call, ~30 sec)
3. step-3-triage             — Classify severity (on-call, ~2 min)
4. step-4-mitigate           — Apply mitigation (on-call, ~5 min)
5. step-5-verify             — Verify mitigation took effect (on-call, ~3 min)
6. step-99-escalation        — Escalation path (incident commander, branches)
```

## Validation hints (Phase 6)

For runbook, the dependency graph in `document-structure.mmd` MUST
be a DAG (no cycles) — runbook steps execute forward.
`validate_doc_structure.py` already catches cycles via the
declared-node-edge check, but for runbook the Phase 7 rubric should
also check that the graph has a single root (the entry point) and
that every non-escalation step has a documented next-step or
end-state.

## Implementer handoff notes

`document-implementer` for runbook generates markdown with one `##`
or `###` heading per step. Common rendered patterns:
- Numbered checklist (preferred for short runbooks)
- Numbered headings with collapsible "verify" subsections (preferred
  for long incident playbooks)

`[[stub-id]]` transformation: markdown anchor `#<stub-id>`. For
escalation references (`[[step-99-escalation]]`), the rendered link
text should preserve the "step N" prefix so the operator knows where
they're being sent.

## Honest limitations

- v1 stub primitive is one-step-one-stub. A "step" that takes 30
  minutes and includes 10 sub-actions is probably too big — split.
- Branching runbooks (decision trees) are representable via the
  `dependencies` graph but render as flat numbered lists in
  markdown. If the runbook is fundamentally a decision tree, the
  implementer may need to emit a Mermaid diagram in the rendered
  doc body (separate from the planner's structural Mermaid).
- Runbooks frequently reference external automation (Ansible,
  Terraform, internal tooling). Those references go in
  `evidence sources`, not in stub bodies.
