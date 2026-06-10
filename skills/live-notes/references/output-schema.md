# Output schema — the saved note file

The shape of the markdown file the skill writes at Phase 3 `confirm
save`. Designed for Obsidian compatibility (frontmatter YAML, wikilinks
optional, tag syntax) and grep portability.

## Path

```
{NOTES_DIR}/{CATEGORY}/{YYYY-MM-DD}-{HHmm}-{title-slug}.md
```

See [workspace-layout.md](workspace-layout.md) for the path components.

## File structure

```markdown
---
title: "{title}"
date: {YYYY-MM-DD}
time: "{HH:MM}"
created: {ISO_LOCAL_started}
modified: {ISO_LOCAL_finished}
category: {category-slug}
tags:
  - {tag1}
  - {tag2}
source: live-notes
---

# {title}

> _{YYYY-MM-DD HH:MM} · {duration} · {turn-count} turns captured_

## TL;DR

- {bullet 1}
- {bullet 2}
- {bullet 3}
{up to 5 bullets total}

---

## {Section heading 1}

{section body — preserves user's prose; light edits only}

## {Section heading 2}

{…}

{optional further sections}

---

## References

{only present when web research happened OR the user pasted URLs}

- [{source title}]({URL}) — {one-line synopsis}
- [{source title}]({URL}) — {one-line synopsis}
```

The horizontal-rule (`---`) above each major boundary is intentional —
it makes the TL;DR / detail / references separation visible in
Obsidian's reading view without forcing a heavier H1/H2 nesting scheme.

## Frontmatter keys (always English)

| Key | Type | Source | Notes |
|---|---|---|---|
| `title` | string | AI-synthesized in Phase 2 | Quoted to allow `:` and other YAML-special chars |
| `date` | string `YYYY-MM-DD` | Capture **start** date, local | Unquoted (YAML date) |
| `time` | string `HH:MM` | Capture **start** time, local | Quoted (avoid YAML sexagesimal coercion) |
| `created` | string ISO-8601 with TZ offset | Capture start | Machine-readable variant |
| `modified` | string ISO-8601 with TZ offset | Phase 3 save time | Machine-readable variant |
| `category` | string | Phase 2 proposal / Phase 3 override | Whitelisted slug; see [workspace-layout.md](workspace-layout.md) |
| `tags` | list of strings | AI-derived from content | 3–7 tags; kebab-case lowercase ASCII; Obsidian-compatible (no leading `#`) |
| `source` | constant `live-notes` | hardcoded | Lets the user grep all live-notes outputs across vaults |

The frontmatter is **stable across LANGUAGE settings** — keys stay
English so Obsidian's parsers, future grep, and any downstream
tooling read the same schema regardless of who wrote the note.

`tags` examples:

```yaml
tags:
  - meeting
  - q3-planning
  - team-sync
```

NOT `- 회의` — Obsidian tags must be ASCII-clean for query reliability.
The display label is the prose body's job, not the tag's.

## Body content rules

### Title heading (H1)

One H1, matches `title` in frontmatter. Obsidian treats this as the
canonical document title even when the file name differs.

### Provenance line

Single italicized line right under the H1, blockquoted, giving:

```
> _{YYYY-MM-DD HH:MM} · {Nm Ms duration} · {N} turns captured_
```

Examples:

- `> _2026-06-10 14:30 · 1h 12m · 38 turns captured_`
- `> _2026-06-10 14:30 · 22m · 14 turns captured_`

Duration uses `Nh Mm` ≥ 1h, `Mm` ≥ 1m, `Ss` < 1m. Turns = number of
content chunks (excluding meta-commands).

### TL;DR section

H2 heading `TL;DR`. 3–5 bullets, single-sentence each. See
[synthesis-and-research.md#synthesis-steps](synthesis-and-research.md)
for the synthesis rules.

The exact heading string follows `LANGUAGE`:

- English: `## TL;DR`
- Korean: `## 한 줄 요약` (Korean readers don't always parse "TL;DR";
  the explicit translation is clearer)

### Detail sections

H2 sections derived from the buffer's topic structure. See
[synthesis-and-research.md#synthesis-steps](synthesis-and-research.md)
step 4 — user-inserted section dividers are honored exactly.

Within sections:

- Preserve user prose verbatim where possible. Light edits (typo, obvious
  abbreviation expansion) allowed; heavy rewriting forbidden.
- Code blocks: preserve fence language tag if present, infer if missing
  (e.g. `bash` for shell snippets, `python` for `def`/`import`).
- Quoted external material: blockquote with attribution if the user
  said where it came from.

### References section

Present **only if** Phase 2 did web research or the user pasted URLs
during capture. Omitted entirely when empty — no `## References` with
"(none)" body, just no section.

Heading follows `LANGUAGE`:

- English: `## References`
- Korean: `## 참고 자료`

### Obsidian wikilinks

If during synthesis the AI notices a reference to *another note in the
same vault* (the user said "see my Q2 sync notes"), it MAY format as
`[[Q2-sync]]` only when:

- The user explicitly used wikilink-style syntax in the buffer, OR
- A file named `*Q2-sync*.md` exists in `${NOTES_DIR}` (cheap glob
  check — `find "${NOTES_DIR}" -name '*Q2-sync*.md' -type f`).

Otherwise prefer plain prose. **Never fabricate wikilinks** to notes
that don't exist — broken wikilinks pollute the vault's graph view.

## Write atomicity

The Phase 3 write must be atomic-enough that a crash mid-write
doesn't half-create the file, AND must never silently overwrite an
existing target (the no-silent-overwrite rule in
[SKILL.md's Forbidden actions](../SKILL.md#forbidden-actions)).

**Do not use a bash heredoc to embed the note content.** Same reason
as the capture-mode append recipe — user content can contain a line
that matches the heredoc terminator and close it early, truncating
the saved note. See
[capture-mode.md](capture-mode.md#append-mechanics--byte-safe-two-step-recipe).

Use a **two-step recipe** instead — `Write` tool carries the note
content (byte-safe), `bash` only handles the path-level rename and
collision guard:

**Step 1** — ensure the target's parent directory exists:

```bash
mkdir -p "$(dirname "${TARGET_PATH}")"
```

**Step 2** — write the full note content to a temp path via the
`Write` tool:

```
Write tool input:
  file_path: "{TARGET_PATH}.tmp.{SESSION_ID}"
  content:   "{full note bytes — frontmatter + body + references}"
```

Using `{SESSION_ID}` (not `$$`) in the temp suffix keeps the temp
filename deterministic from the agent's perspective, so a crashed
half-write leaves a clearly-named orphan the user can inspect.

**Step 3** — atomic rename with collision refusal. POSIX `link(2)`
fails when the destination exists — that's the race-safe primitive:

```bash
TMP_PATH="${TARGET_PATH}.tmp.${SESSION_ID}"

if ln "${TMP_PATH}" "${TARGET_PATH}" 2>/dev/null; then
  rm -f "${TMP_PATH}"
else
  # Two possible reasons: target exists (collision), or cross-FS link
  # (would only happen if user's TEMP_DIR is on a different FS than the
  # notes dir, which our temp-in-same-dir pattern prevents).
  if [ -e "${TARGET_PATH}" ]; then
    echo "BLOCKER: target exists at ${TARGET_PATH} — use 'revise overwrite' if intentional" >&2
    # Keep ${TMP_PATH} so the user can inspect what would have been written.
    exit 1   # (use `return 1` instead if you embed this in a shell function)
  fi
  # Should not reach here — surface for diagnosis.
  echo "BLOCKER: rename failed for unknown reason (target absent, but ln rejected)" >&2
  exit 1   # (use `return 1` instead if you embed this in a shell function)
fi
```

`ln` (hard-link) on the same filesystem is atomic and refuses to
overwrite. `rm "${TMP_PATH}"` after a successful `ln` finalizes the
"move" — the target now has the canonical name and the temp inode
is gone.

**On `revise overwrite`** (explicit user override after the Phase 3
preview surfaced a collision), substitute step 3 with:

```bash
mv "${TMP_PATH}" "${TARGET_PATH}"
```

Plain `mv` here is appropriate because the user has explicitly asked
to overwrite. **Never use `mv` as the default path — it overwrites
silently on macOS / Linux / BSD.** This was empirically reproduced
during review; do not regress it.

> **macOS portability note**: `mv -n` (no-clobber) does work on
> macOS Darwin, but on collision it exits 0 silently and leaves the
> source intact, which is fragile to detect from the calling agent.
> The `ln` + `rm` pattern above is portable and explicit, so prefer it.

After successful rename:

1. Print the final absolute path to the user.
2. Delete the buffer-draft file **and any leftover per-chunk temps**
   for the session (defensive — under normal flow the per-turn sweep
   has already merged all chunks, so the `*.chunk.*.tmp` glob is
   empty, but the cleanup keeps `.live-notes-drafts/` tidy after any
   anomaly). Both `rm` calls use `-f` so the cleanup is silent on
   already-absent paths:
   ```bash
   rm -f "${NOTES_DIR}/.live-notes-drafts/${SESSION_ID}.draft.md"
   { setopt null_glob 2>/dev/null || shopt -s nullglob 2>/dev/null; } || true
   rm -f "${NOTES_DIR}/.live-notes-drafts/${SESSION_ID}.chunk."*.tmp
   ```
3. Surface the next-step hint:
   - English: `Saved. Open in Obsidian or your editor of choice.`
   - Korean: `저장 완료. 옵시디언 또는 선호하는 편집기로 열어 확인하세요.`

## Failure handling at write

- Target path's parent directory missing → `mkdir -p`, then retry.
- Permission denied → surface OSError; offer to write to
  `~/${NOTES_DIR_NAME}/` as a fallback (with user confirmation).
- Disk full → surface error; offer to truncate the References section
  and retry (if research bloated the note unexpectedly).
- Concurrent same-filename race (extremely unlikely) → the collision
  check at Phase 3 preview should catch this; if it slips through,
  the `ln`-based rename in step 3 above refuses cleanly and leaves
  both files intact for the user to resolve.

## Honest limitations

- The frontmatter schema is fixed; the user cannot configure it
  per-session. A user who wants e.g. `summary:` as a frontmatter key
  edits the note post-save.
- Obsidian's tag query syntax requires ASCII tags — non-ASCII tags
  break searches. This is a hard Obsidian constraint, not a skill
  choice.
- The skill does not generate Obsidian backlinks proactively. Users
  who want a backlinks-rich vault build that themselves via Obsidian's
  graph plugin.
- Notes written by this skill carry the `source: live-notes` frontmatter
  field — useful for greppability, but if you fork the skill and rename
  it, update that constant accordingly.
