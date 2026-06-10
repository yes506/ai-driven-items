# Workspace layout & categorization

How `live-notes` decides *where* to write the final note, and how the
sub-directory category is chosen. The Phase 0 inspector
(`scripts/inspect_workspace.sh`) emits the JSON this document
interprets — see the schema comment at the top of that script.

## Project root resolution

1. Run `scripts/inspect_workspace.sh` once on invocation.
2. If `in_git_repo: true` → `ROOT = git_toplevel`. The notes dir lives
   at the **repo root**, not the cwd. Rationale: the user invariably
   means "the project I'm in", and the repo root is the canonical
   anchor; capturing notes from a deep subdirectory shouldn't fragment
   the notes tree.
3. If `in_git_repo: false` → `ROOT = cwd`. No git → no canonical root,
   so cwd is the best we have.

## Notes directory naming

```
NOTES_DIR_NAME = "{basename(ROOT)}-notes"
NOTES_DIR      = "{ROOT}/{NOTES_DIR_NAME}"
```

Examples:

| `ROOT` | `NOTES_DIR` |
|---|---|
| `/repos/my-app` | `/repos/my-app/my-app-notes/` |
| `/Users/dh/Desktop/scratch` | `/Users/dh/Desktop/scratch/scratch-notes/` |
| `/Users/dh/Obsidian Vault/Daily` | `/Users/dh/Obsidian Vault/Daily/Daily-notes/` |

Edge cases:

- `basename(ROOT)` contains spaces (e.g. `Obsidian Vault`) → kept as-is;
  the path-quoting handles it. The notes dir is still browsable in Obsidian.
- `NOTES_DIR` path already exists as a *file* (not a directory) —
  the inspector reports `notes_dir_kind: "file"`. Refuse cleanly
  during the Phase 0 ACK with a hard error like *"❌ `{NOTES_DIR}` is
  a regular file, not a directory. Rename or remove it and re-run
  `/live-notes`."* — never `mkdir -p` over a file (that fails with
  "Not a directory"), never overwrite. The user must resolve the
  collision before continuing.
- `ROOT` is read-only (e.g. mounted FS) — surface the OSError when Phase
  3 attempts the write, and offer a sibling-of-`$HOME` fallback.

## Creation gate

`NOTES_DIR` is **NOT** created in Phase 0. The Phase 0 ACK only echoes
the resolved path. Creation is deferred to **Phase 3 (`confirm save`)**:

```bash
mkdir -p "${NOTES_DIR}/${CATEGORY}"
```

Reason: a capture session that the user aborts must leave **zero**
filesystem residue. The buffer-draft (under `.live-notes-drafts/`) is
the only mid-session write, and it lives **inside** `NOTES_DIR` so its
creation also waits — but Phase 1's first content message triggers
`mkdir -p "${NOTES_DIR}/.live-notes-drafts"` as the first on-disk
mutation (Phase 1 boundary, not Phase 0).

## Gitignore handling (non-blocking)

If `in_git_repo: true` and `gitignore_has_notes: false`, attach a
**non-blocking** one-line nudge to the Phase 0 ACK. The user is NOT
required to respond — anything other than the literal `gitignore yes`
token is treated as note content (chunk 1) and means "leave tracked".

> 💡 `<NOTES_DIR_NAME>/` will be tracked by git. Type `gitignore yes`
> to add it to `.gitignore`, or just start typing your note.

Recognized responses:

- `gitignore yes` → append `<NOTES_DIR_NAME>/` to `${ROOT}/.gitignore`,
  no commit. The user can commit later or keep it as an unstaged change.
  Echo the appended entry, then begin Phase 1 awaiting chunk 1.
- **Anything else** → treat as chunk 1 content (the "leave tracked"
  default). Begin Phase 1 immediately with this message as the first
  capture.

This honors the user's "별다른 것은 물어볼 필요 없이" spec: the nudge
is informational, not a gate. Some users *want* their notes versioned;
some absolutely don't — but neither group should be forced to type a
yes/no token before their first note lands.

If `in_git_repo: false` or `gitignore_has_notes: true`, omit the nudge
entirely.

## Categorization (sub-directory selection)

The AI proposes a sub-directory at **Phase 2 synthesis**, the user
confirms or overrides at **Phase 3 preview**.

### Proposal rules

1. **Inspect the captured content** for category signals:
   - Words like "meeting", "회의", "standup", "1:1", "review" → `meetings/`
   - Words like "study", "공부", "tutorial", "learning", "course" → `study/`
   - Project-name mentions (e.g. "kt-id-front-v2", "auth flow") →
     `projects/<project-slug>/`
   - Code/lang-heavy content (extensive snippets, error stacks) →
     `tech/<lang-or-topic>/` (e.g. `tech/typescript/`, `tech/git/`)
   - Personal reflection / journal-ish prose → `journal/`
   - Research / link-heavy / topic-survey content → `research/<topic-slug>/`
   - None of the above match → `inbox/` (default catch-all; user re-files later)

2. **Single proposal, not a menu.** Show the user *one* proposed
   category with a one-line rationale, plus the `revise category
   <slug>` escape hatch. Avoid decision fatigue at finish time.

3. **Slug rules** for the proposed category:
   - Lowercase ASCII, kebab-case, hyphen-separated.
   - Up to two levels deep (e.g. `projects/auth-flow/`); deeper nests
     create file-system clutter without paying back in discoverability.
   - No leading slash, no trailing slash in the slug; the skill
     concatenates `${NOTES_DIR}/${CATEGORY}/`.
   - Reject category overrides that contain `..`, absolute paths, or
     path-traversal patterns. The whitelist regex enforces "exactly
     0 or 1 slash":

     ```
     ^[a-z0-9][a-z0-9_-]*(/[a-z0-9][a-z0-9_-]*)?$
     ```

     Examples that pass: `inbox`, `meetings`, `projects/auth-flow`,
     `tech/typescript`. Examples that fail (rejected): `projects/foo/deep`
     (too deep), `/abs`, `../up`, `A-bad` (uppercase), `foo bar` (space).

### Override at Phase 3

User can type:

- `revise category meetings/weekly-sync` — change category, re-preview
- `revise category inbox` — fall back to catch-all

The skill validates the slug against the whitelist before re-rendering.

## File naming

Within `${NOTES_DIR}/${CATEGORY}/`:

```
{YYYY-MM-DD}-{HHmm}-{title-slug}.md
```

Examples:

- `2026-06-10-1430-q3-roadmap-sync.md`
- `2026-06-10-1602-rust-iterators-deep-dive.md`

Rules:

- Date+time prefix uses **local time** (matches user mental model;
  ISO-8601 in frontmatter for machine-readable variant).
- `title-slug` is derived from the AI-synthesized title, kebab-cased,
  ASCII-folded for non-Hangul characters. **Hangul characters in the
  title are preserved verbatim in the slug** — Obsidian and macOS/Linux
  handle Hangul in filenames natively, and the user reads filenames
  too. (If portability to non-Unicode-aware tooling matters, override
  via `revise title <english-title>` at Phase 3.)
- Length: clamp slug to 60 chars; truncate at the last word boundary.
- Collision: if `{filename}.md` exists in the target category, append
  `-2`, `-3`, …. Never silently overwrite. Surface the collision in
  the Phase 3 preview so the user can choose to overwrite explicitly
  (`revise overwrite`).

## Honest limitations

- Category proposal is heuristic — the AI looks at surface keywords,
  not semantic intent. `revise category` is the cheap escape hatch.
- The `inbox/` default exists so a category mismatch never blocks save.
- The skill does not move or re-file previously-saved notes. Once a
  note lands in `meetings/`, moving it to `projects/X/` is a manual
  user action.
- Categories are flat per session. The skill writes **one** category
  per save. If a single capture session genuinely belongs in two
  categories, the user splits it manually post-hoc (or runs the skill
  twice on the same content via `revise content`).
