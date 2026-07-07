#!/usr/bin/env python3
"""Validate a knowledge note's frontmatter before it is trusted.

A thin CLI over the shared validators in kh_common (single source of truth with
apply_plan's create-body check). Enforces the schema in references/vault-schema.md:
required keys, safe concept-id slug, legal category/status, aliases shape, and
(optionally) that concept-id/category match the deterministically resolved target.

Usage:
  validate_note.py --skill-dir DIR --file NOTE.md
  validate_note.py --skill-dir DIR --stdin --category Tools --concept-id slug
Prints a JSON verdict; exit 0 if valid, 1 if invalid.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import kh_common as kh


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-dir", required=True, type=Path)
    ap.add_argument("--file", type=Path)
    ap.add_argument("--stdin", action="store_true")
    ap.add_argument("--concept-id")
    ap.add_argument("--category")
    args = ap.parse_args()
    kh.load_config(args.skill_dir)  # validates config exists

    if args.file:
        if not args.file.is_file():
            print(json.dumps({"valid": False, "errors": [f"no such file: {args.file}"]}))
            return 1
        text = args.file.read_text(encoding="utf-8", errors="replace")
    else:
        text = sys.stdin.buffer.read().decode("utf-8", "replace")

    fm = kh.parse_frontmatter(text)
    if fm is None:
        print(json.dumps({"valid": False, "errors": ["no parseable frontmatter"]}))
        return 1
    errs = kh.validate_note_fields(fm, expect_concept=args.concept_id,
                                   expect_category=args.category)
    print(json.dumps({"valid": not errs, "errors": errs,
                      "concept_id": fm.get("concept-id")}, ensure_ascii=False))
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
