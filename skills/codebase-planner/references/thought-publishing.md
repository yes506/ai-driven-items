# Thought publishing — shared-memory checkpoints

The planner publishes its in-progress thinking to a shared-memory location
alongside the existing user-facing chat output and the private (gitignored)
`.planner-state.json`. Peer agents in the same collaboration session can read
those checkpoints and write back free-form feedback files. **Publishing is
publish-and-continue: the user remains the only confirmation gate.** Peer
feedback is advisory — the planner does not block on it.

This is intentionally a *social* protocol, not an enforcement layer. If no
collab-memory directory is detected, publishing is a silent no-op and the
skill behaves exactly as it did before this feature existed.

## When to publish

| Phase | Topic slug | Lanes | Body |
|---|---|---|---|
| `0.5` | `triage` | all four | The discovery summary, the (scope, risk, ambiguity) tuple with reasoning, and the resolved lane |
| `light` | `plan` | micro, local | The 3–7 bullet reflection (touched files, steps, validation, risks) |
| `1` | `plan-ingestion` | feature, system | The normalized synthesis fenced block reflected to the user |
| `2` | `packages` | feature, system | The package tree + dependency-direction summary |
| `3` | `decomposition` | feature, system | The pipeline-node table (Mermaid is reflected in chat; reference it by filename here) |
| `5` | `skeletons` | system (always), feature (only when `emit skeletons` was typed) | A short summary of interfaces + method counts; do NOT copy full docstrings (they live in the worktree and would balloon the file) |
| `7` | `rubric` | feature, system | The 4-point × 6-criteria rubric scores and the human-confirmation checklist |
| `8` | `outcome` | feature, system (every prompt resolution); micro, local (confirm only — `revise` is captured by re-publishing `light/plan` at step 3) | The gate decision: `confirm plan` (and `confirm merge` if applicable), `revise`, or aborted |

The Phase L language preamble does **not** publish — it's metadata, not
thinking. The `.planner-state.json` write at Phase 4 is also not republished
here; it's already on disk in the worktree and peers can read it directly if
they have access.

## How to publish

From any phase that owns a checkpoint:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/publish_thought.sh" "${PLANNER_ID}" "<phase>" "<topic>" <<'EOF'
<body markdown>
EOF
```

The script:

1. Resolves the active session dir under a strict three-case rule (mirrors
   `scripts/publish_thought.sh` — do not weaken back to two cases or the
   "stale env var poisons wrong session" bug reintroduces):
   - `CANVAS_TERMINAL_COLLAB_DIR` **unset** → auto-detect the most-recently-modified
     `~/.cache/canvas-terminal/collab-memory/session-*/`.
   - **Set and valid** (`-d` passes) → use it verbatim.
   - **Set but invalid** (missing dir, empty string) → exit 0 silently. **Never**
     fall through to auto-detect — that silently writes to the wrong session.
2. Writes `planner-<id>-phase-<phase>-<topic>.md` atomically (tmp + `mv -f`)
   so peer readers never see a half-written file.
3. Prints the resolved path on stdout (capture or discard — the planner is not
   required to surface the path to the user; chat already contains the content).
4. Exits 0 silently when no session dir is found (auto-detect with unset/empty
   `HOME` or no `session-*` directories present).

## `PLANNER_ID` for all lanes

`PLANNER_ID` is the stable handle that ties together every checkpoint file
for a single planner run. It MUST be computed at Phase 0.5 (not Phase 4) so
that micro and local lanes — which never create a worktree — still have a
unique id to tag their published thoughts with.

```bash
PLANNER_ID="$(date +%s | tail -c 6)-$$-${RANDOM}"
```

Entropy rationale (do not weaken without checking container deployments):
the epoch tail keeps the prefix stable within a second, `$$` distinguishes
concurrent shells on a single host, and `$RANDOM` covers PID-namespaced
containers where `$$` is always `1` (so a same-second-concurrent run inside
two containers still gets distinct ids).

For feature and system lanes, the same `PLANNER_ID` is reused verbatim when
Phase 4 creates the worktree path (`.worktrees/planner-<slug>-<id>`) and
branch (`planner/<slug>-<id>`). Recomputing it at Phase 4 would split a
single run across two ids in the collab-memory log and confuse peers.

## Idempotency under `revise`

Per-checkpoint files overwrite on republish. When a user types `revise` and
the planner re-enters a phase, the corresponding checkpoint file is
rewritten with the new content under the same name. This is intentional:
peers should see the *current* state of the planner's thinking, not the
accumulated history. The chat log and (for feature/system) git history
remain the audit trail.

If a peer wrote feedback on the old revision, their `planner-<id>-feedback-*`
file remains untouched — the planner does not delete peer files.

## Peer-feedback convention

Peers writing feedback into the same session dir should use the filename
pattern noted at the bottom of every published checkpoint:

```
planner-<id>-feedback-<your-handle>-<topic>.md
```

Example: `planner-abc-123-456-feedback-claude2-phase-3-concern.md`.

The planner does not poll for these files (publish-and-continue), but a
future phase or a user-driven `revise` can grep them on demand. Peers should
include a clear verdict + reasoning so the user can decide whether to act
on the feedback.

## Failure modes

| Symptom | Cause | Action |
|---|---|---|
| `publish_thought.sh` exits 0 with no stdout | No session dir found (running standalone) | Continue normally — publishing is best-effort |
| `publish_thought.sh` exits 2 | Bad arg count or empty id/phase/topic after sanitize | Fix the call site; do NOT swallow this — it's a planner bug |
| Stale session dir picked | User has multiple old `session-*` dirs and env var is unset | Suggest the user set `CANVAS_TERMINAL_COLLAB_DIR` explicitly, or clean up old session dirs |
| Peer-feedback file written but ignored | Expected — planner does not auto-poll | Surface to user during `revise` if asked to "incorporate peer feedback" |

## What NOT to publish

- Full method bodies, full docstrings, or anything that would balloon the
  checkpoint file beyond a few KB. Summaries + filenames are sufficient.
- Secrets, credentials, or absolute paths under `/Users/<name>/` — peers may
  log or forward the content. Use placeholders.
- The contents of `.planner-state.json` itself — peers with access to the
  worktree can read it directly.
- Anything the user explicitly asked to keep out of shared memory. The user
  remains in control.
