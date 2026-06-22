# Phase L — Communication-language selection

Determines the language for **all user-facing dialog** in this skill —
gate prompts, progress lines, blocker diagnostics, the
report (`report.<implementer-id>.md`) prose sections, the Phase 6 merge prompt.
Held in memory through Phases 0–1; persisted to
`.implementer-state.json` at Phase 2 (when the worktree is created).

## What is and isn't translated

| Surface | Language behavior |
|---|---|
| User-facing chat dialog prose (gate prompts, progress, blockers) | follows `LANGUAGE` |
| Gate tokens (`confirm merge`, `confirm plan`, `proceed`, `keep`, `revise`, `resume`, `abort`) | **always English, verbatim — never translated.** The skill expects to receive these tokens as input from the user; translating them would break gate matching and silently let the user bypass the gate by typing the Korean word instead |
| Planner artifacts the implementer parses (`plan.md` structural headings like `## Implementation steps`, step-prefixing imperative verbs, `plan.mmd` Mermaid label text, 9-field docstring tags inside interface skeletons) | natural form (English) — Phase 1's work-queue extraction is a machine grammar; translating these breaks the handoff. The planner's own `language-selection.md` mirrors this rule |
| Report (`report.<implementer-id>.md`) prose sections (Source / Work queue summary / Validation prose / Scope-discipline self-check) | follows `LANGUAGE` |
| Report file paths, command output, validation tails | natural form (these are code/CLI artifacts) |
| Generated implementation code (method bodies, helpers, inline comments inside generated code) | natural form (English) |
| Commit messages | natural form (Conventional Commits stay in English for tooling compatibility) |
| Merge-commit marker `(impl-<scale>, human-confirmed)` | natural form (verbatim — the marker family is grep-target for downstream tools) |
| This skill's own SKILL.md / references/ / scripts/ | never translated (agent-facing) |

The rule of thumb: anything the human reads as **prose** follows
`LANGUAGE`; anything that is **code, commit message, or marker
string** stays in its natural form. Marker strings are particularly
load-bearing — translating them would break the downstream
implementer-contract grep.

## Detection rule

1. Inspect the invocation utterance (the user's `/codebase-implementer
   ...` message plus any same-turn follow-up text).
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
   - Any other language → fall back to English with a polite note: *"Other languages aren't first-class supported yet — I'll continue in English. You can use Korean or English freely at any point."*

5. Mid-flow switches: if the user explicitly asks to change language
   later ("switch to English" / "영어로 바꿔줘"), update `LANGUAGE`
   in memory immediately and continue in the new language. If the
   implementer state file already exists (Phase 2 onward), update its
   top-level `language` field too. If the state file doesn't exist
   yet (Phases 0–1), just hold `LANGUAGE` in memory — it lands on
   disk when Phase 2 creates the state file. Do NOT reset other
   phase progress.

## Where Phase L runs in the workflow

Phase L is a **preamble**: it runs before Phase 0 (repo state
detection + marker verification) so the Phase 0 refusal or proceed
message is already in the right language. No mutations, no commits —
pure dialog-language capture.

## On resume

When Phase 0 detects `inside-implementer-worktree` and reads
`.implementer-state.json`, the loaded `language` field becomes the
session's `LANGUAGE` immediately. Phase L does not re-run on resume
(silent inheritance), but the user can still trigger a mid-flow
switch per step 5 above.

If the loaded state file is missing the `language` field (e.g., it
was written by an older implementer-skill build before Phase L
existed), default to `Korean` and continue — do not refuse, do not
re-prompt.

## Persistence

`.implementer-state.json` schema gains:

```json
"language": "Korean | English"
```

at the top level, written for the first time at Phase 2 (worktree
creation). Until then, `LANGUAGE` lives only in memory.

## Honest limitations

- Only Korean and English are first-class. Any other language
  request falls back to English with a polite note.
- Detection is character-frequency based; mixed-language or
  technical-jargon-heavy invocations may misclassify. The
  echo+confirm step at step 3 is the safety net.
- The merge-commit marker `(impl-<scale>, human-confirmed)` is
  deliberately not translatable — it's the grep contract for
  downstream tools. Translating it would silently break review/CI
  automation that relies on the marker family.
