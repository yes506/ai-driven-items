# `.architect-state.json` — schema and resume

The state file lives at the worktree root and is **gitignored** on the
architect branch (per Phase 4 step 3). It is local-only working state,
updated **incrementally** after each Phase sub-step so any mid-run
failure stays resumable. It is NEVER committed; Phase 8's
human-confirmation marker lives in the architecture artifacts
(`architecture.html`, `architecture.mmd`) and the merge commit
message, not in this file. See SKILL.md "Implementation gate
(downstream contract)" for the canonical gate check.

## Schema

```json
{
  "project_slug": "string (kebab-case ascii, used in worktree path + branch name)",
  "main_checkout": "absolute path to the main worktree (physical, symlinks resolved)",
  "base_branch": "string (default: dev; configurable when dev doesn't exist)",
  "architect_id": "string (e.g. '12345-67890' — `date +%s | tail -c 6`-`$$`)",
  "language_stack": "java | python | typescript | go | rust",
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
  "rubric_scores": {
    "decomposition_completeness": "int 1-4",
    "docstring_quality": "int 1-4",
    "interface_cohesion": "int 1-4",
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
| `decomposition_done` | Phase 5 (skeleton) |
| `skeleton_written` | Phase 6 (validate) |
| `validated` | Phase 7 (artifacts) |
| `artifacts_emitted` | Phase 8 (human gate) |
| `human_confirmed` | Phase 8 (merge offer) — re-prompt for `confirm merge` |

If `inside-architect-worktree` but no state file → refuse and ask the
user to either delete the worktree or supply a state file.

If the state file exists but `phase_completed` is missing or invalid →
refuse, surface the file contents, and ask the user to repair or
discard.

## Update discipline

After each sub-step, write the file atomically (so a crash mid-write
can't corrupt it):

```bash
tmp="$(mktemp)"
jq '. + {phase_completed: "skeleton_written"}' .architect-state.json > "$tmp"
mv "$tmp" .architect-state.json
```

The file is gitignored, so the temp-file dance doesn't dirty git status.
If `jq` is unavailable, fall back to writing the JSON directly via a
language-native writer (Python: `json.dump`).

## Read by downstream automation

Downstream automation does NOT read `.architect-state.json` (it's
gitignored — wouldn't survive merge to dev). The canonical
implementation-gate check looks at the **tracked** architecture
artifacts and the architect-merge commit on the current branch:

```bash
test -f architecture.html && test -f architecture.mmd \
  && git log --grep='(interfaces only, human-confirmed)' \
       --format=%H | grep -q .
```

See SKILL.md "Implementation gate (downstream contract)" for the full
contract, including its honest forgeability limitations.
