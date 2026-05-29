#!/usr/bin/env python3
"""parse_frontmatter.py — narrow scalar-only frontmatter parser for
document-plan.md.

Validates the frontmatter contract that document-implementer reads:

  1. Body starts with line `---` (no preamble).
  2. A closing `---` appears before the first `## stub: <id>` heading.
  3. No `---` delimiter line appears between the closing frontmatter
     delimiter and EOF (rejects in-body YAML drift; document-plan.md
     uses only one frontmatter block at top).
  4. All required keys present exactly once inside the frontmatter
     block; raise on missing or duplicate.

Grammar inside the frontmatter block:
  - Each non-blank line is `<key>: <value>` (scalar only).
  - Keys: lowercase ASCII + underscore.
  - Values: rest of line after `: `, trimmed. No flow syntax (`{`, `[`),
    no nested structures, no multi-line strings.
  - Lines starting with `#` are comments (skipped).

Required keys + allowed values:
  doctype:         api-spec | tech-spec | runbook | ppt
  output_stack:    text | structured
  audience:        free-form string
  output_language: Korean | English
  target_path:     free-form string
  scale:           feature | system
  intent_slug:     kebab-case ASCII
  docplanner_id:   free-form string

Exits 0 on success (prints `OK` + the parsed dict as JSON on stdout),
1 on validation failure (writes to stderr), 2 on usage error.

Imports stdlib only — no PyYAML, no third-party deps.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REQUIRED_KEYS = [
    "doctype",
    "output_stack",
    "audience",
    "output_language",
    "target_path",
    "scale",
    "intent_slug",
    "docplanner_id",
]

ENUM_VALUES = {
    "doctype": ("api-spec", "tech-spec", "runbook", "ppt"),
    "output_stack": ("text", "structured"),
    "scale": ("feature", "system"),
    "output_language": ("Korean", "English"),
}

DELIM = "---"
STUB_HEADING = re.compile(r"^\s*##\s+stub:\s")
KEY_VALUE = re.compile(r"^([a-z][a-z0-9_]*)\s*:\s*(.*)$")
FORBIDDEN_VALUE_PREFIX = ("[", "{")  # flow-syntax openers as value
FORBIDDEN_VALUE_EXACT = ("|", ">")  # block-scalar markers as value


def validate(path: Path) -> tuple[dict[str, str], list[str]]:
    """Return (parsed_fields, errors). Empty errors list means valid."""
    errors: list[str] = []
    parsed: dict[str, str] = {}

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return {}, [f"cannot read {path}: {e}"]

    lines = text.splitlines()

    # Boundary 1: line 1 is `---`.
    if not lines or lines[0].rstrip() != DELIM:
        errors.append("frontmatter must start at line 1 with `---` delimiter")
        return parsed, errors

    # Find closing `---` and verify no stub heading appears first.
    close_idx = -1
    for i, raw in enumerate(lines[1:], start=2):
        if STUB_HEADING.match(raw):
            errors.append(
                f"line {i}: `## stub:` heading appears before closing `---` delimiter"
            )
            return parsed, errors
        if raw.rstrip() == DELIM:
            close_idx = i
            break

    if close_idx < 0:
        errors.append("frontmatter has no closing `---` delimiter")
        return parsed, errors

    # Boundary 3: no `---` delimiter line after close.
    for i, raw in enumerate(lines[close_idx:], start=close_idx + 1):
        if raw.rstrip() == DELIM:
            errors.append(
                f"line {i}: `---` delimiter appears in body after frontmatter; "
                "only one frontmatter block at top is permitted"
            )

    # Parse key:value pairs inside the block (lines 2 .. close_idx-1).
    seen_keys: dict[str, int] = {}
    for lineno in range(2, close_idx):
        raw = lines[lineno - 1]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = KEY_VALUE.match(stripped)
        if not match:
            errors.append(f"line {lineno}: not a `key: value` line")
            continue
        key, value = match.group(1), match.group(2).strip()
        # Strip wrapping quotes if present (single or double).
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        # Forbid flow-syntax openers and block-scalar markers AS the value.
        # Brackets/braces inside a longer value (e.g. "SRE team [internal]")
        # are fine — only a value that BEGINS with `[`/`{` is YAML flow syntax.
        if value[:1] in FORBIDDEN_VALUE_PREFIX:
            errors.append(
                f"line {lineno}: value starts with flow syntax `{value[0]}`"
            )
            continue
        if value in FORBIDDEN_VALUE_EXACT:
            errors.append(
                f"line {lineno}: value is a block-scalar marker `{value}` (multi-line not supported)"
            )
            continue
        if key in seen_keys:
            errors.append(
                f"line {lineno}: duplicate key `{key}` (first declared line {seen_keys[key]})"
            )
            continue
        seen_keys[key] = lineno
        parsed[key] = value

    # Required-key check.
    missing = [k for k in REQUIRED_KEYS if k not in parsed]
    if missing:
        errors.append(f"missing required keys: {', '.join(missing)}")

    # Enum-value check.
    for key, allowed in ENUM_VALUES.items():
        if key in parsed and parsed[key] not in allowed:
            errors.append(
                f"key `{key}`: value `{parsed[key]}` not in allowed set {list(allowed)}"
            )

    return parsed, errors


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write(f"usage: {argv[0]} <document-plan.md>\n")
        return 2

    target = Path(argv[1])
    if not target.is_file():
        sys.stderr.write(f"not a file: {target}\n")
        return 2

    parsed, errors = validate(target)

    if errors:
        sys.stderr.write(f"parse_frontmatter: FAIL ({len(errors)} issue(s))\n")
        for e in errors:
            sys.stderr.write(f"  - {e}\n")
        return 1

    sys.stdout.write("parse_frontmatter: OK\n")
    sys.stdout.write(json.dumps(parsed, indent=2, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
