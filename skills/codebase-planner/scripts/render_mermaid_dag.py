#!/usr/bin/env python3
"""Render a Mermaid DAG from .planner-state.json.

Reads the state file (path arg) and emits a Mermaid `graph LR` block to stdout.
Edges come from each interface's methods' `collaborators` field if present in
the state; otherwise just nodes are emitted.

Read-only: writes only to stdout. Caller redirects with
`> "$RUN_DIR/architecture.mmd"` (or `$RUN_DIR/plan.mmd` for the feature lane).

Safety:
- Node IDs come from `_iface_graph.build_id_map()` — same source of truth
  the in-html embedded Mermaid + inline SVG use, so all three outputs
  agree on the id-collision-free naming (fixes round-4 R4-1 where the
  in-html paths had the F-D collision fix but this sibling did not).
- Node labels are escaped against Mermaid syntax injection by
  `_iface_graph.mermaid_label()` — quotes, angle brackets, click-directive
  separators, newlines, and backticks all neutralized.
"""

import json
import sys
from pathlib import Path

# Sibling module — same id-map + edge logic the in-html paths use.
from _iface_graph import build_id_map, collect_edges, mermaid_label


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

    name_to_id = build_id_map(interfaces)
    for original, node_id in name_to_id.items():
        print(f'  {node_id}["{mermaid_label(original)}"]')
    for src_id, dst_id in collect_edges(interfaces, name_to_id):
        print(f"  {src_id} --> {dst_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
