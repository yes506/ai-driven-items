# Phase L — Communication-language selection

Determines the language for **all user-facing dialog** in this skill
— triage questions, DOCTYPE classification echoes, scale-confirmation
prompts, gate prompts, error messages, merge prompts. Persisted in
`.document-planner-state.json` (feature + system lanes) for
resumability; held in memory only at micro / local lanes (no state
file at those scales).

## What is and isn't translated

| Surface | Language behavior |
|---|---|
| User-facing chat dialog prose (questions, echoes, gate descriptions) | follows `LANGUAGE` |
| Gate tokens (`confirm plan`, `confirm scale`, `confirm outline`, `confirm decomposition`, `confirm merge`, `revise`, `escalate`, `keep`, `proceed`) | **always English, verbatim — never translated.** The skill expects to receive these tokens as input; translating would break gate matching and let the user bypass a gate by typing the Korean word instead |
| `document-plan.md` prose (Goal, audience, in-scope, success criteria) | follows `LANGUAGE` |
| `document-plan.md` structural headings (`## stub: <id>`) and field names inside the YAML body (`purpose`, `audience`, `key_claims`, …) | natural form (English) — `validate_internal_refs.py` and the future `document-implementer` parse these as a machine grammar; translating would break the handoff |
| `document-structure.mmd` Mermaid node labels | natural form |
| `document-structure.html` prose (lane summary, gate explanation) | follows `LANGUAGE` |
| `document-structure.html` machine-derived content (rubric scores, file paths, Mermaid render) | natural form |
| Chat-handoff block (`DOCTYPE`, `OUTPUT_STACK`, `TARGET_PATH`, `MARKER`) | natural form (verbatim — read by `document-implementer`) |
| Merge-commit marker `(document-plan-<scale>, human-confirmed)` | natural form (verbatim — grep contract for downstream tools) |
| This skill's own SKILL.md / references/ / scripts/ | never translated (agent-facing) |

The rule of thumb: anything the human reads as **prose** follows
`LANGUAGE`; anything the human reads as **code or schema** stays in
its natural form. Stub field names stay in English because they're
the implementer-skill contract.

## Detection rule

1. Inspect the invocation utterance (the user's
   `/document-planner ...` message plus any same-turn follow-up).
2. Classify:

   | Signal | `LANGUAGE` |
   |---|---|
   | Predominantly Hangul characters in the utterance | `Korean` |
   | Predominantly English text in the utterance | `English` |
   | Empty, ambiguous, or non-text invocation | `Korean` (default) |

3. Echo the choice and wait for confirmation in the chosen language:
   - **Korean**: `진행 언어를 한국어로 설정했습니다. 다른 언어를 원하시면 알려주세요 (지원: 한국어, 영어). 그대로 진행하려면 "확인"이라고 답해 주세요.`
   - **English**: `Communication language set to English. Reply with another language name to switch (supported: Korean, English). Type "confirm" to proceed.`

4. On user override:
   - "한국어" / "Korean" → `LANGUAGE=Korean`
   - "영어" / "English" → `LANGUAGE=English`
   - Any other language → fall back to English with a polite note:
     *"Other languages aren't first-class supported yet — I'll continue
     in English. You can use Korean or English freely at any point."*

5. Mid-flow switches: if the user explicitly asks to change language
   later, update `LANGUAGE` in memory immediately and continue in
   the new language. If the state file already exists (feature/system,
   Phase 4 onward), update its top-level `language` field too. Do NOT
   reset other phase progress.

## Where Phase L runs in the workflow

Phase L is a **preamble**: it runs before Phase 0 (repo state
detection) so the Phase 0 dialog is already in the right language.
No mutations, no commits — pure dialog-language capture.

## On resume

When Phase 0 detects `inside-document-planner-worktree` (feature +
system only — micro/local have no state file to resume from) and
reads `.document-planner-state.json`, the loaded `language` field
becomes the session's `LANGUAGE` immediately. Phase L does NOT
re-run on resume (silent inheritance), but the user can still trigger
a mid-flow switch per step 5 above.

If the loaded state file is missing the `language` field (e.g., it
was written by an older build), default to `Korean` and continue —
do not refuse, do not re-prompt.

## Persistence

`.document-planner-state.json` schema gains:

```json
"language": "Korean | English"
```

at the top level, written for the first time at Phase 4 (worktree
creation). Until then, `LANGUAGE` lives only in memory.

## Honest limitations

- Only Korean and English are first-class. Any other language
  request falls back to English with a polite note.
- The detection rule is character-frequency based; multilingual or
  technical-jargon-heavy invocations may misclassify. The
  echo+confirm step at step 3 is the safety net.
- Stub field names and Mermaid label text intentionally stay in
  English regardless of `LANGUAGE` — the implementer skill reads
  stubs as a machine spec.
