#!/usr/bin/env python3
"""Stage 1a — build a redacted Evidence Bundle and compute evidence_id.

The bundle is the ONLY thing the distill LLM is allowed to see (pre-redaction
gate, A2/A3). Raw transcript/diff never reaches the model or the vault.

Usage:
  prepare_source.py --skill-dir DIR --mode manual|hook|file|stdin \
      [--repo REPO_ROOT] [--excerpt-file PATH] [--session ID] [--turn ID]

Reads the source excerpt from --excerpt-file or stdin. Diff is derived from the
repo via `git status --porcelain` semantics (ignored files excluded, A14).
Writes <vault>/Knowledge/.state/evidence/<evidence_id>.json and prints the
evidence_id and a redaction summary as JSON on stdout.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import kh_common as kh


def git_dirty_hash(repo: str | None) -> tuple[str | None, str | None]:
    if not repo:
        return None, None
    try:
        head = subprocess.run(["git", "-C", repo, "rev-parse", "HEAD"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None, None
    # Porcelain excludes gitignored files by default -> never hashes secret.env.
    porc = subprocess.run(["git", "-C", repo, "status", "--porcelain"],
                          capture_output=True, text=True).stdout
    names = sorted(line[3:] for line in porc.splitlines() if line[3:].strip())
    dirty = kh.hashlib.sha256("\n".join(names).encode()).hexdigest()[:16]
    return head, dirty


def redact(text: str) -> tuple[str, list[dict]]:
    """Pre-LLM redaction: replace findings with typed placeholders."""
    findings = kh.scan_secrets(text)
    out = text
    for pat in kh._HARD_PATTERNS:
        out = pat.sub("«REDACTED:credential»", out)
    for pat in kh._PII_PATTERNS:
        out = pat.sub("«REDACTED:pii»", out)
    # entropy sweep replacement
    def _mask(m):
        return "«REDACTED:high-entropy»" if kh._looks_like_live_secret(m.group(0)) else m.group(0)
    out = kh.re.sub(r"[A-Za-z0-9_\-]{24,}", _mask, out)
    return out, findings


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill-dir", required=True, type=Path)
    ap.add_argument("--mode", required=True,
                    choices=["manual", "hook", "file", "stdin"])
    ap.add_argument("--repo")
    ap.add_argument("--excerpt-file", type=Path)
    ap.add_argument("--session")
    ap.add_argument("--turn")
    ap.add_argument("--tool", default="claude")
    ap.add_argument("--source-range", default="")
    args = ap.parse_args()

    cfg = kh.load_config(args.skill_dir)

    # Read binary-safe (never crash on invalid UTF-8) and bound the excerpt —
    # the bundle is meant to be a bounded excerpt, and an unbounded blob would
    # also make the redaction entropy sweep expensive.
    MAX_EXCERPT = 256 * 1024
    if args.excerpt_file:
        data = args.excerpt_file.read_bytes()
    else:
        data = sys.stdin.buffer.read()
    truncated = len(data) > MAX_EXCERPT
    raw = data[:MAX_EXCERPT].decode("utf-8", "replace")
    if truncated:
        raw += "\n\n[…excerpt truncated to 256KB…]"

    head, dirty = git_dirty_hash(args.repo)
    redacted, findings = redact(raw)

    if not redacted.strip() and not dirty:
        print(json.dumps({"status": "nothing-harvestable"}))
        return 0

    bundle = {
        "schema_version": 1,
        "source_mode": args.mode,
        "tool": args.tool,
        "session_id": args.session,
        "turn_id": args.turn,
        "repo_root": args.repo,
        "git_head": head,
        "git_dirty_hash": dirty,
        "source_range": args.source_range,
        "excerpt": redacted,
        "redaction": kh.redaction_summary(findings),
    }
    evidence_id = kh.stable_hash(bundle)
    bundle["evidence_id"] = evidence_id
    bundle["harvested"] = kh.now_iso()  # volatile, excluded from evidence_id

    ev_dir = kh.state_dir(cfg) / "evidence"
    ev_dir.mkdir(parents=True, exist_ok=True)
    (ev_dir / f"{evidence_id}.json").write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": "ok",
        "evidence_id": evidence_id,
        "bundle_path": str(ev_dir / f"{evidence_id}.json"),
        "redaction": bundle["redaction"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
