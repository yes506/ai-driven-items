#!/usr/bin/env python3
"""Stage 1b — build a deterministic index of the vault for fuzzy matching.

Parses YAML frontmatter with a real parser (never regex, A13). Emits a bounded
JSON-lines index the match LLM consumes; the LLM never scans the vault itself.
Malformed notes are surfaced as errors (routed to _needs-review by the caller),
never silently skipped.

Ignores operational/hidden paths: dot-dirs (.state/.ledger), _needs-review,
backups, temp files, and non-markdown.

Usage: build_index.py --skill-dir DIR
Writes <vault>/Knowledge/.state/index.jsonl and prints a summary JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

import kh_common as kh

IGNORE_DIRS = {kh.NEEDS_REVIEW, ".state", ".ledger", "backups", "evidence", "plans"}


def parse_frontmatter(text: str) -> dict | None:
    text = text.lstrip("﻿")   # tolerate a UTF-8 BOM from some editors
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    data = yaml.safe_load(text[3:end])   # may raise yaml.YAMLError — caller guards
    return data if isinstance(data, dict) else None


def first_summary_line(text: str, fm_end: int) -> str:
    for line in text[fm_end:].splitlines():
        s = line.strip()
        if s and not s.startswith("#") and not s.startswith("##"):
            return s[:200]
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-dir", required=True, type=Path)
    args = ap.parse_args()
    cfg = kh.load_config(args.skill_dir)
    root = kh.knowledge_root(cfg)

    entries: list[dict] = []
    errors: list[dict] = []
    if root.exists():
        for cat in kh.CATEGORIES:
            cat_dir = root / cat
            if not cat_dir.is_dir():
                continue
            for md in sorted(cat_dir.rglob("*.md")):
                parts = set(md.relative_to(root).parts)
                if parts & IGNORE_DIRS or md.name.startswith(".tmp"):
                    continue
                if not md.is_file():        # a directory literally named "x.md"
                    continue
                try:
                    text = md.read_text(encoding="utf-8", errors="replace")
                    fm = parse_frontmatter(text)
                except (OSError, yaml.YAMLError) as e:
                    errors.append({"path": str(md), "reason": f"unreadable/invalid: {e}"})
                    continue
                if not fm or "concept-id" not in fm:
                    errors.append({"path": str(md), "reason": "missing/invalid frontmatter"})
                    continue
                cid = fm.get("concept-id")
                if not isinstance(cid, str):   # int/None concept-id would crash downstream
                    errors.append({"path": str(md), "reason": f"concept-id not a string: {cid!r}"})
                    continue
                fm_cat = fm.get("category", cat)
                if fm_cat != cat:              # frontmatter must agree with the folder
                    errors.append({"path": str(md),
                                   "reason": f"category {fm_cat!r} != folder {cat!r}"})
                    continue
                aliases = fm.get("aliases", [])
                if not isinstance(aliases, list):
                    aliases = [aliases] if isinstance(aliases, str) else []
                tags = fm.get("tags", [])
                if not isinstance(tags, list):
                    tags = [tags] if isinstance(tags, str) else []
                fm_end = text.lstrip("﻿").find("\n---", 3) + 4
                content_sha = kh.hashlib.sha256(md.read_bytes()).hexdigest()
                entries.append({
                    "path": str(md),
                    "concept_id": cid,
                    "content_sha256": content_sha,   # deterministic CAS source for updates
                    "title": str(fm.get("title", "")),
                    "category": cat,
                    "tags": tags,
                    "aliases": aliases,
                    "status": fm.get("status", "active"),
                    "superseded_by": fm.get("superseded-by"),
                    "summary": first_summary_line(text, fm_end),
                    "updated": str(fm.get("updated", "")),
                })

    out = kh.state_dir(cfg) / "index.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(json.dumps({
        "status": "ok",
        "index_path": str(out),
        "count": len(entries),
        "errors": errors,
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
