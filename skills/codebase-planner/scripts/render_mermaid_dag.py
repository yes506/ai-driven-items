#!/usr/bin/env python3
"""Render a Mermaid DAG from .planner-state.json.

Reads the state file (path arg) and emits a Mermaid `graph LR` block to stdout.
Edges come from each interface's methods' `collaborators` field if present in
the state; otherwise just nodes are emitted.

Read-only: writes only to stdout. Caller redirects with `> architecture.mmd`.

Safety:
- Node IDs are deterministic and collision-free even when interface names share
  the same _safe()-stripped form (a counter suffix is appended for collisions).
- Node labels are escaped against Mermaid syntax injection — quotes, angle
  brackets, and click-directive separators in interface names cannot break
  out of the label or inject directives.
"""

import json
import sys
from pathlib import Path


def _safe(name: str) -> str:
    """Conservative ASCII identifier from arbitrary text."""
    cleaned = "".join(c if c.isalnum() else "_" for c in name)
    return cleaned or "node"


def _label_escape(name: str) -> str:
    """Escape a string for safe use as a Mermaid quoted label.

    Mermaid renders `id["LABEL"]` blocks; the label is HTML-decoded by the
    renderer, so we use #-prefixed entity codes (Mermaid's preferred form)
    plus standard HTML entities to neutralize quotes, brackets, click
    directives, newlines, and backticks (Mermaid v10+ alternate label
    delimiter).
    """
    return (
        str(name)
        .replace("&", "&amp;")
        .replace('"', "#quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", " ")
        .replace("\r", " ")
        .replace("|", "&#124;")
        .replace("[", "&#91;")
        .replace("]", "&#93;")
        .replace("`", "&#96;")
    )


def _unique_id(base: str, taken: dict) -> str:
    """Return a unique node id; if `base` is already taken, append a counter."""
    if base not in taken:
        taken[base] = 1
        return base
    taken[base] += 1
    return f"{base}_{taken[base]}"


def main() -> int:
    if len(sys.argv) != 2:
        sys.stderr.write("usage: render_mermaid_dag.py <path-to-.planner-state.json>\n")
        return 2

    state_path = Path(sys.argv[1])
    if not state_path.is_file():
        sys.stderr.write(f"state file not found: {state_path}\n")
        return 2

    state = json.loads(state_path.read_text(encoding="utf-8"))
    interfaces = state.get("interfaces") or []

    print("graph LR")
    if not interfaces:
        print('  empty["(no interfaces emitted yet)"]')
        return 0

    # First pass: assign unique node ids per interface.
    name_to_id = {}
    taken = {}
    for iface in interfaces:
        original = str(iface.get("name", "?"))
        node_id = _unique_id(_safe(original), taken)
        name_to_id[original] = node_id
        print(f'  {node_id}["{_label_escape(original)}"]')

    # Second pass: emit edges from collaborators.
    seen_edges = set()
    for iface in interfaces:
        src_name = str(iface.get("name", "?"))
        src_id = name_to_id.get(src_name)
        if src_id is None:
            continue
        for method in iface.get("methods") or []:
            for collab in method.get("collaborators") or []:
                target_name = str(collab).split(".", 1)[0]
                target_id = name_to_id.get(target_name)
                if target_id is None or target_id == src_id:
                    continue
                edge = (src_id, target_id)
                if edge in seen_edges:
                    continue
                seen_edges.add(edge)
                print(f"  {src_id} --> {target_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
