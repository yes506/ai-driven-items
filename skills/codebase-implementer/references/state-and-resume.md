# `.implementer-state.json` — schema and resume

The state file lives at the worktree root and is **gitignored** on the
implementer branch (per Phase 2 worktree-creation step 3). It is
local-only working state, updated incrementally so a mid-run failure
stays resumable. It is NEVER committed.

**Write deferral**: Phases 0 and 1 hold their captured values in
memory only. The state file is first written at the **end of Phase
2**, after the worktree directory exists. This prevents a Phase 0 or
Phase 1 crash from leaving a stray `.implementer-state.json` on the
main checkout (where it is not gitignored and would dirty `git
status` on `${BASE_BRANCH}`).

The canonical confirmation record on the implementer branch is the
Phase 5 commit of the report (`${RUN_DIR}/report.${IMPLEMENTER_ID}.md`)
plus the Phase 6 merge
commit message `feat(implementer): merge <slug> (impl-<scale>,
human-confirmed)`. Downstream automation (CI, review skills) reads
those, not this file.

## Schema

```json
{
  "scale": "micro | local | feature | system",
  "language": "Korean | English (captured at Phase L; written for the first time when this state file is created at Phase 2; absent value on resume defaults to Korean)",
  "planner_marker_scale": "micro | local | feature | system",
  "planner_marker_commit": "string (sha — empty for micro/local since they have no commit)",
  "planner_artifact_dir": "string (feature/system: the trailer-resolved run-dir, e.g. 'ai-artifacts/runs/code/<slug>-<planner-id>'; micro/local: the implementer's own id-keyed sibling dir 'ai-artifacts/runs/code/<slug>-impl-<implementer-id>'. On resume, reuse this rather than re-resolving the newest marker)",
  "planner_artifact_paths": ["plan.md", "plan.mmd (run-dir-relative — join under planner_artifact_dir)"],
  "source_hash": "sha256 of the concatenated planner artifacts (or chat block for micro/local)",
  "project_slug": "string (kebab-case ascii, used in worktree path + branch name)",
  "main_checkout": "absolute path to main worktree (physical, symlinks resolved)",
  "base_branch": "string (default: dev)",
  "implementer_id": "string (e.g. '12345-67890-12345')",
  "language_stack": "java | python | typescript | javascript | go | rust",
  "validation_command": "string (the actual command, with <package> already substituted)",
  "baseline_validation_exit": "int (exit code of validation_command on BASE_BRANCH before any change; 0 means baseline-clean)",
  "max_autofix_attempts": "int (default 3; reduced to 1 if validation is slow)",
  "phase_completed": "marker_verified | queue_extracted | worktree_created | impl_in_progress | impl_done | validated | report_emitted | human_confirmed",
  "work_queue": [
    {
      "item_id": "string (e.g. 'OrderRepository.save' or 'step-3' or 'bullet-1')",
      "kind": "method-body | plan-step | plan-bullet",
      "status": "pending | in_progress | completed | blocked",
      "blocker_reason": "string (only when status=blocked)",
      "files_touched": ["array of relative paths edited for this item"],
      "started_at": "ISO-8601 (only after status leaves pending)",
      "completed_at": "ISO-8601 (only when status=completed)",
      "spec_payload": "{...item-shape per work-queue-extraction.md...}"
    }
  ],
  "validation_runs": [
    {
      "attempt": "int (1-based; 0 is baseline)",
      "exit_code": "int",
      "duration_seconds": "int",
      "tail_lines": ["last 20 lines of stderr+stdout"],
      "fix_summary": "string (one-line description of what was changed for this attempt; empty for baseline)"
    }
  ]
}
```

## Report path (Phase 5 producer)

The self-verification report is written under `ai-artifacts/` inside the
worktree and merges via the normal Phase 6 worktree merge for **all**
lanes (no carve-out). Resolve the directory by lane:

```bash
case "${SCALE}" in
  # feature/system: reuse the trailer-resolved run-dir.
  feature|system) REPORT_DIR="${RUN_DIR}" ;;
  # micro/local: no planner run-dir → self-keyed sibling dir. <slug> is
  # the sanitized PROJECT_SLUG already computed at Phase 2.
  micro|local)    REPORT_DIR="ai-artifacts/runs/code/${PROJECT_SLUG}-impl-${IMPLEMENTER_ID}" ;;
esac
REPORT_PATH="${REPORT_DIR}/report.${IMPLEMENTER_ID}.md"
mkdir -p "${REPORT_DIR}"   # idempotent
```

For micro/local, persist `REPORT_DIR` into the state field
`planner_artifact_dir` (the lane has no planner-resolved dir of its
own) so resume reuses the same report location instead of minting a new
`IMPLEMENTER_ID`-keyed dir.

## Write discipline (incremental)

The state file is written after EACH of these sub-steps. Anything less
risks resume losing track of in-flight work.

| Sub-step | What's written |
|---|---|
| Phase 0 done | **in memory only** — `scale`, `planner_marker_*`, `planner_artifact_dir`, `planner_artifact_paths`, `source_hash` |
| Phase 1 done | **in memory only** — `work_queue` (all items, status=pending), tentative `language_stack`, tentative `validation_command` |
| Phase 2 done | **first on-disk write** — flushes all in-memory values plus `project_slug`, `main_checkout`, `base_branch`, `implementer_id`, `baseline_validation_exit`, `max_autofix_attempts`; `phase_completed: worktree_created` |
| Phase 3 per item start | `work_queue[i].status: in_progress`, `started_at` |
| Phase 3 per item end | `work_queue[i].status: completed/blocked`, `files_touched`, `completed_at` (or `blocker_reason`) |
| Phase 3 done | `phase_completed: impl_done` (or `impl_in_progress` if blocked) |
| Phase 4 per attempt | `validation_runs[]` append |
| Phase 4 done | `phase_completed: validated` |
| Phase 5 done | `phase_completed: report_emitted` |
| Phase 6 confirm | `phase_completed: human_confirmed` |

A Phase-0 or Phase-1 crash therefore leaves NO on-disk trace; the
user simply re-invokes `/codebase-implementer` and the earlier work
is recomputed from the planner artifacts (cheap because both phases
are read-only).

## Resume map

When Phase 0 detects `inside-implementer-worktree`:

1. **Verify the worktree is registered.** Run `git -C
   "${MAIN_CHECKOUT}" worktree list --porcelain` and confirm the
   current path is listed. This defends against a hand-staged
   `.worktrees/implementer-fake/` directory dropped in to trick
   path-prefix detection. If not registered: refuse.
2. Read `.implementer-state.json`. If absent → refuse, ask user to
   either delete the worktree or supply a state file.
3. **Validate the loaded state file structurally** before trusting it:
   `scale` ∈ {micro, local, feature, system}; `phase_completed` ∈ the
   documented enum; `main_checkout` resolves to an existing directory
   that is itself a git worktree top; `base_branch` is a non-empty
   string. On any failure → refuse with a clear "state file is
   corrupt or hostile" message. Do NOT attempt to repair.
4. Check `source_hash` against the current planner artifacts (read
   them from the persisted `planner_artifact_dir` — do NOT re-resolve
   the newest marker).
   - If mismatch: blocker — planner artifacts changed since extraction.
     Surface diff, ask user whether to re-extract (discards in-progress
     impl) or abort.
5. Resume per `phase_completed`:

| `phase_completed` | Resume from |
|---|---|
| `marker_verified` | (should be unreachable — Phase 0 never persists this; if present, treat as a corrupted/hand-crafted state file and refuse per step 3) |
| `queue_extracted` | (same — Phase 1 holds in memory, so this value should not be on disk; refuse) |
| `worktree_created` | Phase 3, queue position 0 |
| `impl_in_progress` | Phase 3, **next pending item** in `work_queue`. Skip `completed`. Treat `in_progress` items (left-over from a crash mid-item) as `pending` and re-run them — Phase 3 is idempotent per item for `method-body` items (Edit/Write overwrites). **Idempotency caveat for `plan-step` and `plan-bullet` items**: if the action was non-overwriting (append to a list, insert a migration entry, modify config) and the user manually completed the item between the crash and resume, the auto-rerun will double-apply. If `in_progress` items appear on resume AND any have `kind != method-body`, surface them as a question instead of auto-rerunning: "These items were in-progress at crash time and may have been completed manually: [...]. Resume (re-runs) or skip (mark completed) per item?". Surface `blocked` items as a single question batch ("blocker reasons were X, Y; resolve and type `resume` to re-queue them as pending"). |
| `impl_done` | Phase 4 |
| `validated` | Phase 5 |
| `report_emitted` | Phase 6 |
| `human_confirmed` | already merged or merge-pending. If merge already happened (check `git log` for the impl marker on `${BASE_BRANCH}`): nothing to do, exit. Else re-prompt Phase 6. |

6. **Don't re-do completed items.** The whole point of the per-item
   state writes is that resume picks up where we stopped.

## What this file does NOT cover

- Per-item full LLM output (too large; would balloon the state file).
  Save reasoning to chat / model thinking only.
- Per-item full diff (recoverable from `git diff` against the prior
  commit on the implementer branch — don't duplicate).
- User identity / timestamps for audit. The merge commit and any
  squashed prior commits carry git's own author info — don't shadow it.
