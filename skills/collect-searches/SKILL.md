---
name: collect-searches
description: |
  Run the Chrome-search-history → Obsidian pipeline once. Reads Chrome's
  local SQLite history, classifies each Google search into an Obsidian
  category folder, enriches with WebSearch (1–3 reliable sources), and
  writes one Markdown note per query. Stage 1 is a deterministic Python
  collector (`scripts/collect.py`) that owns the cursor and stages JSON
  to a vault inbox; Stage 2 is this prompt-orchestrated workflow that
  classifies, enriches, and writes the final notes. Designed to be run
  periodically (e.g. `/loop 6h /collect-searches`). Has side effects:
  writes notes under the vault, deletes inbox files after success.
  Manual invocation only — `/collect-searches`.
disable-model-invocation: true
---

# Collect Searches

## Overview

Drain the search inbox and refresh the user's Obsidian Search vault. One pass
through the pipeline:

1. `scripts/collect.py` reads Chrome's history DB → writes new search records
   as JSON files to the vault inbox. Owns the cursor and the lock.
2. This SKILL.md workflow reads each inbox JSON, classifies into a category
   folder, enriches with WebSearch, writes the final Markdown note, deletes
   the inbox JSON.

First-time setup (config copy, optional cursor seed, coverage check) lives in
`${CLAUDE_SKILL_DIR}/references/setup.md`. Architecture and the rationale for
reading Chrome's local SQLite (rather than the Data Portability API) live in
`${CLAUDE_SKILL_DIR}/references/design.md`.

## Paths

- Skill root: `${CLAUDE_SKILL_DIR}`
- Vault root: read `vault.path` from the user's `config.toml` next to this
  file (created on first run by copying `config.example.toml`; see
  `${CLAUDE_SKILL_DIR}/references/setup.md` if missing)
- Inbox: `${vault}/Search/_inbox/`
- Category root: `${vault}/Search/`

If `config.toml` is missing, stop and direct the user to
`${CLAUDE_SKILL_DIR}/references/setup.md`.

## Steps

1. **Collect** — invoke the Python collector:

   ```bash
   python3 ${CLAUDE_SKILL_DIR}/scripts/collect.py
   ```

   The collector copies Chrome's History DB, queries for new Google searches
   since the cursor, deduplicates, and stages each new record as a JSON file
   in `${vault}/Search/_inbox/`. It exits cleanly if another invocation
   already holds the lock.

   When there are no new searches, no inbox files are written — proceed to
   step 2 anyway. If `collect.py` exits non-zero, stop and surface the error.

2. **Process inbox** — list `${vault}/Search/_inbox/*.json`. If empty, you're
   done.

3. **For each inbox file**:

   a. **Read** the JSON record. Fields you'll use: `query`, `time` (ISO
      datetime), `titleUrl` (the search URL), `page_title`.

   b. **Classify** using the rules in
      `${CLAUDE_SKILL_DIR}/prompts/classify.md`.

      List existing folders directly under `${vault}/Search/` (excluding
      `_inbox`) and pick one, or propose a new TitleCase category.

      **Sanitize** the chosen category name. It must match `^[A-Za-z0-9 _-]+$`
      and must not contain `..`, `/`, or `\`. If sanitization fails, fall
      back to `Misc`.

   c. **Enrich** using the rules in `${CLAUDE_SKILL_DIR}/prompts/enrich.md`.

      Use the WebSearch tool to add 1–3 reliable sources. Skip enrichment for
      vague navigational queries (mark `enrichment: skipped`).

      Note: WebSearch is US-only. If WebSearch returns no usable results,
      write the note with `enrichment: skipped` and proceed.

   d. **Write** the resulting Markdown to
      `${vault}/Search/<Category>/<YYYY-MM-DD>-<slug>.md`. Create the
      category folder if needed. If the filename collides, append `-2`,
      `-3`, etc.

   e. **Delete** the inbox JSON file only after the note is written
      successfully.

      If any step fails for this record, leave the inbox file in place and
      continue with the next.

4. **Summary** — print a brief report: how many records processed, how many
   succeeded, how many failed (with reasons), and which categories were used.

## Constraints

- Do not modify files outside `${vault}/Search/` and the inbox.
- Do not advance any cursor manually — `collect.py` owns that state.
- Do not query Chrome's DB directly — `collect.py` is the only thing that
  reads it.

## Supporting files

- `scripts/collect.py` — Stage 1 Python collector (Chrome SQLite reader,
  dedup, inbox writer)
- `prompts/classify.md` — categorization rules used in step 3b
- `prompts/enrich.md` — enrichment rules + Obsidian note template used in
  step 3c
- `config.example.toml` — template; user copies to `config.toml` on first run
- `state/cursor.json` — runtime cursor (managed by `collect.py`, do not edit
  manually)
- `references/setup.md` — first-time setup walkthrough, prerequisites,
  coverage check, troubleshooting
- `references/design.md` — design rationale, architecture, coverage scope,
  operational notes
