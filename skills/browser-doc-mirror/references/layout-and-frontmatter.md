# Layout, frontmatter, and manifest spec

Full specification for the mirror tree. Confluence is the worked example; the
frontmatter abstracts to any browser-authenticated source via `source_*` fields.

## Table of contents

- Directory layout
- Filename convention
- Mirror-file frontmatter (Confluence keys are mandatory for Confluence)
- Canonical-URL rule
- Create vs. update, and staleness/refresh
- `_manifest.md` spec (incl. path base)

## Directory layout (project root)

```
doc-mirror/              # gitignored — internal knowledge, excluded from VCS.
  README.md               #   carries the `browser-doc-mirror` sentinel line + spec
  planning/               # mirror subtree; folder named after the source tree
    _manifest.md          # page index + sync-status checklist
    <number>-<slug>.md    # one mirror file per source page, hierarchy preserved
  analysis/               # notes DERIVED from the source (kept apart from mirrors)
```

- Default root is `doc-mirror/`, **not** `docs/` — a project's own `docs/` is
  usually version-controlled, and gitignoring it would silently un-track the
  team's real documentation. If the user names a different root, honor it, but
  the Step 0 fail-closed guard still applies (refuse a git-tracked or foreign
  root; verify the ignore on a concrete path before writing).
- Adopt-vs-bootstrap is decided by the **sentinel** — the `browser-doc-mirror`
  marker line in `<root>/README.md` — not by the mere existence of a README.
- Name the mirror subtree after the source tree/space (`planning/`, `arch/`, …).
- Keep raw mirrors and derived analysis in separate folders so provenance is
  unambiguous: `planning/` = faithful copy of the source, `analysis/` = your own
  design/analysis notes.

## Filename convention

Preserve the source's numbering and hierarchy in the filename so local order
matches the source tree:

```
03-01-2-con-상세설계.md      # section 3 › 1 › 2, "con" tag, title slug
```

Slugs may be Korean or English — mirror the source title. Zero-pad numeric
segments so lexical sort matches tree order.

## Mirror-file frontmatter

Every mirror file starts with YAML frontmatter. **Pick the key family by source
and make it mandatory** — do not mix:

- **Confluence source → the `confluence_*` keys are REQUIRED:** `confluence_id`
  (numeric page ID), `confluence_url`, `confluence_updated`.
- **Any other browser-authenticated source → the `source_*` keys:** `source_id`,
  `source_url`, `source_updated`.

Confluence example (required form for the default case):

```yaml
---
title: "상세 설계"
confluence_id: 123456789
confluence_url: https://wiki.example.com/pages/viewpage.action?pageId=123456789
confluence_version: 12            # source revision id (preferred for staleness); - if none
author: 홍길동
confluence_updated: 2026-07-10
synced_at: 2026-07-21            # when this body was fetched (freshness → manifest)
status: WIP           # WIP | 정본 (canonical) | -
parent: 03-01-con-설계개요
---
```

Non-Confluence source:

```yaml
---
title: '<source page title>'          # single-quoted; double any embedded '
source_id: '<stable page id>'         # QUOTE — a generic id may be YAML-unsafe
source_url: '<canonical URL>'
source_revision: '<revision id, or - if none>'
author: '<author>'
source_updated: <YYYY-MM-DD>
synced_at: <YYYY-MM-DD>
status: <WIP|정본|->
parent: '<parent mirror slug, if any>'
---
```

- **Serialize every externally-derived string scalar safely** — `title`,
  `author`, `source_url`, `parent`, **and `source_id`/`source_revision`** (a
  generic id like `*prod`, `{x: 1}`, `yes`, or one containing `: ` changes YAML
  type or breaks the parse). Wrap each in **single quotes and double any embedded
  single quote** (`O'Brien` → `'O''Brien'`), or emit it as a `|`-block scalar.
  Do not hand-add double quotes (a title with `"` then breaks). Numeric
  `confluence_id`/`confluence_version` may stay bare.
- If `author` or the source Updated date is genuinely unavailable, write `-`
  (never invent one); note the gap in the body.
- **Manifest cells** (`_manifest.md` is the sole resume record, so a corrupt row
  breaks reconciliation): before writing any cell, replace CR/LF with a space and
  escape `|` as `\|` and backslash as `\\`; strip other control characters.

## Canonical-URL rule

Store a **stable permalink / page-ID URL**, and strip anything ephemeral or
sensitive before persisting: auth callback codes, session tokens, signed query
params, tracking params (`utm_*`, etc.), and `#fragments`. For Confluence prefer
the `pageId=`/`viewpage.action` permalink over a display-title URL. If no safe
canonical URL can be determined, **stop** rather than persist a
credential-bearing URL.

## Create vs. update, re-sync reconciliation, and staleness

The skill mirrors **and** re-syncs. Match every page on its **stable source id**
(`confluence_id`/`source_id`), never on filename or title (those change on
rename).

- **Create** (no local file for this source id): write a fresh file from the
  frontmatter template. Use collision-refusing `ln tmp target && rm tmp` so an
  id/name clash fails loudly instead of clobbering.
- **Update, same path** (matched id, unchanged filename): rebuild the body,
  refresh `synced_at`/`source_updated`/revision, but **preserve the prior
  `> domain note`** (carry forward verbatim, or move to `analysis/`). Write to a
  temp file and atomically replace with `mv tmp target` only when complete.
  `doc-mirror/` is gitignored, so an in-place overwrite is unrecoverable.
- **Update, renamed** (matched id, changed number/slug): this is **not** an
  ordinary `mv` — the new filename may already belong to a *different* page, and
  `mv` would silently overwrite it. Treat as **create-new-then-retire**: confirm
  the destination is absent or maps to the *same* source id, `ln tmp new_target`
  (fails EEXIST on a foreign collision → stop and surface both source ids), then
  remove the old path only after the new file + manifest row are durable. A crash
  before removal leaves a safe duplicate, never data loss.
- **Atomic manifest.** `_manifest.md` is the sole resume record — update it via a
  same-directory temp + `mv`, never in place. Build mirror temp files **inside**
  the mirror root (same filesystem, no confidential temp content in the tracked
  tree or `/tmp`). There is no lock — the skill is single-invocation and rests
  crash-safety on these atomic writes + startup reconcile (lifecycle reference).
- **Re-sync reconciliation** (existing manifest vs. live tree): matched rows keep
  their status (refresh candidates — never reset `synced`→`pending`); pages only
  in the live tree are added as `pending`; pages only in the manifest are marked
  `removed?` and surfaced to the user **without** auto-deleting the local file or
  its `analysis/` notes.
- **Staleness requires a remote read.** `source_updated > synced_at` alone can
  never flip to stale after a sync — both dates freeze at the last fetch. On the
  refresh pass re-read the source's current **revision id** (preferred) or Updated
  value and compare to the stored one (`synced → stale → synced`). Record a
  separate `checked_at` for when that probe ran.
- **Metadata unavailable = cannot prove unchanged, not unchanged.** If the source
  exposes no comparable revision id (a bare `YYYY-MM-DD` date does **not** count —
  it misses same-day edits), mark the row `unknown` and **fully re-mirror** by
  default — never silently report it current. Optional content-hash short-circuit
  is defined in the lifecycle reference.

## `_manifest.md` spec

One manifest per mirror subtree. Header block records the source space/root and
that sync happens via the browser. Then a coverage table, then a priority
section.

Table columns (Revision + Checked carry the freshness contract):

| # | 페이지 (Page) | 소스 ID (Source ID) | 리비전 (Revision) | 상태 (Status) | 원문갱신 (Src updated) | 확인 (Checked) | 동기화 (Synced) | 로컬파일 (Local file) |

- **Revision** = `confluence_version` (Confluence) or `source_revision` (other),
  `-` if the source exposes none. Freshness comparison prefers it over the date.
- **Checked** = `checked_at`, the date of the last remote freshness probe (kept
  in the manifest so an unchanged page's mirror file stays byte-stable while
  "0 stale" still has durable evidence).

- **Path base:** the `로컬파일` column is written **relative to the mirror
  root** (e.g. `planning/03-01-con-설계개요.md`), not relative to the manifest's
  own folder. State this at the top of the manifest.
- Status values: `pending` (registered, not yet fetched), `synced` (mirrored,
  current), `stale` (mirrored but source changed since — set on the refresh
  pass), `unknown` (matched but freshness cannot be proven — no comparable
  revision/date), `removed?` (in the manifest but gone from the live tree on a
  re-sync; awaits user direction, local file kept). On an **initial mirror**
  register the entire tree `pending` first, then flip to `synced` as fetched. On
  a **re-sync** never reset established `synced` rows — reconcile (see the
  create/update section above).
- The **우선순위 (Priority)** section lists the user's own-domain pages to sync
  first, with checkboxes for completion tracking.
- The shipped `_manifest.md.template` has an **empty** table and priority list —
  fill it with the real tree; never leave example rows behind.
