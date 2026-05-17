# Phase L — Communication-language selection

Determines the language for **all user-facing dialog** in this skill —
triage questions, classification echoes, scale-confirmation prompts,
gate prompts, error messages, merge prompts. Persisted in
`.planner-state.json` (feature + system lanes) for resumability;
held in memory only at micro / local lanes (no state file at those
scales).

## What is and isn't translated

| Surface | Language behavior |
|---|---|
| User-facing chat dialog prose (questions, echoes, gate descriptions) | follows `LANGUAGE` |
| Gate tokens (`confirm plan`, `confirm scale`, `confirm packages`, `confirm decomposition`, `confirm merge`, `revise`, `escalate`, `emit skeletons`, `keep`, `proceed`) | **always English, verbatim — never translated.** The skill expects to receive these tokens as input; translating would break gate matching and let the user bypass a gate by typing the Korean word instead |
| `plan.md` prose body (goal, in-scope, out-of-scope, success criteria, rationale paragraphs) | follows `LANGUAGE` |
| `plan.md` structural headings (`## Implementation steps`, `## In scope`, etc.) and step-text imperative verbs (`Add`, `Implement`, `Refactor`, `Wire`, `Replace`) | natural form (English) — the implementer skill's Phase 1 parses these as a machine grammar to build the work queue; translating headings would break the handoff |
| `plan.mmd` Mermaid node labels | natural form (English / code identifiers) |
| Interface skeleton code (Java / Python / TS / Go / Rust) | natural form (code stays in English) |
| 9-field docstring contents inside the skeletons | natural form (English) — the implementer skill reads these as a machine-readable spec |
| `architecture.html` prose sections (lane summary, gate explanation) | follows `LANGUAGE` |
| `architecture.html` machine-derived content (rubric scores, file paths, Mermaid render) | natural form |
| `architecture.mmd` raw artifact | natural form |
| Merge-commit marker `(plan-<scale>, human-confirmed)` and `(interfaces only, human-confirmed)` | natural form (verbatim — the marker family is the grep contract for downstream tools) |
| This skill's own SKILL.md / references/ / scripts/ | never translated (agent-facing) |

The rule of thumb: anything the human reads as **prose** follows
`LANGUAGE`; anything the human reads as **code or schema** stays in
its natural form, even when `LANGUAGE=Korean`. Docstrings stay in
English because they're the implementer-skill contract.

## Detection rule

1. Inspect the invocation utterance (the user's `/codebase-planner ...`
   message plus any same-turn follow-up text).
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
   planner state file already exists (feature/system, Phase 4
   onward), update its top-level `language` field too. If the state
   file doesn't exist yet (micro/local at any time, or feature/system
   before Phase 4), just hold `LANGUAGE` in memory — it lands on disk
   when Phase 4 creates the state file. Do NOT reset other phase
   progress.

## Where Phase L runs in the workflow

Phase L is a **preamble**: it runs before Phase 0 (repo state
detection) so the Phase 0 dialog is already in the right language. No
mutations, no commits — pure dialog-language capture.

## On resume

When Phase 0 detects `inside-planner-worktree` (feature + system
only — micro/local have no state file to resume from) and reads
`.planner-state.json`, the loaded `language` field becomes the
session's `LANGUAGE` immediately. Phase L does NOT re-run on resume
(silent inheritance), but the user can still trigger a mid-flow
switch per step 5 above.

If the loaded state file is missing the `language` field (e.g., it
was written by an older planner-skill build before Phase L existed),
default to `Korean` and continue — do not refuse, do not re-prompt.

## Persistence

`.planner-state.json` schema gains:

```json
"language": "Korean | English"
```

at the top level, written for the first time at Phase 4 (worktree
creation; this is the planner's first on-disk mutation — implementer
analog persists at Phase 2 because its worktree comes earlier in its
flow). Until then, `LANGUAGE` lives only in memory.

## Honest limitations

- Only Korean and English are first-class. Any other language
  request falls back to English with a polite note.
- The detection rule is character-frequency based; multilingual or
  technical-jargon-heavy invocations may misclassify. The
  echo+confirm step at step 3 is the safety net.
- Code, docstrings, and Mermaid label text intentionally stay in
  English regardless of `LANGUAGE` — the implementer skill reads
  docstrings as a machine spec, and tooling generally assumes ASCII
  for identifiers.
