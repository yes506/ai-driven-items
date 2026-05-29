# Stub schema — the 9-field contract

Every stub emitted in Phase 5 (feature + system lanes) MUST carry
all 9 fields. A stub missing any field fails Phase 7
self-verification rubric explicitly. This is the binding contract
between `document-planner` and the future `document-implementer` —
the implementer reads these fields to generate the actual prose.

The 9 fields, in canonical order:

1. `id`
2. `purpose`
3. `audience`
4. `key claims`
5. `evidence sources`
6. `dependencies`
7. `acceptance criteria`
8. `length budget`
9. `open questions`

## Machine-readable format

To let `validate_internal_refs.py` parse the stub list deterministically,
emit each stub as a markdown `## stub: <id>` heading followed by a
fenced YAML block containing the other 8 fields:

````markdown
## stub: <stub-id>

```yaml
purpose: <one-paragraph string>
audience: <one-paragraph string>
key_claims:
  - <claim 1>
  - <claim 2>
evidence_sources:
  - <pointer 1>
  - <pointer 2>
dependencies:
  - <other-stub-id>
acceptance_criteria:
  - <criterion 1>
length_budget: <doctype-specific value — see table below>
open_questions:
  - <question 1>
```
````

- The fenced `yaml` block keeps editors from rendering the field
  values as prose.
- The heading-and-fence convention is what `validate_internal_refs.py`
  walks to collect declared stub IDs and inbound `[[stub-id]]`
  references.
- Field names in the YAML body use `snake_case` (machine grammar) even
  though the contract field NAMES in this doc use spaces for human
  readability. `key claims` ↔ `key_claims`, `evidence sources` ↔
  `evidence_sources`, etc.

## Field semantics

### 1. `id`
Short, lowercase, kebab-case identifier. Must be unique within the
document-plan. Stable across plan revisions — never rename an `id`
once stubs are committed; downstream cross-references in
`[[stub-id]]` form will break.

Examples: `intro`, `auth-handshake`, `step-3-rollback`,
`slide-pricing-overview`.

### 2. `purpose`
One paragraph (1–4 sentences) answering: *why does this stub exist in
the document?* Should describe the **role** of the content, not the
content itself (content is drafted by `document-implementer`).

### 3. `audience`
Primary audience(s) for this stub. May differ from the document-level
audience captured in Phase 0.5 (e.g. an api-spec where most sections
target partners, but one section is for internal SRE). Multiple
audiences are allowed as a YAML list.

### 4. `key claims`
Bullet list of the load-bearing claims the stub must make. Phase 7
rubric scores partly on whether claims are concrete and verifiable.
A claim with no supporting evidence source (field 5) is flagged.

### 5. `evidence sources`
Bullet list of pointers backing the claims: file paths, URLs,
internal-doc references, names of subject-matter experts, dataset
identifiers. Each evidence source should link back to at least one
claim. Missing-evidence-for-a-claim is a Phase 7 rubric demerit.

### 6. `dependencies`
List of other stub `id`s this stub depends on (semantically — e.g. a
"Rollback procedure" step depends on "Backup procedure" being defined
first). Phase 6 `validate_doc_structure.py` walks the dependency graph
to check that every dependency resolves to a declared stub.

Empty list is allowed (root stub).

### 7. `acceptance criteria`
Bullet list. What must be true for the implementer's output of this
stub to be considered correct? Concrete, checkable items only. These
become checklist entries in the Phase 8 human-confirmation prompt.

### 8. `length budget`
The expected size of the implementer's output for this stub.
Per-doctype semantics:

| DOCTYPE | Unit |
|---|---|
| api-spec | endpoint complexity — short string like `simple-CRUD`, `auth-flow`, `paginated-list-with-filters`. Optionally a request/response byte-size hint |
| tech-spec | word count target — e.g. `~400 words`, `~1500 words` |
| runbook | step count + estimated execution time — e.g. `5-step / ~15 min` |
| ppt | bullet-slot count + speaker-time — e.g. `4 bullets / 90 sec` |

These are **planner-side budgets** for the implementer to honor; the
human reviewer can override at Phase 8 by editing the stub before
merge.

### 9. `open questions`
Bullet list of unresolved questions about this stub. Carries forward
from Phase 1's plan-establisher open-questions for any question that
narrows to a specific stub. Empty list is allowed.

## `[[stub-id]]` internal references

Within prose fields (typically `key claims`, `acceptance criteria`,
`open questions`), use `[[stub-id]]` wikilink syntax to reference
other stubs. `validate_internal_refs.py` walks these and verifies
each one resolves to a declared `## stub: <id>` heading.

**This syntax is intermediate-only.** `document-implementer` MUST
transform every `[[stub-id]]` into the target format's native
anchor syntax when generating the user-facing document — markdown
`#anchor`, HTML `<a href>`, pptx slide-jump. Never ship literal
`[[stub-id]]` to the user.

See [implementer-contract.md](implementer-contract.md) for the full
transformation contract.

## Worked example — runbook stub

This example is **one stub from a larger document-plan**; the
`[[step-99-escalation]]` cross-reference in `acceptance_criteria`
would resolve to a stub declared elsewhere in the same
`document-plan.md`. A self-contained copy of just this stub run
through `validate_internal_refs.py` would flag the cross-reference
as unresolved.

````markdown
## stub: step-3-verify-rollback

```yaml
purpose: |
  Confirm the rollback completed cleanly by checking the canary's
  reported version against the expected pre-rollback commit. Catches
  the case where step-2 silently re-applied the new deploy due to a
  controller race.
audience: [SRE on-call]
key_claims:
  - The canary reports version <pre-rollback-commit-sha>
  - The canary is responding to /healthz within SLO
  - No new errors above the baseline rate in the last 5 minutes
evidence_sources:
  - <pointer to canary-version-check script>
  - <pointer to /healthz SLO definition>
  - <pointer to error-rate dashboard>
dependencies:
  - step-2-execute-rollback
acceptance_criteria:
  - All three claims verified before proceeding to step-4
  - If any claim fails, escalate per [[step-99-escalation]]
length_budget: 3-step / ~5 min
open_questions:
  - Should we add a 10-minute soak period before declaring success?
```
````

## What NOT to put in stubs

- The actual prose / slide content. That's `document-implementer`'s
  job. Stubs are the **plan**, not the deliverable.
- Long-form analysis. Stubs are concise — typically <30 lines each.
- Cross-stub prose. If something belongs in multiple stubs, name a
  dependency in field 6, don't duplicate.
- Secrets, credentials, customer PII. These are also out for the
  collab-memory thought-publishing path per
  [thought-publishing.md](thought-publishing.md).
