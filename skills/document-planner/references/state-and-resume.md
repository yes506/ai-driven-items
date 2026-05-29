# State and resume — `.document-planner-state.json` schema

The state file is the per-run persistent record for feature/system
lanes. It's gitignored on the worktree's own `.gitignore` (Phase 4
step 3) so it never lands on `${BASE_BRANCH}` — purely local
working state for resumability.

Micro/local lanes create no state file; the chat history + the
chat-handoff block at end-of-flow are their entire record.

## Schema

```json
{
  "schema_version": 1,
  "docplanner_id": "<stable id from Phase 0.5>",
  "intent_slug": "<sanitized slug>",
  "main_checkout": "<absolute path>",
  "base_branch": "<default: dev>",
  "language": "Korean | English",
  "doctype": "api-spec | tech-spec | runbook | ppt",
  "output_stack": "text | structured",
  "audience": "<document-level primary audience>",
  "output_language": "Korean | English",
  "target_path": "<where the user-facing document will live>",
  "scale": "feature | system",
  "scores": {
    "scope": 0,
    "risk": 0,
    "ambiguity": 0,
    "reasoning": "<one-paragraph string>"
  },
  "phase_completed": "<see phase mapping below>",
  "stubs": [
    {
      "id": "<stub-id>",
      "title": "<short title — used in Mermaid label>",
      "dependencies": ["<other-stub-id>", ...]
    }
  ],
  "human_confirmation": {
    "reviewer": "<chat handle or empty>",
    "confirmed_at": "<ISO-8601 ts or empty>"
  }
}
```

The `stubs` array is used by `render_doc_structure.py` to emit the
Mermaid DAG and HTML preview. Full 9-field bodies live in
`document-plan.md`, not in this state file (that would balloon it).

**Lockstep update rule (Phase 5)**: every time the agent emits a
`## stub: <id>` heading + YAML body into `document-plan.md`, it
MUST also append a matching `{"id", "title", "dependencies"}` entry
to `stubs[]` in this file. Field names in the state file are
snake_case (matching the YAML body in `document-plan.md`); the title
mirrors the stub heading's human-readable form. If the two get out
of sync, the renderer's Mermaid DAG will not match the stub list and
Phase 7 self-verification will fail.

## `phase_completed` values

Written incrementally as the workflow progresses. On resume, the
planner re-enters the phase AFTER the one named here.

| Value | Set at |
|---|---|
| `worktree_created` | Phase 4 step 4 (initial write) |
| `stubs_emitted` | Phase 5 (after the commit) |
| `validated` | Phase 6 success |
| `artifacts_emitted` | Phase 7 (after the commit) |
| `human_confirmed` | Phase 8 on `confirm plan` |

## Resume flow

When Phase 0 detects `inside-document-planner-worktree` and finds a
state file at the worktree root, the planner reads it and dispatches:

| `phase_completed` | Resume from |
|---|---|
| `worktree_created` | Phase 5 (stub emission) |
| `stubs_emitted` | Phase 6 (validate) |
| `validated` | Phase 7 (artifacts) |
| `artifacts_emitted` | Phase 8 (human gate) |
| `human_confirmed` | Phase 8 merge sub-step (re-print the prompt) |

If the state file is missing or unreadable, refuse. Do NOT recreate
from scratch — that loses the user's prior work and the merge marker
audit trail.

## Incremental write strategy

`.document-planner-state.json` is rewritten **atomically** (tmp file
+ `mv -f`) at each phase boundary AND at sub-step boundaries within
Phase 5 (stub emission). The rationale: a crash mid-stub-emission
should leave the planner resumable from the last committed stub, not
from the beginning of Phase 5.

```bash
write_state() {
  local tmp="${PWD}/.document-planner-state.json.tmp.$$"
  cat > "${tmp}" <<EOF
<JSON body>
EOF
  mv -f "${tmp}" "${PWD}/.document-planner-state.json"
}
```

## Worktree creation edge cases

### Path collision
If `.worktrees/docplanner-${INTENT_SLUG}-${DOCPLANNER_ID}/` already
exists when Phase 4 runs (extremely unlikely given `DOCPLANNER_ID`
entropy, but possible on a hand-crafted path):
1. Refuse to overwrite.
2. Ask the user whether to recompute `DOCPLANNER_ID` and try again.

### Dirty `BASE_BRANCH`
If `${BASE_BRANCH}` has uncommitted changes when Phase 4 tries to
`worktree add`, the command fails. Surface the failure verbatim — do
NOT auto-stash. Ask the user to commit/stash manually.

### Nested invocation
If the user invokes `/document-planner` from inside an existing
`docplanner-*` worktree but with a DIFFERENT intent slug, refuse.
The inspector classifies the cwd as `inside-document-planner-worktree`
and the resume flow expects matching state.

### Untracked files on resume
If the worktree has untracked files NOT covered by the worktree's
`.gitignore`, surface them to the user before resuming. They might
be intentional (user's draft notes) or accidental (a half-written
stub from a prior crash). Don't auto-`git clean`.

### Merge conflicts at Phase 8
If `git merge --no-ff` fails with conflicts, do NOT auto-resolve.
Print the conflict status, leave the worktree intact, and ask the
user to resolve manually. The Phase 8 gate stays open until the
merge actually lands.

## On-default-needs-dev dialog

When Phase 0 detects `on-default-needs-dev` and the lane will be
feature/system:

```
You're on <default_branch> but `dev` doesn't exist locally.
Should I create `dev` from <default_branch> for you?
(This is the project convention; document-planner's heavy lanes
target `dev` as the base branch by default.)
Type `proceed` to create + switch, or `revise` to handle it manually.
```

On `proceed`:
```bash
git -C "${MAIN_CHECKOUT}" checkout -b dev
```

On `revise`: refuse and ask the user to set up `dev` and re-invoke.

For micro/local: skip — no worktree, no `BASE_BRANCH` needed.
