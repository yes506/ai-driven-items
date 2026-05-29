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
| feature | `(document-plan-feature, human-confirmed)` | merge commit on `${BASE_BRANCH}` | `document-plan.md` + `document-structure.mmd` committed on the merged branch |
| system | `(document-plan-system, human-confirmed)` | merge commit on `${BASE_BRANCH}` | `document-plan.md` + `document-structure.mmd` + `document-structure.html` committed on the merged branch |

## Canonical metadata source (feature + system)

`document-plan.md` carries a YAML frontmatter block at the top with
`doctype`, `output_stack`, `audience`, `output_language`,
`target_path`, `scale`, `intent_slug`, `docplanner_id`. Spec +
boundary checks: [state-and-resume.md](state-and-resume.md). The
implementer parses the frontmatter via `parse_frontmatter.py` (bundled
stdlib-only scalar parser; no PyYAML). Absence or malformed
frontmatter is an implementer-side refusal.

## Canonical gate check (feature + system)

```bash
# feature
test -f document-plan.md && test -f document-structure.mmd \
  && git log --grep='(document-plan-feature, human-confirmed)' --format=%H | grep -q .

# system
test -f document-plan.md && test -f document-structure.mmd && test -f document-structure.html \
  && git log --grep='(document-plan-system, human-confirmed)' --format=%H | grep -q .
```

## Canonical gate check (micro + local)

No file-system check. The implementer must verify the chat history
contains BOTH:

1. A chat-handoff block (DOCTYPE / OUTPUT_STACK / AUDIENCE /
   OUTPUT_LANGUAGE / TARGET_PATH / MARKER), AND
2. A user confirmation token (`confirm plan` typed by the user)
   within the same conversation.

If the implementer can't see the planner output (e.g., running in a
fresh session), the gate fails and the implementer must refuse.

## Chat-adjacency pairing rule (micro + local)

When the same conversation contains multiple micro/local handoff
blocks (e.g. user planned two different intents in one session),
the implementer MUST pair each marker with its handoff block by
**chat-adjacency**: the marker is paired with the **nearest
preceding** handoff block in the conversation transcript.

This rule mirrors codebase-planner's chat-adjacency convention for
multiple parallel planner runs. The implementer should refuse if
ordering is ambiguous (e.g. marker with no preceding handoff block,
or handoff block with no following marker).

## `[[stub-id]]` transformation contract (feature + system)

`document-plan.md` uses `[[stub-id]]` wikilink syntax for cross-stub
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
- Treat presence of `document-plan.md` alone as sufficient — the
  marker commit must also be reachable in `git log` history.
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
