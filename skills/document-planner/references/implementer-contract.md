# Implementer contract — downstream gate per lane

Skills, subagents, and Claude sessions that intend to write
**document prose / slides** based on a `document-planner` run MUST
honor the scale-tagged marker family below. This is the contract
`document-implementer` (future) is built against.

The marker family is a **new choice** for document-planner — it does
NOT inherit codebase-planner's legacy `(interfaces only,
human-confirmed)` system marker (which exists for backward
compatibility with the pre-rename `codebase-architect`).
`document-implementer` greps for `document-plan-*` family only.

## Marker family

All markers follow the form `(document-plan-<scale>, human-confirmed)`
and appear verbatim either in the merge commit message that lands the
docplanner branch on `${BASE_BRANCH}` (feature/system) or in the
chat-handoff block (micro/local).

| Scale | Marker | Where it lives | Artifacts that satisfy the gate |
|---|---|---|---|
| micro | `(document-plan-micro, human-confirmed)` | chat history only — no commit | chat-handoff block + in-chat confirmation token |
| local | `(document-plan-local, human-confirmed)` | chat history only — no commit | chat-handoff block + in-chat confirmation token |
| feature | `(document-plan-feature, human-confirmed)` | merge commit on `${BASE_BRANCH}` | `$RUN_DIR/document-plan.md` + `$RUN_DIR/document-structure.mmd` committed on the merged branch |
| system | `(document-plan-system, human-confirmed)` | merge commit on `${BASE_BRANCH}` | `$RUN_DIR/document-plan.md` + `$RUN_DIR/document-structure.mmd` + `$RUN_DIR/document-structure.html` committed on the merged branch |

## Canonical metadata source (feature + system)

`$RUN_DIR/document-plan.md` carries a YAML frontmatter block at the top with
`doctype`, `output_stack`, `audience`, `output_language`,
`target_path`, `scale`, `intent_slug`, `docplanner_id`. Spec +
boundary checks: [state-and-resume.md](state-and-resume.md). The
implementer parses the frontmatter via `parse_frontmatter.py` (bundled
stdlib-only scalar parser; no PyYAML). Absence or malformed
frontmatter is an implementer-side refusal.

Validate the frontmatter against the **marker-tree blob**
(`${PLANNER_MARKER_COMMIT}:${RUN_DIR}/document-plan.md`), **never the
live worktree path** — the worktree may have advanced past the marker
commit, so a HEAD-bound read can false-refuse a valid marker or
false-pass a corrected-since-marker file. `parse_frontmatter.py` takes a
file path, so extract the blob with `git cat-file -p` first (see the gate
snippet below; the implementer mirror in
`document-implementer/references/marker-detection.md` ships the same
binding).

## Canonical gate check (feature + system)

The run-dir is NOT a fixed path — it is carried by the
`AI-Artifacts-Run-Dir:` git trailer on the marker merge commit. The
document-implementer first scans `git log` for the marker, then reads
the trailer off the marker commit to resolve `$RUN_DIR`:

```bash
# 1. find the marker commit (subject grep). Feature lane shown; for the
#    system lane use the -system grep AND set SCALE=system. (A real
#    implementer derives SCALE from the inspector's marker scan.)
PLANNER_MARKER_COMMIT="$(git -C "${MAIN_CHECKOUT}" log \
  --grep='(document-plan-feature, human-confirmed)' --format=%H | head -1)"
SCALE=feature

# 2. resolve the run-dir from the SECOND -m (git trailer) on that commit
TRAILER="$(git -C "${MAIN_CHECKOUT}" show -s --format=%B "${PLANNER_MARKER_COMMIT}" \
  | git interpret-trailers --parse | grep '^AI-Artifacts-Run-Dir:' || true)"
[ "$(printf '%s' "${TRAILER}" | grep -c .)" -eq 1 ] \
  || { echo "BLOCKER: expected exactly 1 AI-Artifacts-Run-Dir trailer"; exit 1; }   # never tail -1
RUN_DIR="$(printf '%s' "${TRAILER}" | sed 's/^AI-Artifacts-Run-Dir: *//')"
printf '%s' "${RUN_DIR}" | grep -Eqx '^ai-artifacts/runs/doc/[a-z0-9-]+-[A-Za-z0-9._-]+$' \
  || { echo "BLOCKER: run-dir failed allowlist"; exit 1; }   # rejects absolute, '..', whitespace

# 3. verify per-lane artifacts exist at the MARKER COMMIT's tree (not HEAD).
#    Branch by ${SCALE} so a verbatim copy checks only the lane's artifacts —
#    a single sequential block would false-fail a valid feature run on the
#    system-only document-structure.html.
case "${SCALE}" in
  feature)
    git cat-file -e "${PLANNER_MARKER_COMMIT}:${RUN_DIR}/document-plan.md" 2>/dev/null \
      && git cat-file -e "${PLANNER_MARKER_COMMIT}:${RUN_DIR}/document-structure.mmd" 2>/dev/null \
      || { echo "BLOCKER: document-plan.md/document-structure.mmd missing at ${PLANNER_MARKER_COMMIT}:${RUN_DIR}"; exit 1; }
    ;;
  system)
    git cat-file -e "${PLANNER_MARKER_COMMIT}:${RUN_DIR}/document-plan.md" 2>/dev/null \
      && git cat-file -e "${PLANNER_MARKER_COMMIT}:${RUN_DIR}/document-structure.mmd" 2>/dev/null \
      && git cat-file -e "${PLANNER_MARKER_COMMIT}:${RUN_DIR}/document-structure.html" 2>/dev/null \
      || { echo "BLOCKER: document-plan.md/document-structure.{mmd,html} missing at ${PLANNER_MARKER_COMMIT}:${RUN_DIR}"; exit 1; }
    ;;
  *)
    # Fail closed: an unset/unexpected scale must never skip artifact checks.
    echo "BLOCKER: unexpected planner marker scale: ${SCALE:-<unset>}"; exit 1
    ;;
esac

# 4. validate frontmatter against the SAME marker-tree blob (not the worktree)
TMP_PLAN="$(mktemp)"
git cat-file -p "${PLANNER_MARKER_COMMIT}:${RUN_DIR}/document-plan.md" > "${TMP_PLAN}" \
  || { rm -f "${TMP_PLAN}"; echo "BLOCKER: cannot read document-plan.md at the marker tree"; exit 1; }
python3 "${CLAUDE_SKILL_DIR}/scripts/parse_frontmatter.py" "${TMP_PLAN}" \
  || { rm -f "${TMP_PLAN}"; echo "BLOCKER: document-plan.md frontmatter invalid"; exit 1; }
rm -f "${TMP_PLAN}"
```

Any failure on a feature/system marker → REFUSE; never fall back to a
root path. Persist the resolved dir as state field `planner_artifact_dir`.

## Canonical gate check (micro + local)

No file-system check. The implementer must verify the chat history
contains BOTH:

1. A chat-handoff block (DOCTYPE / OUTPUT_STACK / AUDIENCE /
   OUTPUT_LANGUAGE / TARGET_PATH / MARKER), AND
2. A user confirmation token (`confirm plan` typed by the user)
   within the same conversation.

If the implementer can't see the planner output (e.g., running in a
fresh session), the gate fails and the implementer must refuse.

## Chronological pairing rule (micro + local)

The planner's lightweight-lane emission order is:

```
[earliest] light/plan content (3–7 bullet reflection)
           ↓
           [user types `revise` → planner re-emits a new light/plan
            (publish_thought.sh light/plan files overwrite per
            DOCPLANNER_ID); 0..N revise cycles possible]
           ↓
           User token: `confirm plan`
           ↓
[latest]   Handoff block (6 fields) — emitted ON confirm
```

The implementer pairs by **chronological backward walk** from the
handoff block:

1. Locate the handoff block (6 fields visible in current
   conversation; pasted transcripts refused).
2. Walk backward to the **nearest preceding `confirm plan`**. That
   token is the gate confirmation that produced the handoff.
3. Walk further backward to the **nearest preceding `light/plan`**
   before that `confirm plan`. Those are the bullets the user
   confirmed.

Older `light/plan` blocks before a `revise` or before a later
`light/plan` are **superseded, not ambiguous** — the implementer
ignores them.

**Refuse only when** (each rule fires the matching worked-example
case below):

- **(a)** Multiple plausible `light/plan` blocks appear at the
  same chronological position (e.g. two consecutive `light/plan`
  events with no `revise` / `escalate` token between them), OR
- **(b)** No `confirm plan` token appears between the matched
  `light/plan` and the handoff block, OR
- **(c)** A `revise` / `escalate` token appears AFTER the matched
  `light/plan` and BEFORE the matched `confirm plan` (indicates
  a later `light/plan` should have been emitted; broken planner
  output), OR
- **(d)** Any `light/plan` token appears AFTER the matched
  `confirm plan` AND BEFORE the handoff block (indicates broken
  planner output — the planner emitted a later reflection that
  was never user-confirmed by a subsequent `confirm plan`).

### Worked examples

| Transcript pattern | Decision | Rule fired |
|---|---|---|
| `light/plan` → `confirm plan` → handoff | Pair. Normal path. | — |
| `light/plan` → `revise` → `light/plan` → `confirm plan` → handoff | Pair 2nd light/plan with handoff. 1st superseded. | — |
| `light/plan` → `light/plan` → `confirm plan` → handoff | Refuse — ambiguous. | (a) |
| `light/plan` → `confirm plan` → `light/plan` → handoff | Refuse — orphan light/plan after confirm. | (d) |
| Just a handoff, no `light/plan` visible | Refuse — fresh session or pasted partial. | (b) |
| `light/plan` in chat, no `confirm plan` | Refuse — user never confirmed. | (b) |

**Chat is canonical.** The `publish_thought.sh`-emitted collab-memory
file `docplanner-<DOCPLANNER_ID>-phase-light-plan.md` MAY be consulted
to attach a `DOCPLANNER_ID` to chat-visible bullets when two planner
runs in the same conversation produce visually similar reflections.
The collab-memory file alone does NOT satisfy the gate.

A `(document-plan-micro|local, human-confirmed)` marker found in
`git log` is **refused as forged** — those scales are chat-only per
the marker contract above.

## `[[stub-id]]` transformation contract (feature + system)

`$RUN_DIR/document-plan.md` uses `[[stub-id]]` wikilink syntax for cross-stub
references. This syntax is **intermediate** — standard markdown
renderers display `[[foo]]` verbatim.

`document-implementer` MUST transform every `[[stub-id]]` into the
target format's native cross-reference syntax when generating the
user-facing document:

| OUTPUT_STACK | DOCTYPE | Transformation |
|---|---|---|
| text | api-spec | `[<title>](#<endpoint-anchor>)` (markdown heading anchor) or OpenAPI `$ref` if generating openapi.yaml |
| text | tech-spec | `[<title>](#<section-anchor>)` |
| text | runbook | `[step N](#<step-anchor>)` (preserve step ordering in the link text) |
| structured | ppt | slide-jump action (python-pptx `hyperlink.slide` referencing the target slide's index) |

If the user-facing document is HTML, `<a href="#stub-id">…</a>` is the
canonical form. **Never ship literal `[[stub-id]]` to the user.**

The implementer resolves `[[stub-id]]` against the same `## stub: <id>`
headings that `validate_internal_refs.py` walked at Phase 6 —
unresolved references would already have failed planner gate.

## What downstream agents MUST NOT do

- Generate prose body content for any planner output that has no
  marker — this includes a planner that crashed before Phase 8
  (feature/system) or one that printed a plan but never received
  `confirm plan` (micro/local).
- Treat presence of `$RUN_DIR/document-plan.md` alone as sufficient —
  the marker commit (carrying the `AI-Artifacts-Run-Dir:` trailer) must
  also be reachable in `git log` history.
- Reuse codebase-planner's marker family. `(interfaces only,
  human-confirmed)` and `(plan-<scale>, human-confirmed)` are code
  markers; a document-implementer that greps for them is a bug.
- Ship literal `[[stub-id]]` references to the end user.
- Auto-bump a missing-marker situation by re-running the planner —
  the planner is gated on human confirmation, not on AI judgment.

## Honest limitations

The marker is a **documented social contract, not a cryptographic
one**. A determined user can hand-craft the marker files and a fake
merge commit to bypass any of these checks; the goal is to catch
accidental misuse and make any deliberate bypass visible in git
history. Stronger enforcement (signed commits, git notes verified
against a maintainer key, external attestation) is out of scope —
layer it on top if your project needs it.

## No backward-compatibility shim

`document-planner` is a new skill — there is intentionally NO
inherited marker form. The pre-rename `codebase-architect` legacy
marker `(interfaces only, human-confirmed)` belongs to code-side
planning only.
