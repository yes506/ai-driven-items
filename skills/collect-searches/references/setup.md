# First-time setup

How to wire up `collect-searches` on a fresh machine. The design rationale,
architecture, and what is / isn't captured live in [design.md](design.md).

## Prerequisites

- Python 3.11+ (uses stdlib `tomllib`, `fcntl`, `sqlite3` — Unix-like systems
  only; Windows users should run via WSL)
- Chrome installed and signed in with **history sync ON**
- An Obsidian vault you can write to
- Claude Code in a US-region context (WebSearch is US-only)

## Verify your coverage first (10 seconds)

Before you set anything up, check whether Chrome has enough data to make this
worthwhile. Use SQLite's `immutable=1` URI mode so you don't have to quit
Chrome:

```bash
sqlite3 'file:'"$HOME"'/Library/Application Support/Google/Chrome/Default/History?mode=ro&immutable=1' \
  'SELECT COUNT(*) FROM keyword_search_terms;'

sqlite3 'file:'"$HOME"'/Library/Application Support/Google/Chrome/Default/History?mode=ro&immutable=1' \
  "SELECT COUNT(*) FROM urls WHERE url LIKE '%google.%/search%';"
```

A few syntax notes that bite people:

- Use **single quotes** around the URI in the outer position. In zsh the `&`
  is a job-control operator and `?` is a glob wildcard; double quotes
  preserve `&` but the shell still errors on the `?` with
  `zsh: no matches found`. Single quotes neutralize both.
- If you see `Error: database is locked`, you dropped the
  `?mode=ro&immutable=1` URI parameters — Chrome holds an exclusive write
  lock on the live DB, and that flag tells SQLite to skip lock acquisition.
  Alternative: quit Chrome (⌘Q) and use a plain double-quoted path.
- On Linux, replace the path with `~/.config/google-chrome/Default/History`.
  On Windows (WSL), point at the Chrome profile under `/mnt/c/Users/...`.

If both numbers are reasonable for your last few months of searching, proceed.
If they're tiny but you search a lot, your search activity is probably
happening in Safari or another browser — this pipeline won't help. See
[design.md](design.md) for what's in/out of scope.

## Setup (one-time)

1. **Configure**

   From the skill root (the directory containing `SKILL.md`):

   ```bash
   cp config.example.toml config.toml
   ```

   Edit `config.toml` and confirm `vault.path` and `chrome.history_path` are
   correct. Both fields accept `~` / `$HOME`. Multi-profile users: replace
   `Default` with `Profile 1`, `Profile 2`, etc.

2. **Seed the cursor (recommended)**

   To avoid a flood on first run, seed the cursor to "now" so only future
   searches are ingested:

   ```bash
   python3 -c 'import json, datetime, pathlib; \
   ts_us = int((datetime.datetime.now(datetime.timezone.utc).timestamp() + 11644473600) * 1_000_000); \
   p = pathlib.Path("state/cursor.json"); p.parent.mkdir(parents=True, exist_ok=True); \
   json.dump({"last_seen_chrome_ts": ts_us, "recent_hashes": []}, open(p, "w"), indent=2)'
   ```

   Skip this step if you want to backfill your entire Chrome history.

3. **First run (manual)**

   From the skill root:

   ```bash
   python3 scripts/collect.py
   ```

   Expected output:

   ```
   [collect] cursor.last_seen_chrome_ts=…
   [collect] copied Chrome history DB to /tmp/chrome-hist-…/History
   [collect] keyword_search_terms: N rows
   [collect] google.com/search urls: N rows
   [collect] N new records after dedup
   [collect] wrote N files to <Vault>/Search/_inbox
   [collect] cursor advanced to chrome_ts=…
   ```

   Verify (substitute your vault path):

   ```bash
   ls "<Vault>/Search/_inbox/"
   ```

4. **Verify Stage 2 manually**

   In Claude Code:

   ```
   /collect-searches
   ```

   Confirm Claude reads each inbox JSON, classifies it, enriches with
   WebSearch, writes a Markdown note under `<Vault>/Search/<Category>/`, and
   deletes the inbox JSON.

5. **Start the loop (optional)**

   ```
   /loop 6h /collect-searches
   ```

   No upper bound on cadence — pick what you want (1h / 6h / 24h are all
   fine). Lighter cadence = fewer wake-ups but larger batches.

## File layout

```
collect-searches/
├── SKILL.md                     Stage 2 entrypoint (frontmatter + steps)
├── config.example.toml          template — copy to config.toml
├── config.toml                  your config (gitignored)
├── requirements.txt             empty — stdlib only
├── .gitignore
├── scripts/
│   └── collect.py               Stage 1: Python collector (Chrome SQLite)
├── prompts/
│   ├── classify.md              Stage 2 classify rules
│   └── enrich.md                Stage 2 enrich rules
├── references/
│   ├── setup.md                 you are here
│   └── design.md                design rationale + coverage + ops notes
└── state/                       runtime state (gitignored)
    ├── cursor.json              { last_seen_chrome_ts, recent_hashes[] }
    └── collect.lock             fcntl mutex (auto-released on process exit)
```

## Troubleshooting

- `Chrome history DB not found at …` → check `chrome.history_path` in
  `config.toml`. Chrome must be installed and signed in at least once.
- `database is locked` → unlikely because we copy first, but if it happens,
  close Chrome and retry. The copy approach should make this near-impossible.
- Empty `keyword_search_terms` count → omnibox search recording is disabled,
  or you've never searched via the address bar. The `urls` query should still
  pick up search activity.
- Stage 2 enrichment skipped on every record → WebSearch returns nothing.
  Verify your Claude Code session is in a US region.
- Same record written twice → the cursor + hash dedup should prevent this.
  Inspect `state/cursor.json` and file an issue.
