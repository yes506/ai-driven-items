# Design rationale, architecture, and coverage scope

For installation steps and troubleshooting, see [setup.md](setup.md).

## Why this design (and not the Data Portability API)

An earlier iteration of this pipeline used Google's Data Portability API. That
API is restricted to EU/EEA + Switzerland + UK and is unavailable to many
non-EU accounts. The current design reads Chrome's local SQLite history
directly, which:

- Works in any region, no API gating
- Captures Chrome searches across all your synced devices (mobile + desktop)
- Has no OAuth, no Google Cloud project, no 7-day re-auth cycle
- Has no rate limit; you can run it as often as you want

The trade-off: it doesn't capture searches done outside Chrome (Safari, in-app
search bars, etc.). See coverage section below.

## Architecture

```
┌─ /loop 6h /collect-searches ─────────────────────────────────────┐
│                                                                  │
│  Stage 1 (Python, deterministic) — collect.py                    │
│   ├─ Copy Chrome's History DB to a tempfile (it's locked open)   │
│   ├─ Read keyword_search_terms (local omnibox queries)           │
│   ├─ Read urls table for google.com/search?q=… (synced devices)  │
│   ├─ Filter by cursor.last_seen_chrome_ts + content-hash dedup   │
│   ├─ Write each new record as JSON to <Vault>/Search/_inbox/     │
│   └─ Advance cursor only on success                              │
│                                                                  │
│  Stage 2 (Claude, intelligent) — /collect-searches               │
│   For each inbox/*.json:                                         │
│   ├─ Classify into <Vault>/Search/<Category>/                    │
│   ├─ Enrich with WebSearch (1–3 reliable sources)                │
│   ├─ Write <Category>/<YYYY-MM-DD>-<slug>.md                     │
│   └─ Delete the inbox JSON on success                            │
└──────────────────────────────────────────────────────────────────┘
```

## Coverage — what's captured

- Google searches done in Chrome on this machine (typed into omnibox or
  address bar)
- Google searches done in Chrome on **any other signed-in device**
  (iPhone/Android/iPad/Windows) via Chrome Sync
- Google searches via clicked search-result URLs (extracted from the `urls`
  table)

## Coverage — what's NOT captured

- Safari searches (mobile or desktop) — different browser, no sync to Chrome
- In-app searches on iOS (Google app, Spotlight web fallback)
- Chrome with Sync disabled or signed out
- Chrome Incognito / private windows
- Searches on engines other than Google (the script restricts to
  `google.<tld>/search`)

If you mostly search in Safari on iPhone, this won't capture much. Run the
coverage verification queries in [setup.md](setup.md) to check your actual
coverage before committing.

## Operational notes

- **Chrome must release its DB lock** for `sqlite3.connect` to succeed
  cleanly. We side-step this by `shutil.copy2`-ing `History` (and any `-wal`
  / `-shm` sidecars) to a tempfile and querying the copy. Chrome can stay
  open.
- **Cursor advances every run** because Chrome history is idempotent —
  re-querying the same range with the same cursor returns the same data, and
  hash dedup keeps the inbox clean. Failure paths exit before cursor write.
- **Cost** — Stage 2 makes a few Claude calls + WebSearches per record.
  Trivial at typical search volumes.
- **First run** without the cursor seed will export every Google search
  Chrome remembers (potentially years). See `setup.md` step 2 for the
  one-liner that seeds the cursor to "now" before backfill kicks in.
- **Stage 2 is prompt-orchestrated**, not a deterministic script. Acceptable
  for personal use; a future hardening would move file iteration, YAML
  escaping, and inbox cleanup into Python.
- **Concurrency** — `collect.py` acquires a non-blocking `fcntl` lock on
  `state/collect.lock`. A second invocation while the first is running exits
  cleanly.
