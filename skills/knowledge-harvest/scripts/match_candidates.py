#!/usr/bin/env python3
"""Stage 1d — deterministic Fast-tier match + bounded top-k candidate retrieval.

Given a distilled unit's title/aliases/tags, this does the deterministic work the
match step must NOT delegate to the LLM:
  - Fast tier: exact concept-id / alias hit across ALL categories (global-flat).
  - Top-k: rank the rest by alias/tag/lexical overlap and return only a bounded
    slice, so the LLM judges a candidate list instead of the whole vault.

Reads `.state/index.jsonl` (produced by build_index.py). Prints JSON:
  { "concept_id": "<slugified title>",
    "exact": {concept_id, path, category, status} | null,
    "candidates": [ {concept_id, path, category, title, aliases, score}, ... ] }

Usage:
  match_candidates.py --skill-dir DIR --title "…" [--alias A --alias B] \
      [--tag T ...] [--top-k N]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import kh_common as kh


def tokens(*strings: str) -> set[str]:
    out: set[str] = set()
    for s in strings:
        for t in kh.re.split(r"[^a-z0-9]+", (s or "").lower()):
            if len(t) >= 3:
                out.add(t)
    return out


def load_index(cfg: dict) -> list[dict]:
    p = kh.state_dir(cfg) / "index.jsonl"
    if not p.exists():
        return []
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-dir", required=True, type=Path)
    ap.add_argument("--title", required=True)
    ap.add_argument("--alias", action="append", default=[])
    ap.add_argument("--tag", action="append", default=[])
    ap.add_argument("--top-k", type=int, default=10)
    args = ap.parse_args()
    cfg = kh.load_config(args.skill_dir)

    concept_id = kh.slugify(args.title)
    alias_slugs = {kh.slugify(a) for a in args.alias}
    query = tokens(args.title, *args.alias) | {t.lower() for t in args.tag}

    index = load_index(cfg)
    cap = cfg["limits"]["max_index_entries_per_category"]
    by_id = {e.get("concept_id"): e for e in index}

    def as_target(e: dict) -> dict:
        # A superseded note must not win — redirect to its successor if present,
        # else flag for review so stale knowledge stops being an update target.
        if e.get("status") == "superseded":
            succ = by_id.get(e.get("superseded_by"))
            if succ is not None:
                return {"concept_id": succ.get("concept_id"), "path": succ.get("path"),
                        "category": succ.get("category"), "status": succ.get("status"),
                        "content_sha256": succ.get("content_sha256"),
                        "redirected_from": e.get("concept_id")}
            return {"concept_id": e.get("concept_id"), "path": e.get("path"),
                    "category": e.get("category"), "status": "superseded",
                    "content_sha256": e.get("content_sha256"), "review_required": True}
        return {"concept_id": e.get("concept_id"), "path": e.get("path"),
                "category": e.get("category"), "status": e.get("status"),
                "content_sha256": e.get("content_sha256")}

    exact = None
    scored: list[tuple[float, dict]] = []
    for e in index:
        if e.get("status") in ("deprecated", "superseded"):   # not candidate targets
            # still allow exact detection below (for redirect), but skip scoring
            e_aliases0 = e.get("aliases") or []
            e_alias_slugs0 = {kh.slugify(a) for a in e_aliases0 if isinstance(a, str)}
            if exact is None and (e.get("concept_id") == concept_id
                                  or concept_id in e_alias_slugs0
                                  or alias_slugs & ({e.get("concept_id")} | e_alias_slugs0)):
                exact = as_target(e)
            continue
        e_aliases = e.get("aliases") or []
        e_alias_slugs = {kh.slugify(a) for a in e_aliases if isinstance(a, str)}
        # Fast tier: exact concept-id or alias-slug overlap.
        if exact is None and (
            e.get("concept_id") == concept_id
            or concept_id in e_alias_slugs
            or alias_slugs & ({e.get("concept_id")} | e_alias_slugs)
        ):
            exact = as_target(e)
            continue
        cand_tokens = tokens(e.get("title", ""), *[a for a in e_aliases if isinstance(a, str)]) \
            | {str(t).lower() for t in (e.get("tags") or [])}
        overlap = len(query & cand_tokens)
        if overlap:
            scored.append((overlap, e))

    scored.sort(key=lambda x: (-x[0], x[1].get("concept_id", "")))
    candidates = [{
        "concept_id": e.get("concept_id"), "path": e.get("path"),
        "category": e.get("category"), "title": e.get("title", ""),
        "aliases": e.get("aliases") or [], "score": score,
        "content_sha256": e.get("content_sha256"),
    } for score, e in scored[:min(args.top_k, cap)]]

    print(json.dumps({"concept_id": concept_id, "exact": exact,
                      "candidates": candidates}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
