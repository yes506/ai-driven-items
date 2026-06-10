# Phase L — Communication-language selection

Determines the language for **all user-facing dialog** in this skill —
the opening ACK, mid-capture meta-echoes, the synthesis preview, the
final save-preview prompt — and for the body of the note that gets
written to disk. Held in memory only (this skill has no on-disk state
file between turns; the buffer-draft file under `.live-notes-drafts/`
records `language` so a resume can recover it — see
[capture-mode.md](capture-mode.md#draft-buffer-on-disk-crash-safety)).

## What is and isn't translated

| Surface | Language behavior |
|---|---|
| User-facing chat dialog prose (opening ACK, finish synthesis preview, save-preview, error messages) | follows `LANGUAGE` |
| Gate tokens (`confirm save`, `revise`, `abort`, `finish`, `done`, `status`, `section`, `category`) | **always English, verbatim — never translated.** The skill matches these as input tokens; translating would break gate detection |
| Korean finish synonyms (`종료`, `끝`, `마치기`) and Korean meta-command synonyms (`상태`, `섹션`, `카테고리`) | recognized as input aliases regardless of `LANGUAGE` — the user may switch input language mid-capture and finish in their first-thought language. The English forms remain canonical for documentation and matching |
| The captured note content (user's verbatim messages) | **never translated** — appended exactly as the user typed, in whatever language they used. Verbatim preservation is the point of live capture |
| The synthesized output note — TL;DR bullets, section headings, organizing prose | follows `LANGUAGE` — the AI's organizing voice writes in the dialog language. Verbatim user excerpts inside the note stay in their original language |
| The output note's YAML frontmatter **keys** (`title`, `date`, `time`, `tags`, `created`, `modified`, `category`, `source`) | always English — Obsidian and downstream tooling read these as a schema |
| The output note's frontmatter **values** (e.g. the `title` string, `tags` list, `category`) | follows `LANGUAGE` for prose fields like `title`; `date`/`time`/`created`/`modified` use ISO formats verbatim; `tags` and `category` slugs stay lowercase-kebab-ASCII for Obsidian compatibility, but the AI may surface a Korean-language display label in the prose body if helpful |
| Web research references section (`## References` heading) | follows `LANGUAGE`; URLs and source titles preserved verbatim from the source |
| This skill's own SKILL.md / references/ / scripts/ | never translated (agent-facing) |

The rule of thumb: anything the human reads as **prose** follows
`LANGUAGE`; anything the human reads as **schema / token / URL** stays
in its natural ASCII form, even when `LANGUAGE=Korean`. The note's
verbatim user-typed content always preserves what the user actually
typed — translating the user's own notes would defeat the skill.

## Detection rule (capture-first, no blocking confirmation)

The user's original spec was explicit: *"사용자가 /{스킬명} 형태로
스킬 사용 개시하면 사용자에게 별다른 것은 물어볼 필요 없이 바로 노트
작성 모드 시작됨"* — capture mode starts immediately, **without
asking anything first**. Phase L therefore detects-and-acknowledges
but does NOT block on a `확인`/`confirm` reply. The user's first
content message is implicit consent for the detected language, and a
later `language <ko|en>` meta-command (documented in
[capture-mode.md](capture-mode.md)) switches mid-stream.

1. Inspect the invocation utterance (the user's `/live-notes ...`
   message plus any same-turn follow-up text).
2. Classify:

   | Signal | `LANGUAGE` |
   |---|---|
   | Predominantly Hangul characters in the utterance | `Korean` |
   | Predominantly English text in the utterance | `English` |
   | Empty, ambiguous, or non-text invocation | `Korean` (default) |

3. Echo the choice in a single line as part of the Phase 0 ACK (no
   separate gate). The capture-mode banner immediately follows. The
   user does NOT have to reply for capture to start.

   - **Korean**: `🌐 언어: 한국어 (변경하려면 \`language en\` 또는 \`/live-notes\` 재실행)`
   - **English**: `🌐 Language: English (switch with \`language ko\` or re-invoke \`/live-notes\`)`

4. Mid-flow switches via the `language <ko|en>` meta-command (full
   spec in [capture-mode.md](capture-mode.md#operating-contract-during-phase-1)):
   update `LANGUAGE` in memory immediately, ACK in the new language,
   continue at the same chunk index. Do NOT retroactively re-tag any
   already-captured content — verbatim user input is never translated.

5. Free-text language requests in non-command form ("switch to English"
   / "영어로 바꿔줘") are ambiguous between a directive and note
   content. Treat as a switch only when the message is short and
   imperative-form *and* the user has not yet started capturing
   substantive content (i.e. it's the first or second turn). After
   that, free-text language phrases are treated as note content; the
   user must use the explicit `language <ko|en>` meta-command to
   switch.

6. Unsupported language requests: any language other than Korean or
   English falls back to English with a polite note: *"Other languages
   aren't first-class supported yet — I'll continue in English. You can
   still type your notes in any language; the organizing voice will
   be English."* This rule applies whether the request arrives at
   invocation time or via a free-text turn before substantive capture.

## Where Phase L runs in the workflow

Phase L is a **preamble**: it runs before Phase 0 (workspace detection)
so the Phase 0 ACK (`Notes will be saved to: <path>`) is already in
the right language. No mutations, no writes — pure dialog-language
capture.

## On resume (from a stale buffer-draft)

If on a fresh `/live-notes` invocation the workspace inspector reports
an existing buffer-draft file (`.live-notes-drafts/<sid>.draft.md`)
older than the current session, ask the user whether to resume that
session or start fresh — see
[capture-mode.md](capture-mode.md#resume-from-stale-buffer-draft).

If the user opts to resume, parse the draft's HTML-comment header
line (NOT a YAML field) for the prior language. The exact format is:

```
<!-- live-notes language: Korean -->
```

Match with:

```bash
grep -oE '<!-- live-notes language: (Korean|English) -->' "${DRAFT_PATH}" | head -1
```

If matched, that value silently overrides the freshly-detected
`LANGUAGE` — the user's earlier choice wins. If the header line is
absent (defensive guard — should never happen since Phase 1 always
writes it), keep the freshly-detected language and continue.

## Persistence

`.live-notes-drafts/<sid>.draft.md` (the only on-disk artifact during
capture) carries a single header line. The literal value is one of:

```
<!-- live-notes language: Korean -->
<!-- live-notes language: English -->
```

written when the draft is first created (Phase 1, first turn after
ACK). The synthesized output note's frontmatter does NOT carry a
language field — Obsidian doesn't need it and the content's language
is self-evident.

## Honest limitations

- Only Korean and English are first-class. Any other language request
  falls back to English with a polite note.
- The detection rule is character-frequency based; multilingual or
  technical-jargon-heavy invocations may misclassify. Recovery: the
  user types `language <ko|en>` (or `언어 <ko|en>`) at any point to
  switch mid-stream, or re-invokes `/live-notes` from scratch. There
  is no confirmation gate — that was a deliberate removal to honor
  the user's "별다른 것은 물어볼 필요 없이" spec.
- The output frontmatter keys, the `tags` / `category` slugs, gate
  tokens, and the buffer-draft header marker intentionally stay in
  English / ASCII regardless of `LANGUAGE` — Obsidian, file systems,
  and grep portability all need ASCII.
- Verbatim user-typed content is **never translated**, even on
  mid-flow language switches. The organizing voice (TL;DR, section
  intros) follows the current `LANGUAGE` at synthesis time.
- Web research excerpts preserve the source language. A Korean session
  citing an English source gets the English quote with Korean
  surrounding prose, and vice versa.
