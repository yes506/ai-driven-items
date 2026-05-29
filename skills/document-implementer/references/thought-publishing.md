# Thought publishing — shared-memory checkpoints

The implementer publishes its in-progress thinking to a shared-memory
location alongside the user-facing chat output and the private
(gitignored) `.document-implementer-state.json`. Peer agents in the
same collaboration session can read those checkpoints and write back
free-form feedback. **Publishing is publish-and-continue: the user
remains the only confirmation gate.** Peer feedback is advisory — the
implementer does not block on it.

If no collab-memory directory is detected, publishing is a silent
no-op and the skill behaves exactly as it did before this feature
existed.

## When to publish

| Phase | Topic slug | Body |
|---|---|---|
| `0` | `marker-verify` | Inspector JSON + chosen SCALE + frontmatter or chat-handoff fields parsed |
| `1` | `work-queue` | Item count by status; first/last item ids; any TARGET_PATH precondition outcome |
| `2` | `worktree` | Created path + branch name; baseline state file write summary |
| `3` | `progress` | Republished after each commit batch — items completed since last publish, dep_context_degraded summary |
| `3` | `blocker` | On any blocker mid-queue — blocker_reason + implicated item id |
| `4` | `validate` | Per-validator exit code; auto-fix attempts used + outcome |
| `5` | `report` | The implementation-report.md path (committed) + summary line count |
| `6` | `outcome` | Gate decision (`confirm merge` / `revise` / `keep` / aborted); marker landed (if confirm merge) |

The Phase L language preamble does NOT publish — it's metadata, not
thinking. The `.document-implementer-state.json` write at Phase 2 is
also not republished here; it's already on disk in the worktree.

## How to publish

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/publish_thought.sh" "${DOCIMPL_ID}" "<phase>" "<topic>" <<'EOF'
<body markdown>
EOF
```

The script:

1. Resolves the active session dir under a strict three-case rule:
   - `CANVAS_TERMINAL_COLLAB_DIR` **unset** → auto-detect the
     most-recently-modified
     `~/.cache/canvas-terminal/collab-memory/session-*/`.
   - **Set and valid** (`-d` passes) → use it verbatim.
   - **Set but invalid** → exit 0 silently. **Never** fall through to
     auto-detect — that would silently write to the wrong session.
2. Writes `docimpl-<id>-phase-<phase>-<topic>.md` atomically
   (tmp + `mv -f`) so peer readers never see a half-written file.
3. Prints the resolved path on stdout (capture or discard).
4. Exits 0 silently when no session dir is found.

## `DOCIMPL_ID` for all lanes

`DOCIMPL_ID` is the stable handle that ties together every
checkpoint file for a single implementer run. Computed at Phase 2
(not earlier — Phases 0–1 may refuse before reaching mutation).

```bash
DOCIMPL_ID="$(date +%s | tail -c 6)-$$-${RANDOM}"
```

Entropy rationale: epoch tail keeps the prefix stable within a
second, `$$` distinguishes concurrent shells on a single host,
`$RANDOM` covers PID-namespaced containers where `$$` is always `1`.

`DOCIMPL_ID` is reused verbatim when Phase 2 creates the worktree
path (`.worktrees/docimpl-<intent-slug>-<id>`) and branch
(`docimpl/<intent-slug>-<id>`). Recomputing it would split a single
run across two ids in collab-memory.

## Idempotency under `revise`

Per-checkpoint files overwrite on republish. When a user types
`revise` and the implementer re-enters a phase, the corresponding
checkpoint file is rewritten with the new content under the same
name. Peers see the *current* state, not accumulated history. The
chat log and git history remain the audit trail.

If a peer wrote feedback on the old revision, their
`docimpl-<id>-feedback-*` file remains untouched — the implementer
does not delete peer files.

## Peer-feedback convention

Peers writing feedback into the same session dir should use the
filename pattern noted at the bottom of every published checkpoint:

```
docimpl-<id>-feedback-<your-handle>-<topic>.md
```

The implementer does not poll for these files
(publish-and-continue), but a user-driven `revise` can grep them on
demand.

## Failure modes

| Symptom | Cause | Action |
|---|---|---|
| `publish_thought.sh` exits 0 with no stdout | No session dir found (standalone) | Continue normally — publishing is best-effort |
| `publish_thought.sh` exits 2 | Bad arg count or empty id/phase/topic after sanitize | Fix the call site; do NOT swallow — it's an implementer bug |
| Stale session dir picked | User has multiple old `session-*` dirs + env var unset | Suggest user set `CANVAS_TERMINAL_COLLAB_DIR` explicitly |
| Peer-feedback file written but ignored | Expected — implementer does not auto-poll | Surface to user during `revise` if asked to "incorporate peer feedback" |

## What NOT to publish

- Full generated prose / slide bodies — would balloon the
  checkpoint file beyond a few KB. Summaries + counts are
  sufficient.
- Secrets, credentials, absolute paths under `/Users/<name>/` —
  peers may log or forward the content. Use placeholders.
- The full contents of `.document-implementer-state.json` —
  peers with worktree access can read it directly.
- Anything the user explicitly asked to keep out of shared memory.

## Relationship to planner publishes

Both `docplanner-<id>-phase-*-*.md` (planner) and
`docimpl-<id>-phase-*-*.md` (implementer) coexist in the same
session dir. They are distinguished by filename prefix; peers
reading both can correlate planner-implementer pairs by the chat
context but not by id (the two IDs are independently generated).
