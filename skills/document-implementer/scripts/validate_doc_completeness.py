#!/usr/bin/env python3
"""validate_doc_completeness.py — structural completeness for text-stack output.

For OUTPUT_STACK=text only. Verifies that every `## stub: <id>` in the
planner-emitted `document-plan.md` produced a corresponding section in the
implementer-emitted TARGET_PATH (markdown anchor `#<stub-id>` reachable).

Usage:
  validate_doc_completeness.py <document-plan.md> <target-path.md>

Exits 0 on completeness, 1 on missing-section, 2 on usage error.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

STUB_HEADING = re.compile(r"^\s*##\s+stub:\s*([A-Za-z0-9_-]+)\s*$")


def slugify_heading(text: str) -> str:
    """Approximate GitHub-style markdown anchor slugification."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text.strip("-")


def declared_stub_ids(plan_path: Path) -> set[str]:
    declared: set[str] = set()
    for raw in plan_path.read_text(encoding="utf-8").splitlines():
        match = STUB_HEADING.match(raw)
        if match:
            declared.add(match.group(1))
    return declared


def target_anchors(target_path: Path) -> set[str]:
    """Collect anchors from every markdown heading + explicit `id=` attrs."""
    anchors: set[str] = set()
    text = target_path.read_text(encoding="utf-8")
    for raw in text.splitlines():
        heading = re.match(r"^\s*#{1,6}\s+(.+?)\s*$", raw)
        if heading:
            anchors.add(slugify_heading(heading.group(1)))
            for stub_id in re.findall(r"<a\s+id=[\"']([A-Za-z0-9_-]+)[\"']", raw):
                anchors.add(stub_id)
    for stub_id in re.findall(r"<a\s+id=[\"']([A-Za-z0-9_-]+)[\"']", text):
        anchors.add(stub_id)
    return anchors


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        sys.stderr.write(f"usage: {argv[0]} <document-plan.md> <target-path.md>\n")
        return 2

    plan_path = Path(argv[1])
    target_path = Path(argv[2])
    if not plan_path.is_file():
        sys.stderr.write(f"not a file: {plan_path}\n")
        return 2
    if not target_path.is_file():
        sys.stderr.write(f"not a file: {target_path}\n")
        return 2

    declared = declared_stub_ids(plan_path)
    anchors = target_anchors(target_path)
    missing = sorted(declared - anchors)

    if missing:
        sys.stderr.write(
            f"validate_doc_completeness: FAIL — {len(missing)} stub(s) "
            f"missing from {target_path.name}\n"
        )
        for stub_id in missing:
            sys.stderr.write(f"  - {stub_id}\n")
        return 1

    sys.stdout.write(
        f"validate_doc_completeness: OK "
        f"({len(declared)} stub(s) resolved in {target_path.name})\n"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
