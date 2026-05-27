# Phase L — Communication-language selection

Determines the language for **all user-facing dialog** in this skill —
repo-state messages, intent-selection prompts, resource-intake echoes,
per-resource synthesis previews, gate prompts, error messages, merge
prompts. Persisted in `.seed-state.json` (top-level `language` field) at
Phase 4 for resumability; held in memory only through Phases L, 0, 1, 2, 3
(no state file before Phase 4).

## What is and isn't translated

| Surface | Language behavior |
|---|---|
| User-facing chat dialog prose (questions, reflections, synthesis previews, gate descriptions) | follows `LANGUAGE` |
| Gate tokens (`confirm intent`, `confirm seeds`, `confirm merge`, `revise`, `keep`, `done`, `proceed`) | **always English, verbatim — never translated.** The skill expects these tokens as input; translating would break gate matching and let the user bypass a gate by typing the Korean word instead |
| `seed.<intent-slug>.<resource-slug>.md` **field names** (`Source`, `Resource type`, `Extracted at`, `Intent slug`, `Extracted content (intent-filtered)`, `Relevance rationale`) | natural form (English) — these are the machine grammar that the downstream `plan-establisher` parser reads. Translating them would break the handoff |
| `seed.<intent-slug>.<resource-slug>.md` **field values** (the extracted content, the rationale prose) | follows `LANGUAGE` — the extraction step writes in the dialog language so the human reviewer reads the same language they're conversing in |
| `seed.<intent-slug>.<resource-slug>.html` **section headings, lang attribute** | follows `LANGUAGE` — the renderer ships a KO/EN string table keyed off `state.language`. Fallback chain: `Korean` / `ko` / `kr` → ko; missing, null, or empty → ko (per resume contract below); any other non-empty value (e.g. `English`, `Spanish`) → en |
| `seed.<intent-slug>.<resource-slug>.html` **field values** | follows `LANGUAGE` (the renderer escapes whatever's in the state file) |
| Merge commit marker `(seeds, human-confirmed)` | natural form (verbatim — the marker is the grep contract for downstream tools / future audits) |
| Commit subject lines (`feat(seeds): emit <slug> resource batch ...`, `feat(seeds): merge ... (seeds, human-confirmed)`) | natural form (English) — keeps `git log` searchable across language settings |
| This skill's own SKILL.md / references/ / scripts/ | never translated (agent-facing) |

The rule of thumb: anything the human reads as **prose** follows
`LANGUAGE`; anything the human reads as **code or schema** stays in its
natural form, even when `LANGUAGE=Korean`. Field names in
`seed.<intent-slug>.<resource-slug>.md` stay English because they're the
downstream-skill contract.

The user's verbatim resource content (extracted excerpts) follows the
source's own language — if the resource is in English, the extracted
quote stays in English regardless of `LANGUAGE`. Only the surrounding
prose (the "relevance rationale", any summarizing intro) follows
`LANGUAGE`.

## Detection rule

1. Inspect the invocation utterance (the user's `/seed-gather-for-plan ...`
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
   `.seed-state.json` already exists (Phase 4 onward), update its
   top-level `language` field too. If the state file doesn't exist
   yet (Phases L–3), just hold `LANGUAGE` in memory — it lands on
   disk when Phase 4 creates the state file. Do NOT reset other phase
   progress, and do NOT re-extract resources that have already been
   processed — extracted content stays verbatim regardless of dialog
   language.

## Where Phase L runs in the workflow

Phase L is a **preamble**: it runs before Phase 0 (repo state detection)
so the Phase 0 dialog is already in the right language. No mutations,
no commits — pure dialog-language capture.

## On resume

Phase L is a preamble that runs before Phase 0, so on a resume
invocation it *does* still run (the agent doesn't know it's a resume
until Phase 0 reads the state file). The Phase L tentative detection
is then **silently overridden** by `state.language` once Phase 0
detects `inside-seed-worktree` — no re-prompt, no echo, no
acknowledgement. The user's earlier `language` choice is the source
of truth on resume; Phase L's tentative result is discarded.

If the loaded state file is missing the `language` field (defensive
guard — should never happen since Phase 4 always writes it), default
to `Korean` and continue — do not refuse, do not re-prompt.

The user can still trigger a mid-flow language switch per step 5
above (in either fresh or resume invocations).

## Persistence

`.seed-state.json` schema includes:

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
- `seed.*.md` field names, commit messages, gate tokens, and the
  `(seeds, human-confirmed)` marker intentionally stay in English
  regardless of `LANGUAGE` — the downstream `plan-establisher` reads
  `seed.*.md` as a machine spec, and `git log` greps need ASCII for
  portability.
- Mid-flow language switches do NOT re-extract resources already
  processed. The extracted content stays verbatim — only future
  dialog prose and future extractions switch language.
- Resource contents themselves stay in whatever language the source
  was written in. A Korean session extracting from English docs gets
  English quotes with Korean rationale, and vice versa. This is
  intentional — paraphrasing source material into a different language
  loses fidelity and is downstream's call.
