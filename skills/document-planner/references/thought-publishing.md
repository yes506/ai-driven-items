# Thought publishing — shared-memory checkpoints

The planner publishes its in-progress thinking to a shared-memory
location alongside the existing user-facing chat output and the
private (gitignored) `.document-planner-state.json`. Peer agents in
the same collaboration session can read those checkpoints and write
back free-form feedback. **Publishing is publish-and-continue: the
user remains the only confirmation gate.** Peer feedback is advisory
— the planner does not block on it.

If no collab-memory directory is detected, publishing is a silent
no-op and the skill behaves exactly as it did before this feature
existed.

## When to publish

| Phase | Topic slug | Lanes | Body |
|---|---|---|---|
| `0.5` | `triage` | all four | Discovery summary, the (scope, risk, ambiguity) tuple with reasoning, DOCTYPE classification, resolved lane, TARGET_PATH |
| `light` | `plan` | micro, local | The 3–7 bullet reflection (outline, audiences, evidence, open questions, risks) |
| `1` | `plan-ingestion` | feature, system | The normalized synthesis fenced block reflected to the user |
| `2` | `outline` | feature, system | The proposed TOC + per-section audience-and-purpose summary |
| `3` | `decomposition` | feature, system | The stub table (Mermaid reflected in chat; reference it by filename here) |
| `5` | `stubs` | feature, system | Short summary of stub count + DOCTYPE primitive; do NOT copy full 9-field bodies (they live in the worktree and would balloon the file) |
| `7` | `rubric` | feature, system | The 4-point × 6-criteria rubric scores and the human-confirmation checklist |
| `8` | `outcome` | feature, system (every prompt resolution); micro, local (confirm only — `revise` is captured by re-publishing `light/plan`) | The gate decision: `confirm plan` (and `confirm merge` if applicable), `revise`, or aborted |

The Phase L language preamble does **not** publish — it's metadata,
not thinking. The `.document-planner-state.json` write at Phase 4 is
also not republished here; it's already on disk in the worktree.

## How to publish

From any phase that owns a checkpoint:

```bash
bash "${CLAUDE_SKILL_DIR}/scripts/publish_thought.sh" "${DOCPLANNER_ID}" "<phase>" "<topic>" <<'EOF'
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
2. Writes `docplanner-<id>-phase-<phase>-<topic>.md` atomically
   (tmp + `mv -f`) so peer readers never see a half-written file.
3. Prints the resolved path on stdout (capture or discard).
4. Exits 0 silently when no session dir is found.

## `DOCPLANNER_ID` for all lanes

`DOCPLANNER_ID` is the stable handle that ties together every
checkpoint file for a single planner run. It MUST be computed at
Phase 0.5 (not Phase 4) so that micro and local lanes — which never
create a worktree — still have a unique id to tag their published
thoughts with.

```bash
DOCPLANNER_ID="$(date +%s | tail -c 6)-$$-${RANDOM}"
```

Entropy rationale: epoch tail keeps the prefix stable within a
second, `$$` distinguishes concurrent shells on a single host,
`$RANDOM` covers PID-namespaced containers where `$$` is always `1`.

For feature and system lanes, the same `DOCPLANNER_ID` is reused
verbatim when Phase 4 creates the worktree path
(`.worktrees/docplanner-<intent-slug>-<id>`) and branch
(`docplanner/<intent-slug>-<id>`). Recomputing it at Phase 4 would
split a single run across two ids in the collab-memory log.

## Idempotency under `revise`

Per-checkpoint files overwrite on republish. When a user types
`revise` and the planner re-enters a phase, the corresponding
checkpoint file is rewritten with the new content under the same
name. Peers see the *current* state, not the accumulated history.
The chat log and (for feature/system) git history remain the audit
trail.

If a peer wrote feedback on the old revision, their
`docplanner-<id>-feedback-*` file remains untouched — the planner
does not delete peer files.

## Peer-feedback convention

Peers writing feedback into the same session dir should use the
filename pattern noted at the bottom of every published checkpoint:

```
docplanner-<id>-feedback-<your-handle>-<topic>.md
```

The planner does not poll for these files (publish-and-continue),
but a user-driven `revise` can grep them on demand.

## Failure modes

| Symptom | Cause | Action |
|---|---|---|
| `publish_thought.sh` exits 0 with no stdout | No session dir found (running standalone) | Continue normally — publishing is best-effort |
| `publish_thought.sh` exits 2 | Bad arg count or empty id/phase/topic after sanitize | Fix the call site; do NOT swallow this — it's a planner bug |
| Stale session dir picked | User has multiple old `session-*` dirs and env var is unset | Suggest the user set `CANVAS_TERMINAL_COLLAB_DIR` explicitly |
| Peer-feedback file written but ignored | Expected — planner does not auto-poll | Surface to user during `revise` if asked to "incorporate peer feedback" |

## What NOT to publish

- Full stub bodies, full 9-field expansions, or anything that would
  balloon the checkpoint file beyond a few KB. Summaries + filenames
  are sufficient.
- Secrets, credentials, or absolute paths under `/Users/<name>/` —
  peers may log or forward the content. Use placeholders.
- The contents of `.document-planner-state.json` itself — peers with
  access to the worktree can read it directly.
- Anything the user explicitly asked to keep out of shared memory.
