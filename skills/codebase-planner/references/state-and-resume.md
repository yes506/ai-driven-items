# `.planner-state.json` — schema and resume

The state file lives at the worktree root and is **gitignored** on the
planner branch (per Phase 4 step 3). It is local-only working state,
updated **incrementally** after each Phase sub-step so any mid-run
failure stays resumable. It is NEVER committed; the human-confirmation
marker lives in the tracked artifacts (system: `architecture.html` +
`architecture.mmd`; feature: `plan.md` + `plan.mmd`) and the merge
commit message, not in this file. See
[implementer-contract.md](implementer-contract.md) for the full
per-lane gate check and SKILL.md "Implementation gate (downstream
contract)" for the summary table.

## Schema

```json
{
  "scale": "feature | system (state file is only created at these scales)",
  "language": "Korean | English (captured at Phase L; written for the first time when this state file is created at Phase 4; absent value on resume defaults to Korean for backward compat with pre-Phase-L state files)",
  "scope_score": "int 0-3 (Phase 0.5 triage)",
  "risk_score": "int 0-3 (Phase 0.5 triage)",
  "ambiguity_score": "int 0-3 (Phase 0.5 triage)",
  "scale_overridden": "bool (true if user manually picked a different lane than the AI suggested)",
  "project_slug": "string (kebab-case ascii, used in worktree path + branch name)",
  "main_checkout": "absolute path to the main worktree (physical, symlinks resolved)",
  "base_branch": "string (default: dev; configurable when dev doesn't exist)",
  "planner_id": "string (e.g. '12345-67890' — `date +%s | tail -c 6`-`$$`)",
  "language_stack": "java | python | typescript | javascript | go | rust",
  "validation_command": "string (the actual command to run in Phase 6, with <package> already substituted)",
  "detected_build_files": ["array (from detect_language_stack.sh output; non-empty when project is a monorepo)"],
  "phase_completed": "worktree_created | plan_normalized | packages_planned | decomposition_done | skeleton_written | validated | artifacts_emitted | human_confirmed",
  "plan": {
    "goal": "string",
    "in_scope": ["..."],
    "out_of_scope": ["..."],
    "constraints": ["..."],
    "success_criteria": ["..."],
    "open_questions": ["..."],
    "sources": [
      {"kind": "file|url|inline", "ref": "...", "fetched_at": "ISO-8601"}
    ]
  },
  "packages": ["string (package paths, e.g. 'com.acme.order.intake')"],
  "interfaces": [
    {
      "name": "string (e.g. 'OrderRepository')",
      "package": "string",
      "cohesion_source": "state | lifecycle | collaboration | failure_domain",
      "methods": [
        {
          "name": "string",
          "node_index": "int (1-based, matches Phase 3 enumeration)",
          "docstring_fields_present": [
            "responsibility", "pipeline_position", "inputs", "outputs",
            "side_effects", "preconditions", "postconditions",
            "failure_modes", "collaborators"
          ],
          "collaborators": ["InterfaceName.method", "..."]
        }
      ]
    }
  ],
  "value_objects": ["string (Java enums, Python dataclasses, TS types — non-interface helpers)"],
  "validation_status": "pending | passed | failed",
  "feature_skeletons_choice": "emit | skip | null (feature lane only — captured at the Phase 3 → Phase 5 transition; null for system lane where skeletons are mandatory)",
  "rubric_scores": {
    "decomposition_completeness": "int 1-4",
    "docstring_quality": "int 1-4 (system + feature-with-skeletons only; omit when no methods are emitted)",
    "interface_cohesion": "int 1-4 (system + feature-with-skeletons only; omit when no interfaces are emitted)",
    "dependency_direction": "int 1-4",
    "validation_status": "int 1-4",
    "plan_coverage": "int 1-4"
  },
  "human_confirmation": {
    "reviewer": "string (free-form, e.g. handle or email)",
    "confirmed_at": "ISO-8601"
  }
}
```

## Resume mapping

| `phase_completed` value | Resume at |
|---|---|
| `worktree_created` | Phase 1 (plan ingestion) |
| `plan_normalized` | Phase 2 (packages) |
| `packages_planned` | Phase 3 (decomposition) |
| `decomposition_done` (system, or feature with `feature_skeletons_choice=emit`) | Phase 5 (skeleton) |
| `decomposition_done` (feature with `feature_skeletons_choice=skip`) | Phase 7 (plan artifacts; Phase 5 + Phase 6 skipped) |
| `skeleton_written` | Phase 6 (validate) |
| `validated` | Phase 7 (artifacts) |
| `artifacts_emitted` | Phase 8 (human gate) |
| `human_confirmed` | Phase 8 (merge offer) — re-prompt for `confirm merge` |

Before trusting the loaded state file, run these defensive checks
(mirrors the implementer's resume protocol — same threat model,
hand-staged worktree directories and tampered state files):

1. **Verify the worktree is registered.** Run `git -C
   "${MAIN_CHECKOUT}" worktree list --porcelain` and confirm the
   current path is listed. Defends against a hand-staged
   `.worktrees/planner-fake/` directory dropped in to trick
   path-prefix detection. If not registered: refuse.
2. **Validate the loaded state structurally.** `scale` ∈
   {feature, system}; `phase_completed` ∈ the documented enum;
   `main_checkout` resolves to an existing directory that is itself a
   git worktree top; `base_branch` is a non-empty string. On any
   failure → refuse with a clear "state file is corrupt or hostile"
   message. Do NOT attempt to repair.
3. `language` field absent on resume → default to `Korean` and
   continue (legacy state file from a pre-Phase-L build).

If `inside-planner-worktree` but no state file → refuse and ask the
user to either delete the worktree or supply a state file.

If the state file exists but `phase_completed` is missing or invalid →
refuse, surface the file contents, and ask the user to repair or
discard.

## Update discipline

After each sub-step, write the file atomically (so a crash mid-write
can't corrupt it):

```bash
tmp="$(mktemp)"
jq '. + {phase_completed: "skeleton_written"}' .planner-state.json > "$tmp"
mv "$tmp" .planner-state.json
```

The file is gitignored, so the temp-file dance doesn't dirty git status.
If `jq` is unavailable, fall back to writing the JSON directly via a
language-native writer (Python: `json.dump`).

## Read by downstream automation

> **Note on the unborn-branch edge case in inspector output**: when a
> repo has been initialized with `git init -b dev` (or `git init -b main`)
> but no commits yet, the inspector emits
> `{"state": "unrelated", "reason": "repo_has_no_commits",
>   "current_branch": "dev", "dev_exists": false, ...}`. The
> `current_branch` and `dev_exists` fields look contradictory at a
> glance but are both correct: `git symbolic-ref HEAD` returns the
> unborn branch name (so it's the conceptual current branch), but
> `refs/heads/dev` doesn't materialize until the first commit (so the
> ref-existence check returns false). Treat the `state` field as
> authoritative; `current_branch` and `dev_exists` are diagnostic.

Downstream automation does NOT read `.planner-state.json` (it's
gitignored — wouldn't survive merge to dev). The canonical
implementation-gate check is a **scale-tagged marker family** — system
lane keeps the original `(interfaces only, human-confirmed)` marker
plus `architecture.html`/`.mmd` files; feature lane uses
`(plan-feature, human-confirmed)` plus `plan.md`/`plan.mmd`; micro and
local use chat-history gates only. See
[implementer-contract.md](implementer-contract.md) for the full
per-lane check and SKILL.md "Implementation gate (downstream contract)"
for the canonical summary table.
