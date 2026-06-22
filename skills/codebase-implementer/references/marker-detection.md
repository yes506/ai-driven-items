# Upstream planner marker — per-scale gate verification

The implementer refuses to start without a confirmed `codebase-planner`
handoff. This file is the authoritative checklist for that gate. The
upstream contract is owned by the planner skill and is shipped inside
its skill folder as `references/implementer-contract.md` (co-located
when both skills are installed). This file is the implementer-side
mirror; if the two files ever drift, **the planner's contract wins**
for marker family and gate semantics.

## Marker family (accepted)

| Scale | Marker (verbatim) | Where to find it |
|---|---|---|
| micro | `(plan-micro, human-confirmed)` | chat history only |
| local | `(plan-local, human-confirmed)` | chat history only |
| feature | `(plan-feature, human-confirmed)` | merge commit on `${BASE_BRANCH}` |
| system | `(interfaces only, human-confirmed)` | merge commit on `${BASE_BRANCH}` (preserved verbatim from pre-rename `codebase-architect` for backward compat — this is the canonical system marker, not a deprecated form) |

The `(interfaces only, human-confirmed)` marker is **load-bearing for
backward compat** — any chain that already grep'd for it continues to
work after the rename, and the planner continues to emit it for the
system lane. Treat it as `scale == system`.

## Gate check — feature + system (commit-based)

The inspector script (`scripts/inspect_repo_state.sh`) extracts the
most-recent marker into `planner_marker_scale` and `planner_marker_commit`
from `git log --branches`. The inspector scans for ALL four scale
markers, but per the contract above, **only `feature` and `system`
markers are valid as commits**. If `planner_marker_scale` is `micro` or
`local`, the implementer must refuse with: "found a `(plan-<scale>,
human-confirmed)` commit, but `${scale}` is chat-only per the contract
— refusing to honor the commit-based marker. The presence of such a
commit indicates a forged or hand-crafted marker; re-run the planner
if this was intentional." If `planner_marker_scale` is empty AND the
chat-history check (below) also fails, refuse to proceed.

### Run-dir resolution via git trailer (feature + system)

The inspector's marker scan emits hash+ts+subject only
(`--format='%H%x09%ct%x09%s'`) and never reads the commit body, so the
run-dir is resolved with a SECOND lookup once `PLANNER_MARKER_COMMIT`
is chosen. The planner's landing merge carries the run-dir as a git
trailer `AI-Artifacts-Run-Dir:`; parse it, count matches, and refuse
unless exactly one is present (do NOT `tail -1`):

```bash
RUN_DIR_LINES="$(git -C "${MAIN_CHECKOUT}" show -s --format=%B "${PLANNER_MARKER_COMMIT}" \
  | git interpret-trailers --parse \
  | grep '^AI-Artifacts-Run-Dir:' || true)"
N="$(printf '%s' "${RUN_DIR_LINES}" | grep -c . )"
[ "${N}" -eq 1 ] || { echo "expected exactly 1 AI-Artifacts-Run-Dir trailer, found ${N} — refusing"; exit 1; }
# Strip the key (and surrounding whitespace) → bare run-dir value.
RUN_DIR="$(printf '%s' "${RUN_DIR_LINES}" | sed -e 's/^AI-Artifacts-Run-Dir:[[:space:]]*//' -e 's/[[:space:]]*$//')"
# ANCHORED, single-line, code-chain allowlist. Rejects absolute paths,
# '..', and any embedded newline/CR/whitespace (the [a-z0-9-]+ slug and
# [A-Za-z0-9._-]+ planner-id segments contain none of those).
printf '%s' "${RUN_DIR}" | grep -Eqx '^ai-artifacts/runs/code/[a-z0-9-]+-[A-Za-z0-9._-]+$' \
  || { echo "run-dir trailer failed code-chain allowlist: ${RUN_DIR}"; exit 1; }
```

`grep -Eqx` anchors the whole string (`-x`) so a value carrying an
embedded newline cannot pass by matching only its first line.

Then verify the per-scale artifacts exist **at the marker commit's
tree** (`git cat-file -e "<commit>:<path>"`) — NOT at the worktree
`HEAD`, which may have drifted since the planner landed:

```bash
case "${PLANNER_MARKER_SCALE}" in
  system)
    git cat-file -e "${PLANNER_MARKER_COMMIT}:${RUN_DIR}/architecture.html" 2>/dev/null \
      && git cat-file -e "${PLANNER_MARKER_COMMIT}:${RUN_DIR}/architecture.mmd" 2>/dev/null \
      || { echo "system marker present but architecture.{html,mmd} missing at ${RUN_DIR}"; exit 1; }
    ;;
  feature)
    git cat-file -e "${PLANNER_MARKER_COMMIT}:${RUN_DIR}/plan.md" 2>/dev/null \
      && git cat-file -e "${PLANNER_MARKER_COMMIT}:${RUN_DIR}/plan.mmd" 2>/dev/null \
      || { echo "feature marker present but plan.{md,mmd} missing at ${RUN_DIR}"; exit 1; }
    ;;
esac
```

Persist the resolved dir as state field `planner_artifact_dir`. On any
failure above (zero/multiple trailers, allowlist rejection, missing
artifact at the marker tree) on a feature/system marker → **REFUSE.
Never fall back to a project-root path.** Treat a missing artifact as a
**tampered or partially reverted** planner run — refuse and ask the
user to either re-run the planner or restore the artifact files. Do NOT
silently downgrade to a lower scale.

micro/local lanes have no planner commit and therefore no trailer — the
run-dir is not resolved here; the implementer uses its own id-keyed
sibling dir (see SKILL.md Phase 5).

## Gate check — micro + local (chat-based)

These scales emit no commit and no file. The implementer must verify
the **current conversation context** contains BOTH:

1. A planner-emitted block tagged with `scale: micro` or `scale: local`
   (the planner prints this verbatim when entering its hand-off step)
   AND
2. A user confirmation token (`confirm plan` typed by the user in chat)
   that appears AFTER the planner block in the same conversation.

**Same-session requirement (load-bearing)**: both signals must be
visible in the implementer's current rendered conversation. The
chat-only gate is the weakest link in the marker family precisely
because chat content is not committed and not signed; the only
defenses are temporal (same-session) and behavioral (user
typing). Specifically:

- A pasted transcript of a previous session does NOT satisfy the
  gate. If the user pastes text that looks like a planner block
  followed by `confirm plan`, refuse — the planner block must come
  from an actual `/codebase-planner` invocation in this session.
- A verbal "I ran planner earlier and confirmed it" does NOT satisfy
  the gate. Refuse politely and ask the user to re-run.
- If invoked in a fresh session (no visible planner history): the
  gate fails. Tell the user: "no in-chat planner handoff visible —
  re-run `/codebase-planner` in this session, OR (if the plan exists
  as a file/PR/Notion) escalate the planner to the `feature` lane so
  the handoff lands on disk."

This is a documented social contract, not cryptographic — the same
"honest limitation" applies as below.

## Conflict cases

### Multiple markers in recent history

The repo has both a `(plan-feature, human-confirmed)` and a
`(interfaces only, human-confirmed)` marker landed within the last few
commits. The inspector picks the newest by `committer-date`
(`%ct`). The implementer should additionally confirm with the user:
"Two planner outputs are present; the newest is `<scale>` from
`<commit short-sha>`. Implement against that one?" — silence is not
yes. This catches the rare case where the user merged two plans
intending to implement the older one.

### Stale marker, hand-edited code since

`git log --grep` returns a marker commit, but `git diff
${PLANNER_MARKER_COMMIT}..HEAD` shows unrelated changes to the planned
files. Surface the diff to the user before starting; ask
"Implement against the original plan, or re-plan first?" — do not
silently overwrite the hand-edits.

### Implementer-marker already present for this plan

`implementer_marker_present` from the inspector is `true`. Check whether
the existing impl-marker commit corresponds to THIS planner marker
(same `project-slug` in the merge subject). If yes, warn: "This plan
appears to already be implemented at `<impl commit>`. Re-running will
produce a new branch off the current base — proceed only if you
intend to revise." Default to refusal; require explicit `proceed` token.

## What this gate does NOT cover

- **Plan freshness**: the gate doesn't measure how stale the plan is
  versus the codebase. The implementer's Phase 1 (plan ingestion) does
  a diff-from-marker scan as a sanity check.
- **Plan correctness**: the gate verifies a human typed `confirm plan`,
  not that the plan is sound. Body-generation will surface gaps as
  blockers.
- **Cryptographic provenance**: per the planner's "Honest limitations"
  section — markers and files can be hand-forged. Layer signed commits
  / external attestation on top if your project needs it.
