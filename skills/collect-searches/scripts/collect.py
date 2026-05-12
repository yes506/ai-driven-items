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

GOOGLE_SEARCH_PATH_RE = re.compile(r"^https?://(www\.)?google\.[a-z.]+/search$")


def log(msg: str) -> None:
    print(f"[collect] {msg}", flush=True)


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


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
    tmpdir = Path(tempfile.mkdtemp(prefix="chrome-hist-"))
    dest = tmpdir / "History"
    shutil.copy2(src, dest)
    for suffix in ("-wal", "-shm"):
        sidecar = src.with_name(src.name + suffix)
        if sidecar.exists():
            shutil.copy2(sidecar, dest.with_name(dest.name + suffix))
    return dest


def query_keyword_search_terms(conn: sqlite3.Connection, since_chrome_ts: int) -> list[dict]:
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
    return [
        {
            "chrome_ts": r[0],
            "query": r[1],
            "url": r[2],
            "page_title": r[3] or "",
            "source": "keyword_search_terms",
        }
        for r in rows
        if r[1]
    ]


def query_google_search_urls(conn: sqlite3.Connection, since_chrome_ts: int) -> list[dict]:
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
    for chrome_ts, url, title in rows:
        parsed = urllib.parse.urlparse(url)
        if not GOOGLE_SEARCH_PATH_RE.match(f"{parsed.scheme}://{parsed.netloc}{parsed.path}"):
            continue
        params = urllib.parse.parse_qs(parsed.query)
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
    return records


def to_record(raw: dict) -> dict:
    """Shape compatible with Stage 2 prompts (title / titleUrl / time)."""
    iso_time = chrome_ts_to_iso(raw["chrome_ts"])
    return {
        "title": f"Searched for {raw['query']}",
        "titleUrl": raw["url"],
        "time": iso_time,
        "query": raw["query"],
        "page_title": raw["page_title"],
        "products": ["Search"],
        "source": raw["source"],
    }


def hash_record(record: dict) -> str:
    key = f"{record.get('time', '')}|{record.get('query', '')}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def filter_new(records: list[dict], cursor: dict) -> list[dict]:
    last_ts = cursor.get("last_seen_chrome_ts") or 0
    seen_hashes = set(cursor.get("recent_hashes", []))
    seen_in_batch: set[str] = set()
    new_records: list[dict] = []
    for record in records:
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
        save_json(path, record)
        written += 1
    return written


def advance_cursor(cursor: dict, raw_records: list[dict], new_records: list[dict]) -> dict:
    if not raw_records:
        return cursor
    max_chrome_ts = max(r["chrome_ts"] for r in raw_records)
    new_hashes = [hash_record(r) for r in new_records]
    cursor["recent_hashes"] = (cursor.get("recent_hashes", []) + new_hashes)[-HASH_HISTORY_SIZE:]
    cursor["last_seen_chrome_ts"] = max_chrome_ts
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
    inbox_dir = vault_path / "Search" / "_inbox"
    history_src = Path(config["chrome"]["history_path"]).expanduser()

    cursor = load_json(CURSOR_PATH, {"last_seen_chrome_ts": 0, "recent_hashes": []})
    log(f"cursor.last_seen_chrome_ts={cursor.get('last_seen_chrome_ts')}")

    db_copy = copy_history_db(history_src)
    log(f"copied Chrome history DB to {db_copy}")
    try:
        with sqlite3.connect(f"file:{db_copy}?mode=ro", uri=True) as conn:
            since = int(cursor.get("last_seen_chrome_ts") or 0)
            kst_rows = query_keyword_search_terms(conn, since)
            url_rows = query_google_search_urls(conn, since)
    finally:
        shutil.rmtree(db_copy.parent, ignore_errors=True)

    log(f"keyword_search_terms: {len(kst_rows)} rows")
    log(f"google.com/search urls: {len(url_rows)} rows")

    raw = sorted(kst_rows + url_rows, key=lambda r: r["chrome_ts"])
    records = [to_record(r) for r in raw]
    new_records = filter_new(records, cursor)
    log(f"{len(new_records)} new records after dedup")

    written = write_inbox(new_records, inbox_dir)
    log(f"wrote {written} files to {inbox_dir}")

    cursor = advance_cursor(cursor, raw, new_records)
    save_json(CURSOR_PATH, cursor)
    log(f"cursor advanced to chrome_ts={cursor.get('last_seen_chrome_ts')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
