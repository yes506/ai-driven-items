# State and resume — `.document-implementer-state.json`

Per-run persistent record for the implementer. Gitignored at both
repo level (the `.worktrees/` parent-level exclude) and worktree
level (Phase 2 step 2 appends to the worktree's `.gitignore`). Never
lands on `${BASE_BRANCH}`.

## Schema

```json
{
  "schema_version": 1,
  "docimpl_id": "<stable id from Phase 2>",
  "intent_slug": "<sanitized slug>",
  "main_checkout": "<absolute path>",
  "base_branch": "<default: dev>",
  "language": "Korean | English",

  "scale": "micro | local | feature | system",
  "doctype": "api-spec | tech-spec | runbook | ppt",
  "output_stack": "text | structured",
  "audience": "<from planner contract>",
  "output_language": "Korean | English",
  "target_path": "<from planner contract>",

  "planner_marker_scale": "<scale>",
  "planner_marker_commit": "<sha or empty for micro/local>",
  "planner_artifact_dir": "<resolved RUN_DIR under ai-artifacts/runs/doc/ for feature/system; empty for micro/local>",
  "report_slug": "<sanitized TARGET_PATH/project basename; used for the micro/local report sibling dir>",
  "source_hash": "<sha256 over planner artifacts at Phase 1>",

  "max_autofix_attempts": 3,

  "work_queue": [
    {
      "item_id": "<stub-id or bullet-N>",
      "kind": "stub-prose | bullet-prose",
      "status": "pending | in_progress | completed | blocked",
      "source_lineno": 42,
      "spec_payload": { /* 9 fields for stub-prose; 3 fields for bullet-prose */ },
      "generated_content": "<text for backward-dep lookup>",
      "files_touched": ["<paths>"],
      "dep_context_degraded": ["<dep-id>"],
      "blocker_reason": "<text or empty>",
      "started_at": "<ISO-8601>",
      "completed_at": "<ISO-8601>"
    }
  ],

  "validation_runs": [
    {
      "attempt": 1,
      "ts": "<ISO-8601>",
      "validators_run": ["..."],
      "exit_codes": [0, 1, 0],
      "implicated_items": ["<stub-id>"],
      "tail": "<200-line capped output>"
    }
  ],

  "phase_completed": "<see phase mapping below>",

  "human_confirmation": {
    "reviewer": "<chat handle or empty>",
    "confirmed_at": "<ISO-8601 or empty>"
  }
}
```

## `phase_completed` values + resume map

| Value | Set at | Resume from |
|---|---|---|
| `worktree_created` | Phase 2 step 3 (initial write) | Phase 3 (generation loop) |
| `impl_in_progress` | Phase 3 on blocker mid-queue | Phase 3 next pending item after blocker resolved |
| `impl_done` | Phase 3 when queue is empty | Phase 4 (validate) |
| `validated` | Phase 4 on success | Phase 5 (report) |
| `report_emitted` | Phase 5 after commit | Phase 6 (human gate) |
| `human_confirmed` | Phase 6 on `confirm merge` | Phase 6 merge sub-step (re-print the prompt) |

## Resume flow

When Phase 0 detects `inside-document-implementer-worktree`:

1. Cross-verify the path appears in
   `git -C "${MAIN_CHECKOUT}" worktree list --porcelain` (defends
   against a hand-staged `.worktrees/docimpl-*` directory that
   isn't a real registered worktree). If unregistered: refuse.
2. Read `.document-implementer-state.json`. If missing or unreadable:
   refuse — ask the user to either remove the worktree
   (`git worktree remove`, NOT `--force`) or supply a state file.
3. Recompute `source_hash` over the merged-branch planner artifacts.
   If it differs from the stored `source_hash`: **blocker** — the
   planner was re-run since extraction. Ask the user:
   - re-extract (discards in-progress impl + re-runs Phase 1), OR
   - abort (leave worktree intact; user investigates manually).
4. Restore in-memory state from the JSON (LANGUAGE, work queue,
   validation runs, etc.). **Reuse the persisted `planner_artifact_dir`
   as `RUN_DIR`** — do NOT re-resolve the newest marker on resume (a
   newer planner run must not silently re-target a mid-flight
   implementer). For micro/local, restore `report_slug`.
5. Dispatch to the next phase per the resume map.

## Incremental write strategy

`.document-implementer-state.json` is rewritten **atomically** (tmp
file + `mv -f`) at:

- Phase 2 step 3 (initial)
- Phase 3 after each work-queue item completion + after each commit
- Phase 4 after each validation run
- Phase 5 after report commit
- Phase 6 on `human_confirmed`

```bash
write_state() {
  local tmp="${PWD}/.document-implementer-state.json.tmp.$$"
  cat > "${tmp}" <<EOF
<JSON body>
EOF
  mv -f "${tmp}" "${PWD}/.document-implementer-state.json"
}
```

This makes a mid-Phase-3 crash leave the planner resumable from the
last completed stub, not from the beginning of Phase 3.

## Worktree creation edge cases

See [git-worktree-flow.md](git-worktree-flow.md) for the full list.
Summary:

- **Path collision** (`.worktrees/docimpl-…` already exists): refuse;
  ask user to remove or recompute `DOCIMPL_ID`.
- **Dirty `BASE_BRANCH`** at Phase 2: `git worktree add` fails;
  surface verbatim; do NOT auto-stash.
- **Nested invocation** (running from inside another implementer
  worktree but with a different intent_slug): refuse; the inspector
  classifies as `inside-document-implementer-worktree` and resume
  expects matching state.
- **Untracked files on resume**: surface before resuming; don't
  auto-`git clean`.
- **Merge conflicts at Phase 6**: print conflict status; leave
  worktree intact; ask user to resolve manually.

## On-default-needs-dev (planner-side concern)

If Phase 0 returns `on-default-needs-dev`, the implementer refuses
unconditionally: "No `dev` branch. Re-run `/document-planner` from a
proper `dev` setup." The implementer does NOT auto-create `dev` —
the planner is the right skill for that bootstrap.

## Source-hash computation (Phase 1)

Use a portable wrapper — `sha256sum` is Linux-default but macOS ships
`shasum -a 256` instead. Fall back transparently:

```bash
sha256_portable() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum
  else
    shasum -a 256
  fi
}

case "${SCALE}" in
  feature|system)
    # Hash the union of planner artifacts on the merged branch.
    SOURCE_HASH="$(
      {
        cat "${RUN_DIR}/document-plan.md" "${RUN_DIR}/document-structure.mmd" 2>/dev/null
        [ "${SCALE}" = "system" ] && cat "${RUN_DIR}/document-structure.html" 2>/dev/null
      } | sha256_portable | cut -c1-12)"
    ;;
  micro|local)
    # No on-disk source; agent records chat state.
    SOURCE_HASH="chat-only"
    ;;
esac
```

Stored in state.json. Re-checked on resume per "Resume flow" step 3.
For micro/local, `source_hash = chat-only` is a sentinel; resume
from a fresh session is refused because the chat-gate can't be
re-verified.
