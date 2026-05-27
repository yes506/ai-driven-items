# Phase L — Communication-language selection

Determines the language for **all user-facing dialog** in this skill —
repo-state messages, intent-selection prompts, verification-finding
echoes, ambiguity-resolution Q&A, synthesis previews, gate prompts,
error messages, merge prompts. Persisted in `.plan-state.json`
(top-level `language` field) at Phase 4 for resumability; held in
memory only through Phases L, 0, 1, 2, 3 (no state file before Phase 4).

## What is and isn't translated

| Surface | Language behavior |
|---|---|
| User-facing chat dialog prose (questions, reflections, finding echoes, synthesis previews, gate descriptions) | follows `LANGUAGE` |
| Gate tokens (`confirm intent`, `confirm plan`, `confirm merge`, `revise`, `keep`, `accept remaining`) | **always English, verbatim — never translated.** The skill expects these tokens as input; translating would break gate matching and let the user bypass a gate by typing the Korean word instead |
| `plan.<intent-slug>.v<N>.md` **field names** (`Goal`, `In-scope`, `Out-of-scope`, `Constraints`, `Success criteria`, `Proposed scale lane`, `Lane reasoning`, `Evidence inventory`, `Resolved ambiguities`, `Remaining open questions`, `Provenance`) | natural form (English) — these are the machine grammar that the downstream `codebase-planner` reads. Translating them would break the handoff |
| `plan.<intent-slug>.v<N>.md` **field values** (refined goal text, rationale prose, ambiguity resolutions) | follows `LANGUAGE` — the user reviews the doc in the same language as the dialog |
| `plan.<intent-slug>.v<N>.html` **section headings, lang attribute** | follows `LANGUAGE` — the renderer ships a KO/EN string table keyed off `state.language`. Fallback chain: `Korean` / `ko` / `kr` → ko; missing, null, or empty → ko (per resume contract below); any other non-empty value (e.g. `English`, `Spanish`) → en |
| `plan.<intent-slug>.v<N>.html` **field values** | follows `LANGUAGE` (the renderer escapes whatever's in the state file) |
| Merge commit marker `(plan, human-confirmed)` | natural form (verbatim — the marker is the grep contract for downstream tools / future audits) |
| Commit subject lines (`feat(plan): emit ... v<N>`, `feat(plan): merge ... (plan, human-confirmed)`) | natural form (English) — keeps `git log` searchable across language settings |
| Carried-through content from inputs (intent rubric values, seed extracted content) | follows the source's language; this skill does NOT re-translate intent/seed values — they're passed through verbatim |
| This skill's own SKILL.md / references/ / scripts/ | never translated (agent-facing) |

The rule of thumb: anything the human reads as **prose** follows
`LANGUAGE`; anything the human reads as **code or schema** stays in
its natural form, even when `LANGUAGE=Korean`. Field names in
`plan.<intent-slug>.v<N>.md` stay English because they're the
downstream-skill contract.

## Detection rule

1. Inspect the invocation utterance (the user's `/plan-establisher ...`
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
   `.plan-state.json` already exists (Phase 4 onward), update its
   top-level `language` field too. If the state file doesn't exist
   yet (Phases L–3), just hold `LANGUAGE` in memory — it lands on
   disk when Phase 4 creates the state file. Do NOT reset other phase
   progress, and do NOT re-translate already-recorded findings or
   resolutions — those stay verbatim regardless of dialog language.

## Where Phase L runs in the workflow

Phase L is a **preamble**: it runs before Phase 0 (repo state
detection) so the Phase 0 dialog is already in the right language.
No mutations, no commits — pure dialog-language capture.

## On resume

Phase L is a preamble that runs before Phase 0, so on a resume
invocation it *does* still run (the agent doesn't know it's a resume
until Phase 0 reads the state file). The Phase L tentative detection
is then **silently overridden** by `state.language` once Phase 0
detects `inside-plan-worktree` — no re-prompt, no echo, no
acknowledgement. The user's earlier `language` choice is the source
of truth on resume; Phase L's tentative result is discarded.

If the loaded state file is missing the `language` field (defensive
guard — should never happen since Phase 4 always writes it), default
to `Korean` and continue — do not refuse, do not re-prompt.

The user can still trigger a mid-flow language switch per step 5
above (in either fresh or resume invocations).

## Persistence

`.plan-state.json` schema includes:

```json
"language": "Korean | English"
```

at the top level, written for the first time at Phase 4 (worktree
creation; this is the skill's first on-disk mutation). Until then,
`LANGUAGE` lives only in memory.

## Honest limitations

- Only Korean and English are first-class. Any other language request
  falls back to English with a polite note.
- The detection rule is character-frequency based; multilingual or
  technical-jargon-heavy invocations may misclassify. The echo+confirm
  step at step 3 is the safety net.
- `plan.*.md` field names, commit messages, gate tokens, and the
  `(plan, human-confirmed)` marker intentionally stay in English
  regardless of `LANGUAGE` — the downstream `codebase-planner` reads
  `plan.*.md` as a machine spec, and `git log` greps need ASCII for
  portability.
- Mid-flow language switches do NOT re-translate recorded findings,
  resolutions, or inherited intent/seed content. The user's own words
  and source quotes stay verbatim.
