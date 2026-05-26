# Phase L — Communication-language selection

Determines the language for **all user-facing dialog** in this skill —
mode-detection questions, elicitation prompts, synthesis echoes, gate
prompts, error messages, merge prompts. Persisted in `.intent-state.json`
(top-level `language` field) at Phase 4 for resumability; held in memory
only through Phases L, 0, 1, 2, 3 (no state file before Phase 4).

## What is and isn't translated

| Surface | Language behavior |
|---|---|
| User-facing chat dialog prose (questions, reflections, gate descriptions) | follows `LANGUAGE` |
| Gate tokens (`confirm mode`, `confirm intent`, `confirm merge`, `revise`, `keep`, `proceed`) | **always English, verbatim — never translated.** The skill expects to receive these tokens as input; translating would break gate matching and let the user bypass a gate by typing the Korean word instead |
| `intent.<slug>.md` **field names** (`Goal`, `In-scope features`, `Out-of-scope`, `Constraints`, `Success criteria`, `Open questions`, `Examples`, `Counter-examples`, `Root-cause`, `Persona`, `Mode`) | natural form (English) — these are the machine grammar that downstream parsers read. Translating them would break the handoff |
| `intent.<slug>.md` **field values** (the user's own words for goal, examples, etc.) | follows `LANGUAGE` — these are the user's verified intent, presented to the planner as-is |
| `intent.<slug>.html` **section headings, mode pill, `<html lang>` attribute** | follows `LANGUAGE` — the renderer ships a KO/EN string table keyed off `state.language` and chooses chrome strings + the lang attribute accordingly. Fallback chain: `Korean` / `ko` / `kr` → ko; missing, null, or empty → ko (per resume contract below); any other non-empty value (e.g. `English`, `Spanish`) → en |
| `intent.<slug>.html` **field values** | follows `LANGUAGE` (the renderer escapes whatever's in the state file) |
| `intent.<slug>.html` **footer** | localized; the next-step pointer to `/plan-establisher` lives in the Phase 6 chat output, not in the verification doc |
| Merge commit marker `(intent, human-confirmed)` | natural form (verbatim — the marker is the grep contract for downstream tools / future audits) |
| Commit subject lines (`feat(intent): synthesize ...`, `feat(intent): merge ... (intent, human-confirmed)`) | natural form (English) — keeps `git log` searchable across language settings |
| This skill's own SKILL.md / references/ / scripts/ | never translated (agent-facing) |

The rule of thumb: anything the human reads as **prose** follows
`LANGUAGE`; anything the human reads as **code or schema** stays in its
natural form, even when `LANGUAGE=Korean`. Field names in
`intent.<slug>.md` stay English because they're the downstream-skill
contract.

## Detection rule

1. Inspect the invocation utterance (the user's `/intent-aligner ...`
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
   in memory immediately and continue in the new language. If
   `.intent-state.json` already exists (Phase 4 onward), update its
   top-level `language` field too. If the state file doesn't exist
   yet (Phases L–3), just hold `LANGUAGE` in memory — it lands on
   disk when Phase 4 creates the state file. Do NOT reset other phase
   progress, and do NOT re-translate intent values already captured —
   the user's own words stay verbatim regardless of dialog language.

## Where Phase L runs in the workflow

Phase L is a **preamble**: it runs before Phase 0 (repo state
detection) so the Phase 0 dialog is already in the right language. No
mutations, no commits — pure dialog-language capture.

## On resume

When Phase 0 detects `inside-intent-worktree` and reads
`.intent-state.json`, the loaded `language` field becomes the session's
`LANGUAGE` immediately. Phase L does NOT re-run on resume (silent
inheritance), but the user can still trigger a mid-flow switch per
step 5 above.

If the loaded state file is missing the `language` field (e.g., it was
written by an older intent-aligner build before Phase L existed —
unlikely but possible during early iteration), default to `Korean` and
continue — do not refuse, do not re-prompt.

## Persistence

`.intent-state.json` schema gains:

```json
"language": "Korean | English"
```

at the top level, written for the first time at Phase 4 (worktree
creation; this is intent-aligner's first on-disk mutation). Until then,
`LANGUAGE` lives only in memory.

## Honest limitations

- Only Korean and English are first-class. Any other language request
  falls back to English with a polite note.
- The detection rule is character-frequency based; multilingual or
  technical-jargon-heavy invocations may misclassify. The echo+confirm
  step at step 3 is the safety net.
- `intent.<slug>.md` field names, commit messages, gate tokens, and the
  `(intent, human-confirmed)` marker intentionally stay in English
  regardless of `LANGUAGE` — downstream skills read `intent.<slug>.md`
  as a machine spec, and `git log` greps need ASCII for portability.
- Mid-flow language switches do NOT re-translate intent values already
  captured. The user's own words stay verbatim — only future dialog
  prose switches language.
