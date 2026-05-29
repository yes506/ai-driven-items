#!/usr/bin/env python3
"""validate_doc_structure.py — structural validator for document-structure.mmd.

Checks:
  1. Exactly one `graph` (or `flowchart`) header.
  2. All declared node IDs are unique.
  3. Every dependency edge references a node ID declared in the same file.
  4. The dependency graph has no cycles (DFS-based detection).

Exits 0 on success, 1 on validation failure, 2 on usage error.
Never mutates the input file.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

NODE_DECL = re.compile(r'^\s*([A-Za-z0-9_-]+)\s*[\[\(\{]')
EDGE = re.compile(r'^\s*([A-Za-z0-9_-]+)\s*-{1,2}>\s*([A-Za-z0-9_-]+)')
GRAPH_HEADER = re.compile(r'^\s*(graph|flowchart)\b', re.IGNORECASE)


def validate(path: Path) -> list[str]:
    """Return a list of error strings; empty list means valid."""
    errors: list[str] = []
    try:
        text = path.read_text(encoding='utf-8')
    except OSError as e:
        return [f"cannot read {path}: {e}"]

    headers = [ln for ln in text.splitlines() if GRAPH_HEADER.match(ln)]
    if len(headers) == 0:
        errors.append("no `graph` or `flowchart` header found")
    elif len(headers) > 1:
        errors.append(f"expected exactly one graph header, found {len(headers)}")

    node_ids: dict[str, int] = {}
    edges: list[tuple[str, str, int]] = []

    for lineno, raw in enumerate(text.splitlines(), start=1):
        if GRAPH_HEADER.match(raw):
            continue
        edge_match = EDGE.match(raw)
        if edge_match:
            edges.append((edge_match.group(1), edge_match.group(2), lineno))
            continue
        node_match = NODE_DECL.match(raw)
        if node_match:
            node_id = node_match.group(1)
            if node_id in node_ids:
                errors.append(
                    f"line {lineno}: duplicate node id `{node_id}` "
                    f"(first declared on line {node_ids[node_id]})"
                )
            else:
                node_ids[node_id] = lineno

    declared = set(node_ids)
    for src, dst, lineno in edges:
        for nid in (src, dst):
            if nid not in declared:
                errors.append(
                    f"line {lineno}: edge references undeclared node `{nid}`"
                )

    cycle = _find_cycle(declared, edges)
    if cycle is not None:
        errors.append(
            f"dependency graph has a cycle: {' -> '.join(cycle)}"
        )

    return errors


def _find_cycle(
    declared: set[str], edges: list[tuple[str, str, int]]
) -> list[str] | None:
    """Return the first cycle found as a list of node ids, or None."""
    adj: dict[str, list[str]] = {n: [] for n in declared}
    for src, dst, _ in edges:
        if src in adj and dst in declared:
            adj[src].append(dst)

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {n: WHITE for n in declared}
    parent: dict[str, str | None] = {n: None for n in declared}

    def walk(start: str) -> list[str] | None:
        stack: list[tuple[str, int]] = [(start, 0)]
        color[start] = GRAY
        while stack:
            node, idx = stack[-1]
            if idx < len(adj[node]):
                stack[-1] = (node, idx + 1)
                nxt = adj[node][idx]
                if color[nxt] == GRAY:
                    cycle = [nxt]
                    cur = node
                    while cur is not None and cur != nxt:
                        cycle.append(cur)
                        cur = parent[cur]
                    cycle.append(nxt)
                    cycle.reverse()
                    return cycle
                if color[nxt] == WHITE:
                    parent[nxt] = node
                    color[nxt] = GRAY
                    stack.append((nxt, 0))
            else:
                color[node] = BLACK
                stack.pop()
        return None

    for n in sorted(declared):
        if color[n] == WHITE:
            cycle = walk(n)
            if cycle is not None:
                return cycle
    return None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write(f"usage: {argv[0]} <document-structure.mmd>\n")
        return 2

    target = Path(argv[1])
    if not target.is_file():
        sys.stderr.write(f"not a file: {target}\n")
        return 2

    errors = validate(target)
    if errors:
        sys.stderr.write(f"validate_doc_structure: FAIL ({len(errors)} issue(s))\n")
        for e in errors:
            sys.stderr.write(f"  - {e}\n")
        return 1

    sys.stdout.write(f"validate_doc_structure: OK ({target})\n")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
