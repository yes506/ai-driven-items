#!/usr/bin/env python3
"""validate_internal_refs.py — resolve [[stub-id]] references in document-plan.md.

Reads `## stub: <id>` headings as the declared-stub set. Walks every
`[[stub-id]]` occurrence in the body and verifies it resolves. Orphaned
stubs (declared but unreferenced) are warned, not failed.

Exits 0 on success, 1 on unresolved references, 2 on usage error.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

STUB_HEADING = re.compile(r'^\s*##\s+stub:\s*([A-Za-z0-9_-]+)\s*$')
WIKILINK = re.compile(r'\[\[([A-Za-z0-9_-]+)\]\]')


def validate(path: Path) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). errors block exit-0, warnings don't."""
    errors: list[str] = []
    warnings: list[str] = []
    try:
        text = path.read_text(encoding='utf-8')
    except OSError as e:
        return [f"cannot read {path}: {e}"], warnings

    declared: dict[str, int] = {}
    references: list[tuple[str, int]] = []

    for lineno, raw in enumerate(text.splitlines(), start=1):
        heading = STUB_HEADING.match(raw)
        if heading:
            stub_id = heading.group(1)
            if stub_id in declared:
                errors.append(
                    f"line {lineno}: duplicate stub declaration `{stub_id}` "
                    f"(first declared on line {declared[stub_id]})"
                )
            else:
                declared[stub_id] = lineno
            continue
        for match in WIKILINK.finditer(raw):
            references.append((match.group(1), lineno))

    declared_set = set(declared)
    referenced_set = {r for r, _ in references}

    for ref_id, lineno in references:
        if ref_id not in declared_set:
            errors.append(
                f"line {lineno}: [[{ref_id}]] does not resolve "
                f"to any declared `## stub: <id>` heading"
            )

    for stub_id, lineno in declared.items():
        if stub_id not in referenced_set:
            warnings.append(
                f"line {lineno}: stub `{stub_id}` declared but never referenced"
            )

    return errors, warnings


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write(f"usage: {argv[0]} <document-plan.md>\n")
        return 2

    target = Path(argv[1])
    if not target.is_file():
        sys.stderr.write(f"not a file: {target}\n")
        return 2

    errors, warnings = validate(target)

    for w in warnings:
        sys.stdout.write(f"  warning: {w}\n")

    if errors:
        sys.stderr.write(f"validate_internal_refs: FAIL ({len(errors)} issue(s))\n")
        for e in errors:
            sys.stderr.write(f"  - {e}\n")
        return 1

    sys.stdout.write(
        f"validate_internal_refs: OK ({target}, "
        f"{len(warnings)} warning(s))\n"
    )
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
