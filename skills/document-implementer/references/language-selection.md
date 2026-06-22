# Phase L — Communication-language selection

Determines the language for **all user-facing dialog** in this skill —
gate prompts, error messages, blocker reports, merge prompts. Persisted
in `.document-implementer-state.json` for resumability.

**Critical distinction**: `LANGUAGE` is the **dialog** language;
`OUTPUT_LANGUAGE` is the **produced document** language. `OUTPUT_LANGUAGE`
is read from the planner contract (frontmatter for feature/system; chat-
handoff for micro/local) — never prompted at Phase L. The two are
independent.

## What is and isn't translated

| Surface | Language behavior |
|---|---|
| User-facing dialog (prompts, error messages, blocker reports) | follows `LANGUAGE` |
| Gate tokens (`confirm merge`, `revise`, `keep`, `proceed`) | **always English, verbatim — never translated** |
| Generated document body (prose / slide content) | follows `OUTPUT_LANGUAGE` (from planner) |
| Stub-id slugs, `[[stub-id]]` wikilinks, anchors | natural form (English / ASCII) |
| Self-verification report (`report.<id>.md`) prose sections | follows `LANGUAGE` |
| Self-verification report tables (file paths, exit codes, item ids) | natural form |
| Merge-commit marker `(document-impl-<scale>, human-confirmed)` | natural form (verbatim — grep contract) |
| This skill's own SKILL.md / references/ / scripts/ | never translated (agent-facing) |
| Commit messages on the implementer branch | English (project convention) |

Rule of thumb: human dialog follows `LANGUAGE`; code / markers / paths
stay in natural form; the **generated document** follows `OUTPUT_LANGUAGE`
(which the implementer reads as a planner contract input, not a user prompt).

## Detection rule

1. Inspect the invocation utterance.
2. Classify:

   | Signal | `LANGUAGE` |
   |---|---|
   | Predominantly Hangul characters | `Korean` |
   | Predominantly English text | `English` |
   | Empty / ambiguous / non-text | `Korean` (default) |

3. Echo + confirm:
   - **Korean**: `진행 언어를 한국어로 설정했습니다. 다른 언어를 원하시면 알려주세요. 그대로 진행하려면 "확인"이라고 답해 주세요.`
   - **English**: `Communication language set to English. Reply with another language name to switch. Type "confirm" to proceed.`

4. Override:
   - "한국어" / "Korean" → `LANGUAGE=Korean`
   - "영어" / "English" → `LANGUAGE=English`
   - Any other → fall back to English with a polite note.

5. Mid-flow switches: update `LANGUAGE` in memory immediately + state
   file if it exists (Phase 2 onward). Do NOT reset phase progress.

## Where Phase L runs

Phase L is a **preamble** — runs before Phase 0 so the inspector
dialog is already in the right language. No mutations.

## On resume

When Phase 0 detects `inside-document-implementer-worktree` and reads
`.document-implementer-state.json`, the loaded `language` field
becomes the session's `LANGUAGE` immediately. Phase L does NOT re-run
on resume (silent inheritance). The user can still mid-flow switch.

Missing `language` field → default `Korean`, continue.

## OUTPUT_LANGUAGE handling (not Phase L's job)

`OUTPUT_LANGUAGE` is captured by the planner at Phase 0.5 and
persisted in:
- Frontmatter (feature/system) — read by `parse_frontmatter.py`
- Chat-handoff block (micro/local) — parsed by the implementer's
  Phase 0 chat-gate logic

If `OUTPUT_LANGUAGE` is missing from the planner contract, **refuse
at Phase 0**. Do NOT prompt the user (autonomy boundary —
Phases 0–5 have no user prompts beyond blockers + final `confirm
merge`). Re-run `/document-planner` to set it.

## Persistence

```json
"language": "Korean | English"
```

Top-level in `.document-implementer-state.json`, first written at
Phase 2.

## Honest limitations

- Only Korean and English are first-class for `LANGUAGE`.
- The detection rule is character-frequency based; multilingual
  invocations may misclassify. Echo + confirm is the safety net.
- Gate tokens stay English regardless — translating them would
  break gate matching.
