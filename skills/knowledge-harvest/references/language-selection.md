# Phase L — Communication-language selection

Determines the language for **all user-facing dialog** in this skill (opening
ACK, source-scope question, unit/action preview, `--review` prompts, summaries).
Detected once at invocation, held for the run.

## What follows LANGUAGE vs what stays fixed

| Surface | Behavior |
|---|---|
| User-facing chat prose (ACK, previews, review prompts, summaries, errors) | follows `LANGUAGE` |
| Gate tokens (`proceed`, `confirm`, `--review`, `allow-once`, `skip`) | **always English, verbatim** — matched as input tokens; translating breaks detection |
| Note frontmatter **keys** (`concept-id`, `category`, `status`, …) | always English/ASCII — schema read by scripts + Obsidian |
| `concept-id` / `tags` slugs | lowercase-kebab-ASCII always (deterministic slug) |
| Note prose (`title`, `body_md`, `Current conclusion`) | follows the language the knowledge was expressed in; the organizing voice may write headings in `LANGUAGE` |
| This skill's SKILL.md / references / scripts | never translated (agent-facing) |

Rule of thumb: prose the human reads follows `LANGUAGE`; anything a script or
Obsidian parses as **schema / token / slug** stays ASCII, even when
`LANGUAGE=Korean`.

## Detection (no blocking confirmation)

1. Inspect the invocation utterance (the `/knowledge-harvest …` message + any
   same-turn text).
2. Classify:

   | Signal | `LANGUAGE` |
   |---|---|
   | Predominantly Hangul | `Korean` |
   | Predominantly English | `English` |
   | Empty / ambiguous | `Korean` (default) |

3. Echo the choice in one line as part of the opening ACK:
   - **Korean**: `🌐 언어: 한국어 (변경하려면 \`language en\`)`
   - **English**: `🌐 Language: English (switch with \`language ko\`)`

4. `language <ko|en>` mid-run switches immediately and ACKs in the new language.

## Persistence

This skill's cross-run state is the config + vault, not a language file. Language
is re-detected each invocation from the utterance; there is no stored language
field (the knowledge notes' language is self-evident from their content). Gate
tokens and the confirmation boundary (`proceed` before first write) remain
English regardless of `LANGUAGE`.

## Honest limitations

- Only Korean and English are first-class; any other request falls back to
  English with a short note.
- Detection is character-frequency based; a jargon-heavy invocation may
  misclassify. Recovery: `language <ko|en>` at any point, or re-invoke.
