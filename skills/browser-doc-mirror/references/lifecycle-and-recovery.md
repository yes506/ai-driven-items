# Lifecycle, transactions, and recovery

Mechanics the Step 0–5 workflow depends on. Read when implementing the write
path, resuming an interrupted run, or handling a non-`planning` subtree.

## Table of contents

- Execution model (no lock, single invocation)
- Subtree mode (decoupled from root mode)
- Filename slug sanitization (untrusted titles)
- The one transaction order (create / update / rename)
- Startup reconcile (crash recovery)
- Unknown-freshness rule

## Execution model (no lock, single invocation)

Claude Code runs **each Bash tool call in a fresh shell** (shell state does not
persist), and a mirror run spans many separate tool calls (browser + Write +
Bash). So a `trap`-based `.lock` or a `cd`/variable set in Step 0 cannot survive
to Steps 1–5 — an OS-process lock here would either release immediately
(protecting nothing) or, if forced to persist, wedge the root. **This skill has
no lock.** It assumes **one invocation at a time** (the manual norm) and rests
crash-safety on three primitives that *are* per-call-atomic:

- collision-refusing `ln` creates (EEXIST surfaces clashes),
- atomic `mv` for same-path updates and every manifest write,
- the **startup reconcile** below, which repairs any page↔manifest gap.

Carry the *absolute* paths forward yourself — `MIRROR_DIR="$TOP/$MIRROR_ROOT"`,
`SUBTREE_DIR="$MIRROR_DIR/$MIRROR_SUBTREE"` — and use them in every later tool
call; do not rely on Step 0's CWD or shell variables persisting. Skill-internal
debris from a crash (`.tmp.*`, `.keep`) is recoverable, not "foreign": Step 0
classifies a root holding only such debris as `new`.

## Subtree mode (decoupled from root mode)

`ROOT_MODE` (Step 0) answers only *is the root ours*. It does **not** answer the
state of the **selected subtree** — resolve `MIRROR_SUBTREE` in preflight
(default `planning`; validate it with the same containment rules as the root:
project-relative, no `..`/absolute/symlink/unsafe chars), then derive:

| `SUBTREE_MODE` | condition | legal operations |
|---|---|---|
| `absent` | `$MIRROR_ROOT/$MIRROR_SUBTREE/` missing | initial, add, **targeted-create** |
| `empty` | dir exists, no `_manifest.md` | initial, add, targeted-create (seed manifest first) |
| `partial` | manifest seeded, no `synced` rows yet | resume-initial, add, targeted |
| `established` | manifest has `synced`/`stale` rows | refresh, add, targeted |

Consequences that fix the round-3 findings:

- **targeted/add work on a NEW root** — a user who gives one URL gets exactly
  that page mirrored; never force a full-tree initial.
- **initial** is legal for `absent`/`empty`/`partial` of the *selected subtree*
  inside either a new or adopted root — so a second source subtree
  (`arch/`) can be initialized under an established root without touching
  `planning/`.
- **adopt** validates the *selected* subtree's manifest, never a hardcoded
  `planning/_manifest.md`.
- Final verification (Step 5) probes an actual fetched file recorded by the
  selected subtree's manifest, not `planning/...`.

## Filename slug sanitization (untrusted titles)

Source titles **and source ids** are untrusted data and must never choose a
path. Derive every mirror filename through this **one self-contained function**
(no leaked globals). Pass `collide=1` when the base name already maps to a
*different* source id — the function then appends a fixed-length hex digest of
the source id (computed inside, never raw id text):

```bash
# slugify PREFIX TITLE SID [COLLIDE]  -> prints the final single-segment filename
slugify() {
  prefix="$1"; title="$2"; sid="$3"; collide="$4"
  # prefix must be a real numbering token: >=1 digit, only digits/dots/hyphens,
  # and short (a legit hierarchy prefix is like "03-01-2"; reject a pathological one)
  case "$prefix" in *[!0-9.-]*|'') echo "ABORT: bad numbering prefix" >&2; return 1;; esac
  case "$prefix" in *[0-9]*) : ;; *) echo "ABORT: prefix needs a digit" >&2; return 1;; esac
  [ "${#prefix}" -gt 40 ] && { echo "ABORT: numbering prefix too long" >&2; return 1; }
  # Allowlist unsupported code points -> '-' (this is NOT Unicode normalization;
  # it just removes anything outside the safe set). Collapse/trim separators.
  slug="$(printf '%s' "$title" \
    | LC_ALL=C.UTF-8 sed 's#[^A-Za-z0-9._가-힣-]#-#g; s#-\{2,\}#-#g; s#^[.-]*##; s#[.-]*$##')"
  case "$slug" in ''|*..*) slug="page";; esac                       # never empty / no '..' token
  case "$slug" in CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9]) slug="_$slug";; esac  # reserved names
  frag=""; [ -n "$collide" ] && frag="-$(printf '%s' "$sid" | { shasum 2>/dev/null || sha1sum; } | cut -c1-8)"
  name="${prefix}-${slug}${frag}.md"
  # Bound the WHOLE filename in bytes (common component limit ~255; stay well under).
  # Trim the slug (not the prefix/frag) if needed, then re-assemble.
  if [ "$(printf '%s' "$name" | wc -c)" -gt 120 ]; then
    keep=$(( 120 - ${#prefix} - ${#frag} - 4 ))                     # 4 = "-" + ".md"
    [ "$keep" -lt 1 ] && keep=1
    slug="$(printf '%s' "$slug" | cut -b1-"$keep")"; name="${prefix}-${slug}${frag}.md"
  fi
  printf '%s\n' "$name"
}
```

The result contains no `/`, so it is a **single path segment** — directory
traversal is structurally impossible. **Before writing**, still resolve the
target's parent and assert it is beneath `$SUBTREE_DIR` without crossing a
symlink (defense in depth); if not, stop.

## The one transaction order (create / update / rename)

Build the **complete** file (frontmatter + body + preserved/refreshed
`> domain note`) in a temp **inside the mirror root**, then publish, then commit
the manifest — one order for every write:

1. Render the complete temp (including the domain note) → `$SUBTREE_DIR/.tmp.<id>`.
2. Install:
   - *create* / *rename-target*: `ln "$SUBTREE_DIR/.tmp.<id>" "$SUBTREE_DIR/<name>" && rm "$SUBTREE_DIR/.tmp.<id>"`
     (fails EEXIST — a foreign collision stops and surfaces both source ids).
   - *update, same path*: `mv "$SUBTREE_DIR/.tmp.<id>" "$SUBTREE_DIR/<name>"` (atomic replace).
3. Commit the manifest row atomically (same-dir temp + `mv`, Step 4), pointing at
   the installed target.
4. *rename only*: retire the old path **after** the manifest row is durable. If
   the `rm` of the old path fails, keep and report the safe duplicate.

The domain note is part of step 1's temp, never appended after install — so the
published file is always complete.

## Startup reconcile (crash recovery)

Before the operation loop, reconcile the manifest against the filesystem by
**stable source id**, with count checks. Two crash states matter:

- **create crash** — `pending` row + exactly one complete matching file → the
  previous run installed the file but died before committing; finish the manifest
  transition (→ `synced`), do not re-create (which would hit `ln` EEXIST).
- **rename crash** — a `synced` row still points at the *old* path while a same-id
  file exists at the *new* path. Repoint only when **exactly one** candidate new
  file exists AND its frontmatter parses AND its `confluence_id`/`source_id`
  matches AND its name equals the sanitized name for the reconciled live
  title/parent; then retire the old file. Otherwise quarantine and surface — do
  **not** delete the known-good old mirror on an ambiguous or hand-made duplicate.
  Symmetric state (manifest already points *new*, old retire failed): keep the
  referenced new file, quarantine the unreferenced same-id old duplicate.
- **orphan / mismatch** — a mirror file with no manifest row, or a duplicate/
  mismatched id → `mkdir -p "$MIRROR_DIR/.quarantine"` then
  `ln "$file" "$MIRROR_DIR/.quarantine/<sid-hexfrag>-<basename>" && rm "$file"`
  (collision-refusing move — the `rm` removes the original only after the link
  succeeds, else the orphan is rediscovered next run). Surface it; never
  overwrite, never auto-index.
- **missing file** — a manifest row whose local file is absent is **local
  corruption**, not upstream removal: re-fetch (create). Mark `removed?` only
  when the upstream page is separately confirmed gone.

## Unknown-freshness rule

Default (safe + executable): **when a page exposes no comparable revision id — a
bare `YYYY-MM-DD` date does not count (it misses same-day edits) — always fully
re-mirror it** on a refresh, keep its freshness `unknown`, and advance manifest
`checked_at`. Never report it `synced`/current on absent evidence.

Optional optimization (only if defined): compute a `content_hash` over the
**canonical extracted source body** — the raw `get_page_text` region, excluding
frontmatter and the local `> domain note` — persist it in the manifest, and
transition `unknown → synced` only when the freshly-extracted body hashes equal.
Do not hash the rendered Markdown file (its frontmatter/notes are volatile).

> The default root was `docs-mirror/` in commits `40b45c6`–`cb8da84` and is now
> `doc-mirror/`. The skill was **never released**, so no external `docs-mirror/`
> caches exist and there is no migration path to maintain — this is noted only so
> a future editor doesn't reintroduce one.
