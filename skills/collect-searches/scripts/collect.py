#!/usr/bin/env python3
"""Collect Google searches from Chrome's local SQLite history and stage to vault inbox.

Stage 1 reads Chrome's History DB (synced across signed-in Chrome instances on
desktop and mobile), extracts Google search queries from two sources, dedupes
against a cursor, and writes inbox JSON files for Stage 2 to enrich.

Sources combined:
  - keyword_search_terms table (queries typed into the local omnibox)
  - urls + visits filtered by google.com/search?q=... (covers synced devices)

State files (gitignored):
  state/cursor.json  { last_seen_chrome_ts, recent_hashes }
  state/collect.lock fcntl mutex
"""

from __future__ import annotations

import datetime as dt
import fcntl
import hashlib
import json
import re
import shutil
import sqlite3
import sys
import tempfile
import tomllib
import urllib.parse
from pathlib import Path

HASH_HISTORY_SIZE = 2000

SKILL_DIR = Path(__file__).resolve().parent.parent
STATE_DIR = SKILL_DIR / "state"
CONFIG_PATH = SKILL_DIR / "config.toml"
CURSOR_PATH = STATE_DIR / "cursor.json"
LOCK_PATH = STATE_DIR / "collect.lock"

CHROME_EPOCH_OFFSET_SECONDS = 11_644_473_600  # 1601-01-01 → 1970-01-01

# Constrained to the Google TLD shape: google.<2-3 letters>(.<2-3 letters>)?
# Real examples: google.com, google.de, google.co.kr, google.com.au, google.co.uk
# Rejects look-alike hosts such as google.example.com or google.evil-site.com.
GOOGLE_SEARCH_PATH_RE = re.compile(
    r"^https?://(www\.)?google\.[a-z]{2,3}(\.[a-z]{2,3})?/search$"
)


def log(msg: str) -> None:
    print(f"[collect] {msg}", flush=True)


def is_google_search_url(url: str) -> bool:
    """Return True iff the URL's scheme+host+path is a Google search endpoint.

    Used by both SQL paths so the Google-only contract is enforced uniformly,
    regardless of whether a row came in via keyword_search_terms or via the
    google.<tld>/search? URL filter.
    """
    if not url:
        return False
    parsed = urllib.parse.urlparse(url)
    return bool(
        GOOGLE_SEARCH_PATH_RE.match(f"{parsed.scheme}://{parsed.netloc}{parsed.path}")
    )


def chrome_ts_to_iso(chrome_us: int) -> str:
    """Convert Chrome's microseconds-since-1601 to ISO 8601 UTC."""
    unix_seconds = (chrome_us / 1_000_000) - CHROME_EPOCH_OFFSET_SECONDS
    return dt.datetime.fromtimestamp(unix_seconds, tz=dt.timezone.utc).isoformat()


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise SystemExit(
            f"Missing {CONFIG_PATH}. Copy config.example.toml to config.toml and fill in values."
        )
    with open(CONFIG_PATH, "rb") as f:
        config = tomllib.load(f)
    if not config.get("vault", {}).get("path"):
        raise SystemExit("config.toml missing required field: vault.path")
    if not config.get("chrome", {}).get("history_path"):
        raise SystemExit("config.toml missing required field: chrome.history_path")
    return config


def load_json(path: Path, default):
    if not path.exists():
        return default
    with open(path) as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def acquire_lock():
    # The lock file at state/collect.lock is created on first run and remains
    # on disk afterwards. fcntl.flock is released automatically when the file
    # descriptor closes (process exit or fp.close()); the file itself is just
    # a stable inode for flock to attach to and is intentionally not unlinked.
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fp = open(LOCK_PATH, "w")
    try:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        fp.close()
        return None
    return fp


def copy_history_db(src: Path) -> Path:
    """Chrome holds an exclusive lock on the live DB. Copy it to a temp path first."""
    if not src.exists():
        raise SystemExit(f"Chrome history DB not found at {src}")
    if not src.is_file():
        raise SystemExit(
            f"chrome.history_path is not a file: {src}. "
            "Point it at Chrome's `History` SQLite file, not the containing profile directory."
        )
    tmpdir = Path(tempfile.mkdtemp(prefix="chrome-hist-"))
    dest = tmpdir / "History"
    shutil.copy2(src, dest)
    for suffix in ("-wal", "-shm"):
        sidecar = src.with_name(src.name + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, dest.with_name(dest.name + suffix))
    return dest


def query_keyword_search_terms(
    conn: sqlite3.Connection, since_chrome_ts: int
) -> tuple[list[dict], int]:
    """Returns (Google-filtered records, max raw chrome_ts seen).

    Chrome populates `keyword_search_terms` for whichever search engine is the
    user's default. If the default is not Google (or if a third-party keyword
    provider writes rows), the visited URL won't be a google.<tld>/search? — we
    drop those rows here to honor the Google-only contract documented in
    SKILL.md and design.md. The max raw chrome_ts is returned separately so
    `_run` can still advance the cursor past rejected rows (otherwise the
    same non-Google rows get re-scanned every run).
    """
    rows = conn.execute(
        """
        SELECT v.visit_time, kst.term AS query, u.url AS visit_url, u.title AS page_title
        FROM visits v
        JOIN urls u ON v.url = u.id
        JOIN keyword_search_terms kst ON kst.url_id = u.id
        WHERE v.visit_time > ?
        ORDER BY v.visit_time
        """,
        (since_chrome_ts,),
    ).fetchall()
    records: list[dict] = []
    max_raw_ts = since_chrome_ts
    for chrome_ts, query, url, page_title in rows:
        if chrome_ts > max_raw_ts:
            max_raw_ts = chrome_ts
        if not query:
            continue
        if not is_google_search_url(url):
            continue
        records.append({
            "chrome_ts": chrome_ts,
            "query": query,
            "url": url,
            "page_title": page_title or "",
            "source": "keyword_search_terms",
        })
    return records, max_raw_ts


def query_google_search_urls(
    conn: sqlite3.Connection, since_chrome_ts: int
) -> tuple[list[dict], int]:
    """Returns (Google-filtered records, max raw chrome_ts seen).

    The SQL `LIKE '%google.%/search?%'` is intentionally loose to keep the
    index path fast; the precise host check happens in `is_google_search_url`.
    Returning the max raw timestamp lets `_run` advance the cursor past
    SQL-matched-but-regex-rejected rows so they don't get re-scanned forever.
    """
    rows = conn.execute(
        """
        SELECT v.visit_time, u.url, u.title
        FROM visits v
        JOIN urls u ON v.url = u.id
        WHERE u.url LIKE '%google.%/search?%'
          AND v.visit_time > ?
        ORDER BY v.visit_time
        """,
        (since_chrome_ts,),
    ).fetchall()
    records: list[dict] = []
    max_raw_ts = since_chrome_ts
    for chrome_ts, url, title in rows:
        if chrome_ts > max_raw_ts:
            max_raw_ts = chrome_ts
        if not is_google_search_url(url):
            continue
        params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        query = (params.get("q") or [None])[0]
        if not query:
            continue
        records.append({
            "chrome_ts": chrome_ts,
            "query": query,
            "url": url,
            "page_title": title or "",
            "source": "urls_google_search",
        })
    return records, max_raw_ts


def to_record(raw: dict) -> dict:
    """Shape compatible with Stage 2 prompts (title / titleUrl / time).

    `chrome_ts` is preserved so `filter_new` can enforce the cursor as a
    Python-side belt-and-suspenders check on top of the SQL `WHERE` clause.
    """
    iso_time = chrome_ts_to_iso(raw["chrome_ts"])
    return {
        "title": f"Searched for {raw['query']}",
        "titleUrl": raw["url"],
        "time": iso_time,
        "chrome_ts": raw["chrome_ts"],
        "query": raw["query"],
        "page_title": raw["page_title"],
        "products": ["Search"],
        "source": raw["source"],
    }


def hash_record(record: dict) -> str:
    key = f"{record.get('time', '')}|{record.get('query', '')}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def filter_new(records: list[dict], cursor: dict) -> list[dict]:
    """Belt-and-suspenders dedup: hash-based identity + cursor-based time bound.

    The SQL `WHERE v.visit_time > ?` already filters by cursor, but defending
    against a future backfill path (or an out-of-order record) requires the
    Python check too.
    """
    last_ts = int(cursor.get("last_seen_chrome_ts") or 0)
    seen_hashes = set(cursor.get("recent_hashes", []))
    seen_in_batch: set[str] = set()
    new_records: list[dict] = []
    for record in records:
        if int(record.get("chrome_ts") or 0) <= last_ts:
            continue
        h = hash_record(record)
        if h in seen_hashes or h in seen_in_batch:
            continue
        seen_in_batch.add(h)
        new_records.append(record)
    return new_records


_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(s: str) -> str:
    return _SAFE_CHARS.sub("_", s).strip("_")[:80] or "record"


def write_inbox(records: list[dict], inbox_dir: Path) -> int:
    inbox_dir.mkdir(parents=True, exist_ok=True)
    written = 0
    for record in records:
        ts = safe_filename(record.get("time", "unknown"))
        h = hash_record(record)
        path = inbox_dir / f"{ts}-{h}.json"
        if path.exists():
            continue
        # Strip the internal-only `chrome_ts` before serializing — Stage 2
        # consumes title / titleUrl / time / query / page_title / source /
        # products. `chrome_ts` exists only so `filter_new` can enforce the
        # cursor as a Python-side belt-and-suspenders check.
        public_record = {k: v for k, v in record.items() if k != "chrome_ts"}
        save_json(path, public_record)
        written += 1
    return written


def advance_cursor(cursor: dict, new_records: list[dict], sql_max_ts: int) -> dict:
    """Advance cursor past every SQL row this run saw, regex-rejected ones too.

    Earlier versions advanced only past kept records, which left
    SQL-matched-but-regex-rejected rows (e.g. news.google.com/search) being
    re-scanned every run forever — wasted work, not data loss. Using the
    `sql_max_ts` from the raw SQL result sets closes that nag.
    """
    new_hashes = [hash_record(r) for r in new_records]
    cursor["recent_hashes"] = (cursor.get("recent_hashes", []) + new_hashes)[-HASH_HISTORY_SIZE:]
    prev_ts = int(cursor.get("last_seen_chrome_ts") or 0)
    cursor["last_seen_chrome_ts"] = max(prev_ts, int(sql_max_ts))
    return cursor


def main() -> int:
    config = load_config()

    lock_fp = acquire_lock()
    if lock_fp is None:
        log("another collect.py is already running; exiting cleanly")
        return 0

    try:
        return _run(config)
    finally:
        lock_fp.close()


def _run(config: dict) -> int:
    vault_path = Path(config["vault"]["path"]).expanduser()
    if not vault_path.is_dir():
        raise SystemExit(
            f"vault.path does not exist or is not a directory: {vault_path}. "
            "Create the Obsidian vault first, then re-run."
        )
    inbox_dir = vault_path / "Search" / "_inbox"
    history_src = Path(config["chrome"]["history_path"]).expanduser()

    cursor = load_json(CURSOR_PATH, {"last_seen_chrome_ts": 0, "recent_hashes": []})
    log(f"cursor.last_seen_chrome_ts={cursor.get('last_seen_chrome_ts')}")

    db_copy = copy_history_db(history_src)
    log(f"copied Chrome history DB to {db_copy}")
    try:
        with sqlite3.connect(f"file:{db_copy}?mode=ro", uri=True) as conn:
            since = int(cursor.get("last_seen_chrome_ts") or 0)
            kst_rows, kst_max_ts = query_keyword_search_terms(conn, since)
            url_rows, url_max_ts = query_google_search_urls(conn, since)
    finally:
        shutil.rmtree(db_copy.parent, ignore_errors=True)

    log(f"keyword_search_terms: {len(kst_rows)} rows (Google-filtered)")
    log(f"google.com/search urls: {len(url_rows)} rows (regex-filtered)")

    sql_max_ts = max(since, kst_max_ts, url_max_ts)

    raw = sorted(kst_rows + url_rows, key=lambda r: r["chrome_ts"])
    records = [to_record(r) for r in raw]
    new_records = filter_new(records, cursor)
    log(f"{len(new_records)} new records after dedup")

    written = write_inbox(new_records, inbox_dir)
    log(f"wrote {written} files to {inbox_dir}")

    cursor = advance_cursor(cursor, new_records, sql_max_ts)
    # Cursor advances on Stage 1 success only; Stage 2 (LLM enrich/write) is
    # decoupled and operates on the inbox JSONs, so a Stage 2 failure leaves
    # files in the inbox without rewinding the cursor.
    save_json(CURSOR_PATH, cursor)
    log(f"cursor advanced to chrome_ts={cursor.get('last_seen_chrome_ts')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
